"""Porcentaje final de seguridad de un signo (confianza_final). No llama a ningún LLM.

La confianza que declara el modelo (confianza_modelo, regla 12 del prompt) suele estar inflada, así que se
corrige con tres señales que no dependen de lo que el modelo diga de sí mismo:
  - el tipo de evidencia que declara (ganancia o pérdida de función > medida directa > contexto o correlación);
  - la frase citada: título o primeras frases (introducción) frente a resultados;
  - si el otro modelo de producción da el mismo signo (ADR-003).

confianza_final = confianza_modelo × factor_evidencia × factor_frase × factor_acuerdo, entre 0 y 100.

Los factores son PROVISIONALES: salen de una prueba del 2026-11-09 con un prompt anterior (43 signos de tres
modelos de API sobre 60 casos) como el cociente entre el acierto de cada grupo y el del mejor, y se acercan a 1
la mitad del camino porque las muestras son pequeñas. Se sustituirán por una regresión logística ajustada en el
gold set. Acierto observado en esa prueba:
  - evidencia: ganancia 17/21 (81 %), pérdida 8/12 (67 %), medida directa 4/7 (57 %), contexto o correlación 1/3;
  - frase: [T], [S1] o [S2] 4/7 (57 %), [S3] o después 26/36 (72 %);
  - otro modelo: mismo signo 44/54 (81 %), UNKNOWN 15/30 (50 %), signo opuesto 1/2.

Solo los signos tienen confianza_final: un UNKNOWN no entra en la agregación y muestra su motivo.
"""
from typing import Any, Dict, Optional

from .esquema import SIGNO_DESCONOCIDO

FACTOR_EVIDENCIA = {
    "gain_of_function": 1.0,
    "loss_of_function": 0.9,       # 67/81 = 0,82
    "direct_measurement": 0.85,    # 57/81 = 0,70
    "correlation_or_marker": 0.7,  # 1/3 frente a 81 % = 0,41
    "background_statement": 0.7,
    "none": 0.7,
}
FRASES_INICIALES = ("T", "S1", "S2")  # título y primeras frases: suelen ser introducción
FACTOR_FRASE_INICIAL = 0.9             # 57/72 = 0,79
FACTOR_ACUERDO = {
    "mismo_signo": 1.0,
    "otro_unknown": 0.8,     # 50/81 = 0,62
    "signo_opuesto": 0.5,    # uno de los dos se equivoca seguro: no se acerca a 1
    "sin_segundo": 0.9,      # no hay respuesta del otro modelo (pendiente, o se usa uno solo)
}


def acuerdo(salida: Dict[str, Any], otra: Optional[Dict[str, Any]]) -> str:
    """Relación entre el signo de una respuesta y el del otro modelo para la misma pregunta."""
    if otra is None or "json_invalido" in otra.get("motivos", ()):
        return "sin_segundo"
    if otra["signo"] == salida["signo"]:
        return "mismo_signo"
    return "otro_unknown" if otra["signo"] == SIGNO_DESCONOCIDO else "signo_opuesto"


def confianza_final(salida: Dict[str, Any], otra: Optional[Dict[str, Any]] = None) -> Optional[int]:
    """salida: lo que devuelve validar_respuesta; otra: la del otro modelo para la misma pregunta, o None.
    Devuelve un entero 0-100, o None si la respuesta no tiene signo."""
    if salida.get("signo", SIGNO_DESCONOCIDO) == SIGNO_DESCONOCIDO:
        return None
    base = salida["confianza_modelo"]  # una respuesta válida siempre la trae (si no, es json_invalido)
    f_evidencia = FACTOR_EVIDENCIA.get(salida.get("tipo_evidencia"), FACTOR_EVIDENCIA["none"])
    f_frase = FACTOR_FRASE_INICIAL if salida.get("id_frase") in FRASES_INICIALES else 1.0
    valor = base * f_evidencia * f_frase * FACTOR_ACUERDO[acuerdo(salida, otra)]
    return max(0, min(100, round(valor)))
