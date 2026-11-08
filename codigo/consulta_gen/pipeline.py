"""Orquestación: fila del Excel -> Evidencia -> PromptLLM (y, aparte, respuesta del LLM -> resultado)."""
from typing import Any, Dict, List, Mapping, Optional

import pandas as pd

from .esquema import PromptLLM
from .lectura import cargar_hoja, fila_a_evidencia, filtrar, iterar_filas, pendientes_de_llm
from .prompt import ConfigPrompt, construir_prompt
from .respuesta import validar_respuesta


def fila_a_prompt(fila: Mapping, cfg: ConfigPrompt = ConfigPrompt()) -> Optional[PromptLLM]:
    """Punto de entrada principal: UNA fila del Excel -> prompt (None si la fila no tiene abstract)."""
    ev = fila_a_evidencia(fila, cfg.max_chars_abstract)
    return construir_prompt(ev, cfg) if ev else None


def df_a_prompts(df: pd.DataFrame, cfg: ConfigPrompt = ConfigPrompt()) -> List[PromptLLM]:
    prompts = (fila_a_prompt(f, cfg) for f in iterar_filas(df))
    return [p for p in prompts if p is not None]


def generar_prompts(ruta_excel: str, gen: Optional[str] = None, go_id: Optional[str] = None,
                    cfg: ConfigPrompt = ConfigPrompt()) -> List[PromptLLM]:
    """Lee el Excel, filtra por gen/ruta y genera un prompt por fila que tenga que leer el LLM."""
    return df_a_prompts(pendientes_de_llm(filtrar(cargar_hoja(ruta_excel), gen, go_id)), cfg)


def resolver_respuesta(prompt: PromptLLM, texto_llm: str) -> Dict[str, Any]:
    """Valida el texto devuelto por el LLM (cuando exista esa pieza) contra su prompt."""
    return validar_respuesta(prompt, texto_llm)
