"""Fase 2: filas del Excel de Fase 1 -> preguntas a dos LLM gratuitos -> signo validado y contrastado por ruta.
Versiones del prompt: v0_original (línea base congelada), v1_proceso y v1_proceso_gen (benchmark) y
v2_veredicto (producción, ejecutar_fase2)."""
from .esquema import V0_ORIGINAL, V1_GEN, V1_PROCESO, V2_VEREDICTO, CasoProceso, Evidencia, PromptLLM
from .pipeline import (df_a_prompts, ejecutar_fase2, fila_a_prompt, generar_prompts, preparar_prompts,
                       resolver_respuesta)
from .prompt import CONFIG_V0, CONFIG_V1, CONFIG_V1_GEN, CONFIG_V2, ConfigPrompt

__all__ = ["Evidencia", "CasoProceso", "PromptLLM", "ConfigPrompt", "CONFIG_V0", "CONFIG_V1", "CONFIG_V1_GEN",
           "CONFIG_V2", "V0_ORIGINAL", "V1_PROCESO", "V1_GEN", "V2_VEREDICTO", "fila_a_prompt", "df_a_prompts",
           "generar_prompts", "preparar_prompts", "resolver_respuesta", "ejecutar_fase2"]
