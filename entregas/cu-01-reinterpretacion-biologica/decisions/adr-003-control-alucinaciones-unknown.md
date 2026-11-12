---
description: Control de alucinaciones mediante un esquema de salida con signo, estado y motivos, reglas automáticas de verificación y contraste con Gene Ontology y entre dos modelos.
state: Aceptado (validación implementada el 2026-11-08; contraste entre modelos y con GO, el 2026-11-10; veredicto obligado con UNKNOWN decidido por el código, el 2026-11-10; sin confianza mínima para `coincide_polaridad_GO` y umbral sobre `confianza_modelo`, el 2026-11-11)
---

# ADR 003 - Control de Alucinaciones: Signo, Estado y Motivos en Lugar de Predicciones Forzadas

## Decisión
El sistema **nunca da por bueno un signo** cuando la evidencia no lo sostiene. Se pregunta al LLM por cada **(gen, PMID, proceso núcleo)**, y el código traslada la respuesta a cada fila **(gen, ruta, PMID)** de la salida (spec de inferencia). Cada pregunta y cada fila llevan tres campos:

| Campo | Valores |
|---|---|
| `signo` | `+1` / `-1` / `neutro` / `UNKNOWN` |
| `estado` | `resuelto` / `revisar` / `no_concluyente` (y `pendiente` si el modelo principal aún no ha respondido) |
| `motivos` | lista de cero o más motivos (tabla siguiente) |

| Motivo | Origen | Estado | Signo |
|---|---|---|---|
| `no_menciona_gen` | Filtro previo (sin llamar al LLM) o limitación `gene_not_discussed` del modelo | `no_concluyente` | `UNKNOWN` |
| `efecto_indirecto` | LLM (el efecto es de otra molécula) | `no_concluyente` | `UNKNOWN` |
| `contradictorio` | LLM (el abstract da las dos direcciones) | `no_concluyente` | `UNKNOWN` |
| `contexto_ajeno` | LLM (el abstract no trata ese proceso) | `no_concluyente` | `UNKNOWN` |
| `direccion_inversa` | LLM (el gen es la diana, no la causa: «TNF induce el gen») | `no_concluyente` | `UNKNOWN` |
| `marcador_correlacion` | LLM (marcador, coexpresión o correlación, sin causalidad) | `no_concluyente` | `UNKNOWN` |
| `especulativo` | LLM (hipótesis sin resultado) | `no_concluyente` | `UNKNOWN` |
| `cita_no_verificada` | Regla automática | `no_concluyente` | `UNKNOWN` |
| `json_invalido` | Regla automática | `no_concluyente` | `UNKNOWN` |
| `baja_confianza` | Regla automática: confianza por debajo de `UMBRAL_VEREDICTO` (80) y sin coincidencia con GO | `no_concluyente` | `UNKNOWN` |
| `incoherencia_respuesta` | Regla automática: veredicto que llega al umbral pero trae una limitación | `revisar` | Se mantiene |
| `coincide_polaridad_GO` | Contraste con GO: el veredicto sobre la ruta coincide con la `Polaridad_GO` de la anotación | `resuelto` (o `revisar` si además hay `discrepancia_entre_modelos` o `incoherencia_respuesta`) | El de GO y el LLM, aunque la confianza no llegue al umbral |
| `discrepancia_polaridad_GO` | Contraste con GO | `revisar` | Se mantiene (`UNKNOWN` si la confianza no llega al umbral) |
| `discrepancia_entre_modelos` | Contraste entre modelos | `revisar` | El del modelo principal |
| `respaldo_secundario` | El principal no respondió (cupo agotado, red) o su JSON no vale, y decide la respuesta válida del secundario | El que resulte de esa respuesta (no añade revisión) | El del modelo secundario |
| `ruta_sin_direccion` | Composición del signo hasta la ruta, solo si `SIN_DIRECCION_COMO_PROCESO = False`: la ruta es «regulation of X» sin dirección. Por defecto esas rutas se tratan como X | — | `UNKNOWN` en esa ruta |
| `sin_evidencia:<causa>` | Fase 1: el par no tiene ningún abstract y no llega al LLM | `no_concluyente` | `UNKNOWN` |

Los motivos `direccion_inversa`, `marcador_correlacion` y `especulativo` separan las trampas de dirección más frecuentes, que si no caerían todas en `efecto_indirecto` o `contexto_ajeno`, para poder analizar los errores por tipo.

### Veredicto obligado (decisión del equipo del 2026-11-10)
El LLM **no puede abstenerse**: para cada pregunta devuelve siempre un veredicto (`INCREASES`, `DECREASES` o `NO_EFFECT`, que se traducen a `+1`, `-1` y `neutro`), una **confianza** de 0 a 100 (su probabilidad de acertar según el abstract, con una guía cualitativa de más a menos apoyo), de 1 a 3 frases que lo motivan con su cita literal, el razonamiento y, si la hay, la **limitación** del abstract (gen diana, marcador, otra molécula, especulación, conflicto, proceso no tratado o gen no mencionado). **La decisión de `UNKNOWN` la toma el código**, no el modelo:

| Situación de la fila (gen, ruta, PMID) | Resultado |
|---|---|
| Ninguna de las frases tiene la cita verificada | `UNKNOWN`, `cita_no_verificada` |
| Hay `Polaridad_GO` (+1/−1) y el veredicto sobre la ruta **coincide** | Se acepta el efecto aunque la confianza no llegue al umbral: `resuelto`, `coincide_polaridad_GO` |
| Hay `Polaridad_GO` y el veredicto **no coincide** (también un neutro frente a +1/−1) | `revisar`, `discrepancia_polaridad_GO`, con las frases y la confianza del LLM. El signo es el del LLM si su confianza llega al umbral; si no, `UNKNOWN` |
| No hay `Polaridad_GO` y la confianza llega al umbral (`UMBRAL_VEREDICTO = 80`, configurable en `esquema.py`; fijado con la curva riesgo-cobertura del benchmark) | El veredicto del LLM: `+1`, `-1` o `neutro` (`resuelto`). Si además trae una limitación, `revisar` con `incoherencia_respuesta` |
| No hay `Polaridad_GO` y la confianza no llega al umbral | `UNKNOWN`, `baja_confianza` más la limitación que dio el modelo (`no_concluyente`) |

`neutro` significa que el abstract muestra que el gen **no cambia** el proceso («no afectó», «fue prescindible»). Es el mismo valor que la Fase 1 da a las inmunoglobulinas y cuenta como respuesta resuelta: entra en la cobertura de la ruta, pero no en el NPS, que promedia solo los pares con signo ±1, y se informa como `Fraccion_neutros` (spec de scoring). Un abstract que no trata el efecto del gen no es neutro: el modelo da una confianza baja y el código lo deja en `UNKNOWN`. **El prompt no menciona ningún umbral** (decisión del 2026-11-10): decirle al modelo dónde se corta sería una fuga de información que predispone su confianza. El umbral lo fija el código según la calidad medida en el benchmark. Como el registro guarda la respuesta cruda, cambiar el umbral solo exige volver a validar, sin llamar de nuevo a los modelos.

`UNKNOWN` queda reservado para los casos **sin evidencia utilizable**, o sin la confianza suficiente para darla por buena. Cuando hay evidencia pero otra fuente la contradice (Gene Ontology o el modelo secundario), se conserva el signo y el caso se marca para revisión experta.

El control se organiza en tres capas:

1. **Prompt** (`codigo/fase2_inferencia/prompt.py`). Pide las frases, el razonamiento y la confianza **antes** del veredicto. Explica cada trampa de dirección con un criterio explícito y enumera los campos del JSON con sus valores permitidos.
   * El modelo siempre elige un veredicto. Las trampas se declaran como `limitacion` y bajan la confianza.
   * La confianza no tiene cifras ni umbral, solo una guía cualitativa de más a menos apoyo.
   * El modelo responde en inglés y el código traduce las limitaciones a los motivos de la tabla (`MOTIVO_MODELO_A_ADR`).
2. **Reglas automáticas**, que no dependen del juicio del modelo (`codigo/fase2_inferencia/respuesta.py`):
   * **Filtro previo** (`casos.py`): si el abstract no nombra al gen como palabra completa por su símbolo, sus alias de MyGene o su nombre completo, la pregunta se cierra con `no_menciona_gen` sin llamar al LLM. `CD7` no cuenta dentro de `CD70`, `CD-7` equivale a `CD7`, los alias de menos de 3 caracteres se ignoran y una forma escrita toda en minúsculas no cuenta como mención.
   * **Verificación de la cita:** el abstract va en frases numeradas (`[T]`, `[S1]`, `[S2]`…) y la cita debe estar dentro de la frase que indica el modelo. Se compara tras una normalización solo para comparar: minúsculas, todos los guiones unificados, letras griegas escritas como palabras (α→alpha, κ→kappa…) y sin puntuación. La cita debe tener **al menos 6 palabras** y coincidir con palabras enteras. El modelo da de 1 a 3 frases y basta con que una se verifique. Si ninguna se verifica, el signo pasa a `UNKNOWN` con `cita_no_verificada`, y se conserva el veredicto original del modelo (`signo_llm`) para auditoría.
   * **Formato:** un JSON no interpretable, un campo que falta o un valor fuera de los permitidos da `json_invalido`. También una confianza ausente o que no sea un entero de 0 a 100, y una lista de frases mal formada.
   * **Confianza y coherencia:** una confianza por debajo de `UMBRAL_VEREDICTO` (80) convierte el veredicto en `UNKNOWN` con `baja_confianza`, salvo que coincida con GO (capa 3). Un veredicto que llega al umbral pero trae una limitación se conserva, añade `incoherencia_respuesta` y queda en `revisar`.
3. **Contraste con fuentes independientes** (`codigo/fase2_inferencia/resultados.py`):
   * **Gene Ontology**, fila a fila (gen, ruta, PMID). Solo se contrasta cuando las anotaciones de ese PMID dan una única `Polaridad_GO` (`+1` o `-1`). Se aplica la tabla de arriba; la coincidencia exige al menos una cita verificada.
   * **Dos modelos:** cada pregunta se evalúa con un **modelo principal** y un **modelo secundario**, ambos gratuitos. El `signo` final es el del principal y se registran los dos (`Signo_principal` y `Signo_secundario`). Cualquier diferencia entre ellos (signos opuestos, o uno `UNKNOWN` y el otro no) añade el motivo `discrepancia_entre_modelos` y deja el caso en `revisar`. Una respuesta del secundario con `json_invalido` no cuenta como discrepancia: no dice nada del abstract, solo que ese modelo falló el formato. **Respaldo:** si el principal no responde (límite diario, red) o su JSON no vale, y el secundario sí tiene una respuesta válida, decide la del secundario, con el motivo `respaldo_secundario` y la columna `Modelo_respuesta`. Esa pregunta se queda sin contraste entre modelos, y `confianza_final` aplica el factor `sin_segundo`. Si ninguno de los dos ha respondido, el caso queda `pendiente`, nunca `UNKNOWN`. Qué modelo es el principal y cuál el secundario se fija en el [ADR-005](adr-005-eleccion-modelo-coste-cero.md), a partir del benchmark.

**Porcentaje final (`confianza_final`).** La confianza declarada suele estar inflada, así que el porcentaje que se muestra junto al signo y al motivo se corrige con señales que no dependen de lo que el modelo diga de sí mismo (`codigo/fase2_inferencia/confianza.py`):

`confianza_final = confianza_modelo × factor_evidencia × factor_frase × factor_acuerdo`, entre 0 y 100.

* **Tipo de evidencia:** ganancia de función 1,0; pérdida de función 0,9; medida directa 0,85; contexto, correlación o ninguna 0,7.
* **Frase citada:** 0,9 si es el título o las frases S1-S2 (suelen ser introducción); 1,0 si es una frase posterior.
* **Otro modelo:** 1,0 si da el mismo signo; 0,8 si da `UNKNOWN`; 0,5 si da el signo opuesto; 0,9 si no hay respuesta suya.

Los factores son provisionales: salen de una prueba del 2026-11-09 con un prompt anterior (43 signos de tres modelos de API sobre 60 casos) como el cociente entre el acierto de cada grupo y el del mejor, acercados a 1 la mitad del camino porque las muestras son pequeñas. Se sustituirán por una regresión logística ajustada en el *gold set*. Solo los signos tienen `confianza_final`: un `UNKNOWN` se explica con su motivo. En una fila aceptada por `coincide_polaridad_GO` cuya confianza no llegaba al umbral, `confianza_final` se calcula sobre el veredicto aceptado y por eso sale baja. Ese porcentaje, multiplicado por un factor de contexto (especie y tipo celular), es el peso de cada respuesta en la agregación por par gen-ruta (spec de scoring).

La normalización de comparación nunca se aplica al texto que lee el LLM: este recibe el abstract limpio pero con la nomenclatura intacta, como exige la spec de limpieza.

**Ejemplo real** (benchmark, Gemini 3.5 Flash-Lite). Es la trampa de la Motivación: en el PMID 10652336 el efecto lo produce el ligando K12-Fc, no CD7. Respuesta validada de la pregunta (CD7, 10652336, proceso núcleo GO:0002369 *T cell cytokine production*), resumida:

```json
{
  "version": "veredicto", "gen": "CD7", "pmid": "10652336", "go_id": "GO:0002369",
  "veredicto": "NO_EFFECT", "signo_llm": "neutro", "confianza_modelo": 0,
  "limitacion": "process_not_addressed",
  "frases": [{"id_frase": "S1", "cita": "CD7 is a 40-kDa protein found primarily on T, NK, and pre-B cells", "verificada": true}],
  "signo": "UNKNOWN", "estado": "no_concluyente", "motivos": ["baja_confianza", "contexto_ajeno"]
}
```

Fila de la hoja `Por_ruta` para la ruta GO:0002443 (*leukocyte mediated immunity*), cuya `Polaridad_GO` es `+1`:

| Signo_ruta | Estado | Motivos | Veredicto_LLM | Confianza_modelo | Confianza_final | Polaridad_GO |
|---|---|---|---|---|---|---|
| `UNKNOWN` | `revisar` | `baja_confianza\|contexto_ajeno\|discrepancia_polaridad_GO` | `neutro` | 0 | (vacía: no hay signo) | `+1` |

El sistema no da el `+1` que un modelo complaciente habría dado. Como el veredicto (neutro) no coincide con GO, la fila queda en `revisar` para que el experto vea las dos fuentes.

## Motivación
1. **Un signo falso es peor que un `UNKNOWN`:** el signo entra en el *Net Pathway Score*; un error invierte la contribución del gen a la ruta, mientras que un `UNKNOWN` solo lo deja sin resolver.
2. **El LLM no sabe cuándo se equivoca:** pedirle que diga `UNKNOWN` si duda solo cubre los casos en que detecta su propia duda. Los errores peligrosos son los que comete con seguridad. Ejemplo real del dataset: en el PMID 10652336 el efecto sobre CD25/CD69 lo produce el ligando K12-Fc, no CD7; un modelo complaciente responde `+1` sin dudar. Por eso hacen falta comprobaciones externas al modelo.
3. **El corte lo decide el código, no el modelo:** el modelo siempre informa de lo que cree y de cuánto lo cree, y el código decide qué se acepta. El umbral se ajusta con el benchmark y se puede cambiar sin volver a llamar a los modelos; si el modelo pudiera abstenerse, el corte quedaría dentro del juicio de cada modelo.
4. **Los motivos hacen el sistema auditable:** un `UNKNOWN` sin motivo no indica si falla la recuperación, el modelo o la propia evidencia.
5. **Las discrepancias son información, no ruido:** la polaridad de GO es curada por expertos y el segundo modelo es independiente del primero. Convertir sus desacuerdos en `UNKNOWN` descartaría justo los casos que más interesa que revise el experto. Cuando discrepan los dos modelos, se conserva el signo del principal, se registran ambas respuestas y el caso queda marcado para que el experto lo resuelva con toda la información.
6. **La conclusión es del experto:** el sistema extrae y verifica evidencia; los casos `revisar` se entregan al profesional biomédico con las citas y los motivos.

**Validación:** sobre el *gold set* se miden la **precisión de las respuestas dadas** (cuando el sistema da `+1`, `-1` o `neutro`, cuántas acierta), la **cobertura** (porcentaje de casos en que el sistema no da `UNKNOWN`, incluidos los que quedan en `revisar`) y el **recall de `UNKNOWN`** (cuántos casos no concluyentes según el experto detecta el sistema), además de la calibración de `confianza_modelo` y `confianza_final` (spec del benchmark). Medición provisional del 2026-11-10 sobre el *gold set* (100 casos: 65 de genes *up* y 35 de genes *down*), con umbral 80:

| Modelo | Exactitud | Precisión de los signos | Cobertura | Recall de `UNKNOWN` |
|---|---|---|---|---|
| Gemini 3.5 Flash-Lite | 84 % | 72 % | 40 % | 85 % |
| gpt-oss-120b (Groq) | 85 % | 79 % | 34 % | 89 % |

Las etiquetas son de anotadores Claude a ciegas (el equipo decidió quedarse con ellas el 2026-11-11), así que el acierto medido puede estar inflado frente al de un experto humano.

Aceptamos los compromisos asociados: duplicar las llamadas (dos modelos) alarga la ejecución en los planes gratuitos; el filtro previo puede descartar abstracts que nombran el gen de forma no recogida en los alias (un error en la dirección segura, que se medirá en el benchmark); y la cobertura bajará frente a un sistema que siempre responde.

**Sin confianza mínima para `coincide_polaridad_GO`** (decidido por el equipo el 2026-11-11): si el veredicto coincide con GO y tiene una cita verificada, se acepta con cualquier confianza. En el benchmark, esta regla acepta 5 signos de Gemini por debajo del umbral y acierta 3 (los 2 errores tenían confianza 0 y 30 y la etiqueta era `UNKNOWN`); en gpt-oss acepta 3 y acierta 1.

**El umbral se aplica a `confianza_modelo`, no a `confianza_final`** (decidido por el equipo el 2026-11-11). `confianza_modelo` decide si hay signo (≥ `UMBRAL_VEREDICTO`, 80) y `confianza_final` solo pesa ese signo en la agregación (spec de scoring). Motivos:
* **Estabilidad:** `confianza_final` incluye el acuerdo con el otro modelo, y mientras el secundario no responde vale ×0,9 (`sin_segundo`). En la ejecución completa del 2026-11-11 gpt-oss solo había respondido 72 de 1.694 preguntas, así que un umbral sobre `confianza_final` cambiaría el resultado de cada caso a medida que avanza el contraste.
* **Recorte:** sobre los 563 signos de esa ejecución (todos con `confianza_modelo` entre 80 y 100, mediana 90), `confianza_final` ≥ 80 quitaría 380 (67 %) y ≥ 70, 164 (29 %).
* **Sin doble penalización:** el tipo de evidencia y la frase citada ya rebajan el peso del voto en el scoring; si decidieran también el umbral, contarían dos veces.
* **El benchmark no la favorece:** para Gemini, `confianza_final` separa algo mejor (AUROC de 0,76 frente a 0,72; ECE de 7 puntos frente a 15), pero para gpt-oss es al revés (AUROC de 0,66 frente a 0,74; ECE de 15 frente a 5). Con 40 y 34 signos ninguna diferencia es concluyente, y sus factores se fijaron con un prompt anterior.

## Alternativas
* **`UNKNOWN` simple, sin motivo:**
  * *Motivo de descarte:* no permite saber por qué falla el sistema ni priorizar mejoras.
* **Dejar que el modelo se abstenga (`NO_CLEAR_EFFECT` con un motivo):**
  * *Motivo de descarte:* el corte depende del juicio de cada modelo y no se puede ajustar sin cambiar el prompt y volver a llamar.
* **Usar la confianza declarada tal cual, sin umbral ajustado ni corrección:**
  * *Motivo de descarte:* la confianza verbalizada de los LLM está mal calibrada y tiende a ser excesiva (se concentra entre 80 y 100 aunque el modelo se equivoque). Por eso el umbral se fija con el benchmark y no en el prompt, y el porcentaje que se muestra es la `confianza_final`, cuya calibración se mide (fiabilidad, ECE, AUROC y curva riesgo-cobertura).
* **Aplicar el umbral a `confianza_final`:**
  * *Motivo de descarte:* depende de si el secundario ya ha respondido, recorta dos tercios de los signos con umbral 80 y penaliza dos veces el tipo de evidencia y la frase citada, que ya pesan en el scoring.
* **Marcar `revisar` cuando la cita no se verifica, en lugar de `UNKNOWN`:**
  * *Motivo de descarte:* una cita que no está en el abstract es justo la señal de alucinación que se quiere bloquear; el equipo decidió tratarla como falta de evidencia.
* **Convertir en `UNKNOWN` cualquier discrepancia (con GO o entre modelos):**
  * *Motivo de descarte:* se perderían los casos con evidencia en conflicto, que son los más valiosos para la revisión experta.
* **Signo `CONTRADICCION` sin preferencia por ningún modelo cuando los dos discrepan:**
  * *Motivo de descarte:* deja sin signo casos que sí tienen evidencia. El equipo prefirió conservar el signo del modelo principal, guardar las dos respuestas y marcar el caso como `revisar`, de modo que la discrepancia queda igualmente visible para el experto.
* **Comparar modelos solo en el benchmark:**
  * *Motivo de descarte:* el equipo prefirió el contraste en todos los casos; con dos planes gratuitos es viable a coste cero, a cambio de más días de ejecución.
* **Dar siempre `+1`/`-1` como resultado final (sin `UNKNOWN`):**
  * *Motivo de descarte:* obligaría a dar por bueno un signo cuando el abstract no lo sostiene. El prompt obliga al modelo a elegir, pero el resultado final puede ser `UNKNOWN`, porque lo decide el código.

## Referencias
* **Código del proyecto (estado actual):**
  * `codigo/fase2_inferencia/respuesta.py`: validación de la respuesta (`_validar`), verificación de la cita, `UNKNOWN` forzado, `json_invalido`, `baja_confianza` e `incoherencia_respuesta`.
  * `codigo/fase2_inferencia/esquema.py`: esquemas JSON estrictos (`ESQUEMA` / `ESQUEMA_LISTA`, `CAMPOS_CONTEXTO`), tabla de motivos y umbral (`UMBRAL_VEREDICTO`).
  * `codigo/fase2_inferencia/prompt.py`: reglas del prompt.
  * `codigo/fase2_inferencia/casos.py`: filtro previo `no_menciona_gen` (con `menciona_gen` de `fase1_ingesta/relevancia.py`).
  * `codigo/fase2_inferencia/limpieza.py`: `forma_comparacion()` y `segmentar_frases()`.
  * `codigo/fase2_inferencia/resultados.py`: contraste entre modelos y con `Polaridad_GO`, y salida `fase2_resultados.xlsx`.
  * `codigo/fase2_inferencia/confianza.py`: `confianza_final` y sus factores provisionales.
  * `codigo/evaluacion/evaluar_gold.py`: métricas y calibración sobre el *gold set*.
  * `codigo/fase1_ingesta/polaridad.py`: cierre `sin_evidencia` de los pares sin abstract.
* **Salidas estructuradas:**
  * Groq: [https://console.groq.com/docs/structured-outputs](https://console.groq.com/docs/structured-outputs)
  * Gemini API: [https://ai.google.dev/gemini-api/docs/structured-output](https://ai.google.dev/gemini-api/docs/structured-output)
* **Literatura:**
  * Xiong et al. (2024), *Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs*, ICLR 2024 (sobreconfianza de la confianza verbalizada).
  * Geifman & El-Yaniv (2017), *Selective Classification for Deep Neural Networks*, NeurIPS 2017 (compromiso entre cobertura y precisión al abstenerse).
* **Decisiones relacionadas:** [ADR-001](adr-001-rag-stateless.md) (arquitectura RAG), [ADR-004](adr-004-persistencia-ficheros-locales.md) (registro de respuestas) y [ADR-005](adr-005-eleccion-modelo-coste-cero.md) (elección de los modelos).
