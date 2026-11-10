"""Fase 2 (preparación): filas del Excel de Fase 1 -> prompts para un LLM ligero. Sin llamadas a APIs.
Versiones del prompt para el benchmark: v0_original (línea base congelada), v1_proceso y v1_proceso_gen."""
from .esquema import V0_ORIGINAL, V1_GEN, V1_PROCESO, CasoProceso, Evidencia, PromptLLM
from .pipeline import df_a_prompts, fila_a_prompt, generar_prompts, preparar_prompts, resolver_respuesta
from .prompt import CONFIG_V0, CONFIG_V1, CONFIG_V1_GEN, ConfigPrompt

__all__ = ["Evidencia", "CasoProceso", "PromptLLM", "ConfigPrompt", "CONFIG_V0", "CONFIG_V1", "CONFIG_V1_GEN",
           "V0_ORIGINAL", "V1_PROCESO", "V1_GEN", "fila_a_prompt", "df_a_prompts", "generar_prompts", "preparar_prompts",
           "resolver_respuesta"]
