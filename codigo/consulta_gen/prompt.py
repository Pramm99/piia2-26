"""Construcción del prompt para un LLM ligero. Solo texto: no sabe nada de proveedores ni de red."""
from dataclasses import dataclass

from .esquema import Evidencia, PromptLLM

SYSTEM = (
    "Eres un asistente de bioinformática. Lees UN resumen científico y decides si el gen indicado "
    "ACTIVA o INHIBE una ruta biológica. Usas solo la información del resumen, nunca tu memoria. "
    "Respondes únicamente con un objeto JSON válido."
)


@dataclass(frozen=True)
class ConfigPrompt:
    max_chars_abstract: int = 1800        # los modelos ligeros rinden mejor con contexto corto
    incluir_estado_scrnaseq: bool = True  # Activada/Suprimida: contexto, pero puede sesgar la respuesta
    incluir_pista_go: bool = False        # polaridad derivada del grafo GO: desactivada para no sesgar


def construir_user(ev: Evidencia, cfg: ConfigPrompt = ConfigPrompt()) -> str:
    contexto = [
        "Contexto: carcinoma escamocelular de cabeza y cuello (laringe/faringe), microambiente inmunitario.",
        f"Gen: {ev.gen}",
        f"Ruta: {ev.ruta_nombre} ({ev.go_id})",
    ]
    if cfg.incluir_estado_scrnaseq and ev.estado_scrnaseq:
        contexto.append(f"Ruta en scRNA-seq: {ev.estado_scrnaseq}")
    if cfg.incluir_pista_go and ev.polaridad_go in ("+1", "-1"):
        contexto.append(f"Pista de Gene Ontology (orientativa): {ev.polaridad_go}")

    return (
        "\n".join(contexto)
        + f"\n\nResumen (PMID {ev.pmid})\nTítulo: {ev.titulo}\nTexto: {ev.abstract}\n\n"
        f"Pregunta: según el resumen, ¿cómo afecta {ev.gen} a la ruta '{ev.ruta_nombre}'?\n"
        '- "+1": {g} activa, estimula o es mediador positivo de la ruta.\n'
        '- "-1": {g} inhibe, reprime o atenúa la ruta.\n'
        '- "UNKNOWN": el resumen no es concluyente, es contradictorio, no trata de {g} o lo trata en un '
        "contexto ajeno a la ruta.\n"
        "El signo describe el efecto del gen sobre la ruta, no si el gen sube o baja en el tumor.\n\n"
        "Responde SOLO con este JSON:\n"
        "{{\n"
        f'  "pmid": "{ev.pmid}",\n'
        f'  "gen": "{ev.gen}",\n'
        '  "signo_funcional": "+1" | "-1" | "UNKNOWN",\n'
        '  "justificacion_literal": "frase copiada EXACTAMENTE del resumen (vacía si UNKNOWN)",\n'
        '  "razonamiento_corto": "una sola frase"\n'
        "}}"
    ).replace("{g}", ev.gen).replace("{{", "{").replace("}}", "}")


def construir_prompt(ev: Evidencia, cfg: ConfigPrompt = ConfigPrompt()) -> PromptLLM:
    return PromptLLM(evidencia=ev, system=SYSTEM, user=construir_user(ev, cfg))
