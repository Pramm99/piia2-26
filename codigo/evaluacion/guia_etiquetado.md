# Guía de etiquetado del gold set

Cada caso es una pregunta: **según este abstract, ¿el gen (o la proteína que codifica) AUMENTA o DISMINUYE el proceso indicado?**

La plantilla (`plantilla_etiquetado.xlsx` o `plantilla_etiquetado.jsonl`) muestra, para cada caso, el gen, otros nombres del gen, el PMID, el proceso, el título `[T]` y las frases del abstract `[S1]…[Sn]`. Contesta **solo con lo que dice el abstract**, sin usar lo que sepas del gen por otras fuentes.

## Qué hay que rellenar

| Campo | Valores |
|---|---|
| `efecto` | `INCREASES`, `DECREASES` o `NO_CLEAR_EFFECT` |
| `motivo` | Si `efecto` es `NO_CLEAR_EFFECT`: uno de `gene_not_discussed`, `gene_is_the_target`, `marker_or_correlation_only`, `effect_of_other_molecule`, `no_effect_found`, `speculation_only`, `conflicting_results`, `process_not_addressed`. Si no, `none`. |
| `id_frase` | La frase que justifica la etiqueta: `T`, `S1`, `S2`… (`none` si ninguna menciona el gen) |
| `cita` | Un fragmento de esa frase copiado literalmente (6 palabras o más) |
| `confianza` | `alta`, `media` o `baja` |
| `nota` | Opcional: una frase si el caso es dudoso |

## Reglas
1. **Causa, no diana.** El gen tiene que ser la causa. Si es otra cosa la que cambia la expresión o la actividad del gen («TNF induce GEN», «GEN sube durante la infección»), la etiqueta es `NO_CLEAR_EFFECT` con el motivo `gene_is_the_target`.
2. **La pérdida de función invierte el signo.** Si el knockout, el knockdown, el siRNA, la deficiencia, un anticuerpo bloqueante o un inhibidor del gen **disminuye** el proceso, el gen lo **aumenta**; si lo aumenta, el gen lo disminuye.
3. **La ganancia de función lo conserva.** Con sobreexpresión, transfección, un agonista o la proteína recombinante, el gen tiene la misma dirección que el efecto observado.
4. **Un marcador o una correlación no es causalidad.** Expresión en las células que hacen el proceso, coexpresión, correlación, pronóstico o supervivencia: `NO_CLEAR_EFFECT`, motivo `marker_or_correlation_only`.
5. **Otra molécula.** Si el efecto se atribuye a otra molécula (ligando, receptor, pareja, complejo o fármaco), solo cuenta para el gen si se manipuló el producto del propio gen o el abstract muestra que el efecto lo requiere. Si no: `effect_of_other_molecule`.
6. **Negación.** «No afectó», «fue prescindible», «sin cambios»: `NO_CLEAR_EFFECT`, motivo `no_effect_found`.
7. **Especulación.** Una hipótesis sin resultado («podría», «proponemos»): `speculation_only`. La conclusión prudente de un experimento sí cuenta.
8. **Conflicto.** Si el abstract da las dos direcciones para este proceso sin forma de elegir: `conflicting_results`.
9. **Alcance.** Una forma más específica del proceso cuenta: por ejemplo, la citotoxicidad NK frente a células tumorales cuenta para «natural killer cell mediated cytotoxicity». Un proceso más amplio o distinto no cuenta: `process_not_addressed`.
10. **El contexto es un dato, no un motivo para abstenerse.** Un estudio en ratón, en otro tipo celular o en otra enfermedad cuenta.
11. **Los resultados mandan sobre la introducción.** Se da preferencia a lo que el estudio demuestra frente a las frases de contexto.
12. **Ante la duda razonable, `NO_CLEAR_EFFECT`.** Es mejor no dar signo que inventarlo.

## Etiquetado a ciegas
No mires la salida de ningún modelo ni la polaridad de Gene Ontology antes de etiquetar. Los casos marcados con `doble_etiquetado` los etiqueta además una segunda persona, sin ver la primera etiqueta.
