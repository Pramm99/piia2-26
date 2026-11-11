"""Normalización de valores sueltos leídos del Excel (NaN, PMIDs como float, HTML)."""
import re
import unicodedata

import pandas as pd

from ._fase1 import limpiar_texto  # puente hacia fase1_ingesta (Fase 1)

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


# --- Forma de comparación (spec de limpieza): solo para comparar, nunca se envía al LLM ---
_GUIONES = re.compile("[‐‑‒–—−]")
_GRIEGAS = {"α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon", "κ": "kappa",
            "λ": "lambda", "μ": "mu", "θ": "theta", "ζ": "zeta", "η": "eta", "ι": "iota", "ν": "nu",
            "ξ": "xi", "π": "pi", "ρ": "rho", "σ": "sigma", "τ": "tau", "φ": "phi", "χ": "chi",
            "ψ": "psi", "ω": "omega"}
_NO_PALABRA = re.compile(r"[\W_]+")


def forma_comparacion(texto: str) -> str:
    """NFKC, casefold, guiones unificados, griegas como palabras y puntuación/guiones a espacios."""
    t = unicodedata.normalize("NFKC", valor_texto(texto)).casefold()
    t = _GUIONES.sub("-", t)
    t = "".join(_GRIEGAS.get(c, c) for c in t)
    return " ".join(_NO_PALABRA.sub(" ", t).split())


# --- Frases numeradas del abstract ([T] título, [S1..Sn]) para la cita determinista ---
_ABREVIATURAS = ("et al", "e.g", "i.e", "vs", "fig", "figs", "approx", "ca", "cf", "no", "resp", "sp", "spp")
_CORTE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")


def segmentar_frases(texto: str) -> list:
    """Parte el abstract en frases de forma determinista. No corta tras abreviaturas ('et al.', 'e.g.')
    ni en decimales (exige espacio y mayúscula, cifra o paréntesis detrás)."""
    trozos, actual = [], ""
    for parte in _CORTE.split(normalizar_espacios(valor_texto(texto))):
        actual = f"{actual} {parte}".strip() if actual else parte
        palabras = actual.rstrip(".!?").casefold().split()
        final = palabras[-1] if palabras else ""
        # dos palabras para las abreviaturas con espacio («et al»): con una sola se veía «al» y se cortaba
        if final in _ABREVIATURAS or " ".join(palabras[-2:]) in _ABREVIATURAS                 or final.endswith(tuple(f".{a}" for a in ("g", "e"))):
            continue
        trozos.append(actual)
        actual = ""
    if actual:
        trozos.append(actual)
    return trozos
