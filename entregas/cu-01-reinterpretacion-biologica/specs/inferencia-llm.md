# Spec: Inferencia del Signo Funcional con LLM y Validación de la Respuesta

## Qué hay que construir
Un módulo de inferencia (Fase 2, `codigo/consulta_gen/`) que, a partir de la hoja `Con_abstract` del Excel de la Fase 1, determine para cada caso si el gen **activa** (`+1`) o **inhibe** (`-1`) la ruta según el abstract, si el abstract muestra que **no la cambia** (`neutro`) o si la evidencia no lo permite (`UNKNOWN`), y produzca una salida validada y trazable.

Hay **dos versiones del prompt**, que se comparan en el benchmark ([ADR-005](../decisions/adr-005-eleccion-modelo-coste-cero.md), [spec del benchmark](benchmark-gold-set.md)) sobre el mismo *gold set*. Las dos usan la misma unidad de pregunta, (gen, PMID, proceso núcleo), y se envían igual: todas las preguntas de un gen en una sola llamada, con salida en lista y troceadas según el límite por llamada de los modelos.

| Versión | Qué devuelve el modelo | Quién decide el `UNKNOWN` | Uso |
|---|---|---|---|
| `v2_veredicto` | **Siempre** un veredicto (`INCREASES` / `DECREASES` / `NO_EFFECT`), su confianza (0-100), de 1 a 3 frases con su cita y, si la hay, la limitación del abstract | El código, con la cita, la confianza (`UMBRAL_VEREDICTO`) y `Polaridad_GO` (ADR-003) | **Producción** (`ejecutar_fase2`) y benchmark |
| `v1_proceso_gen` | Un efecto (`INCREASES` / `DECREASES` / `NO_CLEAR_EFFECT` con un motivo), una cita y su confianza con anclas numéricas | El modelo, al abstenerse con `NO_CLEAR_EFFECT` | Benchmark (`--prompt=v1_proceso_gen`) |

> **Histórico.** Hasta el 2026-11-10 existieron otras dos versiones, eliminadas del código ese día: `v0_original` (el prompt de partida: una pregunta por fila gen–ruta–PMID, en español, con la dirección de scRNA-seq y el abstract recortado a 1.800 caracteres; solo era la línea base del benchmark) y `v1_proceso` (la pregunta de `v1_proceso_gen`, pero una llamada por pregunta). Ningún registro guardado usaba esas versiones. Siguen en el historial de git.

El flujo es:

1. **Construcción de casos** (`casos.py`). Para cada fila de `Con_abstract` con abstract, el **término estrecho** es su `GO_ID_anotado` (filas del GAF; uno por término si hay varios) o su `Termino_coincidente` resuelto a GO ID (filas de GeneRIF y Europe PMC). Se pregunta por su **núcleo**: «negative regulation of T cell proliferation» → «T cell proliferation». Cada ruta cubierta guarda el factor que traduce el efecto en signo (ver *Composición del signo*). Si ningún término compone con la ruta, se pregunta por el núcleo de la propia ruta (**respaldo A**). Las filas que comparten (gen, PMID, núcleo) son una única pregunta (`CasoProceso`). Se procesan las filas de los **dos Excels de CIMUS**: las rutas enriquecidas con genes *up*regulados («rutas activadas») y con genes *down*regulados («rutas suprimidas»); la columna `Estado_Original` indica de cuál viene cada fila. Con la Fase 1 del 2026-11-09 salen **1.694 preguntas** al LLM (1.123 de genes *up* y 571 de genes *down*; 174 genes).
2. **Filtro previo:** si ni el gen, ni sus alias (MyGene), ni su nombre completo aparecen en el título y el abstract como palabra completa (spec de limpieza), la pregunta se cierra con el motivo `no_menciona_gen` **sin llamar al LLM** (134 con la Fase 1 del 2026-11-09).
3. **Construcción del prompt**, idéntico para todos los modelos dentro de cada versión (`prompt.py`). Mensaje de sistema fijo, que va primero para que los proveedores puedan servirlo de su caché, con 14 reglas:
   * **Comunes a las dos versiones:** el gen debe ser la causa y no la diana; la pérdida de función invierte el signo; la ganancia de función lo conserva; marcador o correlación no es causalidad; efecto de otra molécula; negación; especulación; conflicto; alcance del proceso (una forma más específica cuenta, una más amplia no); el contexto (especie, célula) es un dato y no un motivo para abstenerse; se prefieren los resultados frente a la introducción; varias preguntas por mensaje (regla 14: cada respuesta se refiere solo al abstract y al proceso de su pregunta).
   * **`v2_veredicto`:** la regla 1 obliga a dar siempre un veredicto. Las trampas de dirección (gen diana, marcador, otra molécula, especulación, conflicto, alcance) no son una abstención, sino una **limitación** que el modelo declara (`gene_is_the_target`, `marker_or_correlation_only`, `effect_of_other_molecule`, `speculation_only`, `conflicting_results`, `process_not_addressed`, `gene_not_discussed` o `none`). La negación en un experimento es `NO_EFFECT`. La **confianza** (regla 12) es la probabilidad de que el veredicto sea correcto juzgando solo el abstract, con una guía cualitativa de más a menos apoyo (experimento con resultado explícito sobre el proceso; experimento sobre una forma más específica, otra especie o célula, o con un paso de inferencia; apoyo indirecto; sin apoyo) y **sin ninguna cifra de corte**: el prompt no conoce el umbral (decisión del 2026-11-10), porque decírselo predispondría la confianza. De 1 a 3 frases que motivan el veredicto (regla 13).
   * **`v1_proceso_gen`:** las trampas dan `NO_CLEAR_EFFECT` con un motivo (los siete anteriores más `no_effect_found` para la negación); una sola frase con su cita (regla 12); y la confianza (regla 13) con **anclas numéricas**: 90-100 experimento con resultado explícito sobre el mismo proceso; 70-89 experimento claro sobre una forma más específica, otra especie o célula, o con un paso de inferencia; 50-69 apoyo indirecto; por debajo de 50 no basta para un signo y la respuesta debe ser `NO_CLEAR_EFFECT`.
   * Tras las reglas, un bloque `OUTPUT` enumera los campos del JSON en orden con sus valores permitidos. Se genera a partir del esquema (`_campos`), de modo que no puede desincronizarse (los modelos sin salida estructurada estricta se inventaban los nombres de los campos).
   * **Mensaje de usuario** (`construir_prompt_lista`): los abstracts del gen sin repetir PMID, cada uno con su cabecera `ABSTRACT (PMID …)` y sus frases `[T]`, `[S1]…[Sn]`, completo y sin recortes; después el gen con sus alias (`GENE: …. Other names used in the literature: …`) y «The protein encoded by G counts as G.»; después la pregunta (`QUESTIONS: …`) y una línea por pregunta (`Q1. PMID … | PROCESS: …`), en orden determinista (PMID, proceso).
   * **Salida JSON con esquema estricto:** un objeto `{"respuestas": [...]}` con un elemento por pregunta, cada uno con `q` (`Q1`, `Q2`…) y:
     * `v2_veredicto` (`ESQUEMA_LISTA_V2`): `frases` [{`id_frase`, `cita`}], `tipo_evidencia`, `organismo`, `tipo_celular`, `razonamiento_corto`, `limitacion`, `confianza` y `veredicto`;
     * `v1_proceso_gen` (`ESQUEMA_LISTA_V1_GEN`): `id_frase`, `justificacion_literal`, `tipo_evidencia`, `organismo`, `tipo_celular`, `razonamiento_corto`, `confianza`, `efecto` y `motivo_unknown`.
     Los cuatro campos de contexto (`tipo_evidencia`, `organismo`, `tipo_celular`, `razonamiento_corto`) son comunes (`CAMPOS_CONTEXTO` en `esquema.py`). En los dos casos, el razonamiento y la cita van antes que la confianza y el veredicto.
4. **Llamada a dos modelos** (principal y secundario, ADR-005) con un único conector compatible con OpenAI para todos los proveedores (`cliente.py`; Groq, Gemini, Cerebras u Ollama), temperatura 0 y `seed` cuando el proveedor lo admite, y salida JSON estructurada. **Una llamada por gen** (`ejecucion.py`): las preguntas que le faltan a algún modelo se agrupan por gen y se trocean con el `presupuesto_llamada` más pequeño de los modelos (`trocear_por_gen`), para que todos reciban la misma agrupación; a cada modelo se le envían solo las preguntas del grupo que le faltan. `max_completion_tokens` = 2.000 + 600 × (n.º de preguntas − 1). Si la salida se corta (`finish_reason = length`) y la llamada lleva más de una pregunta, se parte en dos y se repite; una pregunta que el modelo se salta queda pendiente.
5. **Validación de cada respuesta** (`respuesta.py`) según el [ADR-003](../decisions/adr-003-control-alucinaciones-unknown.md). Comunes:
   * se extrae el JSON (tolerando vallas ` ```json ` y texto alrededor) y se reparte la lista por pregunta (`Q1`, `q1` o la línea entera de la pregunta);
   * se comprueban los campos y valores del esquema (`json_invalido`);
   * se verifica la cita: forma de comparación, al menos 6 palabras, palabras enteras y **dentro de la frase indicada** por su ID;
   * se traducen la limitación o el motivo del modelo a los motivos del ADR-003.
   
   **`v2_veredicto`** (`_validar_v2`):
   * `frases` vacía o mal formada, o una confianza ausente o que no sea un entero de 0 a 100 → `json_invalido`;
   * se verifica cada una de las 1-3 frases; sin **ninguna** cita verificada → `UNKNOWN` con `cita_no_verificada`;
   * confianza por debajo de `UMBRAL_VEREDICTO` (**80**, en `esquema.py`; fijado el 2026-11-10 con la prueba de umbrales de Gemini sobre el gold v3) → `UNKNOWN` con `baja_confianza` y la limitación (`no_concluyente`);
   * si no, el veredicto: `+1`, `-1` o `neutro` (neutro también en cualquier ruta); si además trae una limitación distinta de `none` (el propio modelo dice que el abstract no lo sostiene), se conserva y pasa a `revisar` con `incoherencia_respuesta`;
   * guarda siempre el veredicto (`signo_llm`, y `signo_llm_ruta` en cada ruta) para el contraste con GO del paso 7.
   
   **`v1_proceso_gen`** (`_validar_v1_gen`):
   * un efecto sin cita verificada → `UNKNOWN` con `cita_no_verificada`, guardando `signo_llm`;
   * combinaciones incoherentes → se conservan en `revisar` con `incoherencia_respuesta` (un efecto con motivo, `NO_CLEAR_EFFECT` sin motivo, un efecto con `tipo_evidencia = correlation_or_marker`, o un signo con confianza por debajo de `MIN_CONFIANZA_SIGNO_V1_GEN` = 50, que contradice la regla 13);
   * la confianza debe ser un entero de 0 a 100 (si no, `json_invalido`); si falta, como en las respuestas registradas antes de la regla 13, queda vacía y no tiene efecto. Un signo con cita verificada y confianza entre 50 y `UMBRAL_CONFIANZA_V1_GEN` (70) **conserva el signo** y pasa a `revisar` con `baja_confianza`.
6. **Composición del signo sobre cada ruta** (las dos versiones). Se calcula `signo_ruta = efecto × factor`, donde el factor es `signo_camino(núcleo del término → núcleo de la ruta) × polaridad de la ruta` (ver *Composición del signo*). `neutro` es neutro en todas las rutas.
7. **Contraste y salida final** (`resultados.py`), por pregunta y por ruta:
   * `signo`: el del modelo principal;
   * `estado`: `resuelto` / `revisar` / `no_concluyente`;
   * `motivos`: se añade `discrepancia_entre_modelos` si los dos modelos dan signos distintos (también `UNKNOWN` frente a un signo); una respuesta del secundario con `json_invalido` no cuenta como discrepancia, y una pregunta que el principal aún no ha respondido queda `pendiente`;
   * **contraste con GO por ruta**, frente a la `Polaridad_GO` de esa anotación (mismo gen, ruta y PMID; si las filas del PMID no dan un único `+1`/`-1`, no se contrasta):
     * en `v2_veredicto`: si el veredicto coincide con `Polaridad_GO` y tiene al menos una cita verificada, se acepta aunque la confianza no llegue al umbral (`coincide_polaridad_GO`); si no coincide (también un `neutro` frente a `+1`/`-1`), `discrepancia_polaridad_GO` y `revisar`, con el signo del LLM si llega al umbral o `UNKNOWN` si no; sin `Polaridad_GO`, el veredicto si llega al umbral y `UNKNOWN` si no (tabla en el ADR-003);
     * en `v1_proceso_gen`: si el signo sobre la ruta difiere de `Polaridad_GO`, `discrepancia_polaridad_GO` y `revisar`, manteniendo el signo;
   * las preguntas cerradas por el filtro previo salen como `UNKNOWN` con `no_menciona_gen`;
   * `confianza_final` (`confianza.py`, solo para los signos): la confianza del principal corregida por el tipo de evidencia, la posición de la frase citada y el acuerdo con el modelo secundario (factores provisionales en el ADR-003). Es el porcentaje que se muestra junto al signo y al motivo.
8. **Registro:** cada pregunta respondida se añade a `respuestas_llm.jsonl` y cada llamada a `llamadas_llm.jsonl` en cuanto llega la respuesta ([ADR-004](../decisions/adr-004-persistencia-ficheros-locales.md)), con la versión del prompt. Las preguntas ya registradas con el mismo prompt no se vuelven a enviar; al reutilizarlas se vuelve a validar su respuesta cruda, así que un cambio del validador no obliga a volver a llamar.
9. **Salida:** `codigo/data/fase2_resultados.xlsx`, regenerable desde el registro, con tres hojas:
   * `Por_ruta`, una fila por (gen, ruta, PMID, proceso): `Signo_ruta`, `Estado`, `Motivos`, `Veredicto_LLM`, `Confianza_modelo`, `Confianza_final`, `Polaridad_GO`, el `Destino` del triaje, `Signo_principal`, `Signo_secundario`, las `Frases` con su cita, el razonamiento, `Id_frase` y `Cita`. Es la entrada del scoring;
   * `Preguntas`, una fila por pregunta, con la respuesta completa del principal (`Signo`, `Estado`, `Motivos`, `Confianza_modelo`, `Confianza_final`, los signos de los dos modelos, `Efecto`, `Limitacion`, `Frases`, `Id_frase`, `Cita`, `Cita_verificada`, `Tipo_evidencia`, `Organismo`, `Tipo_celular`, `Razonamiento`, `Termino_origen`, `Respaldo_ruta`, `Modelo_principal` y `Modelo_secundario`);
   * `Resumen`, con el recuento por estado y signo.

Se ejecuta desde `codigo/` con `python -m consulta_gen ejecutar [principal] [secundario|ninguno] [gen] [GO_ID] [excel]`; un «-» deja ese argumento por defecto, y los modelos por defecto son `gemini-3.5-flash-lite` (principal) y `groq-gpt-oss-120b` (secundario, en prueba; ADR-005). Se procesan las rutas de los dos Excels de CIMUS y los pares que no resolvió el triaje de la Fase 1 (`aceptar_GO` y `sin_evidencia` no llegan al LLM). Si se agota el límite diario de un modelo, sus preguntas quedan pendientes y basta con volver a lanzar el mismo comando. Sin llamar a ningún modelo, `python -m consulta_gen CD7 [GO_ID] [excel] [v2_veredicto|v1_proceso_gen]` imprime la primera llamada que se enviaría para un gen.

La **agregación** de varios casos del mismo par gen–ruta (varios PMIDs, posiblemente con signos distintos) y el cálculo del *Net Pathway Score* quedan fuera de esta spec: se definirán en la spec de scoring, que combinará el signo del gen sobre la ruta con su dirección de expresión (*up*/*down*). Propuesta de partida: una mayoría ponderada en código en la que cada respuesta pesa su `confianza_final` (en lugar de los pesos fijos de 1 para experimento directo en humano y 0,5 para ratón, otra célula o afirmación de contexto del informe «Prompt y modelos gratuitos Fase 2»), sin voto de los `UNKNOWN`; una minoría que pese ⅓ o más manda el par a `revisar`.

## Composición del signo
El signo siempre se expresa **respecto a la ruta tal como se llama**. En una ruta «negative regulation of X», un gen que **reduce** X ejecuta esa regulación y recibe **+1**; uno que aumenta X recibe −1.

* **Polaridad de la ruta:**
  * +1 si es un proceso o «positive regulation of X»;
  * −1 si es «negative regulation of X»;
  * +1 también si es «regulation of X» sin dirección: **se trata como X**, de modo que +1 significa «el gen promueve X» (decisión del 2026-11-08; son el 25 % de las filas). La opción `SIN_DIRECCION_COMO_PROCESO` está en `codigo/extraer_info/config.py` y se aplica igual en la Fase 1 (`Polaridad_GO`), para que el contraste con GO también funcione en estas rutas; con `False`, recibirían `UNKNOWN` con el motivo `ruta_sin_direccion`.
  * La dirección se detecta por la estructura del OBO, y las regulaciones encadenadas multiplican su signo («regulation of negative regulation of X» se comporta como «negative regulation of X»).
* **Signo del camino** entre núcleos (`proceso.py`, reutilizando `grafo_go` de la Fase 1):
  * `is_a` y `part_of` conservan el signo (un subtipo o una parte de X);
  * las regulaciones con signo multiplican;
  * lo rompen un `regulates` sin signo, una regulación por encima de un `part_of` (deprecado en RO) y los caminos con signos opuestos.
* **Camino roto:** si se rompe desde todos los términos estrechos de la fila, la fila pregunta por el núcleo de su ruta (respaldo A).

## Por qué
El objetivo del proyecto es resolver qué genes activan o inhiben cada ruta enriquecida. La polaridad curada de Gene Ontology solo cubre una parte de los pares: para el resto, la única fuente de signo es la lectura del abstract. Este módulo automatiza esa lectura con un LLM, pero de forma que cada signo sea **verificable** (cita literal comprobada), **auditable** (respuesta original registrada) y **prudente** (`UNKNOWN` antes que un signo inventado).

Por qué la unidad de pregunta es el proceso núcleo del término estrecho:
* **Menos preguntas:** medido el 2026-11-08 sobre todas las rutas de CIMUS, la pregunta por proceso núcleo necesitaba **1.794 casos** frente a 4.526 de la pregunta por fila gen–ruta–PMID de `v0_original` (versión ya eliminada).
* **Una respuesta coherente por abstract y proceso:** con la pregunta por ruta, el mismo abstract se evaluaba una vez por cada ruta en la que aparece el gen (p. ej. LGALS9 está en 147 rutas).
* **Sin doble negación:** el 56 % de las filas tienen rutas «(positive/negative) regulation of X», y preguntar si un gen «activa *negative regulation of X*» confunde a los modelos. La inversión la hace el código.
* **La pregunta está más cerca del abstract:** es lo que leyó y anotó el curador de GO.

Por qué una llamada por gen: el mensaje de sistema y el esquema son un prefijo fijo de unos 1.000 tokens; enviarlos una vez por gen y no una vez por pregunta reduce mucho los tokens (informe «Coste de una llamada por gen en la Fase 2») y los proveedores pueden servir ese prefijo de su caché. La huella de cada pregunta es la de su parte del prompt, así que si la Fase 1 añade un abstract a un gen solo se pregunta lo nuevo.

Por qué `v2_veredicto` en producción: con `v1_proceso_gen` el modelo se abstenía y el `UNKNOWN` dependía de su criterio. En `v2_veredicto` el modelo siempre declara qué cree y con qué confianza, y el `UNKNOWN` lo decide el código con reglas fijas (cita, umbral y GO) que se ajustan con el benchmark sin tocar el prompt.

Tres decisiones del prompt buscan que la respuesta dependa solo del abstract:
* **No se envía la dirección de expresión del gen** (*up*/*down*) ni la etiqueta de la lista de CIMUS (ruta activada o suprimida): esa etiqueta procede del mismo enriquecimiento que se quiere interpretar y empujaría al modelo a confirmarla.
* **No se envía la polaridad de GO:** se usa después para contrastar la respuesta; si el modelo la viera, el contraste dejaría de ser independiente. Una pista en el prompt puede bajar el acierto hasta un 36 % (informe «Prompt y modelos gratuitos Fase 2»).
* **No se envía el contexto del tumor (HNSC):** empujaría a responder «contexto ajeno» en la mitad de los abstracts, que no tratan de HNSC. El organismo y el tipo celular se piden como campos de salida.

## Restricciones
* **Coste cero:** solo modelos y planes gratuitos (ADR-005). Las credenciales (`GROQ_API_KEY`, `GEMINI_API_KEY`, `CEREBRAS_API_KEY`) se leen del entorno o de `codigo/.env`, documentadas en `.env.example`.
* **Mismo prompt para todos los modelos** dentro de cada versión: lo que se envía es una `PromptLista` (`como_mensajes()`), construida una sola vez; solo cambia la configuración del modelo. La versión del prompt se guarda en cada respuesta.
* **El prompt no contiene** la dirección de expresión del gen ni la lista de CIMUS (`Activada`/`Suprimida`, `UP`/`DOWN`), ni `Polaridad_GO`, ni el contexto HNSC, ni el umbral de confianza.
* **Abstract completo:** no se recorta por longitud.
* **`pmid`, `gen` y `go_id` de la salida se toman de la pregunta**, nunca de lo que devuelva el LLM.
* **Un fallo de red no es un `UNKNOWN`:** si un modelo no responde tras los reintentos (p. ej. por superar el límite diario), sus preguntas quedan **pendientes**, ese modelo deja de llamarse en esa ejecución y se reintenta en la siguiente; solo una respuesta recibida pero no interpretable da `json_invalido` (también el error 400 `json_validate_failed` de Groq, que trae el texto generado).
* **Límites de uso:** pausas entre llamadas según las peticiones por minuto de cada plan y hasta 5 reintentos con espera exponencial (o la que indique `retry-after`) ante `408`, `429` y `5xx`.
* **Sin repetición de llamadas:** antes de llamar se consulta el registro; una pregunta con la misma clave y la misma huella de prompt no se vuelve a enviar.

## Criterios de aceptación
Marcados ✅ los que ya cumple el código, comprobados con datos de la ejecución completa de la Fase 1 y respuestas simuladas (`ClienteSimulado`, sin red); la suite de `pytest` sigue pendiente. La reorganización del 2026-11-10 (eliminación de `v0_original` y `v1_proceso`) se comprobó revalidando las 817 respuestas guardadas del benchmark: salida idéntica, y textos, esquemas y huellas de los dos prompts idénticos byte a byte.

* [x] ✅ **Contenido del prompt:** no contiene `Activada`, `Suprimida`, `UP`, `DOWN`, el valor de `Polaridad_GO`, el contexto HNSC ni el umbral, e incluye el abstract limpio completo en frases numeradas.
* [x] ✅ **Orden del JSON pedido:** la cita (o las frases) y el razonamiento van antes que la confianza y el veredicto, y el prompt enumera los campos del esquema.
* [x] ✅ **Núcleo y polaridad:** «negative regulation of T cell proliferation» → («T cell proliferation», −1); «regulation of T cell activation» → («T cell activation», +1).
* [x] ✅ **Filtro previo:** una pregunta cuyo título y abstract no nombran el gen, sus alias ni su nombre se cierra con `no_menciona_gen` y no genera prompt.
* [x] ✅ **Las dos listas de CIMUS:** `ejecutar_fase2` incluye las rutas de genes *up* y *down* (con la Fase 1 del 2026-11-09, un gen solo de rutas suprimidas como TBX21 sale con sus 26 rutas).
* [x] ✅ **Una llamada por gen:** las preguntas de un gen van en una llamada troceada por el presupuesto; una pregunta que el modelo se salta queda pendiente; no se mezclan versiones en una ejecución.
* [x] ✅ **Respuesta con texto alrededor:** una respuesta del tipo ` ```json {…} ``` ` seguida de texto libre se interpreta correctamente.
* [x] ✅ **Valor no válido:** `"veredicto": "MAYBE"` (v2) o `"efecto": "MAYBE"` (v1_proceso_gen) da `signo = UNKNOWN` y `motivos = ["json_invalido"]`.
* [x] ✅ **Cita no verificada:** un veredicto o efecto cuya cita no está en la frase indicada, tiene menos de 6 palabras o es una paráfrasis da `signo = UNKNOWN`, `cita_no_verificada`, `estado = no_concluyente` y conserva `signo_llm`.
* [x] ✅ **Veredicto obligado y umbral (`v2_veredicto`):** sin GO, un `+1` con confianza por debajo de `UMBRAL_VEREDICTO` da `UNKNOWN` con `baja_confianza` (`no_concluyente`) y con el umbral se acepta; un veredicto por encima del umbral con limitación da `revisar` con `incoherencia_respuesta`; `NO_EFFECT` da `neutro` en todas las rutas; un veredicto que coincide con `Polaridad_GO` se acepta con confianza 20; uno que no coincide da `discrepancia_polaridad_GO`, con el signo del LLM si llega al umbral o `UNKNOWN` si no; sin cita verificada, `UNKNOWN` aunque coincida con GO.
* [x] ✅ **Incoherencia y confianza (`v1_proceso_gen`):** un efecto con `motivo_unknown` distinto de `none` conserva el signo y da `revisar` con `incoherencia_respuesta`; un `INCREASES` con cita verificada y `confianza = 65` conserva `+1` y da `revisar` con `baja_confianza`; con `confianza = 40` da `incoherencia_respuesta`; con `confianza = 101`, `"80"` o `72.5` da `json_invalido`; sin el campo, `confianza_modelo` queda vacía y el estado no cambia.
* [x] ✅ **Composición:** un `DECREASES` sobre «NK cell mediated cytotoxicity» da −1 en «leukocyte mediated immunity» y también en «regulation of immune effector process» (tratada como el proceso).
* [x] ✅ **Discrepancia entre modelos:** con el principal respondiendo `+1` y el secundario `UNKNOWN` (ambos válidos), la salida es `signo = +1`, `estado = revisar`, `motivos` con `discrepancia_entre_modelos`, y se guardan `Signo_principal` y `Signo_secundario`.
* [x] ✅ **Reanudación:** una segunda ejecución con el registro completo y el mismo prompt realiza **0 llamadas** a los modelos.
* [x] ✅ **Fallo de red:** si el cliente simulado devuelve `429` de forma persistente, sus preguntas quedan pendientes (no se escriben como `UNKNOWN`) y el resto continúa; la siguiente ejecución solo pide lo pendiente.
* [ ] **Pruebas desacopladas:** la suite de `pytest` cubre todos los criterios anteriores con un cliente de LLM simulado, sin conexión a internet. Hoy se comprueban con scripts sueltos fuera del repositorio (`research_notes/`); falta pasarlos a `pytest` dentro de `codigo/tests/`.
