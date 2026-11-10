# Spec: Gold Set Etiquetado por Expertos y Benchmark de Modelos

## Qué hay que construir
Un procedimiento de evaluación reproducible que permita elegir los modelos de producción ([ADR-005](../decisions/adr-005-eleccion-modelo-coste-cero.md)), medir la eficacia del control de alucinaciones ([ADR-003](../decisions/adr-003-control-alucinaciones-unknown.md)) y comparar las dos versiones del prompt de la [spec de inferencia](inferencia-llm.md). Consta de cuatro partes. El código está en `codigo/evaluacion/`.

1. **Selección del *gold set*.** La unidad de caso es la misma pregunta que responden los modelos: **(gen, PMID, proceso núcleo)**. La etiqueta es el efecto del gen sobre ese proceso según el abstract, y el signo sobre cada ruta lo compone el código igual que con los modelos.
   * **Selección inicial (gold v1 y v2, `seleccionar_gold.py`):** 60 casos de las rutas de genes *up* (lista «activadas» de CIMUS), con la semilla fija 20261109:
     * 21 con `Polaridad_GO` de signo conocido en alguna de sus rutas (11 «+1» y 10 «−1», tomando la primera ruta con signo), para poder medir el acuerdo con GO;
     * 39 sin ella;
     * como máximo 5 casos por gen, para que los genes más repetidos no dominen la muestra;
     * el caso de receptor frente a ligando (CD7 y K12, PMID 10652336) siempre dentro;
     * 12 casos (20 %) marcados para doble etiquetado.

     Quedan fuera los pares que no llegan al LLM (`aceptar_GO` y `sin_evidencia` en el triaje de la Fase 1, y los que el filtro previo cierra con `no_menciona_gen`) y el **conjunto de desarrollo**: las preguntas de la ruta GO:0002443 y del gen ICAM1, usadas para ajustar el prompt, salvo CD7/10652336. Con `--actualizar`, el script rehace la selección sobre una Fase 1 nueva sin volver a sortear: conserva los casos que siguen existiendo y solo sustituye los que han desaparecido.
   * **Gold v3 (2026-11-10, histórico; archivado en `codigo/evaluacion/v3/`):** **124 casos**, formados por los 60 del v2 más los candidatos a neutro de `buscar_neutros.py`: 51 de la primera ronda y 13 de la segunda (`--amplia`) que pasaron una criba previa. El script busca abstracts con una frase de negación («did not affect», «was dispensable»…) que nombra al gen, entre las preguntas que no están en el gold ni en el conjunto de desarrollo. El v2 no tenía ningún neutro, así que la clase no se podía medir. Composición del v3:
     * por `Polaridad_GO`: 18 con «+1», 7 con «−1» y 99 sin ella;
     * por etiqueta: 27 «+1», 13 «−1», 2 neutros y 82 `UNKNOWN`. Los abstracts casi nunca informan de que un gen no cambia un proceso: solo 2 de 174 candidatos lo hacían;
     * 50 genes, con un máximo de 7 casos por gen (CCR7 y CD83), así que el v3 ya no cumple el máximo de 5;
     * los 124 casos con doble etiquetado.

     El v3 se montó con `construir_gold_v3.py`, que hoy está fuera del repositorio (`research_notes/Gold v3 etiquetado/`). El detalle está en `etiquetas_provisionales/CAMBIOS_v3.md`.
   * **Gold v4, el vigente (2026-11-10):** **100 casos**, con genes *up* y *down*, porque la Fase 2 procesa las dos listas de CIMUS y el v3 solo tenía genes *up*. Se monta con `seleccionar_gold.py --v4`:
     * **65 casos *up* del v3, con sus etiquetas:**
       * los 60 de la muestra aleatoria del v2;
       * los 2 `NO_EFFECT` (G104 y G114);
       * 3 sorteados entre los demás añadidos del v3 (G77, G96 y G116).

       Salen 59 de los candidatos a neutro, que se habían elegido por contener una negación. CD7/10652336 (G11) sigue dentro.
     * **35 casos *down* nuevos (G128–G162):** sorteados entre las preguntas de la lista «suprimidas», con los estratos de `Polaridad_GO` de la muestra original en proporción (6 «+1», 6 «−1» y 23 sin ella) y como máximo 5 por gen (22 genes).
     * **Comprobación por código contra los Excels de CIMUS** (`codigo/tools_cimus/`), sin errores:
       * cada gen está en su lista y no en la otra;
       * todas las rutas de cada caso están enriquecidas con ese gen en su lista;
       * ningún gen aparece en las dos listas.
     * **Composición:**
       * por `Polaridad_GO`: 20 con «+1», 13 con «−1» y 67 sin ella;
       * por etiqueta: 20 «+1», 12 «−1», 3 neutros y 65 `UNKNOWN`. Los *up* son 9 / 5 / 2 / 49 y los *down*, 11 / 7 / 1 / 16;
       * 57 genes y los 100 casos con doble etiquetado.

     El detalle está en `etiquetas_provisionales/CAMBIOS_v4.md`.
   * **Pendiente:** `buscar_neutros.py` sigue buscando candidatos a neutro solo en las rutas de genes *up*.
2. **Etiquetado a ciegas** según la guía `codigo/evaluacion/guia_etiquetado.md`. Cada caso se etiqueta con:
   * `efecto`: `INCREASES` (+1), `DECREASES` (−1), `NO_EFFECT` (neutro: el abstract muestra que el gen no cambia el proceso) o `NO_CLEAR_EFFECT` (`UNKNOWN`);
   * `motivo`: si el efecto es `NO_CLEAR_EFFECT`, una de las limitaciones del prompt (`gene_not_discussed`, `gene_is_the_target`, `marker_or_correlation_only`, `effect_of_other_molecule`, `speculation_only`, `conflicting_results`, `process_not_addressed`); si no, `none`;
   * `id_frase` y `cita`: la frase que justifica la etiqueta y un fragmento literal de 6 palabras o más;
   * `confianza` (`alta`, `media` o `baja`), una `nota` opcional y el `anotador`.

   La plantilla (`plantilla_etiquetado.jsonl` y `.xlsx`) muestra solo el gen, sus otros nombres, el PMID, el **proceso núcleo**, el título `[T]` y las frases del abstract `[S1]…[Sn]`. **No muestra la salida de ningún modelo, la `Polaridad_GO` ni la dirección del gen en scRNA-seq**, para que la etiqueta no se ancle en ninguna de las fuentes que se van a evaluar. Los casos marcados con `doble_etiquetado` los etiqueta además una segunda persona, de forma independiente.

   **Estado actual: las etiquetas son provisionales.** Las pusieron anotadores Claude a ciegas, con ids anónimos y mezclados: dos anotadores independientes por caso (A y B) y un árbitro en los desacuerdos.
   * **Gold v3:** el acuerdo fue de 119 sobre 124, con kappa 0,92, y hubo 5 desacuerdos arbitrados.
   * **35 casos *down* del v4:**
     * los anotadores vieron los casos sin PMID ni `Polaridad_GO`;
     * A y B coincidieron en el efecto en 34 de 35 (kappa 0,96);
     * el árbitro resolvió los 2 desacuerdos y revisó los 5 casos con confianza baja y el único neutro, sin cambiar ninguna etiqueta.

   Como esos anotadores son modelos parecidos a los evaluados, su acierto está inflado: las etiquetas que valen son las del equipo clínico (a través de Luis Pérez, con CIMUS), que siguen pendientes.
3. **Ejecución del benchmark:** `evaluar_gold.py ejecutar` hace que cada candidato responda a todas las preguntas del *gold set* con la versión del prompt elegida y el mismo validador de la spec de inferencia. Las preguntas se envían por gen, troceadas con el presupuesto por llamada de cada modelo. Por eso la agrupación del mensaje puede variar entre modelos, aunque cada pregunta y su huella son idénticas. En producción sí es común, porque se usa el presupuesto más pequeño de la pareja. Candidatos evaluados:
   * **benchmarks v1 a v3** (60 casos, `v1_proceso_gen`): `groq-gpt-oss-120b`, `groq-qwen3.8-27b`, `gemini-3.5-flash-lite` y `ollama-qwen3-8b`;
   * **benchmark v4** (`v2_veredicto`): los mismos sin Ollama, más `claude-opus-5.5` como referencia. Claude no es un plan gratuito: sus respuestas son una lectura manual dentro de una sesión de trabajo, y no se pueden repetir a ciegas;
   * **benchmark v5** (gold v3, `v2_veredicto` con el prompt sin umbral): Gemini completo (124 de 124) y gpt-oss en 6 de 124, cortado por el límite diario de Groq;
   * **benchmark v6** (gold v4, `v2_veredicto`, 2026-11-10, `codigo/data/benchmark_v6/`): Gemini y gpt-oss completos, 100 de 100 cada uno.
     * **Gemini:** su registro parte de una copia del de Gemini del v5, así que las 65 preguntas *up* se reutilizaron y solo se llamó para los 35 *down* (22 llamadas, una por gen).
     * **gpt-oss:** se reutilizaron las 4 respuestas del v5 que siguen en el gold y se hicieron 60 llamadas, sin cortes por el límite diario (163 K tokens).

   Como el gold v4 tiene casos de las dos listas, `evaluar_gold.py` construye las preguntas a partir de las dos.

   `qwen3.8-27b` está descartado (ADR-005).
4. **Informe de resultados:** `evaluar_gold.py informe` vuelve a validar las respuestas crudas del registro, **sin llamar a ningún modelo**, y las compara con las etiquetas. La etiqueta `NO_EFFECT` cuenta como `neutro`, y también un `NO_CLEAR_EFFECT` con el motivo `no_effect_found` de las etiquetas v1 y v2. El resto de `NO_CLEAR_EFFECT` cuenta como `UNKNOWN`. Por cada modelo calcula:
   * **Exactitud:** porcentaje de casos en que la clase del sistema coincide con la etiqueta.
   * **Precisión de las respuestas dadas:** de los casos en que el sistema no da `UNKNOWN` (`+1`, `-1` o `neutro`), cuántos coinciden con la etiqueta.
   * **Cobertura:** porcentaje de casos en que el sistema no da `UNKNOWN`, incluidos los que quedan en `revisar`.
   * **Recall de `UNKNOWN`:** de los casos etiquetados como `UNKNOWN`, cuántos detecta el sistema.
   * **Matriz de confusión** 4×4 (`+1`, `-1`, `neutro`, `UNKNOWN`).
   * **JSON válido**, **citas verificadas** y **acuerdo con `Polaridad_GO`** en los casos que la tienen.
   * **Llamadas, latencia media por llamada, tiempo total y tokens** (entrada y salida).
   * **Calibración del porcentaje de seguridad**, sobre los veredictos que da cada modelo (acierto = misma clase que la etiqueta), por separado para `confianza_modelo` (la que declara el modelo) y `confianza_final` (corregida con el tipo de evidencia, la frase citada y el acuerdo con el otro modelo; ADR-003):
     * **tabla de fiabilidad** por tramos (0-49, 50-69, 70-89 y 90-100, los de las anclas de `v1_proceso_gen`; `v2_veredicto` no tiene anclas): número de signos, confianza media y acierto. Si está bien calibrada, las respuestas con un 80 % aciertan un 80 %;
     * **ECE** (error de calibración esperado): la diferencia media, ponderada por tramo, entre la confianza y el acierto;
     * **AUROC** de la confianza frente al acierto: la probabilidad de que un signo correcto tenga más confianza que uno erróneo (0,5 = no separa);
     * **curva riesgo-cobertura:** para cada umbral (0, 50, 60, 70, 80 y 90), cuántos signos quedan por encima y qué precisión tienen. De ella salió `UMBRAL_VEREDICTO = 80` de `v2_veredicto` (prueba de Gemini sobre el gold v3, 2026-11-10). El 70 es solo el umbral de `baja_confianza` de `v1_proceso_gen` (`UMBRAL_CONFIANZA_V1_GEN`).

     Para `confianza_final` se usa como otro modelo el de la pareja de producción: Gemini con gpt-oss y al revés; las alternativas se emparejan con Gemini. La calibración sigue siendo orientativa (56 veredictos de Gemini en el v5; 40 de Gemini y 34 de gpt-oss en el v6), y los factores de `confianza_final` se ajustaron con el benchmark v2, así que evaluarlos sobre esas mismas respuestas es optimista: hay que medirlos en respuestas nuevas.

   Cada métrica se acompaña de su **intervalo de confianza al 95 %** calculado por *bootstrap* (2.000 remuestreos, semilla fija), y se reporta el **acuerdo entre anotadores** (kappa de Cohen) sobre los casos dobles. En `v2_veredicto` el informe aplica la misma regla de GO que producción: un veredicto con cita verificada que coincide con la `Polaridad_GO` del caso se acepta aunque su confianza no llegue al umbral. La versión se toma de la clave guardada en el registro, y la `Polaridad_GO` es la de la primera ruta del caso con signo (`ruta_go` y `factor_ruta_go`), no la de cada ruta.

**Uso** (desde `codigo/`):

```
python evaluacion/evaluar_gold.py ejecutar <modelo> <excel de la Fase 1> [carpeta de datos] [presupuesto] [--dir=<nombre>] [--prompt=v2_veredicto]
python evaluacion/evaluar_gold.py informe <etiquetas.jsonl> [<etiquetas_doble.jsonl>] [--dir=<nombre>] [--comunes=N]
```

* `--dir=<nombre>`: carpeta de los registros dentro de `codigo/data/`; por defecto `benchmark`.
* `--prompt=v2_veredicto`: ejecuta la versión de producción en vez de `v1_proceso_gen`. Solo afecta a `ejecutar`.
* `--comunes=N`: calcula el informe sobre los N primeros casos que han respondido todos los modelos de la carpeta, para comparar sobre los mismos casos cuando alguna ejecución se ha cortado por el límite diario.
* `ejecutar` es reanudable: si se corta por el límite diario, volver a lanzarlo solo hace lo pendiente.
* Un modelo cuya carpeta no tiene `claves.json` (porque su ejecución no terminó ninguna vez) no aparece en el informe.

Con el informe se aplica la regla de selección del ADR-005 y el resultado se documenta actualizando ese ADR.

## Por qué
Elegir un modelo por rankings generales o por reputación no mide lo que importa en este proyecto: distinguir el efecto del gen del de otra molécula, no dar un signo cuando el abstract no es concluyente y citar literalmente. Solo un conjunto de casos reales etiquetados por un experto permite comparar los candidatos en la tarea concreta y justificar la elección ante CIMUS y ante el tribunal.

El etiquetado a ciegas es imprescindible: si el experto ve la respuesta de un modelo o la polaridad de GO, tiende a aceptarla, y el benchmark acaba midiendo el acuerdo con esa fuente en lugar de la calidad real. Los intervalos de confianza evitan sobreinterpretar diferencias pequeñas: con 60, 100 o 124 casos, una diferencia de varios puntos entre dos modelos puede no ser significativa. El acuerdo entre anotadores indica cuánto de difícil es la tarea incluso para personas, y sirve de techo razonable para lo que se puede exigir a un modelo.

## Restricciones
* **Depende de la Fase 1 completa:** el *gold set* se extrae de la salida de la Fase 1 sobre todas las rutas de CIMUS. La selección vigente usa la ejecución completa del 2026-11-09, con la limpieza de abstracts corregida.
* **El *gold set* se congela antes de evaluar:** una vez etiquetado, no se modifica en función de los resultados. Cada versión de las etiquetas se guarda con su huella SHA-256 (`gold_provisional_v4.sha256`: `59158a2d…`; la del v3 era `a782025b…`), y cada cambio de casos o etiquetas se registra con su motivo en `CAMBIOS_vN.md`.
* **Versionado:**
  * se versionan en el repositorio `gold_casos.jsonl` (la selección, que no se enseña a los anotadores), `plantilla_etiquetado.jsonl`, `guia_etiquetado.md`, las etiquetas en `etiquetas_provisionales/` (las vigentes son `gold_provisional_v4.jsonl`, `doble_v4.jsonl` y su `.sha256`; se conservan las de versiones anteriores), los informes `informe_gold_provisional_v*.txt`, el gold v3 archivado en `v3/` y los scripts;
  * no se versionan la plantilla en Excel (el `.gitignore` excluye los `.xlsx`) ni los registros del benchmark, que están en `codigo/data/benchmark*/` y `data/` está excluida.
* **Mismos casos y mismo abstract para todos:** cada candidato recibe exactamente las mismas preguntas, con el mismo abstract completo que verá en producción.
* **Coste cero:** todas las ejecuciones usan planes gratuitos o Ollama en local (ADR-005), y sus respuestas se guardan en el registro del [ADR-004](../decisions/adr-004-persistencia-ficheros-locales.md), con el nombre exacto de cada modelo. La única excepción es la referencia `claude-opus-5.5` del v4, que no es un candidato de producción.
* **Esfuerzo del experto:** etiquetar los 100 casos del v4, más el doble etiquetado que se acuerde, lleva unas horas de trabajo que hay que acordar con CIMUS con antelación.

## Criterios de aceptación
* [ ] **Selección reproducible:** `seleccionar_gold.py` con la misma semilla produce exactamente los mismos 60 casos iniciales, con los estratos 11/10/39, como máximo 5 por gen y 12 dobles (la semilla es fija, pero no se ha comprobado volviendo a ejecutarlo). El montaje del v3 depende de `construir_gold_v3.py`, que está fuera del repositorio. El v4 se monta desde el repositorio (`--v4`, semillas fijas), a partir del `gold_casos.jsonl` del v3 archivado.
* [x] ✅ **Plantilla a ciegas:** la plantilla contiene el gen, sus otros nombres, el PMID, el proceso núcleo, el título y las frases del abstract, y **no** contiene `Polaridad_GO`, la dirección de scRNA-seq ni ninguna salida de modelo.
* [x] ✅ ***Gold set* completo (provisional):** `gold_provisional_v4.jsonl` tiene, para los 100 casos, `id`, `efecto` válido de las 4 clases, `motivo`, `id_frase`, `cita`, `confianza`, `nota` y `anotador`.
* [x] ✅ **Acuerdo entre anotadores (provisional):** los 100 casos tienen las dos etiquetas registradas (`doble_v4.jsonl`) y el informe incluye su kappa de Cohen (0,98 entre la etiqueta final y la segunda; en los 35 *down*, A y B coinciden con kappa 0,96).
* [ ] **Etiquetas de CIMUS:** el equipo clínico etiqueta los casos a ciegas y el informe se regenera con sus etiquetas.
* [x] ✅ **Casos de las rutas de genes *down*** en el *gold set*: 35 de 100 en el v4, comprobados contra los Excels de CIMUS.
* [x] ✅ **Cobertura de la evaluación:** cada candidato tiene una respuesta registrada para el 100 % de los casos del gold v4 (Gemini y gpt-oss: 100 de 100 en el v6).
* [x] ✅ **Informe completo:** para cada modelo evaluado, el informe incluye todas las métricas de la parte 4 con su intervalo de confianza al 95 % y la matriz de confusión (`informe_gold_provisional_v6.txt`, Gemini y gpt-oss).
* [x] ✅ **Calibración en el informe:** `evaluar_gold.py informe` añade, por modelo, la tabla de fiabilidad, el ECE, el AUROC y la curva riesgo-cobertura de `confianza_modelo` y `confianza_final`, a partir del registro y sin llamar a los modelos.
* [x] ✅ **Reproducibilidad del informe:** regenerar el informe v5 a partir del registro, sin ninguna llamada nueva, da un texto idéntico a `informe_gold_provisional_v5.txt` (comprobado el 2026-11-10, antes de pasar al gold v4). `evaluar_gold.py` lee siempre `evaluacion/gold_casos.jsonl`, que ahora es el del v4, así que para regenerar el v5 hay que poner antes en su sitio el `gold_casos.jsonl` archivado en `v3/`.
* [ ] **Decisión documentada:** el ADR-005 recoge el modelo principal (Gemini 3.5 Flash-Lite, decidido el 2026-11-10); el secundario (gpt-oss-120b) ya está medido en el benchmark v6 y falta que el equipo lo confirme.
