---
description: Elección de los modelos de lenguaje con la restricción de coste cero, mediante un benchmark de tres candidatos gratuitos sobre un gold set etiquetado por expertos.
state: Aceptado (candidatos fijados; modelos de producción pendientes del benchmark)
---

# ADR 005 - Elección del Modelo de Lenguaje con Coste Cero mediante Benchmark sobre Gold Set

## Decisión
El proyecto **solo usa modelos que no exijan pagar ninguna cantidad**. Los modelos de producción no se eligen a priori, sino mediante un **benchmark de tres candidatos gratuitos** sobre un *gold set* etiquetado por expertos:

| Candidato | Acceso | Papel previsto |
|---|---|---|
| **Modelo abierto grande** (p. ej. `gpt-oss-120b` o un modelo Qwen) | Plan gratuito de **Groq** (API) | Favorito para modelo principal |
| **Gemini Flash** | Plan gratuito de la **API de Gemini** (Google AI Studio) | Referencia de modelo *frontier* |
| **Modelo pequeño abierto (7-8B)** | **Ollama** en local, sin GPU | Comparación y plan de contingencia |

**Gold set:** 60 filas de la hoja `Con_abstract` (detalle en la [spec del benchmark](../specs/benchmark-gold-set.md)), estratificadas por `Polaridad_GO` (`+1`, `-1`, sin signo) e incluyendo casos ambiguos, como el de receptor frente a ligando (CD7 y K12, PMID 10652336), y una proporción suficiente de casos no concluyentes. Las etiqueta el equipo clínico (a través de Luis Pérez, con CIMUS) **sin ver la salida de ningún modelo**, para evitar el sesgo de anclaje.

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
2. **El volumen es asumible en planes gratuitos:** los 126 genes de las rutas activadas dan como máximo unos **738 casos (gen, PMID)**, de unos 1.000-1.200 tokens cada uno. Con los límites publicados en noviembre de 2026 (p. ej. del orden de 200.000 tokens diarios en Groq), una pasada completa con un modelo lleva unos 4-5 días, compatible con el calendario si el registro permite reanudar (ADR-004).
3. **Decidir con datos de la propia tarea:** los rankings generales cambian cada pocas semanas y no miden lo que importa aquí: distinguir el efecto del gen del de otra molécula, abstenerse cuando el abstract no es concluyente y citar literalmente. Solo un benchmark sobre casos reales del proyecto responde a eso.
4. **Reproducibilidad:** un modelo de pesos abiertos puede volver a ejecutarse en otra infraestructura aunque el proveedor lo retire. El modelo previsto inicialmente (`llama3-8b-8192` en Groq) ya no está disponible, lo que muestra el riesgo de depender de un único modelo cerrado.
5. **Privacidad aceptable:** los abstracts de PubMed son públicos. Los planes gratuitos pueden usar los datos enviados para entrenar sus modelos; se informará a CIMUS, ya que también se enviarán los prompts.

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
  * `codigo/consulta_gen/consultar_gen.py` (primera versión con Groq; usa el modelo retirado `llama3-8b-8192` y debe actualizarse).
* **Proveedores** (comprobar límites y catálogo en la consola de cada uno antes de ejecutar):
  * Groq, límites de uso: [https://console.groq.com/docs/rate-limits](https://console.groq.com/docs/rate-limits)
  * Gemini API, límites de uso: [https://ai.google.dev/gemini-api/docs/rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits)
  * Ollama: [https://ollama.com/](https://ollama.com/)
* **Decisiones relacionadas:** [ADR-001](adr-001-rag-stateless.md) (arquitectura RAG con LLM externo), [ADR-003](adr-003-control-alucinaciones-unknown.md) (métricas, esquema de salida y uso de dos modelos) y [ADR-004](adr-004-persistencia-ficheros-locales.md) (registro de respuestas y versión de cada modelo).
