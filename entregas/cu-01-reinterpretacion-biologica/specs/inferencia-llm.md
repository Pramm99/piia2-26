# Spec: Inferencia del Signo Funcional con LLM y Validación de la Respuesta

## Qué hay que construir
Un módulo de inferencia (Fase 2, `codigo/consulta_gen/`) que, a partir de la hoja `Con_abstract` del Excel de la Fase 1, determine para cada caso si el gen **activa** (`+1`) o **inhibe** (`-1`) la ruta según el abstract, o si la evidencia no lo permite (`UNKNOWN`), y produzca una salida validada y trazable.

Hay **dos versiones del prompt**, que se comparan en el benchmark ([ADR-005](../decisions/adr-005-eleccion-modelo-coste-cero.md)) sobre el mismo *gold set*:

| Versión | Unidad de pregunta (caso) | Qué se pregunta | Uso |
|---|---|---|---|
| `v0_original` | (gen, ruta, PMID): una fila de `Con_abstract` | El efecto del gen sobre la ruta del Excel, en español, con la dirección de scRNA-seq y el abstract recortado a 1.800 caracteres | **Solo benchmark**: es el prompt de partida, congelado, como línea base |
| `v1_proceso` | (gen, PMID, proceso núcleo) | El efecto del gen sobre el proceso núcleo del término estrecho (sin «positive/negative regulation of»), en inglés, con el abstract completo en frases numeradas | Candidata a producción |

El flujo es:

1. **Construcción de casos.**
   * `v0_original`: una fila = un caso.
   * `v1_proceso` (`casos.py`): para cada fila, el **término estrecho** es su `GO_ID_anotado` (filas del GAF; uno por término si hay varios) o su `Termino_coincidente` resuelto a GO ID (filas de GeneRIF y Europe PMC). Se pregunta por su **núcleo**: «negative regulation of T cell proliferation» → «T cell proliferation». Cada ruta cubierta guarda el factor que traduce el efecto en signo (ver *Composición del signo*). Si ningún término compone con la ruta, se pregunta por el núcleo de la propia ruta (**respaldo A**). Las filas que comparten (gen, PMID, núcleo) son un único caso.
2. **Filtro previo**, en las dos versiones: si ni el gen, ni sus alias (MyGene), ni su nombre completo aparecen en el título y el abstract como palabra completa (spec de limpieza), el caso se cierra con el motivo `no_menciona_gen` **sin llamar al LLM**.
3. **Construcción del prompt**, idéntico para todos los modelos dentro de cada versión. En `v1_proceso`:
   * Mensaje de sistema con 12 reglas: el gen debe ser la causa y no la diana; la pérdida de función invierte el signo; la ganancia de función lo conserva; marcador o correlación no es causalidad; efecto de otra molécula; negación; especulación; conflicto; alcance del proceso; el contexto (especie, célula) es un dato, no un motivo para abstenerse; se prefieren los resultados frente al contexto; y la cita.
   * Mensaje de usuario: el abstract primero, en frases `[T]`, `[S1]…[Sn]`, completo y sin recortes; después el gen y sus alias, el proceso y la pregunta.
   * Salida JSON con esquema estricto (`ESQUEMA_V1`), en este orden: `id_frase`, `justificacion_literal` (≥6 palabras copiadas de esa frase), `tipo_evidencia`, `organismo`, `tipo_celular`, `razonamiento_corto`, `efecto` (`INCREASES` / `DECREASES` / `NO_CLEAR_EFFECT`) y `motivo_unknown`.
   * Variante V2, desactivada por defecto: añade la frase en la que la Fase 1 vio el gen y el proceso (`Frase_fuente`). Solo se activa si mejora a V1 en el conjunto de desarrollo.
4. **Llamada a dos modelos** (principal y secundario, ADR-005) mediante un cliente independiente del proveedor (Cerebras, Groq, Gemini u Ollama), con temperatura 0 y `seed` cuando el proveedor lo permita y salida JSON estructurada.
5. **Validación de cada respuesta** según el [ADR-003](../decisions/adr-003-control-alucinaciones-unknown.md):
   * se extrae el JSON (tolerando vallas ` ```json ` y texto alrededor);
   * se comprueban los campos y valores del esquema (`json_invalido`);
   * se verifica la cita: forma de comparación, al menos 6 palabras, palabras enteras y, en `v1_proceso`, dentro de la frase `id_frase`. Si falla, se fuerza `UNKNOWN` con `cita_no_verificada` y se guarda `signo_llm`;
   * se traducen los motivos del modelo a los del ADR-003, y las respuestas incoherentes pasan a `revisar` con `incoherencia_respuesta`.
6. **Composición del signo sobre cada ruta** (solo `v1_proceso`). Se calcula `signo_ruta = efecto × factor`, donde el factor es `signo_camino(núcleo del término → núcleo de la ruta) × polaridad de la ruta` (ver *Composición del signo*).
7. **Contraste y salida final por caso:**
   * `signo`: el del modelo principal;
   * `estado`: `resuelto` / `revisar` / `no_concluyente`;
   * `motivos`: se añade `discrepancia_entre_modelos` si los dos modelos difieren, y `discrepancia_polaridad_GO` si el signo sobre la ruta difiere de `Polaridad_GO` cuando esta existe.
8. **Registro:** cada respuesta se añade al registro `respuestas_llm.jsonl` en cuanto llega ([ADR-004](../decisions/adr-004-persistencia-ficheros-locales.md)), con la versión del prompt. Los casos ya registrados con el mismo prompt no se vuelven a enviar.

La **agregación** de varios casos del mismo par gen–ruta (varios PMIDs, posiblemente con signos distintos) y el cálculo del *Net Pathway Score* quedan fuera de esta spec: se definirán en la spec de scoring. Propuesta de partida del informe: una mayoría ponderada en código (1 para experimento directo en humano y 0,5 para ratón, otra célula o afirmación de contexto), sin voto de los `UNKNOWN`; una minoría que pese ⅓ o más manda el par a `revisar`.

## Composición del signo (`v1_proceso`)
El signo siempre se expresa **respecto a la ruta tal como se llama**. En una ruta «negative regulation of X», un gen que **reduce** X ejecuta esa regulación y recibe **+1**; uno que aumenta X recibe −1.

* **Polaridad de la ruta:**
  * +1 si es un proceso o «positive regulation of X»;
  * −1 si es «negative regulation of X»;
  * +1 también si es «regulation of X» sin dirección: **se trata como X**, de modo que +1 significa «el gen promueve X» (decisión del 2026-11-08; son el 25 % de las filas). Con `SIN_DIRECCION_COMO_PROCESO = False` en `proceso.py`, esas rutas recibirían `UNKNOWN` con el motivo `ruta_sin_direccion`.
  * La dirección se detecta por la estructura del OBO, y las regulaciones encadenadas multiplican su signo («regulation of negative regulation of X» se comporta como «negative regulation of X»).
* **Signo del camino** entre núcleos, reutilizando `grafo_go` de la Fase 1:
  * `is_a` y `part_of` conservan el signo (un subtipo o una parte de X);
  * las regulaciones con signo multiplican;
  * lo rompen un `regulates` sin signo, una regulación por encima de un `part_of` (deprecado en RO) y los caminos con signos opuestos.
* **Camino roto:** si se rompe desde todos los términos estrechos de la fila, la fila pregunta por el núcleo de su ruta (respaldo A).

## Por qué
El objetivo del proyecto es resolver qué genes activan o inhiben cada ruta enriquecida. La polaridad curada de Gene Ontology solo cubre una parte de los pares: para el resto, la única fuente de signo es la lectura del abstract. Este módulo automatiza esa lectura con un LLM, pero de forma que cada signo sea **verificable** (cita literal comprobada), **auditable** (respuesta original registrada) y **prudente** (`UNKNOWN` antes que un signo inventado).

Por qué la unidad de `v1_proceso` es el proceso núcleo del término estrecho:
* **Menos llamadas:** sobre todas las rutas de CIMUS (activadas y suprimidas), `v1_proceso` necesita **1.794 casos** frente a 4.526 en `v0_original`.
* **Una respuesta coherente por abstract y proceso:** antes, el mismo abstract se evaluaba una vez por cada ruta en la que aparece el gen (p. ej. LGALS9 está en 147 rutas).
* **Sin doble negación:** el 56 % de las filas tienen rutas «(positive/negative) regulation of X», y preguntar si un gen «activa *negative regulation of X*» confunde a los modelos. La inversión la hace el código.
* **La pregunta está más cerca del abstract:** es lo que leyó y anotó el curador de GO.

Tres decisiones del prompt buscan que la respuesta dependa solo del abstract:
* **No se envía la dirección de scRNA-seq** (ruta activada o suprimida): esa etiqueta procede del mismo enriquecimiento que se quiere interpretar y empujaría al modelo a confirmarla.
* **No se envía la polaridad de GO:** se usa después para contrastar la respuesta; si el modelo la viera, el contraste dejaría de ser independiente. Una pista en el prompt puede bajar el acierto hasta un 36 % (informe «Prompt y modelos gratuitos Fase 2»).
* **No se envía el contexto del tumor (HNSC):** empujaría a responder «contexto ajeno» en la mitad de los abstracts, que no tratan de HNSC. El organismo y el tipo celular se piden como campos de salida.

## Restricciones
* **Coste cero:** solo modelos y planes gratuitos (ADR-005). Las credenciales (`CEREBRAS_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`) se leen de `.env`, documentadas en `.env.example`.
* **Mismo prompt para todos los modelos** dentro de cada versión, construido una sola vez (`PromptLLM.como_mensajes()`); solo cambia el conector del proveedor. La versión del prompt se guarda en cada respuesta.
* **En producción, el prompt no contiene** la dirección de scRNA-seq (`Activada`/`Suprimida`, `UP`/`DOWN`), ni `Polaridad_GO`, ni el contexto HNSC. La única excepción es `v0_original`, que existe solo como línea base del benchmark.
* **Abstract completo** en `v1_proceso`: no se recorta por longitud.
* **`pmid`, `gen` y `go_id` de la salida se toman de la evidencia**, nunca de lo que devuelva el LLM.
* **Un fallo de red no es un `UNKNOWN`:** si un modelo no responde tras los reintentos (p. ej. por superar el límite diario), el caso queda **pendiente** y se reintenta en la siguiente ejecución; solo una respuesta recibida pero no interpretable da `json_invalido`.
* **Límites de uso:** reintentos con espera exponencial ante `429` y pausas entre llamadas para respetar los límites por minuto y por día de cada plan gratuito.
* **Sin repetición de llamadas:** antes de llamar se consulta el registro; un caso con la misma clave y la misma huella de prompt no se vuelve a enviar.

## Criterios de aceptación
Marcados ✅ los que ya cumple el código (commit `1738e0b`, comprobados con datos de la ejecución completa y respuestas simuladas; la suite de `pytest` sigue pendiente).

* [x] ✅ **Línea base congelada:** los prompts de `v0_original` son idénticos byte a byte a los del código anterior (4.927 filas comprobadas).
* [x] ✅ **Contenido del prompt `v1_proceso`:** no contiene `Activada`, `Suprimida`, `UP`, `DOWN`, el valor de `Polaridad_GO` ni el contexto HNSC, e incluye el abstract limpio completo en frases numeradas.
* [x] ✅ **Orden del JSON pedido:** en `v1_proceso`, `id_frase`, `justificacion_literal` y `razonamiento_corto` van antes que `efecto`.
* [x] ✅ **Núcleo y polaridad:** «negative regulation of T cell proliferation» → («T cell proliferation», −1); «regulation of T cell activation» → («T cell activation», +1).
* [x] ✅ **Filtro previo:** un caso cuyo título y abstract no nombran el gen, sus alias ni su nombre se cierra con `no_menciona_gen` y no genera prompt.
* [x] ✅ **Respuesta con texto alrededor:** una respuesta del tipo ` ```json {…} ``` ` seguida de texto libre se interpreta correctamente.
* [x] ✅ **Valor no válido:** `"efecto": "MAYBE"` (v1) o `"signo_funcional": "maybe"` (v0) da `signo = UNKNOWN` y `motivos = ["json_invalido"]`.
* [x] ✅ **Cita no verificada:** un efecto cuya cita no está en la frase indicada, tiene menos de 6 palabras o es una paráfrasis da `signo = UNKNOWN`, `cita_no_verificada`, `estado = no_concluyente` y conserva `signo_llm`.
* [x] ✅ **Incoherencia:** un efecto con `motivo_unknown` distinto de `none` conserva el signo y da `estado = revisar` con `incoherencia_respuesta`.
* [x] ✅ **Composición:** un `DECREASES` sobre «NK cell mediated cytotoxicity» da −1 en «leukocyte mediated immunity» y también en «regulation of immune effector process» (tratada como el proceso).
* [ ] **Discrepancia entre modelos:** con el principal respondiendo `+1` y el secundario `UNKNOWN` (ambos válidos), la salida es `signo = +1`, `estado = revisar`, `motivos` con `discrepancia_entre_modelos`, y se guardan `signo_modelo_principal` y `signo_modelo_secundario`.
* [ ] **Discrepancia con GO:** un `+1` válido frente a `Polaridad_GO = -1` da `estado = revisar` con `discrepancia_polaridad_GO`, manteniendo `signo = +1`.
* [ ] **Reanudación:** una segunda ejecución con el registro completo y el mismo prompt realiza **0 llamadas** a los modelos.
* [ ] **Fallo de red:** si el cliente simulado devuelve `429` de forma persistente, el caso queda pendiente (no se escribe como `UNKNOWN`) y el resto de casos continúa.
* [ ] **Pruebas desacopladas:** la suite de `pytest` cubre todos los criterios anteriores con un cliente de LLM simulado, sin conexión a internet.
