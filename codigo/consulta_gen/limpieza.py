"""Normalización de valores sueltos leídos del Excel (NaN, PMIDs como float, HTML, longitud)."""
import re

import pandas as pd

from ._extraer_info import limpiar_texto  # puente hacia extraer_info (Fase 1)

_ESPACIOS = re.compile(r"\s+")


def valor_texto(v) -> str:
    """Convierte cualquier celda a str limpio; NaN/None/'nan' -> ''."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def normalizar_pmid(v) -> str:
    """'12345678.0' (típico de pandas al leer Excel) -> '12345678'."""
    return valor_texto(v).split(".")[0].strip()


def normalizar_espacios(texto: str) -> str:
    return _ESPACIOS.sub(" ", texto).strip()


def limpiar_abstract(v) -> str:
    """Quita restos de HTML/entidades y colapsa espacios."""
    return normalizar_espacios(limpiar_texto(valor_texto(v)))


def recortar(texto: str, max_caracteres) -> str:
    """Recorta a max_caracteres intentando cortar en final de frase (o de palabra)."""
    if not max_caracteres or len(texto) <= max_caracteres:
        return texto
    corte = texto[:max_caracteres]
    fin_frase = corte.rfind(". ")
    if fin_frase > max_caracteres * 0.6:
        return corte[:fin_frase + 1]
    return corte.rsplit(" ", 1)[0] + "…"
