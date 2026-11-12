---
description: Elección de los modelos de lenguaje con la restricción de coste cero, mediante un benchmark de candidatos gratuitos sobre un gold set; principal Gemini 3.5 Flash-Lite y secundario gpt-oss-120b.
state: Aceptado (candidatos actualizados el 2026-11-08; modelo principal decidido el 2026-11-10; secundario confirmado por el equipo el 2026-11-11)
---

# ADR 005 - Elección del Modelo de Lenguaje con Coste Cero mediante Benchmark sobre Gold Set

## Decisión
El proyecto **solo usa modelos que no exijan pagar ninguna cantidad**. Los modelos de producción se eligen con un **benchmark de candidatos gratuitos** sobre un *gold set* de casos reales del proyecto, no por rankings generales. El ADR-003 exige dos modelos:

| Papel | Modelo | Estado |
|---|---|---|
| **Principal** | **Gemini 3.5 Flash-Lite** (`gemini-3.5-flash-lite`, plan gratuito de la API de Gemini) | Decidido por el equipo el 2026-11-10 |
| **Secundario** | **`gpt-oss-120b`** en el plan gratuito de **Groq** (`groq-gpt-oss-120b`, pesos abiertos, otra familia y otro proveedor) | Confirmado por el equipo el 2026-11-11, tras completar el benchmark (100 de 100, sin cortes) |
| **Contingencia** | **`qwen3:8b`** en **Ollama**, en local y sin GPU | Solo si un plan gratuito cambia o deja de ofrecer los modelos elegidos |

**Candidatos descartados o sin usar:**
* **`qwen3.8-27b` en Groq:** descartado el 2026-11-10 por su tasa de JSON inválido (solo 34 de 50 respuestas válidas en una prueba). No se vuelve a usar ni en el benchmark ni en producción (su configuración se conserva en `MODELOS`, sin uso).
* **`gpt-oss-120b` en Cerebras:** está configurado (1 M tokens/día en el plan gratuito), pero no se ha probado, porque Cerebras pide datos bancarios para mostrar la clave.
* Ya no están disponibles los Llama del plan gratuito de Groq (`llama3-8b-8192` se retiró el 2025-08-30, y `llama-3.1-8b-instant` y `llama-3.3-70b-versatile` el 2026-08-16) ni GitHub Models (retirado el 2026-07-30). OpenRouter (50 peticiones/día) y Mistral (límites sin verificar) quedan descartados.

**Por qué Gemini es el principal.** El principal da el signo final y tiene que responder a todas las preguntas; si no responde, la pregunta queda `pendiente` (ADR-003). En el benchmark, Gemini responde a las 100 preguntas con JSON siempre válido en 5,5 minutos; gpt-oss tarda 14,9 minutos y da 4 JSON inválidos. Además, el plan gratuito de Groq (200 K tokens/día) corta a gpt-oss en las ejecuciones largas, y una pasada completa de producción le llevaría unos 15 días (ver Motivación). Como secundario ese retraso es aceptable: mientras no responde, el caso sigue adelante con el principal y solo pierde el contraste entre modelos.

**El secundario es solo el respaldo del principal** (2026-11-12). gpt-oss solo recibe una pregunta si Gemini no responde (cupo agotado, red) o devuelve un JSON que no vale, y entonces decide su respuesta, marcada con `respaldo_secundario` (ADR-003). Si Gemini responde, la pregunta no va a gpt-oss. Así el cupo diario de Groq se reserva para los fallos de Gemini. El contraste de los dos modelos en todas las preguntas (`--contraste`) queda solo para experimentos: en una prueba parcial, gpt-oss casi nunca contradijo a Gemini, pero se abstuvo en el 37 % de sus signos (ADR-003).

**Prompt:** el benchmark usa el mismo prompt y el mismo validador que producción (veredicto obligado y `UNKNOWN` decidido por el código), con las preguntas por proceso núcleo enviadas por gen (spec de inferencia).

**Gold set:** 100 preguntas (gen, PMID, proceso núcleo):
* **Origen:** 65 de genes *up* y 35 de genes *down*, porque producción procesa las dos listas de CIMUS.
* **Casos ambiguos:** incluye, por ejemplo, el de receptor frente a ligando (CD7 y K12, PMID 10652336).
* **Etiquetas:** la mayoría son casos no concluyentes: 20 «+1», 12 «−1», 3 neutros y 65 `UNKNOWN`.

Las etiquetas del *gold set* son las de anotadores Claude a ciegas, con doble etiquetado de todos los casos y un árbitro en los desacuerdos (acuerdo de 99 de 100 entre la etiqueta final y la segunda, kappa 0,98). El equipo decidió el 2026-11-11 quedarse con ellas. Como los anotadores son modelos de lenguaje, parecidos a los evaluados, el acierto medido puede estar inflado frente al de un experto humano, y las cifras se leen con esa cautela. Detalle en la [spec del benchmark](../specs/benchmark-gold-set.md).

**Métricas** (las del ADR-003 más las de formato y coste):
* Exactitud, precisión de los veredictos dados (`+1`, `-1` o `neutro`), cobertura y recall de `UNKNOWN`, con intervalos de confianza por *bootstrap* y la matriz de confusión de 4 clases.
* Porcentaje de JSON válido y porcentaje de citas verificadas en el abstract.
* Acuerdo con `Polaridad_GO` en los casos en que existe.
* Calibración de `confianza_modelo` y `confianza_final` (fiabilidad, ECE, AUROC y curva riesgo-cobertura).
* Latencia, tiempo total, llamadas y tokens.

**Resultados medidos** (2026-11-10, umbral 80):

| Modelo | Respondidas | JSON válido | Exactitud | Precisión de los signos | Cobertura | Recall de `UNKNOWN` | Tiempo |
|---|---|---|---|---|---|---|---|
| Gemini 3.5 Flash-Lite | 100/100 | 100/100 | 84 % (76–91) | 72 % (58–86) | 40 % | 85 % | 5,5 min |
| gpt-oss-120b (Groq) | 100/100 | 96/100 | 85 % (78–92) | 79 % (65–92) | 34 % | 89 % | 14,9 min |

**Desglose por lista** (exactitud, precisión de los signos, cobertura y recall de `UNKNOWN`):

| Genes | Casos | Gemini 3.5 Flash-Lite | gpt-oss-120b (Groq) |
|---|---|---|---|
| *up* | 65 | 83 %, 61 %, 35 %, 82 % | 85 %, 65 %, 31 %, 86 % |
| *down* | 35 | 86 %, 88 %, 49 %, 94 % | 86 %, 100 %, 40 %, 100 % |

* **Genes *down*:** ninguno de los dos rinde peor.
  * Gemini tiene 5 errores: uno de signo opuesto y uno en que da signo con la etiqueta `UNKNOWN`.
  * gpt-oss no da ningún signo equivocado: sus 5 errores son `UNKNOWN` donde la etiqueta tiene signo.
* **Genes *up*:** el error típico de los dos es dar un signo cuando la etiqueta es `UNKNOWN` (9 de 11 errores en Gemini y 7 de 10 en gpt-oss).
* **Acuerdo entre los dos modelos:**
  * dan la misma clase en 87 de 100 casos;
  * cuando los dos dan signo (31 casos), coinciden en 30;
  * el único caso de signos opuestos es G133 (CD6 soluble como bloqueante), que también dudaron los anotadores.
* **Intervalos:** con 35 casos son amplios. La precisión de Gemini en los *down* va del 71 al 100 %, y en los *up*, del 41 al 82 %.

gpt-oss es algo más preciso y más prudente (cobertura del 34 % frente al 40 %), pero tiene 4 JSON inválidos y tarda casi el triple. Las diferencias de exactitud y precisión caben dentro de los intervalos. El papel de cada modelo no cambia: Gemini principal, porque responde a todo y rápido, y gpt-oss secundario, cuya independencia de errores es lo que usa el ADR-003. El equipo confirmó el secundario el 2026-11-11.

**Configuración común** (`codigo/fase2_inferencia/cliente.py`): un único conector compatible con la API de chat de OpenAI (`ClienteOpenAICompatible`) para Groq, Gemini (modo compatible), Cerebras y Ollama. Usa temperatura 0, `seed` y salida JSON estricta con el esquema del prompt cuando el proveedor lo admite. Gemini ignora la temperatura y su modo compatible rechaza `seed` (HTTP 400), así que no se le envía ninguno de los dos. gpt-oss usa `reasoning_effort = "low"`. El nombre exacto del modelo que devuelve el proveedor se guarda en cada llamada (ADR-004). Los mensajes se construyen una sola vez (`PromptLista.como_mensajes()`) y solo cambia la configuración de cada modelo (`MODELOS`). En producción las preguntas de un gen se trocean con el presupuesto por llamada más pequeño de los dos modelos (Groq, 7.500 tokens), para que los dos reciban la misma agrupación.

## Motivación
1. **Restricción del equipo:** no se pagará ninguna cantidad. Esto descarta los proveedores que solo ofrecen un crédito inicial (Anthropic, OpenAI, xAI), porque una vez agotado obligan a pagar.
2. **El volumen es asumible en planes gratuitos:** con la Fase 1 del 2026-11-09 hay 1.694 preguntas (1.123 de las rutas de genes *up* y 571 de las de genes *down*). Con el consumo medido por pregunta en el benchmark (unos 1.430 tokens en Gemini y 1.690 en gpt-oss, con el razonamiento), una pasada completa son del orden de 2,4 M tokens con Gemini y 2,9 M con gpt-oss. A 200 K tokens/día, Groq necesita unos 15 días. Es compatible con el calendario porque el registro permite reanudar sin repetir llamadas (ADR-004) y el secundario puede ir por detrás del principal.
3. **Decidir con datos de la propia tarea:** los rankings generales cambian cada pocas semanas y no miden lo que importa aquí: distinguir el efecto del gen del de otra molécula, no dar un signo cuando el abstract no es concluyente y citar literalmente. Solo un benchmark sobre casos reales del proyecto responde a eso.
4. **Independencia de los errores:** el secundario es de otra familia y otro proveedor, para que sus errores sean lo más independientes posible de los del principal y el contraste del ADR-003 tenga sentido.
5. **Privacidad aceptable:** los abstracts de PubMed son públicos. Para usuarios del EEE, Google aplica al plan gratuito de Gemini las condiciones de datos del plan de pago (no usa los prompts para mejorar sus productos), y Groq no conserva por defecto los datos de inferencia. Se informará a CIMUS, ya que también se enviarán los prompts.

Aceptamos los compromisos asociados:
* **Reproducibilidad:** el principal es un modelo cerrado que el proveedor puede cambiar o retirar. El modelo previsto inicialmente (`llama3-8b-8192` en Groq) ya no está disponible, lo que muestra ese riesgo. Lo compensan el registro de todas las respuestas (ADR-004) y un secundario de pesos abiertos, que puede volver a ejecutarse en otra infraestructura.
* **Cuotas:** Gemini no publica las cuotas de su plan gratuito (solo se ven en AI Studio), y los catálogos y límites pueden cambiar sin aviso.
* **Duración:** la ejecución completa con dos modelos lleva varios días.
* **Contingencia lenta:** un modelo pequeño en CPU es lento: unos 2,7 min por pregunta en una prueba en el portátil del equipo. Además necesita arrancar Ollama con `OLLAMA_CONTEXT_LENGTH=16384`, porque si no recorta el prompt sin avisar.

## Alternativas
* **gpt-oss-120b en Groq como principal:**
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
  * `codigo/fase2_inferencia/cliente.py` (`ConfigModelo`, `MODELOS` con las configuraciones de Gemini, Groq, Cerebras y Ollama, y `ClienteOpenAICompatible`).
  * `codigo/fase2_inferencia/esquema.py` (`PromptLista.como_mensajes()`, formato de chat estándar `role`/`content`).
  * `codigo/fase2_inferencia/prompt.py` (el prompt: `SYSTEM`, `construir_prompt` y `construir_prompt_lista`).
  * `codigo/fase2_inferencia/__main__.py` (modelos por defecto de `python -m fase2_inferencia ejecutar`).
  * `codigo/evaluacion/evaluar_gold.py` y el informe `codigo/evaluacion/informe_gold.txt`.
* **Proveedores** (comprobar límites y catálogo en la consola de cada uno antes de ejecutar):
  * Gemini API, límites de uso: [https://ai.google.dev/gemini-api/docs/rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits)
  * Groq, modelos, límites y retiradas: [https://console.groq.com/docs/models](https://console.groq.com/docs/models), [https://console.groq.com/docs/rate-limits](https://console.groq.com/docs/rate-limits), [https://console.groq.com/docs/deprecations](https://console.groq.com/docs/deprecations)
  * Cerebras, modelos y límites: [https://inference-docs.cerebras.ai/models/overview](https://inference-docs.cerebras.ai/models/overview), [https://inference-docs.cerebras.ai/support/rate-limits](https://inference-docs.cerebras.ai/support/rate-limits)
  * Ollama: [https://ollama.com/](https://ollama.com/)
* **Decisiones relacionadas:** [ADR-001](adr-001-rag-stateless.md) (arquitectura RAG con LLM externo), [ADR-003](adr-003-control-alucinaciones-unknown.md) (métricas, esquema de salida y uso de dos modelos) y [ADR-004](adr-004-persistencia-ficheros-locales.md) (registro de respuestas y versión de cada modelo).
