"""Orquestación: Excel de la Fase 1 -> prompts de la versión elegida (y, aparte, respuesta del LLM -> resultado).

  - v0_original: una fila (gen, ruta, PMID) = un prompt.
  - v1_proceso: las filas se agrupan en casos (gen, PMID, proceso núcleo); ver casos.py.
En las dos, el filtro previo «¿menciona el gen?» se aplica antes del LLM (no_menciona_gen, 0 llamadas),
para que el benchmark compare solo los prompts.
"""
from typing import Any, Dict, List, Mapping, Optional, Tuple

import pandas as pd

from ._extraer_info import datos_mygene, menciona_gen, patron_gen
from .casos import construir_casos
from .esquema import V1_PROCESO, PromptLLM
from .lectura import cargar_hoja, fila_a_evidencia, filtrar, iterar_filas, pendientes_de_llm
from .prompt import CONFIG_V0, ConfigPrompt, construir_prompt
from .respuesta import validar_respuesta


def fila_a_prompt(fila: Mapping, cfg: ConfigPrompt = CONFIG_V0) -> Optional[PromptLLM]:
    """v0_original: UNA fila del Excel -> prompt (None si la fila no tiene abstract)."""
    ev = fila_a_evidencia(fila, cfg.max_chars_abstract)
    return construir_prompt(ev, cfg) if ev else None


def df_a_prompts(df: pd.DataFrame, cfg: ConfigPrompt = CONFIG_V0) -> List[PromptLLM]:
    prompts = (fila_a_prompt(f, cfg) for f in iterar_filas(df))
    return [p for p in prompts if p is not None]


def _prefiltro_v0(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Quita las filas cuyo título + abstract no nombran al gen (símbolo, alias o nombre completo)."""
    if df.empty:
        return df, 0
    genes = sorted({str(g).strip().upper() for g in df["Gen"]})
    mg = datos_mygene(genes)
    patrones = {g: patron_gen(g, mg[g]["Alias"], mg[g]["Nombre"]) for g in genes}
    ok = [menciona_gen(f"{t} {a}", patrones[str(g).strip().upper()])
          for g, t, a in zip(df["Gen"], df["Titulo"].fillna(""), df["Abstract"].fillna(""))]
    return df[ok], len(ok) - sum(ok)


def preparar_prompts(ruta_excel: str, cfg: ConfigPrompt = CONFIG_V0, gen: Optional[str] = None,
                     go_id: Optional[str] = None) -> Tuple[List[PromptLLM], Dict[str, int]]:
    """(prompts, recuento) de la versión de cfg para las filas que tiene que leer el LLM."""
    df = pendientes_de_llm(filtrar(cargar_hoja(ruta_excel), gen, go_id))
    if cfg.version == V1_PROCESO:
        casos, cuenta = construir_casos(df)
        return [construir_prompt(c, cfg) for c in casos], cuenta
    df, sin_gen = _prefiltro_v0(df)
    prompts = df_a_prompts(df, cfg)
    return prompts, {"filas": len(df) + sin_gen, "casos": len(prompts), "casos_no_menciona_gen": sin_gen}


def generar_prompts(ruta_excel: str, gen: Optional[str] = None, go_id: Optional[str] = None,
                    cfg: ConfigPrompt = CONFIG_V0) -> List[PromptLLM]:
    """Lee el Excel, filtra por gen/ruta y genera los prompts que tiene que leer el LLM."""
    return preparar_prompts(ruta_excel, cfg, gen, go_id)[0]


def resolver_respuesta(prompt: PromptLLM, texto_llm: str) -> Dict[str, Any]:
    """Valida el texto devuelto por el LLM (cuando exista esa pieza) contra su prompt."""
    return validar_respuesta(prompt, texto_llm)
