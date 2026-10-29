---
description: Adopción de una arquitectura RAG Stateless con LLMs rápidos e inferencia en memoria en lugar de un clasificador BERT local desacoplado.
state: Aceptado
---

# ADR 001 - Pipeline RAG Stateless para la Resolución Transcriptómica en Células de Laringe y Faringe

## Decisión
Se decide implementar una arquitectura basada en un pipeline **RAG (Retrieval-Augmented Generation) "Stateless"** orquestado mediante APIs públicas (Europe PMC / QuickGO) y modelos LLM externos de inferencia rápida (por ejemplo Llama-3 vía Groq) con ejecución en memoria RAM (`@lru_cache`). 

Se descarta el desarrollo y mantenimiento de un modelo clasificador Transformer local entrenado/ajustado ad-hoc (`BioLinkBERT-base` acoplado con `scispaCy`) y la persistencia en bases de datos locales o Lakehouses.

## Motivación
El objetivo del proyecto es resolver las contradicciones biológicas en análisis scRNA-seq (rutas enriquecidas con genes up-regulados y down-regulados simultáneamente en células de laringe y faringe), determinando la contribución cualitativa y mecanicista de cada gen (+1, -1 o 0) respecto a la activación de la ruta.

La elección de esta arquitectura se fundamenta en las siguientes razones:

1. **Principio de Simplicidad y YAGNI:** El volumen de entidades a procesar por ruta es acotado (decenas o cientos de genes clave, no un transcriptoma completo continuo de 20.000 genes simultáneos). Adoptar una infraestructura pesada antes de validar el valor clínico añade complejidad innecesaria.
2. **Resultados suficientemente buenos y trazabilidad clínica (White-Box):** La aproximación generativa mediante RAG permite extraer no solo el signo de regulación, sino la justificación contextual y la cita literal del artículo científico que lo respalda. Esto aporta una explicabilidad inmediata y legible para el profesional biomédico, superando a los clasificadores locales que devuelven probabilidades opacas sin contexto textual.
3. **Time-to-Market y Portabilidad:** Al operar sin bases de datos intermedias persistentes (stateless / in-memory) ni dependencias pesadas de aceleración hardware (PyTorch/CUDA), cualquier investigador o bioinformático puede clonar el repositorio y ejecutar el pipeline directamente en su entorno local sin orquestar contenedores pesados ni sincronizar checkpoints de pesos neuronales.
4. **Higiene del Repositorio:** Evita almacenar modelos binarios voluminosos en Git o recurrir a Git LFS/MLflow para artefactos de cientos de megabytes en fases tempranas del desarrollo.

Aceptamos los compromisos asociados (latencia dependiente de la red HTTP externa, *rate limits* en APIs públicas y necesidad de un esquema de salida JSON estricto a `Temperature=0` con fallback a `UNKNOWN`) como trade-offs asumibles frente a la agilidad y calidad de respuesta que ofrece la opción RAG.

## Alternativas
Se evaluó en profundidad la siguiente alternativa principal:

* **Opción B — Clasificador biomédico local desacoplado (`scispaCy` + `BioLinkBERT-base` + script de inferencia algebraica):**
  * *Descripción:* Pipeline basado en tokenización clínica/NER con `scispaCy`, inserción de marcadores sintácticos de entidad (`[E1]GEN[/E1]` y `[E2]PROCESO[/E2]`), clasificación multiclase formal mediante `BioLinkBERT-base` y resolución posterior del impacto neto ($E_i \times W_i$).
  * *Motivo de descarte:* **Complejidad desproporcionada para el estado actual del proyecto.** Aunque ofrecía un determinismo estricto y ausencia de alucinaciones sintácticas, requería calibrar umbrales probabilísticos multiclase para textos ambiguos, gestionar dependencias complejas (`torch`, `transformers`, modelos spaCy), disponer de GPUs dedicadas para evitar latencias prohibitivas en inferencia CPU, y mantener arneses de pruebas locales (*mocks* y *fixtures*) con sobrecarga de sincronización de tensores y esquemas ontológicos. Los resultados obtenidos con la Opción A son lo suficientemente sólidos y explicables como para preferir su simpleza operativa.

## Referencias
* **Documentación del proyecto:**
  * `PlanesViables/OpcionA.md` y `PlanesViables/OpcionB.md` (análisis comparativo detallado de arquitecturas).
* **APIs y modelos:**
  * Documentación de la API REST de Europe PMC: [https://europepmc.org/RestfulWebService](https://europepmc.org/RestfulWebService)
  * Referencia de inferencia y esquemas estructurados de Groq / Llama-3: [https://console.groq.com/docs](https://console.groq.com/docs)
  * Modelo `BioLinkBERT`: Yasunaga et al., *LinkBERT: Pre-training Language Models with Document Links* ([Hugging Face Model Hub](https://huggingface.co/michiyasunaga/BioLinkBERT-base)).
* **Patrones arquitectónicos:**
  * YAGNI (*You Aren't Gonna Need It*) y diseño de pipelines RAG en memoria / in-process.