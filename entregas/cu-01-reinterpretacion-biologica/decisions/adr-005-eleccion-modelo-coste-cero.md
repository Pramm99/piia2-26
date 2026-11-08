---
description: Elección de los modelos de lenguaje con la restricción de coste cero, mediante un benchmark de cuatro candidatos gratuitos y dos versiones del prompt sobre un gold set etiquetado por expertos.
state: Aceptado (candidatos actualizados el 2026-11-08; modelos de producción pendientes del benchmark)
---

# ADR 005 - Elección del Modelo de Lenguaje con Coste Cero mediante Benchmark sobre Gold Set

## Decisión
El proyecto **solo usa modelos que no exijan pagar ninguna cantidad**. Los modelos de producción no se eligen a priori, sino mediante un **benchmark de cuatro candidatos gratuitos** sobre un *gold set* etiquetado por expertos. Catálogo y límites comprobados en la documentación oficial el 2026-11-08 (informe «Prompt y modelos gratuitos Fase 2»):

| Candidato | Acceso y límites gratuitos | Papel previsto |
|---|---|---|
| **`gpt-oss-120b`** (pesos abiertos) | Plan gratuito de **Cerebras**: 1 M tokens/día, 5 peticiones/min, esquema JSON estricto. El mismo modelo está en Groq como respaldo. | Favorito para modelo principal (`reasoning_effort` bajo) |
| **`qwen3.8-27b`** (pesos abiertos, otra familia) | Plan gratuito de **Groq**: 200 K tokens/día, 1.000 peticiones/día. Está en *Preview* y puede retirarse; Cerebras sirve los mismos pesos. | Favorito para modelo secundario (sin razonamiento) |
| **Gemini 3.5 Flash-Lite** (cerrado) | Plan gratuito de la API de Gemini. No publica sus cuotas (se ven en AI Studio) e ignora la temperatura. | Referencia *frontier* y alternativa de secundario |
| **`qwen3:8b`** (pesos abiertos) | **Ollama** en local, sin GPU (`gpt-oss:20b` no cabe en 15,7 GB de RAM) | Comparación y plan de contingencia |

Ya no están disponibles los Llama del plan gratuito de Groq (`llama3-8b-8192` se retiró el 2025-08-30, y `llama-3.1-8b-instant` y `llama-3.3-70b-versatile` el 2026-08-16) ni GitHub Models (retirado el 2026-07-30). OpenRouter (50 peticiones/día) y Mistral (límites sin verificar) quedan descartados.

**Dos versiones del prompt:** el benchmark compara también `v0_original` (el prompt de partida, congelado, que pregunta por la ruta) y `v1_proceso` (pregunta por el proceso núcleo y el código compone el signo hasta la ruta), con los mismos casos y el mismo validador. `v0_original` es solo una línea base: no se usa en producción porque envía la dirección de scRNA-seq.

**Gold set:** 60 filas de la hoja `Con_abstract` (con 60 casos solo se distinguen modelos que difieran en unos 12 puntos; el informe recomienda un test ciego de 60-100 casos más un conjunto de desarrollo de 40-60 para ajustar el prompt, y cada caso etiquetado con el signo sobre la ruta y el efecto sobre el proceso para comparar las dos versiones) (detalle en la [spec del benchmark](../specs/benchmark-gold-set.md)), estratificadas por `Polaridad_GO` (`+1`, `-1`, sin signo) e incluyendo casos ambiguos, como el de receptor frente a ligando (CD7 y K12, PMID 10652336), y una proporción suficiente de casos no concluyentes. Las etiqueta el equipo clínico (a través de Luis Pérez, con CIMUS) **sin ver la salida de ningún modelo**, para evitar el sesgo de anclaje.

**Métricas** (las del ADR-003 más las de formato):
* Precisión de las respuestas dadas (`+1`/`-1`), cobertura y recall de `UNKNOWN`.
* Porcentaje de JSON válido y porcentaje de citas verificadas en el abstract.
* Acuerdo con `Polaridad_GO` en los casos en que existe.

**Regla de selección para producción** (ADR-003 exige dos modelos):
* **Modelo principal:** el de mejor precisión entre los que alcancen la cobertura mínima acordada con CIMUS. Si el modelo abierto queda a pocos puntos de Gemini Flash (umbral a fijar con CIMUS), se elige el abierto por reproducibilidad.
* **Modelo secundario:** el siguiente mejor candidato **de otro proveedor o familia**, para que sus errores sean lo más independientes posible de los del principal.
* **Ollama** se mantiene como contingencia si un plan gratuito cambia o deja de ofrecer el modelo elegido.

**Configuración común:** temperatura 0 cuando el proveedor lo permita, salida JSON estructurada, nombre y versión exacta del modelo fijados y registrados en cada respuesta (ADR-004), y el mismo prompt para todos los candidatos. El cliente de inferencia será independiente del proveedor: los mensajes se construyen una sola vez (`PromptLLM.como_mensajes()`) y solo cambia el conector.

## Motivación
1. **Restricción del equipo:** no se pagará ninguna cantidad. Esto descarta los proveedores que solo ofrecen un crédito inicial (Anthropic, OpenAI, xAI), porque una vez agotado obligan a pagar.
2. **El volumen es asumible en planes gratuitos:** con la salida de la Fase 1 sobre todas las rutas de CIMUS (activadas y suprimidas), `v1_proceso` necesita **1.794 casos** por modelo y `v0_original` 4.526, de unos 1.000-1.500 tokens cada uno. Con 1 M de tokens diarios, Cerebras hace una pasada de `v1_proceso` en unos 2-3 días; Groq, con 200 K, en unos 9-13, y es el que marca el ritmo. Es compatible con el calendario si el registro permite reanudar (ADR-004) y los dos modelos corren en paralelo.
3. **Decidir con datos de la propia tarea:** los rankings generales cambian cada pocas semanas y no miden lo que importa aquí: distinguir el efecto del gen del de otra molécula, abstenerse cuando el abstract no es concluyente y citar literalmente. Solo un benchmark sobre casos reales del proyecto responde a eso.
4. **Reproducibilidad:** un modelo de pesos abiertos puede volver a ejecutarse en otra infraestructura aunque el proveedor lo retire. El modelo previsto inicialmente (`llama3-8b-8192` en Groq) ya no está disponible, lo que muestra el riesgo de depender de un único modelo cerrado.
5. **Privacidad aceptable:** los abstracts de PubMed son públicos. Para usuarios del EEE, Google aplica al plan gratuito de Gemini las condiciones de datos del plan de pago (no usa los prompts para mejorar sus productos); Groq no conserva por defecto los datos de inferencia; la política de Cerebras para su plan gratuito no está verificada. Se informará a CIMUS, ya que también se enviarán los prompts.

Aceptamos los compromisos asociados: los catálogos y límites de los planes gratuitos pueden cambiar sin aviso, la ejecución completa con dos modelos lleva varios días y un modelo pequeño en CPU es lento (del orden de un minuto por llamada, a medir en el benchmark).

## Alternativas
* **Modelos *frontier* de pago (Claude, GPT, Grok):**
  * *Motivo de descarte:* incumplen la restricción de coste cero. Sus créditos iniciales son limitados y el de xAI exige además ceder los datos para entrenamiento.
* **Modelo abierto de 30-70B en local:**
  * *Motivo de descarte por ahora:* necesita una GPU de 24-48 GB que el equipo no tiene. Se reconsiderará si CIMUS o el CESGA ofrecen acceso a GPU, porque daría reproducibilidad total sin coste.
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
  * `codigo/consulta_gen/esquema.py` (`PromptLLM.como_mensajes()`, formato de chat estándar `role`/`content` que aceptan Groq, Gemini en modo compatible y Ollama).
  * `codigo/consulta_gen/consultar_gen.py` (primera versión con Groq; usa el modelo retirado `llama3-8b-8192` y se sustituirá por un cliente común compatible con la API de OpenAI para Cerebras, Groq, Gemini y Ollama).
  * `codigo/consulta_gen/prompt.py` (`CONFIG_V0` / `CONFIG_V1`: las dos versiones del prompt del benchmark).
* **Proveedores** (comprobar límites y catálogo en la consola de cada uno antes de ejecutar):
  * Cerebras, modelos y límites: [https://inference-docs.cerebras.ai/models/overview](https://inference-docs.cerebras.ai/models/overview), [https://inference-docs.cerebras.ai/support/rate-limits](https://inference-docs.cerebras.ai/support/rate-limits)
  * Groq, modelos, límites y retiradas: [https://console.groq.com/docs/models](https://console.groq.com/docs/models), [https://console.groq.com/docs/rate-limits](https://console.groq.com/docs/rate-limits), [https://console.groq.com/docs/deprecations](https://console.groq.com/docs/deprecations)
  * Gemini API, límites de uso: [https://ai.google.dev/gemini-api/docs/rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits)
  * Ollama: [https://ollama.com/](https://ollama.com/)
* **Decisiones relacionadas:** [ADR-001](adr-001-rag-stateless.md) (arquitectura RAG con LLM externo), [ADR-003](adr-003-control-alucinaciones-unknown.md) (métricas, esquema de salida y uso de dos modelos) y [ADR-004](adr-004-persistencia-ficheros-locales.md) (registro de respuestas y versión de cada modelo).
