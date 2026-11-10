"""Fase 2: filas del Excel de Fase 1 -> preguntas a dos LLM gratuitos -> signo validado y contrastado por ruta.
Versiones del prompt: v1_proceso_gen (benchmark) y v2_veredicto (producción, ejecutar_fase2)."""
from .esquema import V1_GEN, V2_VEREDICTO, CasoProceso, PromptLLM
from .pipeline import ejecutar_fase2, preparar_prompts
from .prompt import CONFIG_V1_GEN, CONFIG_V2, ConfigPrompt

__all__ = ["CasoProceso", "PromptLLM", "ConfigPrompt", "CONFIG_V1_GEN", "CONFIG_V2", "V1_GEN", "V2_VEREDICTO",
           "preparar_prompts", "ejecutar_fase2"]
