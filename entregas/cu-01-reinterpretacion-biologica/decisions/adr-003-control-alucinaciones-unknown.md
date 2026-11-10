---
description: Control de alucinaciones mediante un esquema de salida con signo, estado y motivos, reglas automáticas de verificación y contraste con Gene Ontology y entre dos modelos.
state: Aceptado (validación implementada el 2026-11-08; contraste entre modelos y con GO, el 2026-11-10)
---

# ADR 003 - Control de Alucinaciones: Signo, Estado y Motivos en Lugar de Predicciones Forzadas

## Decisión
El sistema **nunca fuerza un signo** cuando la evidencia no lo sostiene. Cada par evaluado (gen, PMID, término) produce una salida con tres campos:

| Campo | Valores |
|---|---|
| `signo` | `+1` / `-1` / `UNKNOWN` |
| `estado` | `resuelto` / `revisar` / `no_concluyente` |
| `motivos` | lista de cero o más motivos (tabla siguiente) |

| Motivo | Origen | Estado | Signo |
|---|---|---|---|
| `no_menciona_gen` | LLM o filtro previo | `no_concluyente` | `UNKNOWN` |
| `efecto_indirecto` | LLM (el efecto es de otra molécula) | `no_concluyente` | `UNKNOWN` |
| `contradictorio` | LLM (el abstract da las dos direcciones) | `no_concluyente` | `UNKNOWN` |
| `contexto_ajeno` | LLM (el abstract no trata ese proceso) | `no_concluyente` | `UNKNOWN` |
| `direccion_inversa` | LLM (el gen es la diana, no la causa: «TNF induce el gen») | `no_concluyente` | `UNKNOWN` |
| `marcador_correlacion` | LLM (marcador, coexpresión o correlación, sin causalidad) | `no_concluyente` | `UNKNOWN` |
| `sin_efecto` | LLM (el abstract dice que no hay efecto) | `no_concluyente` | `UNKNOWN` |
| `especulativo` | LLM (hipótesis sin resultado) | `no_concluyente` | `UNKNOWN` |
| `cita_no_verificada` | Regla automática | `no_concluyente` | `UNKNOWN` |
| `json_invalido` | Regla automática | `no_concluyente` | `UNKNOWN` |
| `incoherencia_respuesta` | Regla automática (p. ej. un efecto con un motivo de UNKNOWN, o con confianza por debajo de 50) | `revisar` | Se mantiene |
| `baja_confianza` | Regla automática: signo con cita verificada y `confianza_modelo` entre 50 y el umbral (70 por defecto) | `revisar` | Se mantiene |
| `ruta_sin_direccion` | Composición (v1_proceso), solo si `SIN_DIRECCION_COMO_PROCESO = False`: la ruta es «regulation of X» sin dirección. Por defecto esas rutas se tratan como X. | — | `UNKNOWN` en esa ruta |
| `discrepancia_polaridad_GO` | Contraste con GO | `revisar` | Se mantiene |
| `discrepancia_entre_modelos` | Contraste entre modelos | `revisar` | El del modelo principal |
| `sin_evidencia:<causa>` | Fase 1: el par no tiene ningún abstract y no llega al LLM | `no_concluyente` | `UNKNOWN` |

Los motivos `direccion_inversa`, `marcador_correlacion`, `sin_efecto` y `especulativo` se añadieron el 2026-11-08 (informe «Prompt y modelos gratuitos Fase 2»): separan las trampas de dirección más frecuentes, que antes caían todas en `efecto_indirecto` o `contexto_ajeno`, para poder analizar los errores por tipo. El motivo `baja_confianza` se añadió el 2026-11-10 (informe «Benchmark v2 y propuesta de confianza Fase 2»).

`UNKNOWN` queda reservado para los casos **sin evidencia utilizable**. Cuando hay evidencia pero otra fuente la contradice (Gene Ontology o el modelo secundario), se conserva el signo y el caso se marca para revisión experta.

El control se organiza en tres capas:

1. **Prompt:** el modelo puede responder `UNKNOWN` indicando uno de los motivos semánticos, cada uno con un criterio explícito en el prompt (ofrecer «unknown» sin criterios provoca abstenciones falsas). La justificación literal, el razonamiento y la **confianza** (entero de 0 a 100) se piden **antes** del signo. La confianza tiene anclas fijas en el prompt para que todos los modelos usen la misma escala: 90-100 si hay un experimento con el gen y un resultado explícito sobre ese proceso; 70-89 si el experimento es claro pero sobre una forma más específica del proceso, otra especie u otro tipo celular, o con un paso de inferencia; 50-69 si el apoyo es indirecto; por debajo de 50 la respuesta debe ser `NO_CLEAR_EFFECT`. El prompt enumera además los campos del JSON con sus valores permitidos. En `v1_proceso` el modelo devuelve el efecto sobre el proceso (`INCREASES` / `DECREASES` / `NO_CLEAR_EFFECT`) y sus motivos en inglés, que el código traduce a los de esta tabla; la línea base `v0_original` conserva el prompt de partida para el benchmark.
2. **Reglas automáticas**, que no dependen del juicio del modelo:
   * **Filtro previo:** si ni el gen ni sus alias del GAF aparecen en el abstract como palabra completa (`CD7` no cuenta dentro de `CD70`; `CD-7` equivale a `CD7`), la salida es `no_menciona_gen` sin llamar al LLM.
   * **Verificación de la cita:** la justificación debe aparecer literalmente en el abstract tras una normalización solo para comparar (minúsculas, todos los guiones unificados, letras griegas escritas como palabras: α→alpha, κ→kappa…, y sin puntuación). Debe tener **al menos 6 palabras** y coincidir con palabras enteras. En `v1_proceso` el abstract va en frases numeradas y la cita debe estar dentro de la frase que indica el modelo (`id_frase`). Si no se verifica, el signo pasa a `UNKNOWN` con `cita_no_verificada`, y se conserva el signo original del modelo (`signo_llm`) para auditoría.
   * **Formato:** un JSON no interpretable, un campo que falta o un valor fuera de los permitidos da `json_invalido`.
   * **Coherencia:** una respuesta internamente incoherente (un efecto con motivo de `UNKNOWN`, `NO_CLEAR_EFFECT` sin motivo, un efecto basado en `correlation_or_marker` o un efecto con confianza por debajo de 50) conserva el signo, añade `incoherencia_respuesta` y queda en `revisar`.
   * **Confianza baja:** un signo que sobrevive a la verificación de la cita y tiene una `confianza_modelo` por debajo del umbral (`UMBRAL_CONFIANZA = 70` en `esquema.py`, provisional) **conserva el signo**, añade `baja_confianza` y queda en `revisar`. La confianza declarada nunca convierte un signo en `UNKNOWN`: solo pide la revisión del experto. Una confianza que no sea un entero de 0 a 100 da `json_invalido`.
3. **Contraste con fuentes independientes:**
   * **Gene Ontology:** si el signo sobre una ruta difiere de la `Polaridad_GO` de la anotación de ese mismo gen, ruta y PMID (cuando es `+1` o `-1` y no hay signos distintos entre las filas del PMID), se añade `discrepancia_polaridad_GO` a esa fila y queda en `revisar`.
   * **Dos modelos:** cada caso se evalúa con un **modelo principal** y un **modelo secundario**, ambos gratuitos. El `signo` final es el del principal y se registran las respuestas de los dos. Cualquier diferencia entre ellos (signos opuestos, o uno `UNKNOWN` y el otro no) añade el motivo `discrepancia_entre_modelos` y deja el caso en `revisar`. Una respuesta del secundario con `json_invalido` no cuenta como discrepancia: no dice nada del abstract, solo que ese modelo falló el formato. Si el principal todavía no ha respondido (límite diario), el caso queda `pendiente`, nunca `UNKNOWN`. Qué modelo es el principal y cuál el secundario se fija en el [ADR-005](adr-005-eleccion-modelo-coste-cero.md), a partir del benchmark.

**Porcentaje final (`confianza_final`).** La confianza declarada suele estar inflada, así que el porcentaje que se muestra junto al signo y al motivo se corrige con señales que no dependen de lo que el modelo diga de sí mismo (`codigo/consulta_gen/confianza.py`):

`confianza_final = confianza_modelo × factor_evidencia × factor_frase × factor_acuerdo`, entre 0 y 100.

* **Tipo de evidencia:** ganancia de función 1,0; pérdida de función 0,9; medida directa 0,85; contexto, correlación o ninguna 0,7.
* **Frase citada:** 0,9 si es el título o las frases S1-S2 (suelen ser introducción); 1,0 si es una frase posterior.
* **Otro modelo:** 1,0 si da el mismo signo; 0,8 si da `UNKNOWN`; 0,5 si da el signo opuesto; 0,9 si no hay respuesta suya.

Los factores son provisionales: salen del benchmark v2 (43 signos de los tres modelos de API) como el cociente entre el acierto de cada grupo y el del mejor, acercados a 1 la mitad del camino porque las muestras son pequeñas. Cuando haya etiquetas de CIMUS se sustituirán por una regresión logística ajustada en el *gold set*. Solo los signos tienen `confianza_final`: un `UNKNOWN` se explica con su motivo. Ese porcentaje es también el peso propuesto para cada respuesta en la agregación por par gen-ruta (spec de scoring).

La normalización de comparación nunca se aplica al texto que lee el LLM: este recibe el abstract limpio pero con la nomenclatura intacta, como exige la spec de limpieza.

Ejemplo de salida:

```json
{
  "gen": "CD7", "pmid": "10652336", "go_id": "GO:0002443",
  "signo": "+1",
  "estado": "revisar",
  "motivos": ["discrepancia_entre_modelos"],
  "signo_modelo_principal": "+1", "signo_modelo_secundario": "UNKNOWN",
  "confianza_modelo": 85, "confianza_final": 68,
  "justificacion_literal": "Human K12-Fc stimulated the up-regulation of CD25, CD54, and CD69 on human NK cells in vitro.",
  "cita_verificada": true,
  "polaridad_go": "+1"
}
```

## Motivación
1. **Un signo falso es peor que un `UNKNOWN`:** el signo entra en el *Net Pathway Score*; un error invierte la contribución del gen a la ruta, mientras que un `UNKNOWN` solo lo deja sin resolver.
2. **El LLM no sabe cuándo se equivoca:** pedirle que diga `UNKNOWN` si duda solo cubre los casos en que detecta su propia duda. Los errores peligrosos son los que comete con seguridad. Ejemplo real del dataset: en el PMID 10652336 el efecto sobre CD25/CD69 lo produce el ligando K12-Fc, no CD7; un modelo complaciente responde `+1` sin dudar. Por eso hacen falta comprobaciones externas al modelo.
3. **Los motivos hacen el sistema auditable:** un `UNKNOWN` sin motivo no indica si falla la recuperación, el modelo o la propia evidencia. Elegir entre motivos concretos es además una tarea más fiable para un LLM que estimar su propia confianza; por eso la confianza declarada no decide el signo: solo manda casos a revisión y, corregida con señales externas, da el porcentaje final.
4. **Las discrepancias son información, no ruido:** la polaridad de GO es curada por expertos y el segundo modelo es independiente del primero. Convertir sus desacuerdos en `UNKNOWN` descartaría justo los casos que más interesa que revise el experto. Cuando discrepan los dos modelos, se conserva el signo del principal, se registran ambas respuestas y el caso queda marcado para que el experto lo resuelva con toda la información.
5. **La conclusión es del experto:** el sistema extrae y verifica evidencia; los casos `revisar` se entregan al profesional biomédico con la cita y los motivos.

**Validación:** sobre el *gold set* etiquetado por expertos se medirán la **precisión de las respuestas dadas** (cuando el sistema da `+1` o `-1`, cuántas acierta), la **cobertura** (porcentaje de casos con estado `resuelto`) y el **recall de `UNKNOWN`** (cuántos casos no concluyentes según el experto detecta el sistema). Los umbrales mínimos se acordarán con CIMUS.

Aceptamos los compromisos asociados: duplicar las llamadas (dos modelos) alarga la ejecución en los planes gratuitos; el filtro previo puede descartar abstracts que nombran el gen de forma no recogida en los alias (un error en la dirección segura, que se medirá en el benchmark); y la cobertura bajará frente a un sistema que siempre responde.

## Alternativas
* **`UNKNOWN` simple, sin motivo:**
  * *Motivo de descarte:* no permite saber por qué falla el sistema ni priorizar mejoras.
* **Usar la confianza declarada por el propio modelo tal cual (p. ej. "estoy seguro al 80 %"), con un umbral que convierta en `UNKNOWN`:**
  * *Motivo de descarte:* la confianza verbalizada de los LLM está mal calibrada y tiende a ser excesiva (se concentra entre 80 y 100 aunque el modelo se equivoque). Se pide igualmente, con anclas fijas, pero solo para mandar a `revisar` (`baja_confianza`) y como una de las entradas de `confianza_final`, cuya calibración se mide en el benchmark (fiabilidad, ECE, AUROC y curva riesgo-cobertura).
* **Marcar `revisar` cuando la cita no se verifica, en lugar de `UNKNOWN`:**
  * *Motivo de descarte:* una cita que no está en el abstract es justo la señal de alucinación que se quiere bloquear; el equipo decidió tratarla como falta de evidencia.
* **Convertir en `UNKNOWN` cualquier discrepancia (con GO o entre modelos):**
  * *Motivo de descarte:* se perderían los casos con evidencia en conflicto, que son los más valiosos para la revisión experta.
* **Signo `CONTRADICCION` sin preferencia por ningún modelo cuando los dos discrepan:**
  * *Motivo de descarte:* deja sin signo casos que sí tienen evidencia. El equipo prefirió conservar el signo del modelo principal, guardar las dos respuestas y marcar el caso como `revisar`, de modo que la discrepancia queda igualmente visible para el experto.
* **Comparar modelos solo en el benchmark:**
  * *Motivo de descarte:* el equipo prefirió el contraste en todos los casos; con dos planes gratuitos es viable a coste cero, a cambio de más días de ejecución.
* **Responder siempre `+1`/`-1` (sin opción `UNKNOWN`):**
  * *Motivo de descarte:* obliga al modelo a inventar un signo cuando el abstract no lo sostiene.

## Referencias
* **Código del proyecto (estado actual):**
  * `codigo/consulta_gen/respuesta.py`: verificación de la cita, `UNKNOWN` forzado, `json_invalido`, `incoherencia_respuesta` y traducción de los motivos (commit `1738e0b`).
  * `codigo/consulta_gen/limpieza.py`: `forma_comparacion()` y `segmentar_frases()`.
  * `codigo/consulta_gen/pipeline.py`: filtro previo `no_menciona_gen` (alias de MyGene, sin llamar al LLM).
  * `codigo/consulta_gen/esquema.py`: esquema JSON estricto de `v1_proceso`, tabla de motivos y umbral de confianza.
  * `codigo/consulta_gen/confianza.py`: `confianza_final` y sus factores provisionales.
  * `codigo/evaluacion/evaluar_gold.py`: calibración de `confianza_modelo` y `confianza_final` sobre el *gold set*.
  * `codigo/extraer_info/polaridad.py`: cierre `sin_evidencia` de los pares sin abstract.
  * `codigo/consulta_gen/resultados.py`: contraste entre modelos y con `Polaridad_GO`, y salida `fase2_resultados.xlsx` (commit de la Fase 2 del 2026-11-10).
* **Salidas estructuradas:**
  * Groq: [https://console.groq.com/docs/structured-outputs](https://console.groq.com/docs/structured-outputs)
  * Gemini API: [https://ai.google.dev/gemini-api/docs/structured-output](https://ai.google.dev/gemini-api/docs/structured-output)
* **Literatura:**
  * Xiong et al. (2024), *Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs*, ICLR 2024 (sobreconfianza de la confianza verbalizada).
  * Geifman & El-Yaniv (2017), *Selective Classification for Deep Neural Networks*, NeurIPS 2017 (compromiso entre cobertura y precisión al abstenerse).
* **Decisiones relacionadas:** [ADR-001](adr-001-rag-stateless.md) (arquitectura RAG), [ADR-004](adr-004-persistencia-ficheros-locales.md) (registro de respuestas) y [ADR-005](adr-005-eleccion-modelo-coste-cero.md) (elección de los modelos).
