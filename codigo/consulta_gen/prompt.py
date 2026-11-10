"""Construcción del prompt para un LLM ligero. Solo texto: no sabe nada de proveedores ni de red.

Hay dos versiones, que se comparan en el benchmark sobre el mismo gold set:
  - v0_original: el prompt de partida, CONGELADO tal cual (pregunta por la ruta, en español, con la
    dirección de scRNA-seq y el abstract recortado). Es la línea base: solo para el benchmark, no para
    producción (la spec prohíbe enviar la dirección de scRNA-seq).
  - v1_proceso: informe «Prompt y modelos gratuitos Fase 2» (anexo 1). Pregunta por el efecto del gen
    sobre el proceso núcleo, con el abstract completo en frases numeradas y salida JSON estricta; el
    signo sobre la ruta lo calcula el código (casos.py).
  - v1_proceso_gen: las mismas preguntas de v1, enviadas por gen en una sola llamada con salida en lista
    (informe «Coste de una llamada por gen en la Fase 2»). Cada pregunta se registra y se valida sola.
"""
import json
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from .esquema import (ESQUEMA_LISTA, ESQUEMA_LISTA_V2, ESQUEMA_V1, V0_ORIGINAL, V1_GEN, V1_PROCESO, V2_VEREDICTO,
                      CasoProceso, Evidencia,
                      PromptLista, PromptLLM)


@dataclass(frozen=True)
class ConfigPrompt:
    version: str = V0_ORIGINAL
    max_chars_abstract: Optional[int] = 1800  # v0: los modelos ligeros rinden mejor con contexto corto
    incluir_estado_scrnaseq: bool = True      # v0: Activada/Suprimida (contexto, pero puede sesgar)
    incluir_pista_go: bool = False            # v0: polaridad derivada del grafo GO, desactivada para no sesgar
    localizador_frase_fuente: bool = False    # v1, variante V2: añade la frase donde Fase 1 vio gen y proceso


CONFIG_V0 = ConfigPrompt()
CONFIG_V1 = ConfigPrompt(version=V1_PROCESO, max_chars_abstract=None, incluir_estado_scrnaseq=False)
CONFIG_V1_GEN = ConfigPrompt(version=V1_GEN, max_chars_abstract=None, incluir_estado_scrnaseq=False)
CONFIG_V2 = ConfigPrompt(version=V2_VEREDICTO, max_chars_abstract=None, incluir_estado_scrnaseq=False)


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
_REGLAS_V1 = """You read ONE PubMed abstract and report what it states about the causal effect of ONE human
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
    to the gene, or use "none" and "" if no sentence mentions it.
13. CONFIDENCE. After the reasoning, give an integer from 0 to 100: how sure you are that
    your answer is right. For INCREASES or DECREASES use this scale:
    90-100: an experiment on the gene in this abstract with an explicit result on this
            same process;
    70-89:  a clear experiment, but on a more specific form of the process, in another
            species or cell type, or with one step of inference;
    50-69:  indirect support: a comparison between cell subsets, an effect that requires
            the gene without manipulating it, or only a concluding sentence;
    below 50: not enough for a sign; answer NO_CLEAR_EFFECT instead.
    For NO_CLEAR_EFFECT, give how sure you are that the abstract shows no clear effect."""


def _campos(esquema: Dict) -> str:
    """Los campos de la respuesta, en orden y con sus valores, sacados del esquema (los modelos sin salida
    estructurada estricta, como qwen en Groq, se inventaban los nombres)."""
    lineas = []
    for k, p in esquema["properties"].items():
        lineas.append(f'- "{k}": ' + (" | ".join(p["enum"]) if "enum" in p else p["description"]))
    return "\n".join(lineas)


SYSTEM_V1 = _REGLAS_V1 + f"""

OUTPUT. One JSON object with exactly these fields, in this order:
{_campos(ESQUEMA_V1)}
"motivo_unknown" is "none" when "efecto" is INCREASES or DECREASES."""


def _lineas_abstract(caso: CasoProceso) -> List[str]:
    return [f"ABSTRACT (PMID {caso.pmid})", f"[T] {caso.titulo}"] + [f"[S{i}] {f}" for i, f in enumerate(caso.frases, 1)]


def _linea_gen(caso: CasoProceso) -> str:
    otros = f" Other names used in the literature: {', '.join(caso.alias)}." if caso.alias else ""
    return f"GENE: {caso.gen}.{otros}"


def construir_user_v1(caso: CasoProceso, cfg: ConfigPrompt = CONFIG_V1) -> str:
    g, proceso = caso.gen, caso.nucleo_nombre
    lineas = _lineas_abstract(caso)
    lineas.append("")
    if cfg.localizador_frase_fuente and caso.frase_fuente:
        lineas += [f"SENTENCE OF INTEREST (found automatically, may be incomplete; decide from the abstract): "
                   f"{caso.frase_fuente}", ""]
    lineas += [
        _linea_gen(caso),
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


# --------------------------------------------------------------------------------------------------
# v1_proceso_gen: las preguntas de v1 de un mismo gen, en una sola llamada
# --------------------------------------------------------------------------------------------------
# El sistema es fijo (las reglas de v1 + la regla 14) y va primero: es el prefijo común de todas las llamadas,
# el que pueden servir de caché los proveedores (Groq, Cerebras, Gemini). Lo que cambia va detrás.
SYSTEM_LISTA = _REGLAS_V1 + f"""
14. SEVERAL QUESTIONS. The message may contain several abstracts and several questions about
    the gene. Answer every question Q1..Qn, one object per question, in order. Each answer is
    about the abstract (PMID) and the process named in THAT question only: never use another
    abstract to answer it. The sentence IDs ([T], [S1]...) refer to that question's abstract.

OUTPUT. One JSON object {{"respuestas": [...]}} with one object per question. Each object has
exactly these fields, in this order:
{_campos(ESQUEMA_LISTA["properties"]["respuestas"]["items"])}
"motivo_unknown" is "none" when "efecto" is INCREASES or DECREASES."""

SALIDA_BASE_LISTA = 2000    # max_completion_tokens con una pregunta (razonamiento incluido, como en v1)
SALIDA_POR_PREGUNTA = 600   # cada pregunta más: unos 160 de respuesta (medido con Gemini) + razonamiento


def construir_pregunta_gen(caso: CasoProceso) -> PromptLLM:
    """La pregunta de v1_proceso_gen como unidad del registro y del validador. Su `user` es solo SU parte
    (abstract, gen y proceso, sin número de pregunta): la huella no depende de con qué otras preguntas
    se envíe, así que una pregunta respondida no se repite aunque cambien las demás del gen."""
    user = "\n".join(_lineas_abstract(caso) + ["", _linea_gen(caso), f"PROCESS: {caso.nucleo_nombre}"])
    return PromptLLM(evidencia=caso, system=SYSTEM_LISTA, user=user, version=V1_GEN, esquema_json=ESQUEMA_LISTA)


# --------------------------------------------------------------------------------------------------
# v2_veredicto (producción): veredicto obligado con confianza; el UNKNOWN lo decide el código
# --------------------------------------------------------------------------------------------------
# Mismo envío que v1_proceso_gen (por gen, en lista). El modelo SIEMPRE elige INCREASES, DECREASES o NO_EFFECT,
# da su confianza y las frases que lo motivan; las trampas de la v1 (diana, marcador, otra molécula...) ya no
# son una abstención sino una «limitación» con confianza por debajo de 40. El código decide: por debajo de
# UMBRAL_VEREDICTO es UNKNOWN, salvo que coincida con la Polaridad_GO de la anotación (resultados.py).
SYSTEM_V2 = f"""You read PubMed abstracts and report what each one states about the causal effect of ONE
human gene (or its protein product) on ONE biological process. Use only the abstract text,
never your own knowledge. Always give a verdict; when the abstract gives little or no support
for it, say so with a low confidence. Reply with the JSON object only.

Rules:
1. VERDICT. Always choose one:
   INCREASES: the gene causes, promotes or is required for the process.
   DECREASES: the gene suppresses, limits or impairs the process.
   NO_EFFECT: the abstract reports that the gene does not change the process.
   Never leave the verdict out. If the abstract does not support any of them, choose the most
   likely one and give a confidence below 40 (rule 12).
2. CAUSE, NOT TARGET. The gene must be the cause. If something else changes the gene's
   expression or activity ("TNF induced GENE", "GENE was upregulated during infection"), the
   abstract says nothing about the gene's own effect: limitation gene_is_the_target and a
   confidence below 40.
3. LOSS OF FUNCTION INVERTS. If knockout, knockdown, siRNA, deficiency, a blocking antibody
   or an inhibitor of the gene DECREASES the process, the gene INCREASES it; if it
   INCREASES the process, the gene DECREASES it. Say so in the reasoning.
4. GAIN OF FUNCTION KEEPS. Overexpression, transfection, an agonist or the recombinant
   protein: the gene has the same direction as the observed effect.
5. MARKER OR CORRELATION IS NOT CAUSAL. Expression on cells that perform the process,
   co-expression, correlation with the process, prognosis or survival: limitation
   marker_or_correlation_only and a confidence below 40.
6. OTHER MOLECULE. If the effect is attributed to a different molecule (a ligand, receptor,
   partner, complex or drug), it counts for the gene only if the gene's own product was
   manipulated, or the abstract shows the effect requires the gene. Otherwise: limitation
   effect_of_other_molecule and a confidence below 40.
7. NEGATION. "Did not affect", "was dispensable", "no change" in a reported experiment:
   NO_EFFECT. Never answer DECREASES for a negated effect.
8. SPECULATION. A hypothesis without a reported result ("may", "could", "we propose"):
   limitation speculation_only and a confidence below 40. A cautious conclusion of a
   reported experiment does count.
9. CONFLICT. If the abstract reports both directions for this process and gives no way to
   choose: limitation conflicting_results and a confidence below 40.
10. SCOPE. A more specific form of the process counts (e.g. NK cytotoxicity against tumour
    cells counts for "natural killer cell mediated cytotoxicity"). A broader or different
    process does not: limitation process_not_addressed and a confidence below 40.
11. CONTEXT IS DATA. Report the organism and cell type; do not go below 40 only because the
    study is in mouse, another cell type or another disease. PREFER RESULTS over background
    statements from the introduction.
12. CONFIDENCE. An integer from 0 to 100: how strongly the abstract supports your verdict.
    90-100: an experiment on the gene in this abstract with an explicit result on this
            same process;
    70-89:  a clear experiment, but on a more specific form of the process, in another
            species or cell type, or with one step of inference;
    40-69:  indirect support: a comparison between cell subsets, an effect that requires
            the gene without manipulating it, or only a concluding or background sentence;
    0-39:   the abstract does not support the verdict (rules 2, 5, 6, 8, 9, 10), or the gene
            is not discussed (limitation gene_not_discussed).
    The limitation is "none" when the confidence is 40 or more.
13. SENTENCES. Give 1 to 3 sentences that motivate the verdict, each with its ID ([T] = title,
    [S1], [S2]...) and a contiguous span of at least 6 words copied character by character
    from that sentence, with no ellipsis and no rewording. If no sentence supports the verdict,
    give the sentence most relevant to the gene.
14. SEVERAL QUESTIONS. The message may contain several abstracts and several questions about
    the gene. Answer every question Q1..Qn, one object per question, in order. Each answer is
    about the abstract (PMID) and the process named in THAT question only: never use another
    abstract to answer it. The sentence IDs ([T], [S1]...) refer to that question's abstract.

OUTPUT. One JSON object {{"respuestas": [...]}} with one object per question. Each object has
exactly these fields, in this order:
{_campos(ESQUEMA_LISTA_V2["properties"]["respuestas"]["items"])}"""


def construir_pregunta_v2(caso: CasoProceso) -> PromptLLM:
    """La pregunta de v2_veredicto: misma unidad y misma parte del prompt que v1_proceso_gen, otro sistema."""
    user = "\n".join(_lineas_abstract(caso) + ["", _linea_gen(caso), f"PROCESS: {caso.nucleo_nombre}"])
    return PromptLLM(evidencia=caso, system=SYSTEM_V2, user=user, version=V2_VEREDICTO, esquema_json=ESQUEMA_LISTA_V2)


def construir_prompt_lista(preguntas: Sequence[PromptLLM]) -> PromptLista:
    """Preguntas de UN gen (v1_proceso_gen o v2_veredicto) -> lo que se envía. Orden determinista (PMID,
    proceso), abstracts sin repetir."""
    preguntas = tuple(sorted(preguntas, key=lambda p: (p.evidencia.pmid, p.evidencia.nucleo_id)))
    casos = [p.evidencia for p in preguntas]
    if len({c.gen for c in casos}) != 1 or len({p.version for p in preguntas}) != 1:
        raise ValueError("Una llamada por gen solo lleva preguntas de un gen y de una versión")
    v2 = preguntas[0].version == V2_VEREDICTO
    g, lineas, vistos = casos[0].gen, [], set()
    for c in casos:
        if c.pmid not in vistos:
            vistos.add(c.pmid)
            lineas += _lineas_abstract(c) + [""]
    lineas += [
        _linea_gen(casos[0]),
        f"The protein encoded by {g} counts as {g}.",
        "",
    ]
    if v2:
        lineas += [f"QUESTIONS: According to the given abstract only, does {g} INCREASE or DECREASE the process, "
                   "or have NO_EFFECT on it? Always give a verdict, its confidence and the sentences behind it."]
    else:
        lineas += [
            f"QUESTIONS: According to the given abstract only, does {g} INCREASE or DECREASE the process?",
            f"- INCREASES: the abstract shows that {g} causes, promotes or is required for the process.",
            f"- DECREASES: the abstract shows that {g} suppresses, limits or impairs the process.",
            f"- NO_CLEAR_EFFECT: neither is shown for {g}; choose the reason.",
        ]
    lineas += [f"Q{i}. PMID {c.pmid} | PROCESS: {c.nucleo_nombre}" for i, c in enumerate(casos, 1)]
    lineas.append("Return the JSON object with one answer per question.")
    return PromptLista(system=SYSTEM_V2 if v2 else SYSTEM_LISTA, user="\n".join(lineas), preguntas=preguntas,
                       esquema_json=ESQUEMA_LISTA_V2 if v2 else ESQUEMA_LISTA, version=preguntas[0].version,
                       max_salida=SALIDA_BASE_LISTA + SALIDA_POR_PREGUNTA * (len(preguntas) - 1))


CARACTERES_POR_TOKEN = 3.5  # estimación prudente (medido: unos 4 en estos abstracts con el tokenizador de gpt-oss)


def tokens_estimados(lista: PromptLista) -> int:
    """Entrada estimada + max_completion_tokens: lo que puede contar el límite por minuto del proveedor."""
    texto = lista.system + lista.user + json.dumps(lista.esquema_json)
    return math.ceil(len(texto) / CARACTERES_POR_TOKEN) + (lista.max_salida or 0)


def trocear_por_gen(preguntas: Sequence[PromptLLM], presupuesto: int) -> List[PromptLista]:
    """Preguntas de v1_proceso_gen -> llamadas: una por gen, troceada en orden (PMID, proceso) para que ninguna
    pase el presupuesto. Una pregunta que sola ya lo pasa va sola (el proveedor dirá si cabe)."""
    por_gen: Dict[str, List[PromptLLM]] = {}
    for p in preguntas:
        por_gen.setdefault(p.gen, []).append(p)
    listas = []
    for ps in por_gen.values():
        actual: List[PromptLLM] = []
        for p in sorted(ps, key=lambda p: (p.evidencia.pmid, p.evidencia.nucleo_id)):
            if actual and tokens_estimados(construir_prompt_lista(actual + [p])) > presupuesto:
                listas.append(construir_prompt_lista(actual))
                actual = []
            actual.append(p)
        listas.append(construir_prompt_lista(actual))
    return listas


def construir_prompt(ev, cfg: ConfigPrompt = CONFIG_V0) -> PromptLLM:
    """Evidencia (v0) o CasoProceso (v1, v1_gen y v2) -> PromptLLM con el texto final de esa versión.
    En v1_proceso_gen y v2_veredicto es la pregunta suelta; lo que se envía lo arma construir_prompt_lista."""
    if cfg.version == V1_PROCESO:
        return PromptLLM(evidencia=ev, system=SYSTEM_V1, user=construir_user_v1(ev, cfg),
                         version=V1_PROCESO, esquema_json=ESQUEMA_V1)
    if cfg.version == V1_GEN:
        return construir_pregunta_gen(ev)
    if cfg.version == V2_VEREDICTO:
        return construir_pregunta_v2(ev)
    return PromptLLM(evidencia=ev, system=SYSTEM, user=construir_user(ev, cfg), version=V0_ORIGINAL)
