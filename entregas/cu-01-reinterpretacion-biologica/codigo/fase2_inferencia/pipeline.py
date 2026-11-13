"""Orquestación: Excel de la Fase 1 -> preguntas -> modelos -> resultado.

Las filas (gen, ruta, PMID) se agrupan en casos (gen, PMID, proceso núcleo; ver casos.py), cada caso es una
pregunta suelta y ejecucion.py las envía por gen. El filtro previo «¿menciona el gen?» se aplica antes del LLM
(no_menciona_gen, 0 llamadas), para que el benchmark compare solo los prompts.
ejecutar_fase2 encadena todo en producción: preguntas, dos modelos, contraste y salida
(resultados.py).
"""
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .casos import construir_casos, construir_casos_y_cerrados
from .ejecucion import Resumen, ejecutar
from .esquema import PromptLLM
from .lectura import cargar_hoja, filtrar, pendientes_de_llm
from .prompt import construir_prompt
from .registro import Registro
from .resultados import FICHERO_RESULTADOS, escribir, tablas


def preparar_prompts(ruta_excel: str, gen: Optional[str] = None, go_id: Optional[str] = None) -> Tuple[List[PromptLLM], Dict[str, int]]:
    """(preguntas, recuento) para las filas que tiene que leer el LLM."""
    df = pendientes_de_llm(filtrar(cargar_hoja(ruta_excel), gen, go_id))
    casos, cuenta = construir_casos(df)
    return [construir_prompt(c) for c in casos], cuenta


def ejecutar_fase2(ruta_excel: str, clientes: Sequence, gen: Optional[str] = None, go_id: Optional[str] = None,
                   registro: Optional[Registro] = None, salida: Optional[Path] = FICHERO_RESULTADOS,
                   solo_respaldo: bool = True):
    """Fase 2 completa: Excel de la Fase 1 -> preguntas -> modelos (clientes[0] principal, clientes[1] secundario, opcional) -> contraste -> Excel de resultados.
    Reanudable: lo registrado no se vuelve a pedir y lo que no responde queda «pendiente» para la siguiente
    ejecución. Procesa las rutas activadas y las suprimidas. solo_respaldo (por defecto): el secundario solo
    responde lo que el principal no pudo; con False se contrastan los dos (ejecucion.py).
    Devuelve (hoja Preguntas, hoja Por_ruta, resumen de la ejecución, recuento de casos)."""
    df = pendientes_de_llm(filtrar(cargar_hoja(ruta_excel), gen, go_id))
    casos, cerrados, cuenta = construir_casos_y_cerrados(df)
    preguntas = [construir_prompt(c) for c in casos]
    resultados, resumen = ejecutar(preguntas, clientes, registro, solo_respaldo=solo_respaldo) if preguntas         else ([], Resumen())
    nombres = [c.cfg.nombre for c in clientes]
    df_preguntas, df_rutas = tablas(resultados, nombres[0], nombres[1] if len(nombres) > 1 else None, cerrados, df)
    if salida is not None and not df_rutas.empty:
        escribir(df_preguntas, df_rutas, salida)
    return df_preguntas, df_rutas, resumen, cuenta
