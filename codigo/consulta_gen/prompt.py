"""Construcción del prompt para un LLM ligero. Solo texto: no sabe nada de proveedores ni de red.

Hay dos versiones, que se comparan en el benchmark sobre el mismo gold set:
  - v0_original: el prompt de partida, CONGELADO tal cual (pregunta por la ruta, en español, con la
    dirección de scRNA-seq y el abstract recortado). Es la línea base: solo para el benchmark, no para
    producción (la spec prohíbe enviar la dirección de scRNA-seq).
  - v1_proceso: informe «Prompt y modelos gratuitos Fase 2» (anexo 1). Pregunta por el efecto del gen
    sobre el proceso núcleo, con el abstract completo en frases numeradas y salida JSON estricta; el
    signo sobre la ruta lo calcula el código (casos.py).
"""
from dataclasses import dataclass
from typing import Optional

from .esquema import ESQUEMA_V1, V0_ORIGINAL, V1_PROCESO, CasoProceso, Evidencia, PromptLLM


@dataclass(frozen=True)
class ConfigPrompt:
    version: str = V0_ORIGINAL
    max_chars_abstract: Optional[int] = 1800  # v0: los modelos ligeros rinden mejor con contexto corto
    incluir_estado_scrnaseq: bool = True      # v0: Activada/Suprimida (contexto, pero puede sesgar)
    incluir_pista_go: bool = False            # v0: polaridad derivada del grafo GO, desactivada para no sesgar
    localizador_frase_fuente: bool = False    # v1, variante V2: añade la frase donde Fase 1 vio gen y proceso


CONFIG_V0 = ConfigPrompt()
CONFIG_V1 = ConfigPrompt(version=V1_PROCESO, max_chars_abstract=None, incluir_estado_scrnaseq=False)


# --------------------------------------------------------------------------------------------------
# v0_original (congelado: no modificar, es la línea base del benchmark)
# --------------------------------------------------------------------------------------------------
SYSTEM = (
    "Eres un asistente de bioinformática. Lees UN resumen científico y decides si el gen indicado "
    "ACTIVA o INHIBE una ruta biológica. Usas solo la información del resumen, nunca tu memoria. "
    "Respondes únicamente con un objeto JSON válido."
)


def construir_user(ev: Evidencia, cfg: ConfigPrompt = CONFIG_V0) -> str:
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


# --------------------------------------------------------------------------------------------------
# v1_proceso
# --------------------------------------------------------------------------------------------------
SYSTEM_V1 = """You read ONE PubMed abstract and report what it states about the causal effect of ONE human
gene (or its protein product) on ONE biological process. Use only the abstract text, never
your own knowledge. Reply with the JSON object only.

Rules:
1. CAUSE, NOT TARGET. The gene must be the cause. If something else changes the gene's
   expression or activity ("TNF induced GENE", "GENE was upregulated during infection"),
   answer NO_CLEAR_EFFECT with reason gene_is_the_target.
2. LOSS OF FUNCTION INVERTS. If knockout, knockdown, siRNA, deficiency, a blocking antibody
   or an inhibitor of the gene DECREASES the process, the gene INCREASES it; if it
   INCREASES the process, the gene DECREASES it. Say so in the reasoning.
3. GAIN OF FUNCTION KEEPS. Overexpression, transfection, an agonist or the recombinant
   protein: the gene has the same direction as the observed effect.
4. MARKER OR CORRELATION IS NOT CAUSAL. Expression on cells that perform the process,
   co-expression, correlation with the process, prognosis or survival:
   NO_CLEAR_EFFECT, reason marker_or_correlation_only.
5. OTHER MOLECULE. If the effect is attributed to a different molecule (a ligand, receptor,
   partner, complex or drug), it counts for the gene only if the gene's own product was
   manipulated, or the abstract shows the effect requires the gene. Otherwise:
   NO_CLEAR_EFFECT, reason effect_of_other_molecule.
6. NEGATION. "Did not affect", "was dispensable", "no change": NO_CLEAR_EFFECT,
   reason no_effect_found. Never answer DECREASES for a negated effect.
7. SPECULATION. A hypothesis without a reported result ("may", "could", "we propose"):
   NO_CLEAR_EFFECT, reason speculation_only. A cautious conclusion of a reported
   experiment does count.
8. CONFLICT. If the abstract reports both directions for this process and gives no way to
   choose: NO_CLEAR_EFFECT, reason conflicting_results.
9. SCOPE. A more specific form of the process counts (e.g. NK cytotoxicity against tumour
   cells counts for "natural killer cell mediated cytotoxicity"). A broader or different
   process does not: NO_CLEAR_EFFECT, reason process_not_addressed.
10. CONTEXT IS DATA, NOT A REASON TO ABSTAIN. Report the organism and cell type. Do not
    answer NO_CLEAR_EFFECT only because the study is in mouse, another cell type or
    another disease.
11. PREFER RESULTS over background statements from the introduction.
12. QUOTE. Give the ID of ONE sentence ([T] = title, [S1], [S2]...). Copy from that sentence,
    character by character, a contiguous span of at least 6 words that supports your answer,
    with no ellipsis and no rewording. For NO_CLEAR_EFFECT, quote the sentence most relevant
    to the gene, or use "none" and "" if no sentence mentions it."""


def construir_user_v1(caso: CasoProceso, cfg: ConfigPrompt = CONFIG_V1) -> str:
    g, proceso = caso.gen, caso.nucleo_nombre
    lineas = [f"ABSTRACT (PMID {caso.pmid})", f"[T] {caso.titulo}"]
    lineas += [f"[S{i}] {f}" for i, f in enumerate(caso.frases, 1)]
    lineas.append("")
    if cfg.localizador_frase_fuente and caso.frase_fuente:
        lineas += [f"SENTENCE OF INTEREST (found automatically, may be incomplete; decide from the abstract): "
                   f"{caso.frase_fuente}", ""]
    otros = f" Other names used in the literature: {', '.join(caso.alias)}." if caso.alias else ""
    lineas += [
        f"GENE: {g}.{otros}",
        f"The protein encoded by {g} counts as {g}.",
        f"PROCESS: {proceso}",
        "",
        f"QUESTION: According to this abstract only, does {g} INCREASE or DECREASE {proceso}?",
        f"- INCREASES: the abstract shows that {g} causes, promotes or is required for {proceso}.",
        f"- DECREASES: the abstract shows that {g} suppresses, limits or impairs {proceso}.",
        f"- NO_CLEAR_EFFECT: neither is shown for {g}; choose the reason.",
        "Return the JSON object.",
    ]
    return "\n".join(lineas)


def construir_prompt(ev, cfg: ConfigPrompt = CONFIG_V0) -> PromptLLM:
    """Evidencia (v0) o CasoProceso (v1) -> PromptLLM con el texto final de esa versión."""
    if cfg.version == V1_PROCESO:
        return PromptLLM(evidencia=ev, system=SYSTEM_V1, user=construir_user_v1(ev, cfg),
                         version=V1_PROCESO, esquema_json=ESQUEMA_V1)
    return PromptLLM(evidencia=ev, system=SYSTEM, user=construir_user(ev, cfg), version=V0_ORIGINAL)
