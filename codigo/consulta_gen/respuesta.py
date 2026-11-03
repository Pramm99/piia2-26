"""Interpretación y validación de la respuesta (texto) de un LLM. No llama a ningún LLM."""
import json
import re
from typing import Any, Dict

from .esquema import SIGNO_DESCONOCIDO, SIGNO_NEGATIVO, SIGNO_POSITIVO, PromptLLM
from .limpieza import normalizar_espacios

_VALLAS = re.compile(r"```(?:json)?", re.IGNORECASE)


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


def _cita_en_abstract(cita: str, abstract: str) -> bool:
    c = normalizar_espacios(cita).casefold().strip(" .\"'")
    return bool(c) and c in normalizar_espacios(abstract).casefold()


def validar_respuesta(prompt: PromptLLM, texto_llm: str) -> Dict[str, Any]:
    """Devuelve un dict con el esquema fijo. pmid y gen se toman de la evidencia, no del LLM.
    `cita_verificada` indica si la justificación aparece literalmente en el abstract enviado."""
    ev = prompt.evidencia
    base = {"pmid": ev.pmid, "gen": ev.gen, "go_id": ev.go_id}
    try:
        crudo = extraer_json(texto_llm)
    except Exception as err:
        return {**base, "signo_funcional": SIGNO_DESCONOCIDO, "justificacion_literal": "",
                "razonamiento_corto": "", "cita_verificada": False,
                "error": f"Respuesta no interpretable: {err}"}

    signo = normalizar_signo(crudo.get("signo_funcional"))
    cita = str(crudo.get("justificacion_literal") or "").strip()
    return {**base, "signo_funcional": signo, "justificacion_literal": cita,
            "razonamiento_corto": str(crudo.get("razonamiento_corto") or "").strip(),
            "cita_verificada": _cita_en_abstract(cita, ev.abstract), "error": ""}
