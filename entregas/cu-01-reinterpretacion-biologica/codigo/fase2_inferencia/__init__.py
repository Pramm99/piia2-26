"""Fase 2: filas del Excel de Fase 1 -> preguntas a dos LLM gratuitos -> signo validado y contrastado por ruta."""
from .esquema import VERSION_PROMPT, CasoProceso, PromptLLM
from .pipeline import ejecutar_fase2, preparar_prompts

__all__ = ["CasoProceso", "PromptLLM", "VERSION_PROMPT", "preparar_prompts", "ejecutar_fase2"]
