"""Cliente LLM común (ADR-005): un único conector para todos los proveedores gratuitos, porque Cerebras,
Groq, Gemini (modo compatible) y Ollama aceptan la API de chat de OpenAI. Solo usa `requests`.

  - ConfigModelo: proveedor, ID exacto del modelo, URL, variable de la clave y límites del plan gratuito.
  - ClienteOpenAICompatible: temperatura 0, seed, salida JSON estricta, ritmo de llamadas según RPM,
    espera exponencial ante 429/5xx y, si no responde tras los reintentos, ErrorTransitorio: el caso queda
    PENDIENTE para la siguiente ejecución (un fallo de red nunca es un UNKNOWN).
  - ClienteSimulado: responde sin red, para las pruebas y para ensayar la ejecución completa.

Las claves se leen de las variables de entorno o de `codigo/.env` (no se sube al repo; ver .env.example).
Los IDs y límites se comprobaron en la documentación oficial el 2026-11-08 (informe «Prompt y modelos
gratuitos Fase 2»); hay que confirmarlos en la consola de cada proveedor antes de una ejecución real.
"""
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional

import requests

from .esquema import PromptLLM

FICHERO_ENV = Path(__file__).resolve().parent.parent / ".env"


class ErrorTransitorio(Exception):
    """El modelo no respondió tras los reintentos (límite diario, 429 persistente, red): caso pendiente."""


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


MODELOS: Dict[str, ConfigModelo] = {c.nombre: c for c in [
    ConfigModelo("cerebras-gpt-oss-120b", "cerebras", "gpt-oss-120b",
                 "https://api.cerebras.ai/v1/chat/completions", "CEREBRAS_API_KEY", rpm=5, reasoning_effort="low"),
    ConfigModelo("groq-gpt-oss-120b", "groq", "openai/gpt-oss-120b",
                 "https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY", rpm=30, reasoning_effort="low"),
    ConfigModelo("groq-qwen3.8-27b", "groq", "qwen/qwen3.8-27b",
                 "https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY", rpm=30, reasoning_effort="none"),
    ConfigModelo("gemini-3.5-flash-lite", "gemini", "gemini-3.5-flash-lite",
                 "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "GEMINI_API_KEY",
                 rpm=10, temperatura=None),
    ConfigModelo("ollama-qwen3-8b", "ollama", "qwen3:8b",
                 "http://localhost:11434/v1/chat/completions", None, rpm=600, reasoning_effort="none"),
]}


@dataclass
class Respuesta:
    texto: str                        # contenido crudo devuelto por el modelo
    meta: Dict                        # proveedor, modelo, system_fingerprint, tokens, segundos...


def _leer_env(ruta: Path = FICHERO_ENV) -> Dict[str, str]:
    """KEY=valor por línea; se ignoran comentarios y líneas vacías. Las variables de entorno mandan."""
    if not ruta.exists():
        return {}
    pares = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, v = linea.split("=", 1)
            pares[k.strip()] = v.strip().strip('"').strip("'")
    return pares


def clave(var: Optional[str]) -> Optional[str]:
    if not var:
        return None
    return os.environ.get(var) or _leer_env().get(var) or None


class ClienteOpenAICompatible:
    """Conector real. Respeta el ritmo del plan (60/rpm segundos entre llamadas) y reintenta ante 429/5xx."""

    def __init__(self, cfg: ConfigModelo, sesion: Optional[requests.Session] = None,
                 reintentos: int = 5, espera_base: float = 2.0, dormir: Callable[[float], None] = time.sleep):
        self.cfg, self.sesion, self.reintentos, self.espera_base, self.dormir = cfg, sesion or requests.Session(), \
            reintentos, espera_base, dormir
        self._ultima = 0.0
        self.llamadas = 0
        self._clave = clave(cfg.var_clave)
        if cfg.var_clave and not self._clave:
            raise RuntimeError(f"Falta {cfg.var_clave}: ponla en el entorno o en {FICHERO_ENV} (ver .env.example)")

    def _payload(self, prompt: PromptLLM) -> Dict:
        c = self.cfg
        p = {"model": c.modelo, "messages": prompt.como_mensajes(), "max_completion_tokens": c.max_tokens, **c.extra}
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

    def completar(self, prompt: PromptLLM) -> Respuesta:
        cabeceras = {"Content-Type": "application/json"}
        if self._clave:
            cabeceras["Authorization"] = f"Bearer {self._clave}"
        ultimo = ""
        for intento in range(self.reintentos + 1):
            self._esperar_turno()
            t0 = time.monotonic()
            try:
                r = self.sesion.post(self.cfg.url, json=self._payload(prompt), headers=cabeceras, timeout=120)
            except requests.RequestException as e:
                ultimo = f"red: {e}"
            else:
                self.llamadas += 1
                if r.status_code == 200:
                    d = r.json()
                    return Respuesta(texto=d["choices"][0]["message"].get("content") or "", meta={
                        "proveedor": self.cfg.proveedor, "modelo": d.get("model", self.cfg.modelo),
                        "system_fingerprint": d.get("system_fingerprint"), "tokens": d.get("usage", {}),
                        "segundos": round(time.monotonic() - t0, 2)})
                ultimo = f"HTTP {r.status_code}: {r.text[:200]}"
                if r.status_code not in (408, 429, 500, 502, 503, 504):
                    raise RuntimeError(f"{self.cfg.nombre}: {ultimo}")  # error de configuración: no se reintenta
                espera = r.headers.get("retry-after")
                if espera and espera.replace(".", "", 1).isdigit():
                    self.dormir(float(espera))
                    continue
            self.dormir(self.espera_base * 2 ** intento)
        raise ErrorTransitorio(f"{self.cfg.nombre}: sin respuesta tras {self.reintentos} reintentos ({ultimo})")


class ClienteSimulado:
    """Cliente sin red para pruebas. `responder(prompt) -> texto`; `fallar(prompt) -> bool` simula un 429
    persistente (lanza ErrorTransitorio). Cuenta las llamadas para comprobar la reanudación."""

    def __init__(self, nombre: str, responder: Callable[[PromptLLM], str],
                 fallar: Optional[Callable[[PromptLLM], bool]] = None):
        self.cfg = ConfigModelo(nombre, "simulado", nombre, "", None, rpm=10 ** 6, seed=None)
        self.responder, self.fallar, self.llamadas = responder, fallar, 0

    def completar(self, prompt: PromptLLM) -> Respuesta:
        self.llamadas += 1
        if self.fallar and self.fallar(prompt):
            raise ErrorTransitorio(f"{self.cfg.nombre}: 429 simulado")
        return Respuesta(texto=self.responder(prompt), meta={"proveedor": "simulado", "modelo": self.cfg.modelo,
                                                             "system_fingerprint": None, "tokens": {}, "segundos": 0.0})


def crear_cliente(nombre: str, **kw):
    """Cliente real de uno de los MODELOS por su nombre corto."""
    if nombre not in MODELOS:
        raise KeyError(f"Modelo desconocido: {nombre}. Disponibles: {sorted(MODELOS)}")
    return ClienteOpenAICompatible(MODELOS[nombre], **kw)
