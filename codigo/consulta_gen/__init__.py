"""Fase 2 (preparación): filas del Excel de Fase 1 -> prompts para un LLM ligero. Sin llamadas a APIs."""
from .esquema import Evidencia, PromptLLM
from .pipeline import df_a_prompts, fila_a_prompt, generar_prompts, resolver_respuesta
from .prompt import ConfigPrompt

__all__ = ["Evidencia", "PromptLLM", "ConfigPrompt", "fila_a_prompt", "df_a_prompts",
           "generar_prompts", "resolver_respuesta"]
