# Pipeline de Resolución scRNA-seq (Células de Laringe y Faringe)  
  
## 0. Análisis Estratégico Global (El Plan B)

Será pipeline especializado de Machine Learning / PLN biomédico basado en preprocesamiento lingüístico (`scispaCy`) y un modelo Transformer State-of-the-Art (`BioLinkBERT-base`) acoplado a un motor desacoplado de inferencia algebraica en memoria.

- **Ventajas Globales:**
    
    - **Cumplimiento Estricto del Mandato Clínico (Sin Conclusiones Generativas):** Desde la empresa se nos prohíbe explícitamente emitir veredictos basados en alucinaciones o razonamientos post-racionalizados de LLMs. Esta arquitectura delega la inferencia a un cálculo matemático determinista sobre ontologías biomédicas verificadas y deja el peso de la conclusión a los profesionales.
        
    - **Especialización y Determinismo Estricto:** Al utilizar un Transformer preentrenado sobre grafos de citas y literatura biomédica (`BioLinkBERT`), la extracción de relaciones dirigidas (_positive/negative regulation_) produce probabilidades calibradas y etiquetas discretas, eliminando la inestabilidad sintáctica y el _schema drift_.
        
    - **Alineación con Estándares Científicos:** La inferencia final queda formalizada en un cálculo determinista desacoplado ($E_i \times W_i$), garantizando que el experimento es auditable, reproducible e integrable con herramientas analíticas consolidadas.
    
- **Desventajas Globales:**
    
    - **Curva de Ingeniería y Recursos de Cómputo:** Requiere gestionar entornos con dependencias pesadas (`PyTorch`, `transformers`, modelos `scispaCy`) y disponer de aceleración por GPU (CUDA) para que la inferencia mantenga una latencia asumible durante el procesamiento en lote.
        
    - **Complejidad de Calibración:** A diferencia de una consulta a una API cerrada, exige configurar umbrales de confianza probabilística para la clasificación multiclase (+1, -1, 0) y gestionar dependencias de entorno de bajo nivel. Es decir, deben establecerse unos umbrales de confianza para categorizar la función del gen cuando los textos sean ambiguos o contradictorios entre si y el resultado debe ser comunicado junto a su umbral de confianza (p.ej "Función activadora con una confianza del 60%").

## 1. Filosofía de Datos (Arquitectura Stateless / In-Memory / YAGNI)

**Decisión:** Ejecución en memoria RAM bajo demanda (evitando la creación de capas de persistencia complejas en disco como bases de datos analíticas o tablas Parquet locales).

- **Ventajas:**
    
    - **Simplicidad de Despliegue:** El código fuente se clona y ejecuta directamente sin requerir la orquestación de sistemas de almacenamiento externos (MinIO, S3 o clústeres Spark).
        
    - **Cero Deuda de Almacenamiento en Git:** Evita inflar el historial del repositorio con datos binarios intermedios o tablas temporales, cumpliendo con la estricta higiene del `.gitignore`.
    
- **Desventajas:**
    
    - **Coste de Red y Procesamiento Repetido:** Cada ejecución vuelve a requerir la descarga de los términos ontológicos de Gene Ontology/QuickGO y la vectorización con el Transformer si no se mantiene la sesión activa.
        
    - **Vulnerabilidad por Caída de Conexión:** Si el pipeline en memoria no implementa reintentos defensivos o estructuras temporales tipo `@lru_cache`, un corte de conexión HTTP durante la consulta ontológica aborta la ejecución.

## 2. Capa de Ingesta (Gene Ontology / QuickGO API)

**Decisión:** Consumo dinámico de anotaciones ontológicas de Procesos Biológicos (BP) y definiciones curadas desde las APIs REST oficiales de Gene Ontology (QuickGO / AmiGO) a partir de los identificadores oficiales de genes (HGNC). Esta capa es transversal e idéntica para todos los planes evaluados.

- **Ventajas:**
    
    - **Datos Biológicos Curados y Formalizados:** Gene Ontology organiza el conocimiento en un Grafo Acíclico Dirigido (DAG) validado por comités científicos, eliminando el ruido y las ambigüedades inherentes al texto libre no curado de la literatura abierta.
        
    - **Estructuración Inmediata:** La información ontológica ya contiene códigos de relación dirigidos (`positively_regulates`, `negatively_regulates`) y niveles de evidencia experimental (EXP, IDA), aportando una base de conocimiento rigurosa desde la entrada.
    
- **Desventajas:**
    
    - **Límites de Consulta (**_**Rate Limits**_**) y Latencia API:** Las llamadas para listas amplias de genes (300-500 genes por ruta) pueden sufrir latencias o requerir pausas intencionadas para evitar bloqueos por parte del servicio de EBI/GO.
        
    - **Cobertura Incompleta:** Ciertos genes poco caracterizados en el contexto específico de tejido epitelial de laringe/faringe pueden carecer de anotaciones funcionales con dirección explícita en la ontología.


## 3. Capa de Selección y Filtrado (Segmentación con `scispaCy`)

**Decisión:** Tokenización de oraciones (_Sentence Tokenization_), Reconocimiento de Entidades Nombradas (NER) y filtrado estricto por co-ocurrencia del gen y el proceso ontológico utilizando modelos biomédicos de `scispaCy` (`en_core_sci_sm` o `en_core_sci_scibert`).

- **Ventajas:**
    
    - **Preservación de la Sintaxis Biomédica:** `scispaCy` gestiona adecuadamente nombres de genes, abreviaturas clínicas y variantes sin fragmentar oraciones de forma errónea como hacen los segmentadores de texto generalistas.
        
    - **Filtrado Semántico de Alta Fidelidad:** Aísla exclusivamente las sentencias donde coexisten la entidad génica y la entidad funcional, reduciendo drásticamente el volumen de texto procesado por el Transformer.
    
- **Desventajas:**
    
    - **Consumo de Memoria en la Carga Inicial:** El modelo de spaCy requiere tiempo y memoria RAM para inicializarse antes de procesar el primer lote de textos.
        
    - **Riesgo de Falso Negativo por Nomenclatura:** Si un gen aparece identificado bajo un sinónimo no contemplado en el diccionario de la entidad o en la ontología, la oración será descartada silenciosamente.


## 4. Capa de Normalización y Marcadores de Entidad

**Decisión:** Inserción de marcadores sintácticos de entidad (_Entity Markers_, p. ej. `[E1]GEN[/E1]` y `[E2]PROCESO[/E2]`) para focalizar la atención del transformador sobre la relación causal exacta en el contexto epitelial tumoral (laringe/faringe).

- **Ventajas:**
    
    - **Enfoque de Atención Mecanicista:** Informa explícitamente a las capas de auto-atención de BioLinkBERT de cuáles son las dos entidades cuya relación funcional se debe cuantificar, aumentando la precisión del clasificador frente al texto crudo.
        
    - **Normalización Estándar:** Estandariza la entrada hacia una longitud de contexto fija, facilitando el procesamiento por lotes (_batch processing_).
    
- **Desventajas:**
    
    - **Sobrecarga de Preprocesamiento:** Añade un paso de manipulación de cadenas de texto y realineamiento de índices antes de la tokenización del propio modelo Transformer.

## 5. Capa de Ensamblaje e Inferencia (BioLinkBERT / PubMedBERT)

**Decisión:** Inferencia con `michiyasunaga/BioLinkBERT-base` (Hugging Face) utilizando una cabeza de clasificación afinada (_fine-tuned_) para predecir el rol regulador en 3 clases discretas: $+1$ (Activador), $-1$ (Inhibidor) y $0$ (Neutro/Sin evidencia).

- **Ventajas:**
    
    - **Arquitectura Basada en Enlaces de Citas:** BioLinkBERT fue preentrenado relacionando literatura conectada en la red de citas biomédicas, destacando en la captura de causalidad entre genes y rutas frente a modelos no especializados.
        
    - **Salida Numérica Directa:** Produce logits y distribuciones de probabilidad calibradas que no requieren parseo defensivo de texto (eliminando la problemática de _Schema Drift_ o alucinaciones de los LLMs generativos).
    
- **Desventajas:**
    
    - **Dependencia de Checkpoints:** Los pesos del modelo (~400 MB a 1.3 GB) no pueden comitearse en el historial de Git; exigen el uso de `git lfs`, caché de Hugging Face o registro de modelos mediante MLflow.
        
    - **Calibración del Umbral:** Requiere fijar un umbral de confianza probabilística para discriminar cuándo clasificar como neutro ($0$) si la predicción es difusa.
        

## 6. Capa de Inferencia Lógica y Resolución (Script de Inferencia)

**Decisión:** Script determinista de autoría propia que cruza la dirección transcriptómica de scRNA-seq ($E_i \in \{+1 \text{ [Up]}, -1 \text{ [Down]}\}$) con el rol funcional extraído por el modelo ($W_i \in \{+1, -1, 0\}$):

$$\text{Impacto}_i = E_i \times W_i$$

- **Ventajas:**
    
    - **Resolución Bioinformática Formal:** Resuelve matemáticamente la paradoja: un gen infra-expresado ($E_i = -1$) que actúa como represor de la ruta ($W_i = -1$) resulta en una contribución positiva ($+1$), revelando la activación neta por desinhibición de la ruta biológica.
        
    - **Interoperabilidad:** Devuelve una matriz estructurada consumible directamente por entornos de análisis bioinformático en Python (Pandas) o R (`clusterProfiler`).
        
- **Desventajas:**
    
    - **Simplificación Monótona:** Asume independencia lineal entre los miembros de la ruta, obviando efectos combinatorios complejos (p. ej., complejos estequiométricos donde la ausencia de un cofactor bloquea toda la cascada).
        

## 7. Capa de Ingeniería: Repositorio y Mocks

**Decisión:** Diseñar un arnés de pruebas local (_test harness_) que aísle la canalización desacoplada mediante dobles de prueba (Mocks en memoria de las respuestas REST de Gene Ontology/QuickGO) y fixtures sintéticos estandarizados, gobernando el ciclo de vida del clasificador `BioLinkBERT` bajo un esquema de control de versiones estricto (Git LFS / MLflow Tracking).

- **Ventajas:**
      
    - **Aislamiento Funcional del Modelo Frente a la Red:** Los tests unitarios desacoplan la latencia y los _rate limits_ de la API de QuickGO del coste computacional de inferencia de `BioLinkBERT`. Permite validar en segundos si la tokenización con `scispaCy` o el formato de las oraciones con marcadores `[E1]...[E2]` sufren regresiones sintácticas ante respuestas ontológicas simuladas.
        
    - **Verificabilidad y Trazabilidad del Pipeline Desacoplado:** Al tener la inferencia separada en dos etapas (extracción de pesos $W_i$ por el clasificador y cálculo algebraico $\text{Impacto}_i = E_i \times W_i$), los mocks permiten inyectar casos límite sintéticos (ej. contradicciones extremas en células de laringe/faringe donde un represor funcional $W_i = -1$ está infra-expresado $E_i = -1$) y verificar formalmente que el producto resuelve $+1$ sin depender del estado ni de la disponibilidad de la base de datos externa.
        
    - **Higiene del Repositorio ante Modelos Pesados:** Permite fijar contratos claros en `.gitignore` y `git lfs` para aislar los binarios del Transformer (`models/*.safetensors`, `*.pt`, de ~400 MB a 1.3 GB) y las cachés de tokens, garantizando que el repositorio conserve únicamente código ligero, esquemas de entrada y registros de ejecuciones reproducibles.
    
- **Desventajas:**
      
    - **Sobrecarga de Mantenimiento por Desacoplamiento de Dos Capas:** A diferencia de una llamada unificada, aquí el _test harness_ debe mantener dos tipos de simulaciones distintas: mocks de las respuestas JSON/anotaciones del DAG de Gene Ontology y fixtures de tensores/tokens para evaluar la cabeza de clasificación de `BioLinkBERT`, aumentando la cantidad de fixtures y tests a sincronizar.
        
    - **Fragilidad ante el Esquema Semántico de la Ontología (_Schema Drift_ Ontológico):** Los mocks locales replican una estructura fija de términos de Gene Ontology (nombres de procesos biológicos, ancestros y relaciones `positively_regulates` / `negatively_regulates`). Si el consorcio GO actualiza identificadores, definiciones o relaciones jerárquicas en el grafo vivo, los tests pasarán en verde con datos sintéticos obsoletos mientras el pipeline real podría fallar al no encontrar las entidades esperadas. Cabe destacar que esto es improbable ya que no es normal que este tipo de bases de datos se actualicen de esta manera.
        
    - **Fricción en Entornos sin Aceleración Hardware:** Si la suite de integración ejecuta los fixtures a través del modelo real de `BioLinkBERT` en lugar de stubear sus _logits_, las pruebas automáticas o ejecuciones locales en máquinas sin soporte CUDA se ralentizan sensiblemente por el coste de paso hacia delante (_forward pass_) del Transformer sobre CPU.