# Spec: Inferencia del Signo Funcional con LLM y Validación de la Respuesta

## Qué hay que construir
Un módulo de inferencia (Fase 2, `codigo/consulta_gen/`) que, a partir de la hoja `Con_abstract` del Excel de la Fase 1, determine para cada caso si el gen **activa** (`+1`) o **inhibe** (`-1`) la ruta según el abstract, o si la evidencia no lo permite (`UNKNOWN`), y produzca una salida validada y trazable. El flujo es:

1. **Construcción de casos:** agrupar las filas de `Con_abstract` en casos, que son la unidad de llamada al LLM. **Qué es exactamente un caso está pendiente de decidir** (ver la sección *Decisión pendiente*).
2. **Filtro previo:** si ni el gen ni sus alias aparecen en el abstract como palabra completa (spec de limpieza), el caso se cierra con el motivo `no_menciona_gen` **sin llamar al LLM**.
3. **Construcción del prompt**, idéntico para todos los modelos:
   * Mensaje de sistema: el modelo lee un solo abstract, decide únicamente a partir de él y responde solo con JSON.
   * Mensaje de usuario: gen y alias, ruta o término por el que se pregunta, título y **abstract completo** (sin recortes), y las opciones de respuesta.
   * El JSON pedido pone la **justificación literal y el razonamiento antes del signo**:

     ```json
     {
       "justificacion_literal": "frase copiada exactamente del abstract",
       "razonamiento_corto": "una sola frase",
       "signo_funcional": "+1 | -1 | UNKNOWN",
       "motivo_unknown": "no_menciona_gen | efecto_indirecto | contradictorio | contexto_ajeno | null"
     }
     ```
4. **Llamada a dos modelos** (principal y secundario, [ADR-005](../decisions/adr-005-eleccion-modelo-coste-cero.md)) mediante un cliente independiente del proveedor (Groq, Gemini u Ollama), con temperatura 0 cuando el proveedor lo permita y salida JSON estructurada.
5. **Validación de cada respuesta** según el [ADR-003](../decisions/adr-003-control-alucinaciones-unknown.md): extraer el JSON (tolerando vallas ` ```json ` y texto alrededor), normalizar el signo, verificar la cita (spec de limpieza: forma de comparación y 6 palabras como mínimo) y forzar `UNKNOWN` con el motivo correspondiente si falla alguna comprobación.
6. **Contraste y salida final por caso:** `signo` (el del modelo principal), `estado` (`resuelto` / `revisar` / `no_concluyente`) y `motivos`, añadiendo `discrepancia_entre_modelos` si los dos modelos difieren y `discrepancia_polaridad_GO` si el signo difiere de `Polaridad_GO` cuando esta existe.
7. **Registro:** cada respuesta se añade al registro `respuestas_llm.jsonl` en cuanto llega ([ADR-004](../decisions/adr-004-persistencia-ficheros-locales.md)), y los casos ya registrados con el mismo prompt no se vuelven a enviar.

La **agregación** de varios casos del mismo par gen–ruta (varios PMIDs, posiblemente con signos distintos) y el cálculo del *Net Pathway Score* quedan fuera de esta spec: se definirán en la spec de scoring.

## Por qué
El objetivo del proyecto es resolver qué genes activan o inhiben cada ruta enriquecida. En el conjunto completo de rutas activadas, la polaridad curada de Gene Ontology solo existe en un **23 %** de las filas con PMID (428 de 1.868): para el resto, la única fuente de signo es la lectura del abstract. Este módulo automatiza esa lectura con un LLM, pero de forma que cada signo sea **verificable** (cita literal comprobada), **auditable** (respuesta original registrada) y **prudente** (`UNKNOWN` antes que un signo inventado).

Dos decisiones del prompt buscan que la respuesta dependa solo del abstract:
* **No se envía la dirección de scRNA-seq** (ruta activada o suprimida): esa etiqueta procede del mismo enriquecimiento que se quiere interpretar y empujaría al modelo a confirmarla.
* **No se envía la polaridad de GO:** se usa después para contrastar la respuesta; si el modelo la viera, el contraste dejaría de ser independiente.

## Restricciones
* **Coste cero:** solo modelos y planes gratuitos (ADR-005). Las credenciales (`GROQ_API_KEY`, `GEMINI_API_KEY`) se leen de `.env`, documentadas en `.env.example`.
* **Mismo prompt para todos los modelos**, construido una sola vez (`PromptLLM.como_mensajes()`); solo cambia el conector del proveedor.
* **El prompt no contiene** la dirección de scRNA-seq (`Activada`/`Suprimida`, `UP`/`DOWN`) ni `Polaridad_GO`.
* **Abstract completo:** no se recorta por longitud.
* **`pmid`, `gen` y `go_id` de la salida se toman de la evidencia**, nunca de lo que devuelva el LLM.
* **Un fallo de red no es un `UNKNOWN`:** si un modelo no responde tras los reintentos (p. ej. por superar el límite diario), el caso queda **pendiente** y se reintenta en la siguiente ejecución; solo una respuesta recibida pero no interpretable da `json_invalido`.
* **Límites de uso:** reintentos con espera exponencial ante `429` y pausas entre llamadas para respetar los límites por minuto y por día de cada plan gratuito.
* **Sin repetición de llamadas:** antes de llamar se consulta el registro; un caso con la misma clave y la misma huella de prompt no se vuelve a enviar.

## Decisión pendiente: definición de caso
Todavía no está decidido sobre qué se pregunta al LLM. Las dos opciones, con los volúmenes medidos sobre las 314 rutas activadas (antes de descartar los PMIDs sin abstract):

### Opción A — Caso = (gen, ruta, PMID)
Se pregunta por el efecto del gen sobre **la ruta del Excel**: *"¿Cómo afecta CD7 a 'leukocyte mediated immunity'?"*. Es lo que hace el prompt actual.

* **Ventajas:**
  * Responde directamente a la pregunta del experto: el efecto del gen sobre la ruta enriquecida.
  * Ya está implementada en el prompt actual; no hace falta diseñar nada más.
  * Fácil de explicar y de revisar: la respuesta se refiere a la misma ruta que aparece en los resultados.
* **Desventajas:**
  * **1.868 llamadas por modelo**: con dos modelos y unos 170 casos al día por plan gratuito, del orden de **11 días** de ejecución.
  * El mismo abstract se evalúa muchas veces para el mismo gen (una por cada ruta en la que aparece; p. ej. LGALS9 está en 158 rutas), con riesgo de respuestas incoherentes entre rutas.
  * Las rutas amplias (p. ej. *leukocyte mediated immunity*) están lejos de lo que dice el abstract, lo que facilita respuestas `UNKNOWN` o forzadas.

### Opción B — Caso = (gen, PMID, término anotado)
Se pregunta por el efecto del gen sobre **el término concreto al que el curador de GO asoció el artículo**: *"¿Cómo afecta CD7 a 'positive regulation of T cell cytokine production'?"*. El signo sobre la ruta se obtiene después componiendo con el camino del grafo de GO entre el término y la ruta.

* **Ventajas:**
  * **446 llamadas por modelo** (unas 4 veces menos): del orden de **3 días** de ejecución con dos modelos.
  * Una sola respuesta por abstract y término, coherente en todas las rutas que lo contienen.
  * La pregunta está más cerca del contenido del abstract, que es lo que el curador leyó y anotó.
* **Desventajas:**
  * Hay que diseñar la composición del signo del término con el camino hasta la ruta. Funciona con `is_a`/`part_of` (no cambia el signo), `positively_regulates` (lo mantiene) y `negatively_regulates` (lo invierte), pero **no con `regulates` sin signo**, que no permite deducir la dirección sobre la ruta.
  * Los términos del tipo *"positive regulation of X"* dan preguntas poco naturales; probablemente habría que preguntar por el proceso base (*X*) y componer el signo después.
  * Más difícil de explicar: la respuesta del LLM no se refiere directamente a la ruta que ve el experto.

**Cómo se decidirá:** con el benchmark del ADR-005, comparando ambas formulaciones sobre el mismo *gold set*. Al decidir habrá que alinear la clave del registro del ADR-004 y el volumen estimado del ADR-005, que hoy asumen la opción B.

## Criterios de aceptación
* [ ] **Contenido del prompt:** el prompt generado para cualquier caso no contiene las cadenas `Activada`, `Suprimida`, `UP`, `DOWN` ni el valor de `Polaridad_GO`, e incluye el abstract limpio completo (misma longitud que la salida de la sanitización).
* [ ] **Orden del JSON pedido:** en la plantilla del prompt, `justificacion_literal` y `razonamiento_corto` aparecen antes que `signo_funcional`.
* [ ] **Filtro previo:** para un caso cuyo abstract no menciona el gen ni sus alias, el módulo devuelve `motivos = ["no_menciona_gen"]` y el cliente del LLM (simulado) registra **0 llamadas**.
* [ ] **Respuesta con texto alrededor:** una respuesta del tipo ` ```json {…} ``` ` precedida de texto libre se interpreta correctamente.
* [ ] **Signo no válido:** una respuesta con `"signo_funcional": "maybe"` da `signo = UNKNOWN` y `motivos = ["json_invalido"]`.
* [ ] **Cita no verificada:** una respuesta `+1` cuya cita no aparece en el abstract da `signo = UNKNOWN`, `motivos` con `cita_no_verificada`, `estado = no_concluyente` y conserva `signo_llm = "+1"`.
* [ ] **Discrepancia entre modelos:** con el principal respondiendo `+1` y el secundario `UNKNOWN` (ambos válidos), la salida es `signo = +1`, `estado = revisar`, `motivos` con `discrepancia_entre_modelos`, y se guardan `signo_modelo_principal` y `signo_modelo_secundario`.
* [ ] **Discrepancia con GO:** un `+1` válido frente a `Polaridad_GO = -1` da `estado = revisar` con `discrepancia_polaridad_GO`, manteniendo `signo = +1`.
* [ ] **Reanudación:** una segunda ejecución con el registro completo y el mismo prompt realiza **0 llamadas** a los modelos.
* [ ] **Fallo de red:** si el cliente simulado devuelve `429` de forma persistente, el caso queda pendiente (no se escribe como `UNKNOWN`) y el resto de casos continúa.
* [ ] **Pruebas desacopladas:** la suite de `pytest` cubre todos los criterios anteriores con un cliente de LLM simulado, sin conexión a internet.
