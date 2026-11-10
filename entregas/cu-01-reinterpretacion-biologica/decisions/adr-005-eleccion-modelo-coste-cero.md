---
description: Elección de los modelos de lenguaje con la restricción de coste cero, mediante un benchmark de candidatos gratuitos sobre un gold set; principal Gemini 3.5 Flash-Lite y secundario gpt-oss-120b en prueba.
state: Aceptado (candidatos actualizados el 2026-11-08; modelo principal decidido el 2026-11-10; secundario pendiente de terminar el benchmark v5)
---

# ADR 005 - Elección del Modelo de Lenguaje con Coste Cero mediante Benchmark sobre Gold Set

## Decisión
El proyecto **solo usa modelos que no exijan pagar ninguna cantidad**. Los modelos de producción se eligen con un **benchmark de candidatos gratuitos** sobre un *gold set* de casos reales del proyecto, no por rankings generales. El ADR-003 exige dos modelos:

| Papel | Modelo | Estado |
|---|---|---|
| **Principal** | **Gemini 3.5 Flash-Lite** (`gemini-3.5-flash-lite`, plan gratuito de la API de Gemini) | Decidido por el equipo el 2026-11-10 |
| **Secundario** | **`gpt-oss-120b`** en el plan gratuito de **Groq** (`groq-gpt-oss-120b`, pesos abiertos, otra familia y otro proveedor) | En prueba: el benchmark v5 se cortó en 6 de 124 preguntas por el límite diario de Groq y se confirmará al terminarlo |
| **Contingencia** | **`qwen3:8b`** en **Ollama**, en local y sin GPU | Solo si un plan gratuito cambia o deja de ofrecer los modelos elegidos |

**Candidatos descartados o sin usar:**
* **`qwen3.8-27b` en Groq:** descartado el 2026-11-10 por su tasa de JSON inválido (34 de 50 respuestas válidas en el benchmark v4). No se vuelve a usar ni en el benchmark ni en producción.
* **`gpt-oss-120b` en Cerebras:** está configurado (1 M tokens/día en el plan gratuito), pero no se ha probado, porque Cerebras pide datos bancarios para mostrar la clave.
* Ya no están disponibles los Llama del plan gratuito de Groq (`llama3-8b-8192` se retiró el 2025-08-30, y `llama-3.1-8b-instant` y `llama-3.3-70b-versatile` el 2026-08-16) ni GitHub Models (retirado el 2026-07-30). OpenRouter (50 peticiones/día) y Mistral (límites sin verificar) quedan descartados.

**Por qué Gemini es el principal.** El principal da el signo final y tiene que responder a todas las preguntas; si no responde, la pregunta queda `pendiente` (ADR-003). Gemini es el único candidato que ha completado el benchmark v5: 124 de 124 respuestas, todas con JSON válido, 82 % de exactitud y unos 8 minutos de ejecución. En cambio, el plan gratuito de Groq (200 K tokens/día) cortó a gpt-oss antes de terminar en los benchmarks v3 (25 de 60), v4 y v5 (6 de 124), y una pasada completa de producción le llevaría unos 17 días (ver Motivación). Como secundario ese retraso es aceptable: mientras no responde, el caso sigue adelante con el principal y solo pierde el contraste entre modelos.

**Versiones del prompt** comparadas en el benchmark con los mismos casos y el mismo validador: `v2_veredicto` (producción: veredicto obligado y `UNKNOWN` decidido por el código) y `v1_proceso_gen` (el modelo puede abstenerse). Las dos preguntan por el proceso núcleo y se envían por gen (spec de inferencia).

> **Histórico.** Hasta el 2026-11-10 el benchmark comparaba `v0_original` (el prompt de partida, que preguntaba por la ruta) y `v1_proceso`; ya no existen en el código. La propuesta inicial del 2026-11-08 era `gpt-oss-120b` en Cerebras como principal y `qwen3.8-27b` como secundario, y la del benchmark v2 era gpt-oss en Groq como principal y Gemini como secundario.

**Gold set (v3):** 124 preguntas (gen, PMID, proceso núcleo) con casos ambiguos, como el de receptor frente a ligando (CD7 y K12, PMID 10652336), y una mayoría de casos no concluyentes: 27 «+1», 13 «−1», 2 neutros y 82 `UNKNOWN`. Hoy las etiquetas son **provisionales**: las pusieron anotadores Claude a ciegas, con doble etiquetado de todos los casos (kappa 0,92) y un árbitro en los 5 desacuerdos. Su acierto está inflado para cualquier modelo parecido, así que las etiquetas que valen son las del equipo clínico (a través de Luis Pérez, con CIMUS), que se pondrán **sin ver la salida de ningún modelo**, para evitar el sesgo de anclaje. Detalle en la [spec del benchmark](../specs/benchmark-gold-set.md).

**Métricas** (las del ADR-003 más las de formato y coste):
* Exactitud, precisión de los veredictos dados (`+1`, `-1` o `neutro`), cobertura y recall de `UNKNOWN`, con intervalos de confianza por *bootstrap* y la matriz de confusión de 4 clases.
* Porcentaje de JSON válido y porcentaje de citas verificadas en el abstract.
* Acuerdo con `Polaridad_GO` en los casos en que existe.
* Calibración de `confianza_modelo` y `confianza_final` (fiabilidad, ECE, AUROC y curva riesgo-cobertura).
* Latencia, tiempo total, llamadas y tokens.

**Resultados medidos** (gold provisional, así que solo orientan):

| Benchmark | Casos | Gemini 3.5 Flash-Lite | gpt-oss-120b (Groq) | qwen3.8-27b (Groq) | qwen3:8b (Ollama) |
|---|---|---|---|---|---|
| v2 (2026-11-09, `v1_proceso_gen`) | 60 | exactitud 90 %, precisión 73 %, JSON 60/60, 3,2 min | 87 %, 69 %, 59/60, 7,7 min | 88 %, 67 %, 46/60 | 52 %, 26 %, 79 s por pregunta |
| v4 (2026-11-10, `v2_veredicto`, umbral 40) | 50 comunes | 72 %, 42 %, 50/50 | 86 %, 60 %, 49/50 | 86 %, 62 %, 34/50 | — |
| v5 (2026-11-10, `v2_veredicto`, umbral 80) | 124 | 82 %, 66 %, 124/124, 8,1 min | 6/124 (cortado) | — | — |

Con el prompt de entonces, el v4 favorecía a gpt-oss. El v5 usa el prompt definitivo, sin umbral, y la comparación entre los dos se cerrará al terminar gpt-oss.

**Configuración común** (`codigo/consulta_gen/cliente.py`): un único conector compatible con la API de chat de OpenAI (`ClienteOpenAICompatible`) para Groq, Gemini (modo compatible), Cerebras y Ollama. Usa temperatura 0, `seed` y salida JSON estricta con el esquema del prompt cuando el proveedor lo admite. Gemini ignora la temperatura y su modo compatible rechaza `seed` (HTTP 400), así que no se le envía ninguno de los dos. gpt-oss usa `reasoning_effort = "low"`. El nombre exacto del modelo que devuelve el proveedor se guarda en cada llamada (ADR-004). Los mensajes se construyen una sola vez (`PromptLista.como_mensajes()`) y solo cambia la configuración de cada modelo (`MODELOS`). En producción las preguntas de un gen se trocean con el presupuesto por llamada más pequeño de los dos modelos (Groq, 7.500 tokens), para que los dos reciban la misma agrupación.

## Motivación
1. **Restricción del equipo:** no se pagará ninguna cantidad. Esto descarta los proveedores que solo ofrecen un crédito inicial (Anthropic, OpenAI, xAI), porque una vez agotado obligan a pagar.
2. **El volumen es asumible en planes gratuitos:** con la Fase 1 del 2026-11-09 hay 1.694 preguntas (1.123 de las rutas de genes *up* y 571 de las de genes *down*). Con el consumo medido por pregunta (unos 1.500 tokens en Gemini en el v5 y unos 2.000 en gpt-oss, con el razonamiento, en el v4), una pasada completa son del orden de 2,5 M tokens con Gemini y 3,4 M con gpt-oss. A 200 K tokens/día, Groq necesita unos 17 días. Es compatible con el calendario porque el registro permite reanudar sin repetir llamadas (ADR-004) y el secundario puede ir por detrás del principal.
3. **Decidir con datos de la propia tarea:** los rankings generales cambian cada pocas semanas y no miden lo que importa aquí: distinguir el efecto del gen del de otra molécula, no dar un signo cuando el abstract no es concluyente y citar literalmente. Solo un benchmark sobre casos reales del proyecto responde a eso.
4. **Independencia de los errores:** el secundario es de otra familia y otro proveedor, para que sus errores sean lo más independientes posible de los del principal y el contraste del ADR-003 tenga sentido.
5. **Privacidad aceptable:** los abstracts de PubMed son públicos. Para usuarios del EEE, Google aplica al plan gratuito de Gemini las condiciones de datos del plan de pago (no usa los prompts para mejorar sus productos), y Groq no conserva por defecto los datos de inferencia. Se informará a CIMUS, ya que también se enviarán los prompts.

Aceptamos los compromisos asociados:
* **Reproducibilidad:** el principal es un modelo cerrado que el proveedor puede cambiar o retirar. El modelo previsto inicialmente (`llama3-8b-8192` en Groq) ya no está disponible, lo que muestra ese riesgo. Lo compensan el registro de todas las respuestas (ADR-004) y un secundario de pesos abiertos, que puede volver a ejecutarse en otra infraestructura.
* **Cuotas:** Gemini no publica las cuotas de su plan gratuito (solo se ven en AI Studio), y los catálogos y límites pueden cambiar sin aviso.
* **Duración:** la ejecución completa con dos modelos lleva varios días.
* **Contingencia lenta:** un modelo pequeño en CPU es lento, con 79 s por pregunta en el benchmark v2 y unos 2,7 min con el prompt actual. El benchmark v3 se paró por eso. Además necesita arrancar Ollama con `OLLAMA_CONTEXT_LENGTH=16384`, porque si no recorta el prompt sin avisar.

## Alternativas
* **gpt-oss-120b en Groq como principal (propuesta del benchmark v2):**
  * *Motivo de descarte:* el límite diario de Groq lo corta en todas las ejecuciones largas, y el principal tiene que responder a todo. Se mantiene como secundario.
* **Modelos *frontier* de pago (Claude, GPT, Grok):**
  * *Motivo de descarte:* incumplen la restricción de coste cero. Sus créditos iniciales son limitados y el de xAI exige además ceder los datos para entrenamiento.
* **Modelo abierto de 30-70B en local:**
  * *Motivo de descarte por ahora:* necesita una GPU de 24-48 GB que el equipo no tiene (`gpt-oss:20b` ya no cabe en los 15,7 GB de RAM del equipo). Se reconsiderará si CIMUS o el CESGA ofrecen acceso a GPU, porque daría reproducibilidad total sin coste.
* **Clasificador biomédico ajustado (BioLinkBERT, PubMedBERT):**
  * *Motivo de descarte:* ya descartado en el ADR-001; además no produce la cita literal que exige el ADR-003.
* **Elegir un modelo sin benchmark, por rankings o reputación:**
  * *Motivo de descarte:* no mide la tarea concreta ni permite justificar la elección ante el tribunal o ante CIMUS.
* **Pre-etiquetar el *gold set* con un modelo grande y que el experto lo corrija:**
  * *Motivo de descarte:* el experto tiende a aceptar la etiqueta propuesta (anclaje), lo que sesgaría el benchmark a favor de ese modelo.
* **Un solo modelo en producción:**
  * *Motivo de descarte:* el ADR-003 usa la discrepancia entre dos modelos como señal de revisión.

## Referencias
* **Código del proyecto:**
  * `codigo/consulta_gen/cliente.py` (`ConfigModelo`, `MODELOS` con las configuraciones de Gemini, Groq, Cerebras y Ollama, y `ClienteOpenAICompatible`).
  * `codigo/consulta_gen/esquema.py` (`PromptLista.como_mensajes()`, formato de chat estándar `role`/`content`).
  * `codigo/consulta_gen/prompt.py` (`CONFIG_V2` y `CONFIG_V1_GEN`: las dos versiones del prompt).
  * `codigo/consulta_gen/__main__.py` (modelos por defecto de `python -m consulta_gen ejecutar`).
  * `codigo/evaluacion/evaluar_gold.py` e informes `codigo/evaluacion/informe_gold_provisional_v2.txt`, `_v4.txt` y `_v5.txt`.
* **Proveedores** (comprobar límites y catálogo en la consola de cada uno antes de ejecutar):
  * Gemini API, límites de uso: [https://ai.google.dev/gemini-api/docs/rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits)
  * Groq, modelos, límites y retiradas: [https://console.groq.com/docs/models](https://console.groq.com/docs/models), [https://console.groq.com/docs/rate-limits](https://console.groq.com/docs/rate-limits), [https://console.groq.com/docs/deprecations](https://console.groq.com/docs/deprecations)
  * Cerebras, modelos y límites: [https://inference-docs.cerebras.ai/models/overview](https://inference-docs.cerebras.ai/models/overview), [https://inference-docs.cerebras.ai/support/rate-limits](https://inference-docs.cerebras.ai/support/rate-limits)
  * Ollama: [https://ollama.com/](https://ollama.com/)
* **Decisiones relacionadas:** [ADR-001](adr-001-rag-stateless.md) (arquitectura RAG con LLM externo), [ADR-003](adr-003-control-alucinaciones-unknown.md) (métricas, esquema de salida y uso de dos modelos) y [ADR-004](adr-004-persistencia-ficheros-locales.md) (registro de respuestas y versión de cada modelo).
