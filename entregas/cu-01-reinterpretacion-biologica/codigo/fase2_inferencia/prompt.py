"""Construcción del prompt para un LLM ligero. Solo texto: no sabe nada de proveedores ni de red.

Pregunta por el efecto del gen sobre el proceso núcleo, con el abstract completo en frases numeradas, y se envía
por gen en una sola llamada con salida en lista; el signo sobre la ruta lo calcula el código (casos.py). Cada
pregunta se registra y se valida sola. El modelo siempre da un veredicto y su confianza; el UNKNOWN lo decide el
código.
"""
import json
import math
from typing import Dict, List, Sequence

from .esquema import ESQUEMA_LISTA, VERSION_PROMPT, CasoProceso, PromptLista, PromptLLM


def _campos(esquema: Dict) -> str:
    """Los campos de la respuesta, en orden y con sus valores, sacados del esquema (los modelos sin salida
    estructurada estricta, como qwen en Groq, se inventaban los nombres)."""
    lineas = []
    for k, p in esquema["properties"].items():
        lineas.append(f'- "{k}": ' + (" | ".join(p["enum"]) if "enum" in p else p["description"]))
    return "\n".join(lineas)


def _lineas_abstract(caso: CasoProceso) -> List[str]:
    return [f"ABSTRACT (PMID {caso.pmid})", f"[T] {caso.titulo}"] + [f"[S{i}] {f}" for i, f in enumerate(caso.frases, 1)]


def _linea_gen(caso: CasoProceso) -> str:
    otros = f" Other names used in the literature: {', '.join(caso.alias)}." if caso.alias else ""
    return f"GENE: {caso.gen}.{otros}"


def _user_pregunta(caso: CasoProceso) -> str:
    """La parte de UNA pregunta (abstract, gen y proceso, sin número de pregunta): la huella no depende de con
    qué otras preguntas se envíe, así que una pregunta respondida no se repite aunque cambien las demás del gen."""
    return "\n".join(_lineas_abstract(caso) + ["", _linea_gen(caso), f"PROCESS: {caso.nucleo_nombre}"])


# El sistema es fijo y va primero: es el prefijo común de todas las llamadas, el que pueden servir de caché los
# proveedores (Groq, Cerebras, Gemini). Lo que cambia va detrás. Cambiar el texto cambia la huella y obliga a
# repetir las llamadas del registro.
# El modelo SIEMPRE elige INCREASES, DECREASES o NO_EFFECT, da su confianza y las frases que lo motivan; las
# trampas (diana, marcador, otra molécula...) no son una abstención sino una «limitación». El prompt NO menciona
# ningún umbral (decisión del 2026-11-10: sería una fuga de información que predispone la confianza); el código
# decide con UMBRAL_VEREDICTO, que se ajusta con el benchmark, y con la Polaridad_GO de la anotación (resultados.py).
SYSTEM = f"""You read PubMed abstracts and report what each one states about the causal effect of ONE
human gene (or its protein product) on ONE biological process. Use only the abstract text,
never your own knowledge. Always give a verdict; when the abstract gives little or no support
for it, say so with a low confidence. Reply with the JSON object only.

Rules:
1. VERDICT. Always choose one:
   INCREASES: the gene causes, promotes or is required for the process.
   DECREASES: the gene suppresses, limits or impairs the process.
   NO_EFFECT: the abstract reports that the gene does not change the process.
   Never leave the verdict out. If the abstract does not support any of them, still choose the
   most likely one; your confidence (rule 12) must show how weak that choice is.
2. CAUSE, NOT TARGET. The gene must be the cause. If something else changes the gene's
   expression or activity ("TNF induced GENE", "GENE was upregulated during infection"), the
   abstract says nothing about the gene's own effect: limitation gene_is_the_target.
3. LOSS OF FUNCTION INVERTS. If knockout, knockdown, siRNA, deficiency, a blocking antibody
   or an inhibitor of the gene DECREASES the process, the gene INCREASES it; if it
   INCREASES the process, the gene DECREASES it. Say so in the reasoning.
4. GAIN OF FUNCTION KEEPS. Overexpression, transfection, an agonist or the recombinant
   protein: the gene has the same direction as the observed effect.
5. MARKER OR CORRELATION IS NOT CAUSAL. Expression on cells that perform the process,
   co-expression, correlation with the process, prognosis or survival: limitation
   marker_or_correlation_only.
6. OTHER MOLECULE. If the effect is attributed to a different molecule (a ligand, receptor,
   partner, complex or drug), it counts for the gene only if the gene's own product was
   manipulated, or the abstract shows the effect requires the gene. Otherwise: limitation
   effect_of_other_molecule.
7. NEGATION. "Did not affect", "was dispensable", "no change" in a reported experiment:
   NO_EFFECT. Never answer DECREASES for a negated effect.
8. SPECULATION. A hypothesis without a reported result ("may", "could", "we propose"):
   limitation speculation_only. A cautious conclusion of a reported experiment does count.
9. CONFLICT. If the abstract reports both directions for this process and gives no way to
   choose: limitation conflicting_results.
10. SCOPE. A more specific form of the process counts (e.g. NK cytotoxicity against tumour
    cells counts for "natural killer cell mediated cytotoxicity"). A broader or different
    process does not: limitation process_not_addressed.
11. CONTEXT IS DATA. Report the organism and cell type; do not lower your confidence only
    because the study is in mouse, another cell type or another disease. PREFER RESULTS over background
    statements from the introduction.
12. CONFIDENCE. An integer from 0 to 100: your probability that the verdict is right, judged
    only from this abstract. Use the whole scale. From strongest to weakest support:
    - an experiment on the gene in this abstract with an explicit result on this same process;
    - a clear experiment, but on a more specific form of the process, in another species or
      cell type, or with one step of inference;
    - indirect support: a comparison between cell subsets, an effect that requires the gene
      without manipulating it, or only a concluding or background sentence;
    - no support: the abstract does not address the gene's effect on the process (rules 2, 5,
      6, 8, 9, 10) or does not discuss the gene (limitation gene_not_discussed).
    Use limitation "none" when none of those rules applies.
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
{_campos(ESQUEMA_LISTA["properties"]["respuestas"]["items"])}"""

SALIDA_BASE_LISTA = 2000    # max_completion_tokens con una pregunta (razonamiento incluido)
SALIDA_POR_PREGUNTA = 600   # cada pregunta más: unos 160 de respuesta (medido con Gemini) + razonamiento


def construir_prompt(caso: CasoProceso) -> PromptLLM:
    """CasoProceso -> la pregunta suelta, unidad del registro y del validador; lo que se envía lo arma
    construir_prompt_lista."""
    return PromptLLM(evidencia=caso, system=SYSTEM, user=_user_pregunta(caso), version=VERSION_PROMPT,
                     esquema_json=ESQUEMA_LISTA)


def construir_prompt_lista(preguntas: Sequence[PromptLLM]) -> PromptLista:
    """Preguntas de UN gen -> lo que se envía. Orden determinista (PMID, proceso), abstracts sin repetir."""
    preguntas = tuple(sorted(preguntas, key=lambda p: (p.evidencia.pmid, p.evidencia.nucleo_id)))
    casos = [p.evidencia for p in preguntas]
    if len({c.gen for c in casos}) != 1:
        raise ValueError("Una llamada por gen solo lleva preguntas de un gen")
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
    lineas += [f"QUESTIONS: According to the given abstract only, does {g} INCREASE or DECREASE the process, "
               "or have NO_EFFECT on it? Always give a verdict, its confidence and the sentences behind it."]
    lineas += [f"Q{i}. PMID {c.pmid} | PROCESS: {c.nucleo_nombre}" for i, c in enumerate(casos, 1)]
    lineas.append("Return the JSON object with one answer per question.")
    return PromptLista(system=SYSTEM, user="\n".join(lineas), preguntas=preguntas, esquema_json=ESQUEMA_LISTA,
                       version=VERSION_PROMPT,
                       max_salida=SALIDA_BASE_LISTA + SALIDA_POR_PREGUNTA * (len(preguntas) - 1))


CARACTERES_POR_TOKEN = 3.5  # estimación prudente (medido: unos 4 en estos abstracts con el tokenizador de gpt-oss)


def tokens_estimados(lista: PromptLista) -> int:
    """Entrada estimada + max_completion_tokens: lo que puede contar el límite por minuto del proveedor."""
    texto = lista.system + lista.user + json.dumps(lista.esquema_json)
    return math.ceil(len(texto) / CARACTERES_POR_TOKEN) + (lista.max_salida or 0)


def trocear_por_gen(preguntas: Sequence[PromptLLM], presupuesto: int) -> List[PromptLista]:
    """Preguntas sueltas -> llamadas: una por gen, troceada en orden (PMID, proceso) para que ninguna pase el
    presupuesto. Una pregunta que sola ya lo pasa va sola (el proveedor dirá si cabe)."""
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

