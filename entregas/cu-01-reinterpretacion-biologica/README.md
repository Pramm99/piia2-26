# Reinterpretación del Papel de las Rutas Biológicas en Biomedicina (scRNA-seq HNSC)

> Herramienta basada en Inteligencia Artificial y en un pipeline RAG sin infraestructura de datos para resolver discrepancias de regulación génica en análisis transcriptómicos de célula única (células NK en cáncer de cabeza y cuello: laringe y faringe).

## 1. Qué es el proyecto y qué problema resuelve

El análisis transcriptómico de célula única (**scRNA-seq**) permite estudiar la expresión génica a nivel individual en poblaciones celulares complejas, como las células _Natural Killer_ (NK) y el microambiente tumoral en carcinomas de cabeza y cuello (**HNSC**: laringe y faringe). Uno de los pasos fundamentales en bioinformática consiste en el análisis de enriquecimiento funcional en rutas biológicas (como las anotadas en Gene Ontology o KEGG).

### El problema: la contradicción de enriquecimiento

En los métodos bioinformáticos convencionales, las anotaciones de las rutas son cualitativas (presencia o ausencia de un gen en la ruta), sin indicar si un gen concreto actúa como **activador** o **inhibidor/represor** de dicha ruta.

Esto genera contradicciones metodológicas directas: si en una ruta conformada por 100 genes encontramos 10 genes sobre-expresados (_up-regulated_) y 12 genes infra-expresados (_down-regulated_), las herramientas clásicas de enriquecimiento reportan que la ruta se encuentra simultáneamente activada e inhibida, y resolver estas contradicciones a mano resulta tedioso y, a veces, inviable. CIMUS entrega dos listas de rutas enriquecidas: las de genes _up_ («rutas activadas») y las de genes _down_ («rutas suprimidas»). Esos nombres son la lectura ingenua que este proyecto pone en duda, no una conclusión.

### La solución

Este proyecto desarrolla un pipeline asistido por **Inteligencia Artificial** que extrae de forma automatizada el rol mecanístico de cada gen a partir de bases curadas (Gene Ontology) y de la literatura biomédica. Para cada gen y ruta, el sistema determina el signo funcional de su contribución:
- `+1` si el gen activa la ruta;
- `-1` si la inhibe;
- `neutro` si la evidencia muestra que no la cambia (también las inmunoglobulinas, que no activan ni inhiben ninguna ruta);
- `UNKNOWN` si la evidencia no es concluyente o no la hay.

El signo puede venir de dos sitios:
- **De Gene Ontology**, cuando su polaridad curada basta (triaje `aceptar_GO`). En ese caso no se consulta ningún modelo.
- **De dos modelos de lenguaje que leen los _abstracts_.** Su veredicto solo se acepta con una **cita literal verificada** del artículo y con la confianza suficiente, o, si no la alcanza, cuando coincide con la polaridad curada de Gene Ontology. Además, se contrasta con la polaridad de Gene Ontology y entre los dos modelos. Los casos con evidencia en conflicto se marcan para revisión experta.

A partir de esos signos se calcula un **Net Pathway Score**, integrado con la dirección de expresión de cada gen y contrastado con su _log2 Fold-Change_, que transforma las discrepancias en una conclusión biológica cuantitativa y explicable.

La arquitectura completa está descrita en [`ARCHITECTURE.md`](ARCHITECTURE.md).

## 2. Por qué hemos escogido este proyecto y qué queremos conseguir

### Motivación

Escogimos este proyecto por 2 motivos principales:

1. **Impacto biomédico real:** Los tumores de laringe y faringe presentan una elevada heterogeneidad y mecanismos sofisticados de evasión inmunitaria. Resolver las rutas de activación/agotamiento en células inmunitarias es crítico para identificar biomarcadores fiables y potenciales dianas de inmunoterapia. Nuestro equipo se caracteriza por el interés en este tipo de proyectos biomédicos en los que tenemos una ligera experiencia.

2. **Intersección interdisciplinar:** Combina ciencia de datos, bioinformática de célula única (_single-cell RNA-seq_) e ingeniería de IA moderna (modelos de lenguaje e inferencia semántica).

### Objetivo final

Al concluir el proyecto, queremos disponer de un **MVP funcional, reproducible y portable** que:

- Tome como entrada los resultados de enriquecimiento funcional en Gene Ontology que proporciona CIMUS para los genes diferencialmente expresados en células NK de tumores de laringe y faringe: las dos listas, la de genes _up_ y la de genes _down_.

- Determine el signo funcional de **cada par gen–ruta** de esas listas (3.172 pares de 224 genes en la ejecución del 2026-11-09), para poder resolver las rutas ambiguas.

- Recupere la evidencia curada de Gene Ontology y los _abstracts_ que la respaldan mediante APIs abiertas y gratuitas, y los procese con dos modelos de lenguaje gratuitos con justificación literal verificada (citas trazables).

- Genere un _score_ neto de ruta mecanístico que resuelva, para cada ruta, si los genes implicados la activan o la inhiben en conjunto.

## 3. Alcance: qué entra y qué queda explícitamente fuera

Para garantizar la entrega en plazo y la robustez del sistema, el proyecto sigue la **Opción A: pipeline RAG con modelos de lenguaje externos**, frente a un clasificador biomédico entrenado ([ADR-001](decisions/adr-001-rag-stateless.md)).

### Qué entra en el proyecto

- **Dominio específico:** Células NK del microambiente tumoral de cabeza y cuello (HNSC: laringe y faringe).

- **Tamaño que sí entra:** una ejecución con las dos listas de CIMUS:
  - 392 rutas: 314 en la de genes _up_ y 78 en la de genes _down_. Son 352 términos GO distintos, porque 40 salen en las dos listas.
  - 3.172 pares gen–ruta de 224 genes.
  - Entre 2 y 26 genes por ruta, con una mediana de 7.

  Listas mucho mayores o de otro tejido no se han probado.

- **Ingesta de evidencias** ([ADR-002](decisions/adr-002-europe-pmc-api.md)):
  - PMIDs de las anotaciones de Gene Ontology (fichero GAF), propagando cada ruta a todo su subárbol de términos.
  - Para los pares sin _abstract_ en el GAF, PMIDs de **NCBI GeneRIF** (vía MyGene.info) y de una búsqueda dirigida en **Europe PMC**.
  - Descarga del título y el _abstract_ desde **Europe PMC**, con **NCBI** como respaldo.
  - Las **inmunoglobulinas** (lista de HGNC) se apartan como neutras, con la función de la Ig completa según **UniProt**.
  - Un **triaje del signo GO** acepta sin LLM los pares cuya polaridad curada basta y cierra como `UNKNOWN` los que no tienen ningún _abstract_.

- **Limpieza:** Limpieza de los formatos HTML de los _abstracts_ sin alterar la nomenclatura biomédica ni recortar el texto, y una normalización aparte usada solo para verificar citas. Cada fila conserva su lista de origen (`Estado_Original`), de la que sale la dirección del gen (_up_ o _down_) que usará el scoring.

- **Inferencia estructurada:** Extracción del signo funcional con **dos modelos de lenguaje gratuitos** ([ADR-005](decisions/adr-005-eleccion-modelo-coste-cero.md)): Gemini 3.5 Flash-Lite como principal y gpt-oss-120b (Groq) como secundario. La salida es JSON estricto y el modelo siempre da un veredicto y su confianza. El código pone `UNKNOWN` cuando la cita no se verifica o la confianza no llega al umbral (salvo que el veredicto coincida con la polaridad de GO), y marca para revisión los casos en conflicto ([ADR-003](decisions/adr-003-control-alucinaciones-unknown.md)).

- **Evaluación:** Benchmark de los modelos candidatos sobre un _gold set_ de 100 preguntas (65 de genes _up_ y 35 de genes _down_), con etiquetado a ciegas y doble etiqueta de cada caso ([spec](specs/benchmark-gold-set.md)).

- **Métrica de resolución:** Integración del signo inferido con la dirección de expresión de cada gen en el dataset original (_Net Pathway Score_), implementada según la [spec de scoring](specs/scoring-net-pathway-score.md) (`python -m fase3_scoring`). Todos los genes pesan igual; el _log2 Fold-Change_ de CIMUS da un segundo score de sensibilidad que señala las rutas cuya conclusión depende de cuánto cambia cada gen.

- **Reproducibilidad:**
  - registro de todas las respuestas de los modelos, que permite reanudar una ejecución y regenerar los resultados sin volver a llamar ([ADR-004](decisions/adr-004-persistencia-ficheros-locales.md));
  - un cliente simulado (`ClienteSimulado`) que permite probar el pipeline sin red ni cuotas;
  - pruebas con `pytest` en `codigo/tests/` (limpieza, validación, contraste, ejecución reanudable, ingesta y scoring), sin red: las APIs y los modelos se simulan.

### Qué queda explícitamente fuera

- **Bases de datos y Data Lakes:** Sin PostgreSQL, SQLite, DuckDB, bases vectoriales ni Data Lakehouses (Delta Lake/Iceberg). El estado se guarda solo en ficheros locales: cachés desechables y un registro JSONL de respuestas ([ADR-004](decisions/adr-004-persistencia-ficheros-locales.md)).

- **Modelos de pago:** Solo se usan modelos y planes gratuitos; no se paga ninguna cantidad por inferencia ([ADR-005](decisions/adr-005-eleccion-modelo-coste-cero.md)).

- **Entrenamiento o Fine-Tuning de modelos propios:** No se entrenarán clasificadores BERT biomédicos desde cero ni se ajustarán pesos de LLMs. Se usan modelos ya preentrenados, vía API externa o en local.

- **Limpieza de la lista de rutas de entrada:** No se agrupan ni se eliminan las rutas redundantes del enriquecimiento (p. ej. «X», «regulation of X» y «positive regulation of X»). Cada Excel de entrada puede traer rutas distintas y redundancias nuevas, así que esa limpieza es un paso previo al proyecto: el pipeline procesa la lista tal como llega, y cada término GO se puntúa por separado.

- **Texto completo de los artículos:** Solo se descargan el título y el _abstract_ de PubMed. No se descarga ningún artículo completo, ni de acceso abierto ni de pago.

- **Modelado biológico no lineal / combinatorio:** No se contemplan interacciones génicas de orden superior complejas (efectos epistáticos o condicionales no lineales); el score se fundamenta en una agregación mecanicista sumativa y transparente.

- **Escalado al transcriptoma global (>20.000 genes simultáneos):** El pipeline está diseñado para los genes de las rutas enriquecidas que entrega CIMUS (unos cientos de genes), no para reprocesar el genoma completo en una sola corrida.

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
  | [ADR-003](decisions/adr-003-control-alucinaciones-unknown.md) | Control de alucinaciones: signo, estado y motivos, con verificación de citas, umbral de confianza y contraste con GO y entre modelos. |
  | [ADR-004](decisions/adr-004-persistencia-ficheros-locales.md) | Persistencia en ficheros locales, sin bases de datos. |
  | [ADR-005](decisions/adr-005-eleccion-modelo-coste-cero.md) | Elección de modelos con coste cero mediante benchmark. |

- **Especificaciones funcionales:**

  | Spec | Funcionalidad |
  |---|---|
  | [`descarga-evidencias-go-pmc.md`](specs/descarga-evidencias-go-pmc.md) | Ingesta de evidencias GO y descarga de abstracts. |
  | [`limpieza-abstracts-particion-genica.md`](specs/limpieza-abstracts-particion-genica.md) | Limpieza de abstracts, normalización para comparar y dirección del gen. |
  | [`inferencia-llm.md`](specs/inferencia-llm.md) | Inferencia del signo con LLM y validación de la respuesta. |
  | [`benchmark-gold-set.md`](specs/benchmark-gold-set.md) | Gold set etiquetado a ciegas y benchmark de modelos. |
  | [`scoring-net-pathway-score.md`](specs/scoring-net-pathway-score.md) | Agregación de los artículos de cada par y *Net Pathway Score* de cada ruta (Fase 3). |

- **Limitaciones conocidas:** [`docs/limitacion-pares-sin-abstract.md`](docs/limitacion-pares-sin-abstract.md) (pares gen–ruta sin ningún _abstract_).
- **Gestión de tareas:** [`DOR.md`](DOR.md) (cuándo una tarea puede empezar), [`DOD.md`](DOD.md) (cuándo está terminada) y [`TABLERO.md`](TABLERO.md) (ciclo del tablero, sistema de bloqueos y revisión en cada reunión). Plantillas de issue en [`docs/plantillas-issue/`](docs/plantillas-issue/).

## 6. Estructura del repositorio

Todo el trabajo del equipo vive en esta carpeta, como pide el repositorio de la asignatura: la documentación, el código fuente (`codigo/`) y el análisis previo de alternativas (`PlanesViables/`). Las rutas de este documento son relativas a ella.

```Plaintext
entregas/cu-01-reinterpretacion-biologica/
├── README.md                      # Puerta de entrada: visión de conjunto, objetivos y estructura.
├── .gitignore                     # Excluye el entorno virtual, codigo/data/, los .env, los .xlsx y los .csv.
├── ARCHITECTURE.md                # Diagrama de componentes y recorrido del dato.
├── AGENTS.md                      # Instrucciones operativas para asistentes de IA y colaboradores: estructura, comandos y reglas.
├── DOR.md                         # Definition of Ready: lo que necesita una tarea para empezar.
├── DOD.md                         # Definition of Done: lo que cumple una tarea para cerrarse.
├── TABLERO.md                     # Ciclo del tablero, sistema de bloqueos y rutina de cada reunión.
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
│   ├── benchmark-gold-set.md
│   └── scoring-net-pathway-score.md
│
├── docs/                          # Limitaciones documentadas (limitacion-pares-sin-abstract.md) y plantillas de issue (plantillas-issue/).
├── PlanesViables/                 # Análisis de las dos arquitecturas candidatas (OpcionA.md, OpcionB.md; ADR-001).
├── src/                           # Esquema del código fuente (definicion-src.txt).
├── tests/                         # Vacío (test_pipeline.py): las pruebas están en codigo/tests/.
│
└── codigo/                        # Código fuente:
    ├── fase1_ingesta/                 # Fase 1: ingesta (GO, GAF, inmunoglobulinas, triaje del signo GO,
    │   │                              #   GeneRIF y Europe PMC, abstracts) y Excel de salida.
    │   └── fuentes/                   #   Clientes de MyGene/GeneRIF, Europe PMC, UniProt y su caché.
    ├── fase2_inferencia/              # Fase 2: casos, prompts, cliente LLM, registro, validación y contraste.
    ├── fase3_scoring/                 # Fase 3: signo de cada par (gen, ruta) y Net Pathway Score de cada ruta.
    ├── evaluacion/                    # Benchmark: selección del gold set, guía de etiquetado, etiquetas e informes.
    ├── tests/                         # Pruebas con pytest, sin red (python -m pytest desde codigo/).
    ├── tools_cimus/                   # Material de CIMUS: rutas enriquecidas (entrada de la Fase 1) y tabla de log2FC (sensibilidad de la Fase 3).
    ├── data/                          # Ficheros locales (ignorados por git): OBO, GAF, cachés, registro de
    │                                  #   respuestas, fase2_resultados.xlsx, fase3_scoring.xlsx y registros del benchmark.
    ├── .env.example                   # Plantilla de las claves de los modelos y de NCBI.
    └── requirements.txt               # Dependencias de Python (requests, pandas, openpyxl; pytest y pytest-cov para las pruebas).
```

El fichero `.gitignore` está en esta carpeta y excluye el entorno virtual, `codigo/data/`, los `.env` y todos los `.xlsx` y `.csv`. Por eso el Excel de salida de la Fase 1 (`codigo/fase1_ingesta/fase1_dataset_abstracts.xlsx`) no se versiona. Los únicos Excels versionados son las rutas enriquecidas de CIMUS de `codigo/tools_cimus/`; su tabla de log2FC (`NK_cells_DESeq2_results.xlsx`) se reparte dentro del equipo y no se sube.

## 7. Cómo se ejecuta

Desde esta carpeta (`entregas/cu-01-reinterpretacion-biologica/`), con Python 3 y las dependencias de `codigo/requirements.txt`:

1. **Claves:** copiar `codigo/.env.example` como `codigo/.env` y rellenar `GEMINI_API_KEY`, `GROQ_API_KEY` y, para la Fase 1, `NCBI_EMAIL` y `NCBI_API_KEY` (opcional). `codigo/.env` no se sube al repositorio: está en el `.gitignore`. Las variables de entorno del sistema tienen prioridad sobre el fichero.
2. **Fase 1:** `python codigo/fase1_ingesta/main.py`. Lee los Excels de CIMUS (`codigo/tools_cimus/NK_rutas_activadas_GO.xlsx` y `NK_rutas_suprimidas_GO.xlsx`) y escribe `codigo/fase1_ingesta/fase1_dataset_abstracts.xlsx`. La primera ejecución descarga el OBO, el GAF y unos 33.000 _abstracts_ (casi una hora); con las cachés tarda unos minutos.
3. **Fase 2:** desde `codigo/`, `python -m fase2_inferencia ejecutar`. Escribe `codigo/data/fase2_resultados.xlsx`. Si se agota el límite diario de un modelo, basta con volver a lanzar el mismo comando. Sin llamar a ningún modelo, `python -m fase2_inferencia CD7` muestra la primera llamada que se enviaría para un gen.
4. **Fase 3:** desde `codigo/`, `python -m fase3_scoring`. Lee las salidas de las Fases 1 y 2 y escribe `codigo/data/fase3_scoring.xlsx` en unos segundos, sin red. Si existe `codigo/tools_cimus/NK_cells_DESeq2_results.xlsx`, lo usa solo para la sensibilidad (`NPS_log2FC`); un tercer argumento cambia ese fichero, o `ninguno` lo omite.
5. **Benchmark:** desde `codigo/`, `python evaluacion/evaluar_gold.py`, con el uso descrito en la [spec del benchmark](specs/benchmark-gold-set.md).
6. **Pruebas:** desde `codigo/`, `python -m pytest`. No usan la red ni las claves de `.env`.

