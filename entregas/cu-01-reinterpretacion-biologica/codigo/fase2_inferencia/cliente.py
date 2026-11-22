"""Cliente LLM común (ADR-005): un único conector para todos los proveedores gratuitos, porque Cerebras,
Groq, Gemini (modo compatible) y Ollama aceptan la API de chat de OpenAI. Solo usa `requests`.

  - ConfigModelo: proveedor, ID exacto del modelo, URL, variable de la clave y límites del plan gratuito.
  - ClienteOpenAICompatible: temperatura 0, seed, salida JSON estricta, ritmo de llamadas según RPM,
    espera exponencial ante 429/5xx y, si no responde tras los reintentos, ErrorTransitorio: el caso queda
    PENDIENTE para la siguiente ejecución (un fallo de red nunca es un UNKNOWN).
  - Varias claves por proveedor, en orden: si una se queda sin cupo (429 del límite diario, o 429 que sigue tras
    los reintentos), pasa a la siguiente del mismo proveedor. Es el único fallo que cambia de clave: una clave no
    válida, un 5xx o la red dan ErrorTransitorio y la ejecución pasa al modelo de respaldo (ejecucion.py). Si se
    acaban todas las claves, ErrorTransitorio con motivo «cupo», y también pasa al respaldo.
  - ClienteSimulado: responde sin red, para las pruebas y para ensayar la ejecución completa.

Las claves se leen de las variables de entorno o de `codigo/.env` (no se sube al repo; ver .env.example). Una
variable puede llevar varias claves separadas por comas (la interfaz las gestiona en ⚙ → token-api).
Los IDs y límites se comprobaron en la documentación oficial el 2026-11-08 (informe «Prompt y modelos
gratuitos Fase 2»); hay que confirmarlos en la consola de cada proveedor antes de una ejecución real.
"""
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

import requests

from .esquema import PromptLLM

FICHERO_ENV = Path(__file__).resolve().parent.parent / ".env"


class ErrorTransitorio(Exception):
    """El modelo no respondió (límite diario, 429 persistente, clave no válida, red): caso pendiente.
    motivo: «cupo» (sin cupo en todas sus claves), «clave» (clave rechazada), «sin_clave» (ninguna configurada)
    o «fallo» (5xx o red tras los reintentos)."""

    def __init__(self, mensaje: str, motivo: str = "fallo"):
        super().__init__(mensaje)
        self.motivo = motivo


class _SinCupo(Exception):
    """La clave en uso se quedó sin cupo: se prueba la siguiente del mismo proveedor."""


# 429 del límite diario: Gemini lo nombra en quotaId («…PerDay…»); Groq, en el mensaje («tokens per day (TPD)»).
# No tiene sentido reintentarlo: se pasa a la siguiente clave en el momento.
PATRON_LIMITE_DIARIO = re.compile(r"per ?day|\((?:TPD|RPD)\)", re.IGNORECASE)
# Clave rechazada: Groq da 401; Gemini, 400 «API key not valid» o 403
PATRON_CLAVE_NO_VALIDA = re.compile(r"api[ _]?key[ _]?(?:not[ _]valid|invalid)|invalid[ _]api[ _]key", re.IGNORECASE)


@dataclass(frozen=True)
class ConfigModelo:
    nombre: str                       # nombre corto del registro, p. ej. "cerebras-gpt-oss-120b"
    proveedor: str
    modelo: str                       # ID exacto que espera la API
    url: str                          # endpoint /chat/completions
    var_clave: Optional[str]          # variable de entorno con la clave (None = sin clave, p. ej. Ollama)
    rpm: int                          # peticiones por minuto del plan gratuito (marca el ritmo)
    temperatura: Optional[float] = 0.0  # None = el modelo la ignora (Gemini 3.x)
    seed: Optional[int] = 1234
    reasoning_effort: Optional[str] = None  # "low" en gpt-oss; "none" en qwen; None = no se envía
    max_tokens: int = 2000            # en gpt-oss el razonamiento cuenta para este límite
    json_schema: bool = True          # salida estructurada estricta con el esquema del prompt
    extra: Dict = field(default_factory=dict)
    # Tope de tokens de UNA llamada (entrada estimada + max_completion_tokens). Las preguntas de
    # un gen se trocean para no pasarlo: Groq rechaza una petición mayor que su límite por minuto (8K).
    presupuesto_llamada: int = 60_000
    timeout: int = 120                # segundos por petición (un modelo local en CPU tarda minutos con una lista)


MODELOS: Dict[str, ConfigModelo] = {c.nombre: c for c in [
    ConfigModelo("cerebras-gpt-oss-120b", "cerebras", "gpt-oss-120b",
                 "https://api.cerebras.ai/v1/chat/completions", "CEREBRAS_API_KEY", rpm=5, reasoning_effort="low",
                 presupuesto_llamada=28_000),   # 30K tokens/min sin caché; contexto gratuito de 65K
    ConfigModelo("groq-gpt-oss-120b", "groq", "openai/gpt-oss-120b",
                 "https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY", rpm=30, reasoning_effort="low",
                 presupuesto_llamada=7_500),    # 8K tokens/min
    ConfigModelo("groq-qwen3.8-27b", "groq", "qwen/qwen3.8-27b",
                 "https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY", rpm=30, reasoning_effort="none",
                 presupuesto_llamada=7_500),
    ConfigModelo("gemini-3.5-flash-lite", "gemini", "gemini-3.5-flash-lite",
                 "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "GEMINI_API_KEY",
                 rpm=10, temperatura=None, seed=None),  # el modo compatible rechaza `seed` (HTTP 400, 2026-11-09);
                                                        # contexto de 1M; su límite por minuto solo se ve en AI Studio
    ConfigModelo("ollama-qwen3-8b", "ollama", "qwen3:8b",
                 "http://localhost:11434/v1/chat/completions", None, rpm=600, reasoning_effort="none",
                 presupuesto_llamada=14_000, timeout=3_600),
    # Ollama carga el modelo con 4.096 tokens de contexto salvo que el servidor se arranque con
    # OLLAMA_CONTEXT_LENGTH (el modo compatible no deja pasar num_ctx) y recorta por el principio sin avisar:
    # el presupuesto supone OLLAMA_CONTEXT_LENGTH=16384. Unos 100 s por caso en el i7-1355U (2026-11-09).
]}


@dataclass
class Respuesta:
    texto: str                        # contenido crudo devuelto por el modelo
    meta: Dict                        # proveedor, modelo, system_fingerprint, tokens, segundos...


def _leer_env(ruta: Optional[Path] = None) -> Dict[str, str]:
    """KEY=valor por línea; se ignoran comentarios y líneas vacías. Las variables de entorno mandan."""
    ruta = ruta or FICHERO_ENV
    if not ruta.exists():
        return {}
    pares = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, v = linea.split("=", 1)
            pares[k.strip()] = v.strip().strip('"').strip("'")
    return pares


def claves(var: Optional[str]) -> List[str]:
    """Claves de la variable, en orden y sin repetir (varias, separadas por comas)."""
    if not var:
        return []
    valor = os.environ.get(var) or _leer_env().get(var) or ""
    return list(dict.fromkeys(c.strip() for c in valor.split(",") if c.strip()))


def clave(var: Optional[str]) -> Optional[str]:
    """La primera clave de la variable, o None."""
    return next(iter(claves(var)), None)


def guardar_claves(var: str, lista: List[str], ruta: Optional[Path] = None) -> None:
    """Escribe `VAR=k1,k2` en .env sin tocar las demás líneas (si no estaba, la añade al final). Lo usa el
    puente de la Fase 4 (⚙ → token-api). Escribe en un temporal y lo cambia de golpe, para no dejarlo a medias."""
    ruta = ruta or FICHERO_ENV
    original = ruta.read_bytes().decode("utf-8") if ruta.exists() else ""
    salto = "\r\n" if "\r\n" in original else "\n"  # se respetan los saltos de línea que ya tenía
    lineas = original.splitlines()
    nueva, puesta, salida = f"{var}={','.join(lista)}", False, []
    for linea in lineas:
        limpia = linea.strip()
        if not limpia.startswith("#") and "=" in limpia and limpia.split("=", 1)[0].strip() == var:
            if not puesta:  # la primera aparición se sustituye; las repetidas sobran
                salida.append(nueva)
                puesta = True
            continue
        salida.append(linea)
    if not puesta:
        salida.append(nueva)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_bytes((salto.join(salida) + salto).encode("utf-8"))  # en bytes: Windows no traduce los saltos
    os.replace(temporal, ruta)


class ClienteOpenAICompatible:
    """Conector real. Respeta el ritmo del plan (60/rpm segundos entre llamadas) y reintenta ante 429/5xx."""

    def __init__(self, cfg: ConfigModelo, sesion: Optional[requests.Session] = None,
                 reintentos: int = 5, espera_base: float = 2.0, dormir: Callable[[float], None] = time.sleep):
        self.cfg, self.sesion, self.reintentos, self.espera_base, self.dormir = cfg, sesion or requests.Session(), \
            reintentos, espera_base, dormir
        self._ultima = 0.0
        self.llamadas = 0
        # Sin ninguna clave no falla aquí, sino en la primera llamada (ErrorTransitorio «sin_clave»): así una ruta
        # con todo en el registro se ejecuta igual, y si falta la del principal responde el respaldo.
        self._claves = claves(cfg.var_clave)
        self._i = 0  # clave en uso; avanza cuando una se queda sin cupo

    def _payload(self, prompt) -> Dict:
        """prompt: PromptLLM (un caso) o PromptLista (las preguntas de un gen, con su propio max_salida)."""
        c = self.cfg
        p = {"model": c.modelo, "messages": prompt.como_mensajes(),
             "max_completion_tokens": getattr(prompt, "max_salida", None) or c.max_tokens, **c.extra}
        if c.temperatura is not None:
            p["temperature"] = c.temperatura
        if c.seed is not None:
            p["seed"] = c.seed
        if c.reasoning_effort:
            p["reasoning_effort"] = c.reasoning_effort
        if c.json_schema and prompt.esquema_json:
            p["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "efecto_gen_proceso", "strict": True, "schema": prompt.esquema_json}}
        elif c.json_schema:
            p["response_format"] = {"type": "json_object"}
        return p

    def _esperar_turno(self):
        hueco = 60.0 / max(self.cfg.rpm, 1) - (time.monotonic() - self._ultima)
        if hueco > 0:
            self.dormir(hueco)
        self._ultima = time.monotonic()

    def completar(self, prompt) -> Respuesta:
        """Llama con la clave en uso y, si se queda sin cupo, con las siguientes del mismo proveedor."""
        c = self.cfg
        if c.var_clave and not self._claves:
            raise ErrorTransitorio(f"{c.nombre}: no hay ninguna clave en {c.var_clave} (entorno o {FICHERO_ENV})",
                                   motivo="sin_clave")
        while True:
            try:
                return self._completar_con(prompt, self._claves[self._i] if self._claves else None)
            except _SinCupo as e:
                n = len(self._claves)
                if self._i + 1 >= n:
                    raise ErrorTransitorio(f"{c.nombre}: sin cupo en {'su clave' if n == 1 else f'sus {n} claves'} "
                                           f"({e})", motivo="cupo") from None
                self._i += 1
                print(f"🔑 {c.nombre}: la clave {self._i} se quedó sin cupo; sigue con la {self._i + 1} de {n}.")

    def _completar_con(self, prompt, clave_api: Optional[str]) -> Respuesta:
        cabeceras = {"Content-Type": "application/json"}
        if clave_api:
            cabeceras["Authorization"] = f"Bearer {clave_api}"
        ultimo, ultimo_estado = "", None
        for intento in range(self.reintentos + 1):
            self._esperar_turno()
            t0 = time.monotonic()
            try:
                r = self.sesion.post(self.cfg.url, json=self._payload(prompt), headers=cabeceras,
                                     timeout=self.cfg.timeout)
            except requests.RequestException as e:
                ultimo, ultimo_estado = f"red: {e}", None
            else:
                self.llamadas += 1
                if r.status_code == 200:
                    d = r.json()
                    eleccion = d["choices"][0]
                    return Respuesta(texto=eleccion["message"].get("content") or "", meta={
                        "proveedor": self.cfg.proveedor, "modelo": d.get("model", self.cfg.modelo),
                        "system_fingerprint": d.get("system_fingerprint"), "tokens": d.get("usage", {}),
                        "fin": eleccion.get("finish_reason"),  # "length" = salida cortada por max_completion_tokens
                        "segundos": round(time.monotonic() - t0, 2),
                        "n_clave": self._i + 1})  # cuál de las claves respondió (su número, nunca la clave)
                generado = _salida_rechazada(r)
                if generado is not None:  # el modelo respondió, pero su JSON no cumple el esquema: json_invalido
                    return Respuesta(texto=generado, meta={
                        "proveedor": self.cfg.proveedor, "modelo": self.cfg.modelo, "system_fingerprint": None,
                        "tokens": {}, "fin": "json_validate_failed", "segundos": round(time.monotonic() - t0, 2)})
                ultimo, ultimo_estado = f"HTTP {r.status_code}: {r.text[:200]}", r.status_code
                if r.status_code == 429 and PATRON_LIMITE_DIARIO.search(r.text or ""):
                    raise _SinCupo(ultimo)
                if r.status_code in (401, 403) or (
                        r.status_code == 400 and PATRON_CLAVE_NO_VALIDA.search(r.text or "")):
                    raise ErrorTransitorio(f"{self.cfg.nombre}: clave {self._i + 1} no válida ({ultimo})",
                                           motivo="clave")
                if r.status_code not in (408, 429, 500, 502, 503, 504):
                    raise RuntimeError(f"{self.cfg.nombre}: {ultimo}")  # error de configuración: no se reintenta
                espera = r.headers.get("retry-after")
                if espera and espera.replace(".", "", 1).isdigit():
                    self.dormir(float(espera))
                    continue
            self.dormir(self.espera_base * 2 ** intento)
        if ultimo_estado == 429:  # el límite sigue tras los reintentos: esta clave no da más
            raise _SinCupo(f"sin respuesta tras {self.reintentos} reintentos ({ultimo})")
        raise ErrorTransitorio(f"{self.cfg.nombre}: sin respuesta tras {self.reintentos} reintentos ({ultimo})")


def _salida_rechazada(r) -> Optional[str]:
    """Groq devuelve HTTP 400 `json_validate_failed` con el texto generado en `failed_generation` cuando la
    salida no cumple el esquema estricto. Es una respuesta recibida (ADR-003: json_invalido), no un fallo
    de configuración. Devuelve ese texto, o None si el error es de otro tipo."""
    if r.status_code != 400:
        return None
    try:
        err = r.json().get("error", {})
    except ValueError:
        return None
    if err.get("code") != "json_validate_failed":
        return None
    return err.get("failed_generation") or ""


class ClienteSimulado:
    """Cliente sin red para pruebas. `responder(prompt) -> texto`; `fallar(prompt) -> bool` simula un 429
    persistente (lanza ErrorTransitorio). Cuenta las llamadas para comprobar la reanudación."""

    def __init__(self, nombre: str, responder: Callable[[PromptLLM], str],
                 fallar: Optional[Callable[[PromptLLM], bool]] = None, presupuesto_llamada: int = 60_000):
        self.cfg = ConfigModelo(nombre, "simulado", nombre, "", None, rpm=10 ** 6, seed=None,
                                presupuesto_llamada=presupuesto_llamada)
        self.responder, self.fallar, self.llamadas = responder, fallar, 0

    def completar(self, prompt) -> Respuesta:
        self.llamadas += 1
        if self.fallar and self.fallar(prompt):
            raise ErrorTransitorio(f"{self.cfg.nombre}: 429 simulado", motivo="cupo")
        return Respuesta(texto=self.responder(prompt), meta={"proveedor": "simulado", "modelo": self.cfg.modelo,
                                                             "system_fingerprint": None, "tokens": {}, "fin": "stop",
                                                             "segundos": 0.0})
