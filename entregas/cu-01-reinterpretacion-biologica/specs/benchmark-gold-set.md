# Spec: Gold Set Etiquetado por Expertos y Benchmark de Modelos

## Qué hay que construir
Un procedimiento de evaluación reproducible que permita elegir los modelos de producción ([ADR-005](../decisions/adr-005-eleccion-modelo-coste-cero.md)), medir la eficacia del control de alucinaciones ([ADR-003](../decisions/adr-003-control-alucinaciones-unknown.md)) y decidir la definición de caso pendiente en la [spec de inferencia](inferencia-llm.md). Consta de cuatro partes:

1. **Selección del *gold set*:** un script que extrae **60 casos** de la hoja `Con_abstract` generada por la Fase 1 sobre **las 314 rutas activadas**, con una semilla aleatoria fija y estratificados así:
   * **21 casos (35 %)** con `Polaridad_GO` de signo conocido (`+1` y `-1` equilibrados), para poder medir el acuerdo con GO.
   * **39 casos (65 %)** sin polaridad de GO (vacía o `conflicto`), que es la situación del 77 % de las filas.
   * Como máximo 5 casos por gen, para que los genes más repetidos (p. ej. LGALS9, presente en 158 rutas) no dominen la muestra.
   * Se incluyen deliberadamente casos difíciles conocidos, como el de receptor frente a ligando (CD7 y K12, PMID 10652336).
2. **Etiquetado a ciegas:** el equipo clínico (a través de Luis Pérez, con CIMUS) etiqueta cada caso con:
   * `etiqueta`: `+1`, `-1` o `UNKNOWN`.
   * `motivo`: uno de los motivos del ADR-003 si la etiqueta es `UNKNOWN`.
   * `cita`: la frase del abstract que justifica la etiqueta (vacía si es `UNKNOWN`).

   La plantilla de etiquetado muestra solo el gen, la ruta (o el término, según la opción evaluada), el título y el abstract. **No muestra la salida de ningún modelo ni la `Polaridad_GO`**, para que la etiqueta no se ancle en ninguna de las dos fuentes que se van a evaluar. Un subconjunto de **12 casos (20 %)** lo etiqueta además una segunda persona del equipo, de forma independiente, para medir el acuerdo entre anotadores.
3. **Ejecución del benchmark:** los tres candidatos del ADR-005 (modelo abierto en Groq, Gemini Flash y modelo pequeño en Ollama) evalúan todos los casos del *gold set* con el mismo prompt y el mismo proceso de validación de la spec de inferencia. Si la composición del signo de la opción B está definida, se evalúan las dos formulaciones (A y B) sobre los mismos casos.
4. **Informe de resultados:** por cada modelo y formulación se calculan:
   * **Precisión de las respuestas dadas:** de los casos en que el sistema da `+1` o `-1`, cuántos coinciden con la etiqueta del experto.
   * **Cobertura:** porcentaje de casos con estado `resuelto`.
   * **Recall de `UNKNOWN`:** de los casos que el experto etiquetó como `UNKNOWN`, cuántos detecta el sistema.
   * **Matriz de confusión** 3×3 (`+1`, `-1`, `UNKNOWN`).
   * **Porcentaje de JSON válido** y **porcentaje de citas verificadas**.
   * **Acuerdo con `Polaridad_GO`** en los casos que la tienen.
   * **Latencia media por llamada** y número de casos por día que permiten los límites del plan gratuito.

   Cada métrica se acompaña de su **intervalo de confianza al 95 %** calculado por *bootstrap*, y se reporta el **acuerdo entre anotadores** (kappa de Cohen) sobre el subconjunto doble.

Con el informe se aplica la regla de selección del ADR-005 (modelo principal, modelo secundario y, en su caso, opción A o B), y el resultado se documenta actualizando ese ADR.

## Por qué
Elegir un modelo por rankings generales o por reputación no mide lo que importa en este proyecto: distinguir el efecto del gen del de otra molécula, abstenerse cuando el abstract no es concluyente y citar literalmente. Solo un conjunto de casos reales etiquetados por un experto permite comparar los candidatos en la tarea concreta y justificar la elección ante CIMUS y ante el tribunal.

El etiquetado a ciegas es imprescindible: si el experto ve la respuesta de un modelo o la polaridad de GO, tiende a aceptarla, y el benchmark acaba midiendo el acuerdo con esa fuente en lugar de la calidad real. Los intervalos de confianza evitan sobreinterpretar diferencias pequeñas: con 60 casos, una diferencia de varios puntos entre dos modelos puede no ser significativa. El acuerdo entre anotadores indica cuánto de difícil es la tarea incluso para personas, y sirve de techo razonable para lo que se puede exigir a un modelo.

## Restricciones
* **Depende de la Fase 1 completa:** el *gold set* se extrae de la ejecución de la Fase 1 sobre las 314 rutas activadas. Hasta ahora solo se ha ejecutado sobre una ruta de prueba, que no es representativa (en ella todas las filas tenían polaridad de GO).
* **El *gold set* se congela antes de ejecutar ningún modelo:** una vez etiquetado, no se modifica en función de los resultados. Si hay que corregir una etiqueta, se registra el cambio y su motivo.
* **Versionado:** el *gold set* y su script de selección se guardan en el repositorio en un formato de texto (p. ej. `codigo/evaluacion/gold_set.jsonl`). El `.gitignore` actual excluye los ficheros `.csv` y `.xlsx`, por lo que la plantilla de etiquetado en Excel no se versiona; solo su resultado en JSONL.
* **Mismos casos y mismo abstract para todos:** cada candidato recibe exactamente los mismos casos, con el mismo abstract completo que verá en producción.
* **Coste cero:** todas las ejecuciones usan planes gratuitos o Ollama en local (ADR-005), y sus respuestas se guardan en el registro del [ADR-004](../decisions/adr-004-persistencia-ficheros-locales.md), con el nombre y la versión exacta de cada modelo.
* **Esfuerzo del experto acotado:** 72 etiquetados en total (60 más 12 dobles), del orden de unas pocas horas de trabajo, que hay que acordar con CIMUS con antelación.

## Criterios de aceptación
* [ ] **Selección reproducible:** ejecutar dos veces el script de selección con la misma semilla produce exactamente los mismos casos. La muestra tiene 60 casos y cumple los estratos (21 con polaridad de GO conocida y equilibrada, 39 sin ella) y ningún gen aparece más de 5 veces.
* [ ] **Plantilla a ciegas:** la plantilla de etiquetado contiene el gen, la ruta o término, el título y el abstract, y **no** contiene `Polaridad_GO`, la dirección de scRNA-seq ni ninguna salida de modelo.
* [ ] ***Gold set* completo:** el fichero final tiene, para cada caso, un identificador, `gen`, `pmid`, la ruta o término, `etiqueta`, `motivo`, `cita` y `anotador`; el 100 % de los casos tiene etiqueta válida (`+1`, `-1` o `UNKNOWN`).
* [ ] **Acuerdo entre anotadores:** los 12 casos con doble etiquetado tienen las dos etiquetas registradas y el informe incluye su kappa de Cohen.
* [ ] **Cobertura de la evaluación:** cada candidato tiene una respuesta registrada para el 100 % de los casos del *gold set* (los casos pendientes por límites de uso se reintentan hasta completarse).
* [ ] **Informe completo:** para cada modelo y formulación evaluada, el informe incluye todas las métricas de la parte 4 con su intervalo de confianza al 95 % y la matriz de confusión.
* [ ] **Reproducibilidad del informe:** regenerar el informe a partir del registro de respuestas, sin ninguna llamada nueva a los modelos, produce exactamente las mismas cifras.
* [ ] **Decisión documentada:** el ADR-005 se actualiza con los modelos principal y secundario elegidos, la formulación elegida (A o B) y las cifras del informe que justifican la elección.
