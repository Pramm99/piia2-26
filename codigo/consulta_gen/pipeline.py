"""Orquestación: Excel de la Fase 1 -> prompts de la versión elegida (y, aparte, respuesta del LLM -> resultado).

  - v0_original: una fila (gen, ruta, PMID) = un prompt.
  - v1_proceso: las filas se agrupan en casos (gen, PMID, proceso núcleo); ver casos.py.
  - v1_proceso_gen: los mismos casos, como preguntas sueltas; ejecucion.py las envía por gen.
En las dos, el filtro previo «¿menciona el gen?» se aplica antes del LLM (no_menciona_gen, 0 llamadas),
para que el benchmark compare solo los prompts.
ejecutar_fase2 encadena todo en producción: preguntas de v2_veredicto, dos modelos, contraste y salida
(resultados.py).
"""
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

from ._extraer_info import datos_mygene, menciona_gen, patron_gen
from .casos import construir_casos, construir_casos_y_cerrados
from .ejecucion import Resumen, ejecutar
from .esquema import VERSIONES_PROCESO, PromptLLM
from .lectura import cargar_hoja, fila_a_evidencia, filtrar, iterar_filas, pendientes_de_llm, solo_activadas
from .prompt import CONFIG_V0, CONFIG_V2, ConfigPrompt, construir_prompt
from .registro import Registro
from .respuesta import validar_respuesta
from .resultados import FICHERO_RESULTADOS, escribir, tablas


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
    if cfg.version in VERSIONES_PROCESO:  # v1_proceso y v1_proceso_gen: las mismas preguntas
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


def ejecutar_fase2(ruta_excel: str, clientes: Sequence, gen: Optional[str] = None, go_id: Optional[str] = None,
                   registro: Optional[Registro] = None, salida: Optional[Path] = FICHERO_RESULTADOS,
                   activadas: bool = True, cfg: ConfigPrompt = CONFIG_V2):
    """Fase 2 completa: Excel de la Fase 1 -> preguntas (por defecto v2_veredicto; cfg=CONFIG_V1_GEN para la v1)
    -> modelos (clientes[0] principal, clientes[1] secundario, opcional) -> contraste -> Excel de resultados.
    Reanudable: lo registrado no se vuelve a pedir y lo que no responde queda «pendiente» para la siguiente
    ejecución. Por defecto solo las rutas activadas.
    Devuelve (hoja Preguntas, hoja Por_ruta, resumen de la ejecución, recuento de casos)."""
    df = pendientes_de_llm(filtrar(cargar_hoja(ruta_excel), gen, go_id))
    if activadas:
        df = solo_activadas(df)
    casos, cerrados, cuenta = construir_casos_y_cerrados(df)
    preguntas = [construir_prompt(c, cfg) for c in casos]
    resultados, resumen = ejecutar(preguntas, clientes, registro) if preguntas else ([], Resumen())
    nombres = [c.cfg.nombre for c in clientes]
    df_preguntas, df_rutas = tablas(resultados, nombres[0], nombres[1] if len(nombres) > 1 else None, cerrados, df)
    if salida is not None and not df_rutas.empty:
        escribir(df_preguntas, df_rutas, salida)
    return df_preguntas, df_rutas, resumen, cuenta
