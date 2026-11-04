# Reinterpretación del Papel de las Rutas Biológicas en Biomedicina (scRNA-seq HNSC)

> Herramienta basada en Inteligencia Artificial y en un pipeline RAG sin infraestructura de datos para resolver discrepancias de regulación génica en análisis transcriptómicos de célula única (células NK en cáncer de cabeza y cuello: laringe y faringe).

## 1. Qué es el proyecto y qué problema resuelve

El análisis transcriptómico de célula única (**scRNA-seq**) permite estudiar la expresión génica a nivel individual en poblaciones celulares complejas, como las células _Natural Killer_ (NK) y el microambiente tumoral en carcinomas de cabeza y cuello (**HNSC**: laringe y faringe). Uno de los pasos fundamentales en bioinformática consiste en el análisis de enriquecimiento funcional en rutas biológicas (como las anotadas en Gene Ontology o KEGG).

### El problema: la contradicción de enriquecimiento

En los métodos bioinformáticos convencionales, las anotaciones de las rutas son cualitativas (presencia o ausencia de un gen en la ruta), sin indicar si un gen concreto actúa como **activador** o **inhibidor/represor** de dicha ruta.

Esto genera contradicciones metodológicas directas: si en una ruta conformada por 100 genes encontramos 10 genes sobre-expresados (_up-regulated_) y 12 genes infra-expresados (_down-regulated_), las herramientas clásicas de enriquecimiento reportan que la ruta se encuentra simultáneamente activada e inhibida, y resolver estas contradicciones a mano resulta tedioso y, a veces, inviable.

### La solución

Este proyecto desarrolla un pipeline asistido por **Inteligencia Artificial** que extrae de forma automatizada el rol mecanístico de cada gen a partir de bases curadas (Gene Ontology) y de la literatura biomédica. Para cada gen y ruta, el sistema determina el signo funcional de su contribución (+1 si activa la ruta, -1 si la inhibe, o `UNKNOWN` si la evidencia no es concluyente), siempre respaldado por una **cita literal verificada** del artículo y contrastado con la polaridad curada de Gene Ontology y entre dos modelos de lenguaje. Los casos con evidencia en conflicto se marcan para revisión experta. A partir de esos signos se calcula un **Net Pathway Score** integrado con el _log2 Fold-Change_ de scRNA-seq, transformando las discrepancias en una conclusión biológica cuantitativa y explicable.

La arquitectura completa está descrita en [`ARCHITECTURE.md`](ARCHITECTURE.md).

## 2. Por qué hemos escogido este proyecto y qué queremos conseguir

### Motivación

Escogimos este proyecto por 2 motivos principales:

1. **Impacto biomédico real:** Los tumores de laringe y faringe presentan una elevada heterogeneidad y mecanismos sofisticados de evasión inmunitaria. Resolver las rutas de activación/agotamiento en células inmunitarias es crítico para identificar biomarcadores fiables y potenciales dianas de inmunoterapia. Nuestro equipo se caracteriza por el interés en este tipo de proyectos biomédicos en los que tenemos una ligera experiencia.

2. **Intersección interdisciplinar:** Combina ciencia de datos, bioinformática de célula única (_single-cell RNA-seq_) e ingeniería de IA moderna (modelos de lenguaje e inferencia semántica).

### Objetivo final

Al concluir el proyecto, queremos disponer de un **MVP funcional, reproducible y portable** que:

- Tome como entrada los resultados de enriquecimiento funcional en Gene Ontology que proporciona CIMUS para los genes diferencialmente expresados en células NK de tumores de laringe y faringe.

- Identifique automáticamente los genes en conflicto para rutas ambiguas.

- Recupere la evidencia curada de Gene Ontology y los _abstracts_ de los artículos que la respaldan mediante APIs abiertas (Europe PMC y NCBI), y los procese con dos modelos de lenguaje gratuitos a temperatura 0, con justificación literal verificada (citas trazables).

- Genere un _score_ neto de ruta mecanístico que resuelva, para cada ruta, si los genes implicados la activan o la inhiben en conjunto.

## 3. Alcance: qué entra y qué queda explícitamente fuera

Para garantizar la entrega en plazo y la robustez del sistema, el proyecto sigue la **Opción A: pipeline RAG con modelos de lenguaje externos**, frente a un clasificador biomédico entrenado ([ADR-001](decisions/adr-001-rag-stateless.md)).

### Qué entra en el proyecto

- **Dominio específico:** Células NK del microambiente tumoral de cabeza y cuello (HNSC: laringe y faringe).

- **Ingesta de evidencias:** PMIDs obtenidos de las anotaciones de Gene Ontology (fichero GAF), propagando cada ruta a sus términos descendientes, y descarga de los _abstracts_ desde **Europe PMC** con **NCBI** como respaldo ([ADR-002](decisions/adr-002-europe-pmc-api.md)).

- **Limpieza y partición génica:** Limpieza de los formatos HTML de los _abstracts_ sin alterar la nomenclatura biomédica, una normalización aparte usada solo para verificar citas, y la partición de los genes en dos conjuntos según sean _up_ o _down_, para no mezclar su procedencia.

- **Inferencia estructurada:** Extracción del signo funcional del gen con **dos modelos de lenguaje gratuitos** ([ADR-005](decisions/adr-005-eleccion-modelo-coste-cero.md)) a temperatura 0, con salida JSON estricta y un esquema de signo, estado y motivos que devuelve `UNKNOWN` ante falta de evidencia y marca para revisión los casos en conflicto ([ADR-003](decisions/adr-003-control-alucinaciones-unknown.md)).

- **Evaluación:** Benchmark de tres modelos candidatos sobre un _gold set_ de 60 casos etiquetados a ciegas por expertos.

- **Métrica de resolución:** Integración del signo inferido ponderado por el _log2 Fold-Change_ del dataset scRNA-seq original (_Net Pathway Score_).

- **Entorno de pruebas y reproducibilidad:** _Test harness_ con respuestas emuladas (fixtures/mocks locales) para garantizar testing sin conexión ni dependencia de cuotas de red externas, y registro de todas las respuestas de los modelos ([ADR-004](decisions/adr-004-persistencia-ficheros-locales.md)).

### Qué queda explícitamente fuera

- **Bases de datos y Data Lakes:** Sin PostgreSQL, SQLite, DuckDB, bases vectoriales ni Data Lakehouses (Delta Lake/Iceberg). El estado se guarda solo en ficheros locales: cachés desechables y un registro JSONL de respuestas ([ADR-004](decisions/adr-004-persistencia-ficheros-locales.md)).

- **Modelos de pago:** Solo se usan modelos y planes gratuitos; no se paga ninguna cantidad por inferencia ([ADR-005](decisions/adr-005-eleccion-modelo-coste-cero.md)).

- **Entrenamiento o Fine-Tuning de modelos propios:** No se entrenarán clasificadores BERT biomédicos desde cero ni se ajustarán pesos de LLMs. Se usan modelos ya preentrenados, vía API externa o en local.

- **Acceso a artículos de pago (Paywalls):** La ingesta se limita exclusivamente a resúmenes y artículos _Open Access_ de acceso público.

- **Modelado biológico no lineal / combinatorio:** No se contemplan interacciones génicas de orden superior complejas (efectos epistáticos o condicionales no lineales); el score se fundamenta en una agregación mecanicista sumativa y transparente.

- **Escalado al transcriptoma global (>20.000 genes simultáneos):** El pipeline está diseñado para resolver conjuntos acotados de genes en conflicto por ruta, no para reprocesar el genoma completo en una sola corrida.

## 4. Equipo y roles

| **Nombre y Apellidos** | **Rol principal** | **Correo de contacto**          |
| ---------------------- | ----------------- | ------------------------------- |
| Iria Varela Palmás     | MLOps & NLP engineer| `iria.varela.palmas@rai.usc.es` |
| Luis Pérez Jiménez     | Única voz hacia el equipo clínico & ML engineer| `luis.perez2@rai.usc.es` |
| Pablo Rey Mariño       | Project Manager & Data Analyst | `pablo.rey.marino@rai.usc.es`   |

## 5. Documentación técnica

- **Arquitectura:** [`ARCHITECTURE.md`](ARCHITECTURE.md), con el diagrama de componentes, la responsabilidad de cada pieza y el flujo de datos de principio a fin.
- **Decisiones (ADRs):**

  | ADR | Decisión |
  |---|---|
  | [ADR-001](decisions/adr-001-rag-stateless.md) | Pipeline RAG con un LLM externo en lugar de un clasificador biomédico entrenado. |
  | [ADR-002](decisions/adr-002-europe-pmc-api.md) | Evidencias desde el GAF de Gene Ontology y abstracts de Europe PMC con respaldo en NCBI. |
  | [ADR-003](decisions/adr-003-control-alucinaciones-unknown.md) | Control de alucinaciones: signo, estado y motivos, con verificación de citas y contraste con GO y entre modelos. |
  | [ADR-004](decisions/adr-004-persistencia-ficheros-locales.md) | Persistencia en ficheros locales, sin bases de datos. |
  | [ADR-005](decisions/adr-005-eleccion-modelo-coste-cero.md) | Elección de modelos con coste cero mediante benchmark. |

- **Especificaciones funcionales:**

  | Spec | Funcionalidad |
  |---|---|
  | [`descarga-evidencias-go-pmc.md`](specs/descarga-evidencias-go-pmc.md) | Ingesta de evidencias GO y descarga de abstracts. |
  | [`limpieza-abstracts-particion-genica.md`](specs/limpieza-abstracts-particion-genica.md) | Limpieza de abstracts, normalización para comparar y partición Up/Down. |
  | [`inferencia-llm.md`](specs/inferencia-llm.md) | Inferencia del signo con LLM y validación de la respuesta. |
  | [`benchmark-gold-set.md`](specs/benchmark-gold-set.md) | Gold set etiquetado por expertos y benchmark de modelos. |

## 6. Estructura del repositorio

La documentación de la entrega vive en esta carpeta; el código fuente está en la carpeta `codigo/` de la raíz del repositorio.

```Plaintext
entregas/cu-01-reinterpretacion-biologica/
├── README.md                      # Puerta de entrada: visión de conjunto, objetivos y estructura.
├── ARCHITECTURE.md                # Diagrama de componentes y recorrido del dato.
├── AGENTS.md                      # Instrucciones operativas para asistentes de IA y colaboradores (pendiente).
│
├── decisions/                     # Architecture Decision Records (ADRs):
│   ├── adr-001-rag-stateless.md                  # Pipeline RAG con LLM externo.
│   ├── adr-002-europe-pmc-api.md                 # Ingesta: GAF de GO + Europe PMC + NCBI.
│   ├── adr-003-control-alucinaciones-unknown.md  # Control de alucinaciones.
│   ├── adr-004-persistencia-ficheros-locales.md  # Persistencia en ficheros locales.
│   └── adr-005-eleccion-modelo-coste-cero.md     # Elección de modelos gratuitos.
│
├── specs/                         # Especificaciones funcionales:
│   ├── descarga-evidencias-go-pmc.md
│   ├── limpieza-abstracts-particion-genica.md
│   ├── inferencia-llm.md
│   └── benchmark-gold-set.md
│
├── src/                           # Esquema previsto del código fuente (definicion-src.txt).
└── tests/                         # Pruebas del pipeline (test_pipeline.py, pendiente).

codigo/                            # Código fuente (raíz del repositorio):
├── extraer_info/                  # Fase 1: ingesta (GO, GAF, Europe PMC, NCBI) y Excel de salida.
├── consulta_gen/                  # Fase 2: limpieza, prompts y validación de respuestas del LLM.
├── tools_cimus/                   # Material de CIMUS: Excels de rutas enriquecidas y su script de análisis.
├── data/                          # Ficheros locales (ignorados por git): OBO, GAF y cachés.
└── requirements.txt               # Dependencias de Python.
```

El fichero `.gitignore` está en la raíz del repositorio y excluye el entorno virtual, los ficheros de datos y los temporales. La plantilla de variables de entorno (`.env.example`, con `NCBI_EMAIL`, `NCBI_API_KEY`, `GROQ_API_KEY` y `GEMINI_API_KEY`) está pendiente de crear.
