"""Fase 2 (preparación): filas del Excel de Fase 1 -> prompts para un LLM ligero. Sin llamadas a APIs.
Dos versiones del prompt para el benchmark: v0_original (línea base congelada) y v1_proceso."""
from .esquema import V0_ORIGINAL, V1_PROCESO, CasoProceso, Evidencia, PromptLLM
from .pipeline import df_a_prompts, fila_a_prompt, generar_prompts, preparar_prompts, resolver_respuesta
from .prompt import CONFIG_V0, CONFIG_V1, ConfigPrompt

__all__ = ["Evidencia", "CasoProceso", "PromptLLM", "ConfigPrompt", "CONFIG_V0", "CONFIG_V1", "V0_ORIGINAL",
           "V1_PROCESO", "fila_a_prompt", "df_a_prompts", "generar_prompts", "preparar_prompts",
           "resolver_respuesta"]
