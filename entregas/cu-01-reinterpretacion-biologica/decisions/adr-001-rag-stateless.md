---
description: Adopción de una arquitectura RAG con LLMs externos gratuitos y sin infraestructura de datos, en lugar de un clasificador BERT local desacoplado.
state: Aceptado (2026-10-28; la persistencia se concreta en el ADR-004 y los modelos en el ADR-005; texto alineado con el código el 2026-11-10)
---

# ADR 001 - Pipeline RAG sin Infraestructura de Datos para la Resolución Transcriptómica en Células NK del Microambiente Tumoral de Cabeza y Cuello (HNSC)

## Decisión
Se decide implementar una arquitectura basada en un pipeline **RAG (Retrieval-Augmented Generation)**, que se apoya en tres elementos:
* **Fuentes abiertas:** los ficheros oficiales de Gene Ontology (OBO y GAF) y las APIs públicas de Europe PMC, NCBI (E-utilities, y GeneRIF vía MyGene.info), HGNC y UniProt ([ADR-002](adr-002-europe-pmc-api.md)).
* **Modelos de lenguaje externos y gratuitos:** hoy Gemini 3.5 Flash-Lite como principal y gpt-oss-120b en Groq como secundario ([ADR-005](adr-005-eleccion-modelo-coste-cero.md)).
* **Sin infraestructura de datos:** ni servidores ni bases de datos. El estado se guarda solo en ficheros locales: cachés desechables y un registro de respuestas ([ADR-004](adr-004-persistencia-ficheros-locales.md)).

Se descarta el desarrollo y mantenimiento de un modelo clasificador Transformer local entrenado/ajustado ad-hoc (`BioLinkBERT-base` acoplado con `scispaCy`) y la persistencia en bases de datos locales o Lakehouses.

## Motivación
El objetivo del proyecto es resolver las contradicciones biológicas en análisis scRNA-seq (rutas enriquecidas con genes up-regulados y down-regulados simultáneamente en células NK de tumores de laringe y faringe), determinando la contribución cualitativa y mecanicista de cada gen respecto a la activación de la ruta: `+1` si la activa, `-1` si la inhibe, `neutro` si no la cambia o `UNKNOWN` si la evidencia no es concluyente.

La elección de esta arquitectura se fundamenta en las siguientes razones:

1. **Principio de Simplicidad y YAGNI:** El volumen de entidades a procesar por ruta es acotado (decenas o cientos de genes clave, no un transcriptoma completo continuo de 20.000 genes simultáneos). Adoptar una infraestructura pesada antes de validar el valor clínico añade complejidad innecesaria.
2. **Trazabilidad clínica (White-Box):** La aproximación generativa mediante RAG permite extraer no solo el signo de regulación, sino la justificación contextual y la cita literal del artículo científico que lo respalda. Esto aporta una explicabilidad inmediata y legible para el profesional biomédico, superando a los clasificadores locales que devuelven probabilidades opacas sin contexto textual.
3. **Time-to-Market y Portabilidad:** Al operar sin bases de datos ni servicios (solo ficheros locales) y sin dependencias pesadas de aceleración hardware (PyTorch/CUDA), cualquier investigador o bioinformático puede clonar el repositorio y ejecutar el pipeline directamente en su entorno local. No hace falta orquestar contenedores pesados ni sincronizar checkpoints de pesos neuronales. Las dependencias de Python son `requests`, `pandas` y `openpyxl`.
4. **Higiene del Repositorio:** Evita almacenar modelos binarios voluminosos en Git o recurrir a Git LFS/MLflow para artefactos de cientos de megabytes en fases tempranas del desarrollo.

Aceptamos los compromisos asociados como trade-offs asumibles frente a la agilidad y calidad de respuesta que ofrece la opción RAG:
* latencia dependiente de la red HTTP externa;
* *rate limits* y límites diarios en los planes gratuitos;
* necesidad de un esquema de salida JSON estricto y de comprobaciones automáticas de la respuesta. La temperatura es 0 cuando el proveedor lo admite (Gemini la ignora). El modelo siempre da un veredicto con su confianza, y el código decide `UNKNOWN` cuando la cita no se verifica o la confianza no llega al umbral.

El control de alucinaciones de la salida del LLM (esquema de signo, estado y motivos, verificación automática de la cita, umbral de confianza y contraste con Gene Ontology y entre dos modelos) se detalla en el [ADR-003](adr-003-control-alucinaciones-unknown.md).

## Alternativas
Se evaluó en profundidad la siguiente alternativa principal:

* **Opción B — Clasificador biomédico local desacoplado (`scispaCy` + `BioLinkBERT-base` + script de inferencia algebraica):**
  * *Descripción:* Pipeline basado en tokenización clínica/NER con `scispaCy`, inserción de marcadores sintácticos de entidad (`[E1]GEN[/E1]` y `[E2]PROCESO[/E2]`), clasificación multiclase formal mediante `BioLinkBERT-base` y resolución posterior del impacto neto ($E_i \times W_i$).
  * *Motivo de descarte:* **Complejidad desproporcionada para el estado actual del proyecto.** Aunque ofrecía un determinismo estricto y ausencia de alucinaciones sintácticas, tenía varios costes:
    * calibrar umbrales probabilísticos multiclase para textos ambiguos;
    * gestionar dependencias complejas (`torch`, `transformers`, modelos spaCy);
    * disponer de GPUs dedicadas para evitar latencias prohibitivas en inferencia CPU;
    * mantener *fixtures* de tensores y tokens para el clasificador, además de los *mocks* de red que ambas opciones necesitan.

    Se espera que la Opción A ofrezca una explicabilidad suficiente con menor coste operativo. Esta hipótesis se valida con el benchmark sobre el *gold set* ([spec del benchmark](../specs/benchmark-gold-set.md)), etiquetado a ciegas con doble etiqueta.

Durante el avance del proyecto el equipo descartó también dos piezas, porque no son compatibles con la solución adoptada:

* **Reranker de abstracts (#7):**
  * *Motivo de descarte:* los abstracts no salen de una búsqueda abierta que haya que ordenar, sino de los PMIDs curados del GAF y de fuentes ya filtradas por gen y ruta, y todos se envían al LLM, que decide con una cita verificada. Un filtro previo de relevancia, medido el 2026-11-12, perdía el 34 % de los signos ([spec de inferencia](../specs/inferencia-llm.md)).
* **Harness para el LLM (#11):**
  * *Motivo de descarte:* cada pregunta es una llamada sin estado, con un prompt y un esquema JSON fijos, y la validación, el contraste con GO y el registro los hace el código ([ADR-003](adr-003-control-alucinaciones-unknown.md), [ADR-004](adr-004-persistencia-ficheros-locales.md)).

## Referencias
* **Documentación del proyecto:**
  * [`docs/planes-viables/OpcionA.md`](../docs/planes-viables/OpcionA.md) y [`docs/planes-viables/OpcionB.md`](../docs/planes-viables/OpcionB.md) (análisis comparativo detallado de arquitecturas).
  * [ADR-002](adr-002-europe-pmc-api.md) (fuentes de evidencia), [ADR-003](adr-003-control-alucinaciones-unknown.md) (control de alucinaciones), [ADR-004](adr-004-persistencia-ficheros-locales.md) (persistencia en ficheros locales) y [ADR-005](adr-005-eleccion-modelo-coste-cero.md) (elección de los modelos).
* **APIs y modelos:**
  * Documentación de la API REST de Europe PMC: [https://europepmc.org/RestfulWebService](https://europepmc.org/RestfulWebService)
  * Gemini API: [https://ai.google.dev/gemini-api/docs](https://ai.google.dev/gemini-api/docs)
  * Groq, modelos y salidas estructuradas: [https://console.groq.com/docs](https://console.groq.com/docs)
  * Modelo `BioLinkBERT`: Yasunaga et al., *LinkBERT: Pre-training Language Models with Document Links* ([Hugging Face Model Hub](https://huggingface.co/michiyasunaga/BioLinkBERT-base)).
* **Patrones arquitectónicos:**
  * YAGNI (*You Aren't Gonna Need It*) y diseño de pipelines RAG sin infraestructura de datos.
