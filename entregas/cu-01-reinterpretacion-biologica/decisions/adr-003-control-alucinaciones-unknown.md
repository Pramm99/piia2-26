---
description: Control de alucinaciones mediante un esquema de salida con signo, estado y motivos, reglas automáticas de verificación y contraste con Gene Ontology y entre dos modelos.
state: Aceptado (validación implementada el 2026-11-08; contraste entre modelos y con GO, el 2026-11-10; veredicto obligado con UNKNOWN decidido por el código, v2_veredicto, el 2026-11-10)
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
| `sin_efecto` | Solo `v1_proceso_gen` (`no_effect_found`). En `v2_veredicto` ese caso es el veredicto `NO_EFFECT` → `neutro` | `no_concluyente` | `UNKNOWN` |
| `especulativo` | LLM (hipótesis sin resultado) | `no_concluyente` | `UNKNOWN` |
| `cita_no_verificada` | Regla automática | `no_concluyente` | `UNKNOWN` |
| `json_invalido` | Regla automática | `no_concluyente` | `UNKNOWN` |
| `baja_confianza` | Regla automática. `v2_veredicto`: confianza por debajo de `UMBRAL_VEREDICTO` (80) y sin coincidencia con GO. `v1_proceso_gen`: signo con confianza entre 50 y 69 | `v2`: `no_concluyente`; `v1`: `revisar` | `v2`: `UNKNOWN`; `v1`: se mantiene |
| `incoherencia_respuesta` | Regla automática. `v2_veredicto`: veredicto que llega al umbral pero trae una limitación. `v1_proceso_gen`: un efecto con motivo de `UNKNOWN`, `NO_CLEAR_EFFECT` sin motivo, un efecto basado en `correlation_or_marker` o un efecto con confianza por debajo de 50 | `revisar` | Se mantiene |
| `coincide_polaridad_GO` | Contraste con GO, solo en `v2_veredicto`: el veredicto sobre la ruta coincide con la `Polaridad_GO` de la anotación | `resuelto` | El de GO y el LLM, aunque la confianza no llegue al umbral |
| `discrepancia_polaridad_GO` | Contraste con GO | `revisar` | Se mantiene (en `v2`, `UNKNOWN` si la confianza no llega al umbral) |
| `discrepancia_entre_modelos` | Contraste entre modelos | `revisar` | El del modelo principal |
| `ruta_sin_direccion` | Composición del signo hasta la ruta (las dos versiones), solo si `SIN_DIRECCION_COMO_PROCESO = False`: la ruta es «regulation of X» sin dirección. Por defecto esas rutas se tratan como X | — | `UNKNOWN` en esa ruta |
| `sin_evidencia:<causa>` | Fase 1: el par no tiene ningún abstract y no llega al LLM | `no_concluyente` | `UNKNOWN` |

Los motivos `direccion_inversa`, `marcador_correlacion`, `sin_efecto` y `especulativo` se añadieron el 2026-11-08 (informe «Prompt y modelos gratuitos Fase 2»): separan las trampas de dirección más frecuentes, que antes caían todas en `efecto_indirecto` o `contexto_ajeno`, para poder analizar los errores por tipo. El motivo `baja_confianza` se añadió el 2026-11-10 (informe «Benchmark v2 y propuesta de confianza Fase 2»).

### Producción: `v2_veredicto` (decisión del equipo del 2026-11-10)
En producción el LLM **no puede abstenerse**: para cada pregunta devuelve siempre un veredicto (`INCREASES`, `DECREASES` o `NO_EFFECT`, que se traducen a `+1`, `-1` y `neutro`), una **confianza** de 0 a 100 (su probabilidad de acertar según el abstract, con una guía cualitativa de más a menos apoyo), de 1 a 3 frases que lo motivan con su cita literal, el razonamiento y, si la hay, la **limitación** del abstract (gen diana, marcador, otra molécula, especulación, conflicto, proceso no tratado o gen no mencionado). **La decisión de `UNKNOWN` la toma el código**, no el modelo:

| Situación de la fila (gen, ruta, PMID) | Resultado |
|---|---|
| Ninguna de las frases tiene la cita verificada | `UNKNOWN`, `cita_no_verificada` |
| Hay `Polaridad_GO` (+1/−1) y el veredicto sobre la ruta **coincide** | Se acepta el efecto aunque la confianza no llegue al umbral: `resuelto`, `coincide_polaridad_GO` |
| Hay `Polaridad_GO` y el veredicto **no coincide** (también un neutro frente a +1/−1) | `revisar`, `discrepancia_polaridad_GO`, con las frases y la confianza del LLM. El signo es el del LLM si su confianza llega al umbral; si no, `UNKNOWN` |
| No hay `Polaridad_GO` y la confianza llega al umbral (`UMBRAL_VEREDICTO = 80`, configurable en `esquema.py`; fijado con la prueba de umbrales sobre el gold v3) | El veredicto del LLM: `+1`, `-1` o `neutro` (`resuelto`). Si además trae una limitación, `revisar` con `incoherencia_respuesta` |
| No hay `Polaridad_GO` y la confianza no llega al umbral | `UNKNOWN`, `baja_confianza` más la limitación que dio el modelo (`no_concluyente`) |

`neutro` significa que el abstract muestra que el gen **no cambia** el proceso («no afectó», «fue prescindible»). Es el mismo valor que la Fase 1 da a las inmunoglobulinas y cuenta como respuesta resuelta (suma 0 en el score). Un abstract que no trata el efecto del gen no es neutro: el modelo da una confianza baja y el código lo deja en `UNKNOWN`. **El prompt no menciona ningún umbral** (decisión del 2026-11-10): decirle al modelo dónde se corta sería una fuga de información que predispone su confianza. El umbral lo fija el código según la calidad medida en el benchmark. Como el registro guarda la respuesta cruda, cambiar el umbral solo exige volver a validar, sin llamar de nuevo a los modelos.

La versión `v1_proceso_gen`, en la que el modelo sí puede abstenerse (`NO_CLEAR_EFFECT` con un motivo), se conserva para el benchmark.

> **Histórico.** Hasta el 2026-11-10 existían también `v0_original` (el prompt de partida, una llamada por fila) y `v1_proceso` (una llamada por pregunta). Se eliminaron del código al pasar a la llamada por gen; sus resultados siguen en los informes del benchmark v1 y v2.

`UNKNOWN` queda reservado para los casos **sin evidencia utilizable**, o sin la confianza suficiente para darla por buena. Cuando hay evidencia pero otra fuente la contradice (Gene Ontology o el modelo secundario), se conserva el signo y el caso se marca para revisión experta.

El control se organiza en tres capas:

1. **Prompt** (`codigo/consulta_gen/prompt.py`). Las dos versiones piden la justificación, el razonamiento y la confianza **antes** del veredicto. Explican cada trampa de dirección con un criterio explícito, porque ofrecer «unknown» sin criterios provoca abstenciones falsas. Enumeran además los campos del JSON con sus valores permitidos.
   * **`v2_veredicto`:** el modelo siempre elige un veredicto. Las trampas se declaran como `limitacion` y bajan la confianza. La confianza no tiene cifras ni umbral, solo una guía cualitativa de más a menos apoyo.
   * **`v1_proceso_gen`:** el modelo puede responder `NO_CLEAR_EFFECT` con un motivo. La confianza tiene anclas fijas para que todos los modelos usen la misma escala: 90-100 si hay un experimento con el gen y un resultado explícito sobre ese proceso; 70-89 si el experimento es claro pero sobre una forma más específica del proceso, otra especie u otro tipo celular, o con un paso de inferencia; 50-69 si el apoyo es indirecto; por debajo de 50 la respuesta debe ser `NO_CLEAR_EFFECT`.
   * En las dos versiones el modelo responde en inglés y el código traduce los motivos y limitaciones a los de la tabla (`MOTIVO_MODELO_A_ADR`).
2. **Reglas automáticas**, que no dependen del juicio del modelo (`codigo/consulta_gen/respuesta.py`):
   * **Filtro previo** (`casos.py`): si el abstract no nombra al gen como palabra completa por su símbolo, sus alias de MyGene o su nombre completo, la pregunta se cierra con `no_menciona_gen` sin llamar al LLM. `CD7` no cuenta dentro de `CD70`, `CD-7` equivale a `CD7`, los alias de menos de 3 caracteres se ignoran y una forma escrita toda en minúsculas no cuenta como mención.
   * **Verificación de la cita:** el abstract va en frases numeradas (`[T]`, `[S1]`, `[S2]`…) y la cita debe estar dentro de la frase que indica el modelo. Se compara tras una normalización solo para comparar: minúsculas, todos los guiones unificados, letras griegas escritas como palabras (α→alpha, κ→kappa…) y sin puntuación. La cita debe tener **al menos 6 palabras** y coincidir con palabras enteras. En `v1_proceso_gen` hay una sola frase; en `v2_veredicto` hay de 1 a 3 y basta con que una se verifique. Si ninguna se verifica, el signo pasa a `UNKNOWN` con `cita_no_verificada`, y se conserva el veredicto original del modelo (`signo_llm`) para auditoría.
   * **Formato:** un JSON no interpretable, un campo que falta o un valor fuera de los permitidos da `json_invalido`. También una confianza que no sea un entero de 0 a 100 y, en `v2_veredicto`, una confianza ausente o una lista de frases mal formada.
   * **Confianza y coherencia en `v2_veredicto`:** una confianza por debajo de `UMBRAL_VEREDICTO` (80) convierte el veredicto en `UNKNOWN` con `baja_confianza`, salvo que coincida con GO (capa 3). Un veredicto que llega al umbral pero trae una limitación se conserva, añade `incoherencia_respuesta` y queda en `revisar`.
   * **Confianza y coherencia en `v1_proceso_gen`:** un signo con confianza entre `MIN_CONFIANZA_SIGNO_V1_GEN` (50) y `UMBRAL_CONFIANZA_V1_GEN` (70) **conserva el signo**, añade `baja_confianza` y queda en `revisar`. Las respuestas incoherentes (las de la tabla de motivos) conservan el signo, añaden `incoherencia_respuesta` y quedan en `revisar`.
3. **Contraste con fuentes independientes** (`codigo/consulta_gen/resultados.py`):
   * **Gene Ontology**, fila a fila (gen, ruta, PMID). Solo se contrasta cuando las anotaciones de ese PMID dan una única `Polaridad_GO` (`+1` o `-1`). En `v2_veredicto` se aplica la tabla de producción de arriba; la coincidencia exige al menos una cita verificada. En `v1_proceso_gen`, si el signo sobre la ruta difiere de la `Polaridad_GO`, se añade `discrepancia_polaridad_GO` y la fila queda en `revisar`.
   * **Dos modelos:** cada pregunta se evalúa con un **modelo principal** y un **modelo secundario**, ambos gratuitos. El `signo` final es el del principal y se registran los dos (`Signo_principal` y `Signo_secundario`). Cualquier diferencia entre ellos (signos opuestos, o uno `UNKNOWN` y el otro no) añade el motivo `discrepancia_entre_modelos` y deja el caso en `revisar`. Una respuesta del secundario con `json_invalido` no cuenta como discrepancia: no dice nada del abstract, solo que ese modelo falló el formato. Si el principal todavía no ha respondido (límite diario), el caso queda `pendiente`, nunca `UNKNOWN`. Qué modelo es el principal y cuál el secundario se fija en el [ADR-005](adr-005-eleccion-modelo-coste-cero.md), a partir del benchmark.

**Porcentaje final (`confianza_final`).** La confianza declarada suele estar inflada, así que el porcentaje que se muestra junto al signo y al motivo se corrige con señales que no dependen de lo que el modelo diga de sí mismo (`codigo/consulta_gen/confianza.py`):

`confianza_final = confianza_modelo × factor_evidencia × factor_frase × factor_acuerdo`, entre 0 y 100.

* **Tipo de evidencia:** ganancia de función 1,0; pérdida de función 0,9; medida directa 0,85; contexto, correlación o ninguna 0,7.
* **Frase citada:** 0,9 si es el título o las frases S1-S2 (suelen ser introducción); 1,0 si es una frase posterior.
* **Otro modelo:** 1,0 si da el mismo signo; 0,8 si da `UNKNOWN`; 0,5 si da el signo opuesto; 0,9 si no hay respuesta suya.

Los factores son provisionales: salen del benchmark v2 (43 signos de los tres modelos de API) como el cociente entre el acierto de cada grupo y el del mejor, acercados a 1 la mitad del camino porque las muestras son pequeñas. Cuando haya etiquetas de CIMUS se sustituirán por una regresión logística ajustada en el *gold set*. Solo los signos tienen `confianza_final`: un `UNKNOWN` se explica con su motivo. En una fila aceptada por `coincide_polaridad_GO` cuya confianza no llegaba al umbral, `confianza_final` se calcula sobre el veredicto aceptado y por eso sale baja. Ese porcentaje es también el peso propuesto para cada respuesta en la agregación por par gen-ruta (spec de scoring).

La normalización de comparación nunca se aplica al texto que lee el LLM: este recibe el abstract limpio pero con la nomenclatura intacta, como exige la spec de limpieza.

**Ejemplo real** (benchmark v5, Gemini 3.5 Flash-Lite, `v2_veredicto`). Es la trampa de la Motivación: en el PMID 10652336 el efecto lo produce el ligando K12-Fc, no CD7. Respuesta validada de la pregunta (CD7, 10652336, proceso núcleo GO:0002369 *T cell cytokine production*), resumida:

```json
{
  "version": "v2_veredicto", "gen": "CD7", "pmid": "10652336", "go_id": "GO:0002369",
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
3. **El corte lo decide el código, no el modelo:** con `v2_veredicto` el modelo siempre informa de lo que cree y de cuánto lo cree, y el código decide qué se acepta. El umbral se ajusta con el benchmark y se puede cambiar sin volver a llamar a los modelos; con la abstención de `v1_proceso_gen`, el corte quedaba dentro del juicio de cada modelo.
4. **Los motivos hacen el sistema auditable:** un `UNKNOWN` sin motivo no indica si falla la recuperación, el modelo o la propia evidencia.
5. **Las discrepancias son información, no ruido:** la polaridad de GO es curada por expertos y el segundo modelo es independiente del primero. Convertir sus desacuerdos en `UNKNOWN` descartaría justo los casos que más interesa que revise el experto. Cuando discrepan los dos modelos, se conserva el signo del principal, se registran ambas respuestas y el caso queda marcado para que el experto lo resuelva con toda la información.
6. **La conclusión es del experto:** el sistema extrae y verifica evidencia; los casos `revisar` se entregan al profesional biomédico con las citas y los motivos.

**Validación:** sobre el *gold set* se miden la **precisión de las respuestas dadas** (cuando el sistema da `+1`, `-1` o `neutro`, cuántas acierta), la **cobertura** (porcentaje de casos con estado `resuelto`) y el **recall de `UNKNOWN`** (cuántos casos no concluyentes según el experto detecta el sistema), además de la calibración de `confianza_modelo` y `confianza_final` (spec del benchmark). Medición provisional del 2026-11-10 (umbral 80; Gemini 3.5 Flash-Lite salvo donde se indica):

| Gold | Casos | Exactitud | Precisión de los signos | Cobertura | Recall de `UNKNOWN` |
|---|---|---|---|---|---|
| v4 (vigente; 65 de genes *up* y 35 de genes *down*) | 100 | 84 % | 72 % | 40 % | 85 % |
| v4, con gpt-oss-120b | 100 | 85 % | 79 % | 34 % | 89 % |
| v3 (histórico; solo genes *up*) | 124 | 82 % | 66 % | 45 % | 79 % |

Las etiquetas de los dos gold son de anotadores Claude a ciegas; las cifras valdrán cuando etiquete CIMUS. Los umbrales mínimos se acordarán con CIMUS.

Aceptamos los compromisos asociados: duplicar las llamadas (dos modelos) alarga la ejecución en los planes gratuitos; el filtro previo puede descartar abstracts que nombran el gen de forma no recogida en los alias (un error en la dirección segura, que se medirá en el benchmark); y la cobertura bajará frente a un sistema que siempre responde.

### Pendiente de decidir
* **Confianza mínima para `coincide_polaridad_GO`:** hoy se acepta cualquier confianza. En el benchmark v4 (con el prompt anterior) esta regla aceptó veredictos con confianza de 0 a 35 que eran adivinanzas.
* **Umbral sobre `confianza_final` en lugar de `confianza_modelo`:**
  * en el benchmark v4, `confianza_final` separaba mejor los aciertos de los errores;
  * en el v6 (gold v4, con los dos modelos) el resultado es mixto:
    * para Gemini, `confianza_final` separa algo mejor (AUROC de 0,76 frente a 0,72) y está mejor calibrada (ECE de 7 puntos frente a 15);
    * para gpt-oss es al revés (AUROC de 0,66 frente a 0,74; ECE de 15 frente a 5);
    * con 40 y 34 signos, ninguna de las diferencias es concluyente.

  Se decidirá con las etiquetas de CIMUS y con los factores de `confianza_final` reajustados sobre respuestas que no se usaron para fijarlos.

## Alternativas
* **`UNKNOWN` simple, sin motivo:**
  * *Motivo de descarte:* no permite saber por qué falla el sistema ni priorizar mejoras.
* **Dejar que el modelo se abstenga (`v1_proceso_gen`) también en producción:**
  * *Motivo de descarte:* el corte depende del juicio de cada modelo y no se puede ajustar sin cambiar el prompt y volver a llamar. Se conserva como versión de comparación en el benchmark.
* **Usar la confianza declarada tal cual, sin umbral ajustado ni corrección:**
  * *Motivo de descarte:* la confianza verbalizada de los LLM está mal calibrada y tiende a ser excesiva (se concentra entre 80 y 100 aunque el modelo se equivoque). Por eso el umbral se fija con el benchmark y no en el prompt, y el porcentaje que se muestra es la `confianza_final`, cuya calibración se mide (fiabilidad, ECE, AUROC y curva riesgo-cobertura).
* **Marcar `revisar` cuando la cita no se verifica, en lugar de `UNKNOWN`:**
  * *Motivo de descarte:* una cita que no está en el abstract es justo la señal de alucinación que se quiere bloquear; el equipo decidió tratarla como falta de evidencia.
* **Convertir en `UNKNOWN` cualquier discrepancia (con GO o entre modelos):**
  * *Motivo de descarte:* se perderían los casos con evidencia en conflicto, que son los más valiosos para la revisión experta.
* **Signo `CONTRADICCION` sin preferencia por ningún modelo cuando los dos discrepan:**
  * *Motivo de descarte:* deja sin signo casos que sí tienen evidencia. El equipo prefirió conservar el signo del modelo principal, guardar las dos respuestas y marcar el caso como `revisar`, de modo que la discrepancia queda igualmente visible para el experto.
* **Comparar modelos solo en el benchmark:**
  * *Motivo de descarte:* el equipo prefirió el contraste en todos los casos; con dos planes gratuitos es viable a coste cero, a cambio de más días de ejecución.
* **Dar siempre `+1`/`-1` como resultado final (sin `UNKNOWN`):**
  * *Motivo de descarte:* obligaría a dar por bueno un signo cuando el abstract no lo sostiene. `v2_veredicto` obliga al modelo a elegir, pero el resultado final puede ser `UNKNOWN`, porque lo decide el código.

## Referencias
* **Código del proyecto (estado actual):**
  * `codigo/consulta_gen/respuesta.py`: validación de las dos versiones (`_validar_v2`, `_validar_v1_gen`), verificación de la cita, `UNKNOWN` forzado, `json_invalido`, `baja_confianza` e `incoherencia_respuesta`.
  * `codigo/consulta_gen/esquema.py`: esquemas JSON estrictos (`ESQUEMA_V2` / `ESQUEMA_LISTA_V2`, `ESQUEMA_V1_GEN` / `ESQUEMA_LISTA_V1_GEN`, `CAMPOS_CONTEXTO`), tabla de motivos y umbrales (`UMBRAL_VEREDICTO`, `UMBRAL_CONFIANZA_V1_GEN`, `MIN_CONFIANZA_SIGNO_V1_GEN`).
  * `codigo/consulta_gen/prompt.py`: reglas de las dos versiones.
  * `codigo/consulta_gen/casos.py`: filtro previo `no_menciona_gen` (con `menciona_gen` de `extraer_info/relevancia.py`).
  * `codigo/consulta_gen/limpieza.py`: `forma_comparacion()` y `segmentar_frases()`.
  * `codigo/consulta_gen/resultados.py`: contraste entre modelos y con `Polaridad_GO`, y salida `fase2_resultados.xlsx`.
  * `codigo/consulta_gen/confianza.py`: `confianza_final` y sus factores provisionales.
  * `codigo/evaluacion/evaluar_gold.py`: métricas y calibración sobre el *gold set*.
  * `codigo/extraer_info/polaridad.py`: cierre `sin_evidencia` de los pares sin abstract.
* **Salidas estructuradas:**
  * Groq: [https://console.groq.com/docs/structured-outputs](https://console.groq.com/docs/structured-outputs)
  * Gemini API: [https://ai.google.dev/gemini-api/docs/structured-output](https://ai.google.dev/gemini-api/docs/structured-output)
* **Literatura:**
  * Xiong et al. (2024), *Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs*, ICLR 2024 (sobreconfianza de la confianza verbalizada).
  * Geifman & El-Yaniv (2017), *Selective Classification for Deep Neural Networks*, NeurIPS 2017 (compromiso entre cobertura y precisión al abstenerse).
* **Decisiones relacionadas:** [ADR-001](adr-001-rag-stateless.md) (arquitectura RAG), [ADR-004](adr-004-persistencia-ficheros-locales.md) (registro de respuestas) y [ADR-005](adr-005-eleccion-modelo-coste-cero.md) (elección de los modelos).
