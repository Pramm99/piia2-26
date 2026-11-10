"""Interpretación y validación de la respuesta (texto) de un LLM. No llama a ningún LLM.

Las dos versiones del prompt comparten la verificación de la cita (ADR-003, spec de limpieza): la cita,
en forma de comparación, debe tener al menos 6 palabras y aparecer como palabras enteras en el texto
enviado. Si un signo no tiene cita verificada se fuerza UNKNOWN con cita_no_verificada y se guarda el
signo que dio el modelo (signo_llm).
"""
import json
import re
from typing import Any, Dict, List, Optional

from .esquema import (CAMPOS_NUEVOS_V1, EFECTO_A_SIGNO, ESQUEMA_V1, ESTADO_NO_CONCLUYENTE, ESTADO_RESUELTO, ESTADO_REVISAR,
                      MIN_CONFIANZA_SIGNO, MIN_PALABRAS_CITA, MOTIVO_MODELO_A_ADR, MOTIVOS_REVISAR, SIGNO_DESCONOCIDO,
                      SIGNO_NEGATIVO, SIGNO_POSITIVO, UMBRAL_CONFIANZA, VERSIONES_PROCESO, PromptLista, PromptLLM)
from .limpieza import forma_comparacion

_VALLAS = re.compile(r"```(?:json)?", re.IGNORECASE)
_NUM_Q = re.compile(r"\s*\[?Q(\d+)\b", re.IGNORECASE)
_A_SIGNO = {1: SIGNO_POSITIVO, -1: SIGNO_NEGATIVO, None: SIGNO_DESCONOCIDO}


def extraer_json(texto: str) -> Dict[str, Any]:
    """Tolera vallas ```json y texto alrededor (frecuente en modelos pequeños)."""
    limpio = _VALLAS.sub("", texto or "").strip()
    ini, fin = limpio.find("{"), limpio.rfind("}")
    if ini == -1 or fin <= ini:
        raise ValueError("No se encontró un objeto JSON en la respuesta")
    return json.loads(limpio[ini:fin + 1])


def normalizar_signo(valor: Any) -> str:
    """Acepta '+1', 1, '1', '+1.0', '-1', -1...; cualquier otra cosa -> UNKNOWN."""
    s = str(valor).strip().replace(" ", "")
    try:
        n = float(s)
        if n == 1:
            return SIGNO_POSITIVO
        if n == -1:
            return SIGNO_NEGATIVO
    except ValueError:
        pass
    return SIGNO_DESCONOCIDO


def verificar_cita(cita: str, texto: str) -> bool:
    """La cita (≥6 palabras) aparece como palabras enteras en el texto, tolerando mayúsculas, guiones,
    griegas escritas y puntuación (forma_comparacion)."""
    c = forma_comparacion(cita)
    return len(c.split()) >= MIN_PALABRAS_CITA and f" {c} " in f" {forma_comparacion(texto)} "


def _cerrar(signo: str, motivos: List[str], cita_ok: bool, confianza: Optional[int] = None,
            umbral: int = UMBRAL_CONFIANZA) -> Dict[str, Any]:
    """Aplica el UNKNOWN forzado por cita, la baja confianza (solo a un signo que sobrevive a la cita) y decide
    el estado. confianza None = respuesta sin el campo (v0 o registros anteriores a la regla 13)."""
    signo_llm = signo
    if signo != SIGNO_DESCONOCIDO and not cita_ok:
        signo, motivos = SIGNO_DESCONOCIDO, motivos + ["cita_no_verificada"]
    if signo != SIGNO_DESCONOCIDO and confianza is not None and MIN_CONFIANZA_SIGNO <= confianza < umbral:
        motivos = motivos + ["baja_confianza"]
    if any(m in MOTIVOS_REVISAR for m in motivos):
        estado = ESTADO_REVISAR
    else:
        estado = ESTADO_RESUELTO if signo != SIGNO_DESCONOCIDO else ESTADO_NO_CONCLUYENTE
    return {"signo": signo, "signo_llm": signo_llm, "estado": estado, "motivos": motivos, "cita_verificada": cita_ok}


def _validar_v0(prompt: PromptLLM, crudo: Dict[str, Any]) -> Dict[str, Any]:
    ev = prompt.evidencia
    signo = normalizar_signo(crudo.get("signo_funcional"))
    cita = str(crudo.get("justificacion_literal") or "").strip()
    motivos = [] if str(crudo.get("signo_funcional")).strip() in ("+1", "-1", "1", "UNKNOWN") else ["json_invalido"]
    salida = _cerrar(signo, motivos, verificar_cita(cita, f"{ev.titulo} {ev.abstract}"))
    return {**salida, "justificacion_literal": cita, "razonamiento_corto": str(crudo.get("razonamiento_corto") or "").strip(),
            "signo_funcional": salida["signo"]}  # signo_funcional: nombre de la v0, se mantiene


def _texto_frase(caso, id_frase: str) -> str:
    if id_frase == "T":
        return caso.titulo
    if id_frase.startswith("S") and id_frase[1:].isdigit() and 1 <= int(id_frase[1:]) <= len(caso.frases):
        return caso.frases[int(id_frase[1:]) - 1]
    return ""


def _leer_confianza(valor: Any) -> Optional[int]:
    """Entero 0-100 (también 85.0); ausente -> None. Cualquier otra cosa -> ValueError (json_invalido)."""
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not 0 <= valor <= 100 or valor != int(valor):
        raise ValueError(f"confianza fuera de 0-100: {valor!r}")
    return int(valor)


def _validar_v1(prompt: PromptLLM, crudo: Dict[str, Any], umbral: int = UMBRAL_CONFIANZA) -> Dict[str, Any]:
    caso = prompt.evidencia
    props = ESQUEMA_V1["properties"]
    faltan = [k for k in ESQUEMA_V1["required"] if k not in crudo and k not in CAMPOS_NUEVOS_V1]
    fuera = [k for k, p in props.items() if "enum" in p and k in crudo and crudo[k] not in p["enum"]]
    try:
        confianza = _leer_confianza(crudo.get("confianza"))
    except ValueError:
        fuera.append("confianza")
    if faltan or fuera:
        return {**_cerrar(SIGNO_DESCONOCIDO, ["json_invalido"], False), "efecto": "", "confianza_modelo": None, "rutas": []}

    efecto, motivo_modelo = crudo["efecto"], crudo["motivo_unknown"]
    id_frase = str(crudo["id_frase"]).strip().strip("[]")
    cita = str(crudo["justificacion_literal"]).strip()
    signo = _A_SIGNO[EFECTO_A_SIGNO[efecto]]
    motivos = [MOTIVO_MODELO_A_ADR[motivo_modelo]] if motivo_modelo != "none" else []
    # Combinaciones incoherentes -> revisar (se conservan para el análisis de errores). Un signo con confianza
    # por debajo de MIN_CONFIANZA_SIGNO contradice la regla 13 (debía ser NO_CLEAR_EFFECT).
    if (efecto != "NO_CLEAR_EFFECT" and motivo_modelo != "none") or (efecto == "NO_CLEAR_EFFECT" and motivo_modelo == "none") \
            or (efecto != "NO_CLEAR_EFFECT" and crudo["tipo_evidencia"] == "correlation_or_marker") \
            or (efecto != "NO_CLEAR_EFFECT" and confianza is not None and confianza < MIN_CONFIANZA_SIGNO):
        motivos.append("incoherencia_respuesta")
    salida = _cerrar(signo, motivos, verificar_cita(cita, _texto_frase(caso, id_frase)), confianza, umbral)

    # Signo sobre cada ruta del caso: efecto × factor (None = ruta «regulation of X» sin dirección)
    e = EFECTO_A_SIGNO[efecto] if salida["signo"] != SIGNO_DESCONOCIDO else None
    rutas = [{"go_id": r, "ruta_nombre": n,
              "signo_ruta": _A_SIGNO[e * f] if e is not None and f is not None else SIGNO_DESCONOCIDO,
              "motivo_ruta": "ruta_sin_direccion" if f is None and e is not None else ""}
             for r, n, f in caso.rutas]
    return {**salida, "efecto": efecto, "id_frase": id_frase, "justificacion_literal": cita,
            "tipo_evidencia": crudo["tipo_evidencia"], "organismo": crudo["organismo"],
            "tipo_celular": crudo["tipo_celular"], "razonamiento_corto": str(crudo["razonamiento_corto"]).strip(),
            "confianza_modelo": confianza,
            "nucleo_id": caso.nucleo_id, "nucleo_nombre": caso.nucleo_nombre, "rutas": rutas}


def validar_respuesta(prompt: PromptLLM, texto_llm: str, umbral_confianza: int = UMBRAL_CONFIANZA) -> Dict[str, Any]:
    """Dict con el esquema fijo de la versión del prompt. pmid y gen se toman de la evidencia, nunca del LLM.
    Una respuesta recibida pero no interpretable da UNKNOWN con json_invalido. umbral_confianza solo cambia
    para barrer umbrales en el benchmark."""
    ev = prompt.evidencia
    base = {"version": prompt.version, "pmid": ev.pmid, "gen": ev.gen, "go_id": ev.go_id}
    try:
        crudo = extraer_json(texto_llm)
    except Exception as err:
        return {**base, **_cerrar(SIGNO_DESCONOCIDO, ["json_invalido"], False), "error": f"Respuesta no interpretable: {err}"}
    if prompt.version in VERSIONES_PROCESO:
        return {**base, **_validar_v1(prompt, crudo, umbral_confianza), "error": ""}
    return {**base, **_validar_v0(prompt, crudo), "error": ""}


def repartir_lista(lista: PromptLista, texto_llm: str) -> List[Optional[str]]:
    """Respuesta de v1_proceso_gen -> el JSON de cada pregunta (Q1..Qn, en orden), listo para validar_respuesta.
    None = el modelo no respondió esa pregunta (queda pendiente). Si la respuesta entera no se puede leer,
    todas reciben "" (json_invalido al validarlas: es una respuesta recibida, no un fallo de red)."""
    try:
        items = extraer_json(texto_llm).get("respuestas")
        if not isinstance(items, list):
            raise ValueError("falta la lista «respuestas»")
    except Exception:
        return [""] * len(lista.preguntas)
    por_q: Dict[str, Dict] = {}
    for it in items:
        if isinstance(it, dict):
            # «Q3», «q3» o la línea entera («Q3. PMID … | PROCESS: …», como hace qwen3:8b); si se repite, la primera
            m = _NUM_Q.match(str(it.get("q", "")))
            if m:
                por_q.setdefault(f"Q{int(m.group(1))}", it)
    out = []
    for i in range(1, len(lista.preguntas) + 1):
        it = por_q.get(f"Q{i}")
        out.append(None if it is None else json.dumps({k: v for k, v in it.items() if k != "q"}, ensure_ascii=False))
    return out
