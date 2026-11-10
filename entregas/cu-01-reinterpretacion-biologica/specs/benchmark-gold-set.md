# Spec: Gold Set Etiquetado por Expertos y Benchmark de Modelos

## Qué hay que construir
Un procedimiento de evaluación reproducible que permita elegir los modelos de producción ([ADR-005](../decisions/adr-005-eleccion-modelo-coste-cero.md)), y medir la eficacia del control de alucinaciones ([ADR-003](../decisions/adr-003-control-alucinaciones-unknown.md)) con el prompt de la [spec de inferencia](inferencia-llm.md). Consta de cuatro partes. El código está en `codigo/evaluacion/`.

1. **Selección del *gold set*.** La unidad de caso es la misma pregunta que responden los modelos: **(gen, PMID, proceso núcleo)**. La etiqueta es el efecto del gen sobre ese proceso según el abstract, y el signo sobre cada ruta lo compone el código igual que con los modelos.
   * **Composición (2026-11-10): 100 casos de las dos listas de CIMUS**, porque la Fase 2 procesa las dos:
     * **65 de genes *up*** (lista «activadas»):
       * una muestra aleatoria estratificada de 60 casos (semilla fija 20261109): 11 con `Polaridad_GO` «+1», 10 con «−1» y 39 sin ella, tomando la primera ruta del caso con signo, como máximo 5 por gen y con el caso de receptor frente a ligando (CD7 y K12, PMID 10652336, G11) siempre dentro;
       * los 2 casos `NO_EFFECT` que dio `buscar_neutros.py` (G104 y G114), porque al azar casi no salen neutros: los abstracts casi nunca informan de que un gen no cambia un proceso;
       * 3 casos sorteados entre los demás candidatos de esa búsqueda (G77, G96 y G116).
     * **35 de genes *down*** (lista «suprimidas», G128–G162): sorteados con los estratos de `Polaridad_GO` de la muestra en proporción (6 «+1», 6 «−1» y 23 sin ella) y como máximo 5 por gen (22 genes).
     * **Quedan fuera** los pares que no llegan al LLM (`aceptar_GO` y `sin_evidencia` en el triaje de la Fase 1, y los que el filtro previo cierra con `no_menciona_gen`) y el **conjunto de desarrollo**: las preguntas de la ruta GO:0002443 y del gen ICAM1, usadas para ajustar el prompt, salvo CD7/10652336.
     * **Comprobación por código contra los Excels de CIMUS** (`codigo/tools_cimus/`), sin errores:
       * cada gen está en su lista y no en la otra;
       * todas las rutas de cada caso están enriquecidas con ese gen en su lista;
       * ningún gen aparece en las dos listas.
     * **Resultado:**
       * por `Polaridad_GO`: 20 con «+1», 13 con «−1» y 67 sin ella;
       * por etiqueta: 20 «+1», 12 «−1», 3 neutros y 65 `UNKNOWN`. Los *up* son 9 / 5 / 2 / 49 y los *down*, 11 / 7 / 1 / 16;
       * 57 genes y los 100 casos con doble etiquetado.

     El detalle está en `etiquetas_provisionales/LEEME.md`.
   * **Mantenimiento** (`seleccionar_gold.py`): rehace el *gold set* sobre una Fase 1 nueva **sin volver a sortear**. Conserva los casos que siguen existiendo, con su id y su etiqueta, y sustituye cada uno que desaparece por otro de la misma lista de CIMUS y del mismo estrato de GO (semilla fija), con id nuevo. Después regenera la plantilla.
   * **Candidatos a neutro** (`buscar_neutros.py`): busca, en las dos listas y fuera del *gold set* y del conjunto de desarrollo, abstracts con una frase de negación («did not affect», «was dispensable», «no role», «unchanged»…) que nombra al gen. Son solo candidatos: entran en el *gold set* los que los anotadores etiquetan a ciegas como `NO_EFFECT`.
2. **Etiquetado a ciegas** según la guía `codigo/evaluacion/guia_etiquetado.md`. Cada caso se etiqueta con:
   * `efecto`: `INCREASES` (+1), `DECREASES` (−1), `NO_EFFECT` (neutro: el abstract muestra que el gen no cambia el proceso) o `NO_CLEAR_EFFECT` (`UNKNOWN`);
   * `motivo`: si el efecto es `NO_CLEAR_EFFECT`, una de las limitaciones del prompt (`gene_not_discussed`, `gene_is_the_target`, `marker_or_correlation_only`, `effect_of_other_molecule`, `speculation_only`, `conflicting_results`, `process_not_addressed`); si no, `none`;
   * `id_frase` y `cita`: la frase que justifica la etiqueta y un fragmento literal de 6 palabras o más;
   * `confianza` (`alta`, `media` o `baja`), una `nota` opcional y el `anotador`.

   La plantilla (`plantilla_etiquetado.jsonl` y `.xlsx`) muestra solo el gen, sus otros nombres, el PMID, el **proceso núcleo**, el título `[T]` y las frases del abstract `[S1]…[Sn]`. **No muestra la salida de ningún modelo, la `Polaridad_GO` ni la dirección del gen en scRNA-seq**, para que la etiqueta no se ancle en ninguna de las fuentes que se van a evaluar. Los casos marcados con `doble_etiquetado` los etiqueta además una segunda persona, de forma independiente.

   **Estado actual: las etiquetas son provisionales.** Las pusieron anotadores Claude a ciegas, con ids anónimos y mezclados: dos anotadores independientes por caso (A y B) y un árbitro en los desacuerdos.
   * **Acuerdo:** la etiqueta final y la segunda coinciden en 99 de 100 casos (kappa 0,98).
   * **35 casos *down*:**
     * los anotadores vieron los casos sin PMID ni `Polaridad_GO`;
     * A y B coincidieron en el efecto en 34 de 35 (kappa 0,96);
     * el árbitro resolvió los 2 desacuerdos y revisó los 5 casos con confianza baja y el único neutro, sin cambiar ninguna etiqueta.

   Como esos anotadores son modelos parecidos a los evaluados, su acierto está inflado: las etiquetas que valen son las del equipo clínico (a través de Luis Pérez, con CIMUS), que siguen pendientes.
3. **Ejecución del benchmark:** `evaluar_gold.py ejecutar` hace que cada candidato responda a todas las preguntas del *gold set* con el prompt y el validador de producción (spec de inferencia). Las preguntas se envían por gen, troceadas con el presupuesto por llamada de cada modelo. Por eso la agrupación del mensaje puede variar entre modelos, aunque cada pregunta y su huella son idénticas. En producción sí es común, porque se usa el presupuesto más pequeño de la pareja. Las preguntas se construyen a partir de las dos listas de CIMUS.

   Candidatos evaluados (2026-11-10, registro en `codigo/data/benchmark/`): `gemini-3.5-flash-lite` y `groq-gpt-oss-120b`, con 100 de 100 respuestas cada uno. Las preguntas que ya estaban registradas con el mismo prompt se reutilizaron: Gemini solo llamó para los 35 casos *down* (22 llamadas, una por gen), y gpt-oss hizo 60 llamadas sin cortes por el límite diario (163 K tokens). `qwen3.8-27b` está descartado (ADR-005).
4. **Informe de resultados:** `evaluar_gold.py informe` vuelve a validar las respuestas crudas del registro, **sin llamar a ningún modelo**, y las compara con las etiquetas. La etiqueta `NO_EFFECT` cuenta como `neutro` y `NO_CLEAR_EFFECT`, como `UNKNOWN`. Por cada modelo calcula:
   * **Exactitud:** porcentaje de casos en que la clase del sistema coincide con la etiqueta.
   * **Precisión de las respuestas dadas:** de los casos en que el sistema no da `UNKNOWN` (`+1`, `-1` o `neutro`), cuántos coinciden con la etiqueta.
   * **Cobertura:** porcentaje de casos en que el sistema no da `UNKNOWN`, incluidos los que quedan en `revisar`.
   * **Recall de `UNKNOWN`:** de los casos etiquetados como `UNKNOWN`, cuántos detecta el sistema.
   * **Matriz de confusión** 4×4 (`+1`, `-1`, `neutro`, `UNKNOWN`).
   * **JSON válido**, **citas verificadas** y **acuerdo con `Polaridad_GO`** en los casos que la tienen.
   * **Llamadas, latencia media por llamada, tiempo total y tokens** (entrada y salida).
   * **Calibración del porcentaje de seguridad**, sobre los veredictos que da cada modelo (acierto = misma clase que la etiqueta), por separado para `confianza_modelo` (la que declara el modelo) y `confianza_final` (corregida con el tipo de evidencia, la frase citada y el acuerdo con el otro modelo; ADR-003):
     * **tabla de fiabilidad** por tramos (0-49, 50-69, 70-89 y 90-100): número de signos, confianza media y acierto. Si está bien calibrada, las respuestas con un 80 % aciertan un 80 %;
     * **ECE** (error de calibración esperado): la diferencia media, ponderada por tramo, entre la confianza y el acierto;
     * **AUROC** de la confianza frente al acierto: la probabilidad de que un signo correcto tenga más confianza que uno erróneo (0,5 = no separa);
     * **curva riesgo-cobertura:** para cada umbral (0, 50, 60, 70, 80 y 90), cuántos signos quedan por encima y qué precisión tienen. De ella salió `UMBRAL_VEREDICTO = 80` (2026-11-10).

     Para `confianza_final` se usa como otro modelo el de la pareja de producción: Gemini con gpt-oss y al revés. La calibración es orientativa (40 signos de Gemini y 34 de gpt-oss). Los factores de `confianza_final` se fijaron en una prueba anterior, con otro prompt (ADR-003), así que este benchmark los mide en respuestas que no se usaron para fijarlos.

   Cada métrica se acompaña de su **intervalo de confianza al 95 %** calculado por *bootstrap* (2.000 remuestreos, semilla fija), y se reporta el **acuerdo entre anotadores** (kappa de Cohen) sobre los casos dobles. El informe aplica la misma regla de GO que producción: un veredicto con cita verificada que coincide con la `Polaridad_GO` del caso se acepta aunque su confianza no llegue al umbral. La `Polaridad_GO` es la de la primera ruta del caso con signo (`ruta_go` y `factor_ruta_go`), no la de cada ruta.

**Uso** (desde `codigo/`):

```
python evaluacion/evaluar_gold.py ejecutar <modelo> <excel de la Fase 1> [carpeta de datos] [presupuesto] [--dir=<nombre>]
python evaluacion/evaluar_gold.py informe evaluacion/etiquetas_provisionales/gold_provisional.jsonl evaluacion/etiquetas_provisionales/doble.jsonl [--dir=<nombre>] [--comunes=N]
python evaluacion/seleccionar_gold.py <excel de la Fase 1> [carpeta de datos]
python evaluacion/buscar_neutros.py <excel de la Fase 1> <carpeta de datos>
```

* `--dir=<nombre>`: carpeta de los registros dentro de `codigo/data/`; por defecto `benchmark`.
* `--comunes=N`: calcula el informe sobre los N primeros casos que han respondido todos los modelos de la carpeta, para comparar sobre los mismos casos cuando alguna ejecución se ha cortado por el límite diario.
* `ejecutar` es reanudable: si se corta por el límite diario, volver a lanzarlo solo hace lo pendiente.
* Un modelo cuya carpeta no tiene `claves.json` (porque su ejecución no terminó ninguna vez) no aparece en el informe.

Con el informe se aplica la regla de selección del ADR-005 y el resultado se documenta actualizando ese ADR.

## Por qué
Elegir un modelo por rankings generales o por reputación no mide lo que importa en este proyecto: distinguir el efecto del gen del de otra molécula, no dar un signo cuando el abstract no es concluyente y citar literalmente. Solo un conjunto de casos reales etiquetados por un experto permite comparar los candidatos en la tarea concreta y justificar la elección ante CIMUS y ante el tribunal.

El etiquetado a ciegas es imprescindible: si el experto ve la respuesta de un modelo o la polaridad de GO, tiende a aceptarla, y el benchmark acaba midiendo el acuerdo con esa fuente en lugar de la calidad real. Los intervalos de confianza evitan sobreinterpretar diferencias pequeñas: con 100 casos, una diferencia de varios puntos entre dos modelos puede no ser significativa. El acuerdo entre anotadores indica cuánto de difícil es la tarea incluso para personas, y sirve de techo razonable para lo que se puede exigir a un modelo.

## Restricciones
* **Depende de la Fase 1 completa:** el *gold set* se extrae de la salida de la Fase 1 sobre todas las rutas de CIMUS. El *gold set* usa la ejecución completa del 2026-11-09, con la limpieza de abstracts corregida.
* **El *gold set* se congela antes de evaluar:** una vez etiquetado, no se modifica en función de los resultados. Las etiquetas se guardan con su huella SHA-256 (`gold_provisional.sha256`: `59158a2d…`), y cualquier cambio de casos o etiquetas se registra con su motivo en `etiquetas_provisionales/LEEME.md`.
* **Versionado:**
  * se versionan en el repositorio `gold_casos.jsonl` (la selección, que no se enseña a los anotadores), `plantilla_etiquetado.jsonl`, `guia_etiquetado.md`, las etiquetas en `etiquetas_provisionales/` (`gold_provisional.jsonl`, `doble.jsonl`, `gold_provisional.sha256` y `LEEME.md`), el informe `informe_gold_provisional.txt` y los scripts;
  * no se versionan la plantilla en Excel (el `.gitignore` excluye los `.xlsx`) ni los registros del benchmark, que están en `codigo/data/benchmark/` y `data/` está excluida.
* **Mismos casos y mismo abstract para todos:** cada candidato recibe exactamente las mismas preguntas, con el mismo abstract completo que verá en producción.
* **Coste cero:** todas las ejecuciones usan planes gratuitos o Ollama en local (ADR-005), y sus respuestas se guardan en el registro del [ADR-004](../decisions/adr-004-persistencia-ficheros-locales.md), con el nombre exacto de cada modelo.
* **Esfuerzo del experto:** etiquetar los 100 casos, más el doble etiquetado que se acuerde, lleva unas horas de trabajo que hay que acordar con CIMUS con antelación.

## Criterios de aceptación
* [x] ✅ **Mantenimiento reproducible:** `seleccionar_gold.py` sobre la Fase 1 del 2026-11-09 rehace el *gold set* idéntico: no desaparece ningún caso y `gold_casos.jsonl` y `plantilla_etiquetado.jsonl` no cambian (comprobado el 2026-11-10). El sorteo con el que se montó ya no está en el código; queda en el historial de git.
* [x] ✅ **Plantilla a ciegas:** la plantilla contiene el gen, sus otros nombres, el PMID, el proceso núcleo, el título y las frases del abstract, y **no** contiene `Polaridad_GO`, la dirección de scRNA-seq ni ninguna salida de modelo.
* [x] ✅ ***Gold set* completo (provisional):** `gold_provisional.jsonl` tiene, para los 100 casos, `id`, `efecto` válido de las 4 clases, `motivo`, `id_frase`, `cita`, `confianza`, `nota` y `anotador`.
* [x] ✅ **Acuerdo entre anotadores (provisional):** los 100 casos tienen las dos etiquetas registradas (`doble.jsonl`) y el informe incluye su kappa de Cohen (0,98 entre la etiqueta final y la segunda; en los 35 *down*, A y B coinciden con kappa 0,96).
* [ ] **Etiquetas de CIMUS:** el equipo clínico etiqueta los casos a ciegas y el informe se regenera con sus etiquetas.
* [x] ✅ **Casos de las rutas de genes *down*** en el *gold set*: 35 de 100, comprobados contra los Excels de CIMUS.
* [x] ✅ **Cobertura de la evaluación:** cada candidato tiene una respuesta registrada para el 100 % de los casos (Gemini y gpt-oss: 100 de 100).
* [x] ✅ **Informe completo:** para cada modelo evaluado, el informe incluye todas las métricas de la parte 4 con su intervalo de confianza al 95 % y la matriz de confusión (`informe_gold_provisional.txt`, Gemini y gpt-oss).
* [x] ✅ **Calibración en el informe:** `evaluar_gold.py informe` añade, por modelo, la tabla de fiabilidad, el ECE, el AUROC y la curva riesgo-cobertura de `confianza_modelo` y `confianza_final`, a partir del registro y sin llamar a los modelos.
* [x] ✅ **Reproducibilidad del informe:** regenerar el informe a partir del registro, sin ninguna llamada nueva, da un texto idéntico a `informe_gold_provisional.txt` (comprobado el 2026-11-10).
* [ ] **Decisión documentada:** el ADR-005 recoge el modelo principal (Gemini 3.5 Flash-Lite, decidido el 2026-11-10); el secundario (gpt-oss-120b) ya está medido en el benchmark y falta que el equipo lo confirme.
