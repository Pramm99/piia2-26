"""Interpretación y validación de la respuesta (texto) de un LLM. No llama a ningún LLM.

Verificación de la cita (ADR-003, spec de limpieza): la cita, en forma de comparación, debe tener al menos 6
palabras y aparecer como palabras enteras en la frase indicada del texto enviado. El modelo siempre da un
veredicto; el UNKNOWN lo decide el código con la cita y la confianza (_validar), y se guarda el veredicto que dio
el modelo (signo_llm).
"""
import json
import re
from typing import Any, Dict, List, Optional

from .esquema import (ESQUEMA, ESTADO_NO_CONCLUYENTE, ESTADO_RESUELTO, ESTADO_REVISAR, MIN_PALABRAS_CITA,
                      MOTIVO_MODELO_A_ADR, MOTIVOS_REVISAR, SIGNO_DESCONOCIDO, SIGNO_NEGATIVO, SIGNO_NEUTRO,
                      SIGNO_POSITIVO, UMBRAL_VEREDICTO, VERSION_PROMPT, VEREDICTO_A_SIGNO, PromptLista, PromptLLM)
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


def verificar_cita(cita: str, texto: str) -> bool:
    """La cita (≥6 palabras) aparece como palabras enteras en el texto, tolerando mayúsculas, guiones,
    griegas escritas y puntuación (forma_comparacion)."""
    c = forma_comparacion(cita)
    return len(c.split()) >= MIN_PALABRAS_CITA and f" {c} " in f" {forma_comparacion(texto)} "


def _json_invalido() -> Dict[str, Any]:
    """Respuesta recibida pero no interpretable: UNKNOWN con json_invalido."""
    return {"signo": SIGNO_DESCONOCIDO, "signo_llm": SIGNO_DESCONOCIDO, "estado": ESTADO_NO_CONCLUYENTE,
            "motivos": ["json_invalido"], "cita_verificada": False}


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


def pide_revision(signo: str, motivos) -> bool:
    """Algún motivo de MOTIVOS_REVISAR. baja_confianza no cuenta cuando el código ya convirtió el veredicto en
    UNKNOWN: ese caso es no_concluyente."""
    return any(m in MOTIVOS_REVISAR and not (m == "baja_confianza" and signo == SIGNO_DESCONOCIDO) for m in motivos)


def signo_en_ruta(signo: str, factor: Optional[int]) -> str:
    """Signo sobre el proceso -> signo sobre una ruta (factor de casos.py; None = «regulation of X» sin dirección).
    Neutro sigue siendo neutro en cualquier ruta: si el gen no cambia el proceso, tampoco su regulación."""
    if signo == SIGNO_NEUTRO:
        return SIGNO_NEUTRO
    if signo not in (SIGNO_POSITIVO, SIGNO_NEGATIVO) or factor is None:
        return SIGNO_DESCONOCIDO
    return _A_SIGNO[(1 if signo == SIGNO_POSITIVO else -1) * factor]


def _frases(valor: Any) -> Optional[List[Dict[str, str]]]:
    """Lista de 1-3 {id_frase, cita}; cualquier otra forma -> None (json_invalido)."""
    if not isinstance(valor, list) or not valor:
        return None
    frases = []
    for f in valor[:3]:
        if not isinstance(f, dict) or not isinstance(f.get("id_frase"), str) or not isinstance(f.get("cita"), str):
            return None
        frases.append({"id_frase": f["id_frase"].strip().strip("[]"), "cita": f["cita"].strip()})
    return frases


def _validar(prompt: PromptLLM, crudo: Dict[str, Any], umbral: int = UMBRAL_VEREDICTO) -> Dict[str, Any]:
    """El modelo siempre da un veredicto; el código decide el UNKNOWN.
      - sin ninguna cita verificada: UNKNOWN con cita_no_verificada;
      - con confianza por debajo del umbral: UNKNOWN con baja_confianza (y la limitación que dio el modelo);
      - un veredicto que supera el umbral pero trae una limitación (el modelo dice que el abstract no lo
        sostiene): incoherencia_respuesta (revisar). El prompt no conoce el umbral.
    signo_llm y signo_llm_ruta guardan siempre el veredicto, porque resultados.py lo acepta aunque tenga poca
    confianza si coincide con la Polaridad_GO de la anotación."""
    caso = prompt.evidencia
    props = ESQUEMA["properties"]
    faltan = [k for k in ESQUEMA["required"] if k not in crudo]
    fuera = [k for k, p in props.items() if "enum" in p and k in crudo and crudo[k] not in p["enum"]]
    frases = _frases(crudo.get("frases"))
    try:
        confianza = _leer_confianza(crudo.get("confianza"))
    except ValueError:
        confianza = None
    if faltan or fuera or frases is None or confianza is None:
        return {**_json_invalido(), "veredicto": "", "confianza_modelo": None, "frases": [], "rutas": []}

    for f in frases:
        f["verificada"] = verificar_cita(f["cita"], _texto_frase(caso, f["id_frase"]))
    verificadas = [f for f in frases if f["verificada"]]
    signo_llm = VEREDICTO_A_SIGNO[crudo["veredicto"]]
    limitacion = crudo["limitacion"]
    motivo_lim = [MOTIVO_MODELO_A_ADR[limitacion]] if limitacion != "none" else []
    if not verificadas:
        signo, motivos = SIGNO_DESCONOCIDO, ["cita_no_verificada"]
    elif confianza < umbral:
        signo, motivos = SIGNO_DESCONOCIDO, ["baja_confianza"] + motivo_lim
    else:
        signo, motivos = signo_llm, (["incoherencia_respuesta"] + motivo_lim if motivo_lim else [])
    if pide_revision(signo, motivos):
        estado = ESTADO_REVISAR
    else:
        estado = ESTADO_RESUELTO if signo != SIGNO_DESCONOCIDO else ESTADO_NO_CONCLUYENTE
    rutas = [{"go_id": r, "ruta_nombre": n, "signo_ruta": signo_en_ruta(signo, f), "signo_llm_ruta": signo_en_ruta(signo_llm, f),
              "motivo_ruta": "ruta_sin_direccion" if f is None and signo in (SIGNO_POSITIVO, SIGNO_NEGATIVO) else ""}
             for r, n, f in caso.rutas]
    principal = verificadas[0] if verificadas else frases[0]
    return {"signo": signo, "signo_llm": signo_llm, "estado": estado, "motivos": motivos,
            "cita_verificada": bool(verificadas), "veredicto": crudo["veredicto"], "confianza_modelo": confianza,
            "frases": frases, "id_frase": principal["id_frase"], "justificacion_literal": principal["cita"],
            "limitacion": limitacion, "tipo_evidencia": crudo["tipo_evidencia"], "organismo": crudo["organismo"],
            "tipo_celular": crudo["tipo_celular"], "razonamiento_corto": str(crudo["razonamiento_corto"]).strip(),
            "nucleo_id": caso.nucleo_id, "nucleo_nombre": caso.nucleo_nombre, "rutas": rutas}


def validar_respuesta(prompt: PromptLLM, texto_llm: str, umbral_confianza: Optional[int] = None) -> Dict[str, Any]:
    """Dict con el esquema fijo de la respuesta. pmid y gen se toman de la evidencia, nunca del LLM. Una
    respuesta recibida pero no interpretable da UNKNOWN con json_invalido. umbral_confianza solo cambia para
    barrer umbrales en el benchmark (por defecto, UMBRAL_VEREDICTO)."""
    if prompt.version != VERSION_PROMPT:
        raise ValueError(f"Versión de prompt desconocida: {prompt.version}")
    ev = prompt.evidencia
    base = {"version": prompt.version, "pmid": ev.pmid, "gen": ev.gen, "go_id": ev.go_id}
    try:
        crudo = extraer_json(texto_llm)
    except Exception as err:
        return {**base, **_json_invalido(), "error": f"Respuesta no interpretable: {err}"}
    umbral = umbral_confianza if umbral_confianza is not None else UMBRAL_VEREDICTO
    return {**base, **_validar(prompt, crudo, umbral), "error": ""}


def repartir_lista(lista: PromptLista, texto_llm: str) -> List[Optional[str]]:
    """Respuesta de una llamada por gen -> el JSON de cada pregunta (Q1..Qn, en orden), listo para validar_respuesta.
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
