
#  Pipeline de Resolución scRNA-seq (Células NK en HNSC)

## 0. Análisis Estratégico Global (El Plan Completo)

**Arquitectura elegida:** Pipeline RAG (Retrieval-Augmented Generation) "Stateless" orquestado mediante APIs públicas y LLMs de inferencia rápida, descartando el entrenamiento de modelos propios (Fine-Tuning de BERT) y bases de datos persistentes (Data Lakehouses).

* **Ventajas Globales:**
* **Time-to-Market (Deadline Diciembre):** Garantiza la entrega de un MVP funcional en 6 semanas al eliminar los cuellos de botella del etiquetado manual de datos y la configuración de infraestructuras pesadas.
* **Explicabilidad Clínica (White-Box):** Devuelve la cita literal del artículo científico que justifica la decisión biológica, algo que los modelos BERT clasificadores (cajas negras) no pueden hacer nativamente.
* **Portabilidad:** Cualquier bioinformático puede usar la herramienta clonando el repositorio, sin necesidad de levantar contenedores Docker con bases de datos.


* **Desventajas Globales:**
* **Dependencia de Terceros (Vendor Lock-in):** El sistema queda a merced de la disponibilidad y políticas de precios de las APIs externas (Europe PMC para datos, Groq para inferencia).
* **Escalabilidad Limitada por Diseño:** Funciona perfecto para 50 genes. Si el día de mañana el laboratorio pide analizar un transcriptoma completo de 20.000 genes simultáneos, esta arquitectura colapsará por *rate limits* y habrá que reescribirla hacia un procesamiento Batch/Lakehouse.



---

## 1. Filosofía de Datos (Arquitectura Stateless / In-Memory / YAGNI)

**Decisión:** Cero bases de datos. Ejecución al vuelo en RAM y uso de decoradores de caché (`@lru_cache`) para el tiempo de vida del script.

* **Ventajas:**
* **Cero Deuda Técnica:** Elimina mantenimiento de esquemas, migraciones de datos o gestión de almacenamiento.
* **Frescura de Datos (Real-time):** Cada ejecución lee la literatura publicada hasta el minuto actual, sin preocuparse de si la base de datos local está desactualizada.


* **Desventajas:**
* **Latencia Base:** Pagaréis el coste de red HTTP (descargar papers) en cada nueva ejecución, lo que siempre será más lento que leer de un disco local o un `.parquet`.
* **Volatilidad:** Si se interrumpe la conexión a internet en medio del análisis de R, se pierde el progreso y hay que empezar de cero.



---

## 2. Capa de Ingesta (Valorar)

**Decisión:** Peticiones HTTP asíncronas para descargar los *abstracts* en JSON utilizando PMIDs extraídos previamente de Gene Ontology.

* **Ventajas:**
* **Acceso Directo y Limpio:** La API de Europe PMC devuelve campos JSON muy estructurados (ej. `abstractText`), mucho más limpios que el XML nativo de PubMed.


* **Desventajas:**
* **Rate Limits:** Si no programáis *delays* (retrasos intencionados) en el código, el servidor europeo os devolverá errores `HTTP 429 (Too Many Requests)` o bloqueará vuestra IP de la universidad/laboratorio.
* **Sesgo de Open Access:** Solo accederéis a los *abstracts* públicos. Si la clave biológica está en el cuerpo de un artículo de pago (Paywall), la herramienta será "ciega" a ella.



---

## 3. Capa de Selección y Filtrado (Re-Ranker en Cascada)

**Decisión:** Microfiltro léxico rápido (RegEx/BM25) seguido de un modelo Cross-Encoder ligero en CPU (`ms-marco-MiniLM`) para extraer el Top 3 de abstracts.

* **Ventajas:**
* **Protección del LLM (Signal-to-Noise):** Garantiza que al LLM solo le llegue literatura biológicamente densa, reduciendo drásticamente las alucinaciones.
* **Eficiencia de Costes/Tokens:** Reduce el payload que se envía al LLM de miles de palabras a solo un par de párrafos esenciales.


* **Desventajas:**
* **Sesgo del Modelo Genérico:** El Cross-Encoder propuesto puede estar entrenado en lenguaje general. Existe el riesgo (pequeño, pero real) de que asigne baja puntuación a un paper clave porque no entienda un acrónimo inmunológico muy específico.
* **Pérdida Silenciosa (False Negatives):** Si el filtro léxico inicial (RegEx) es demasiado estricto, descartará abstracts válidos antes de que la IA pueda siquiera evaluarlos.



---

## 4. Capa de Normalización de Texto

**Decisión:** Script Python para limpiar HTML, metadatos y concatenar los textos en formato plano puro.

* **Ventajas:**
* **Ahorro de "Atención":** Los modelos Transformer funcionan mejor cuando no tienen que "prestar atención" a ruido (etiquetas HTML, números de referencia bibliográfica cruzada). Mejora la calidad de la predicción final.


* **Desventajas:**
* **Fragilidad del Regex:** Si la limpieza se hace mediante expresiones regulares mal calibradas, podéis borrar accidentalmente signos matemáticos esenciales biológicamente (ej. borrar el `-` de `IL-6`).



---

## 5. Capa de Ensamblaje e Inferencia (LLM Prompting)

**Decisión:** API ultrarrápida (Groq/Llama-3), `Temperature=0`, técnica *Chain of Thought*, JSON Schema estricto y fallback obligatorio a `UNKNOWN`.

* **Ventajas:**
* **Reproducibilidad Estricta:** Temperatura 0 asegura que el comportamiento es determinista, requisito indispensable para un pipeline científico.
* **Failsafe (Mitigación de riesgos):** Al forzar al LLM a devolver `UNKNOWN` si duda, priorizamos la precisión (no mentir) frente al recall (responder siempre).


* **Desventajas:**
* **Inestabilidad de Esquema (Schema Drift):** Incluso a Temperatura 0, los LLMs a veces rompen el formato JSON (añaden texto antes o después de la llave `{`). Requerirá código defensivo extra en Python para parsear la respuesta de forma segura (ej. usar `json.loads` dentro de un bloque `try/except`).
* **Opacidad del Razonamiento Interno:** Aunque pidas que explique sus pasos, no deja de ser un modelo generativo; la justificación que te da es a posteriori y a veces post-racionalizada.



---

## 6. Capa de Resolución (Integración Matemática en R)

**Decisión:** Multiplicación funcional (LLM Output $\times$ scRNA-seq Fold-Change) para obtener el "Net Pathway Score".

* **Ventajas:**
* **Solución Mecanicista:** Resuelve matemáticamente el problema bioinformático original de la contradicción (up/down) en el árbol jerárquico de Gene Ontology.
* **Integración Natural:** Devuelve un *dataframe* que se puede enchufar directamente a paquetes de R como `clusterProfiler` o `ggplot2`.


* **Desventajas:**
* **Reduccionismo Biológico:** Asume que todas las relaciones biológicas son lineales y sumativas (+1, -1). En biología, a veces un gen activa una ruta solo si otro gen está presente (efectos combinatorios no lineales) que este cálculo simplificado ignorará.



---

## 7. Capa de Ingeniería: "Test Harness" Local (Mocking)

**Decisión:** Archivos JSON locales de prueba (Mocks) para simular las respuestas de la API durante las semanas de desarrollo.

* **Ventajas:**
* **Velocidad de Iteración Táctica:** Permite probar el código a la velocidad del disco duro local (0 latencia) y trabajar sin conexión a internet.
* **Protección (Safety Net):** Evita gastar peticiones gratuitas o ser baneados por las APIs reales mientras se arreglan bugs en el código de R o Python.


* **Desventajas:**
* **Ceguera de Red (Network Blindness):** El entorno de prueba simula un mundo perfecto. No ayuda a programar cómo reaccionará el sistema ante problemas reales (errores 500 del servidor, timeouts, cambios sorpresivos en la API de Europe PMC). Podría generar un susto el día de la integración en producción.