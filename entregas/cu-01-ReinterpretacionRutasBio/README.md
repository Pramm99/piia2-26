# Reinterpretación del Papel de las Rutas Biológicas en Biomedicina (scRNA-seq HNSC)

> Herramienta basada en Inteligencia Artificial y arquitecturas RAG _stateless_ para resolver discrepancias de regulación génica en análisis transcriptómicos de célula única (cáncer de cabeza y cuello: laringe y faringe).

## 1. Qué es el proyecto y qué problema resuelve

El análisis transcriptómico de célula única (**scRNA-seq**) permite estudiar la expresión génica a nivel individual en poblaciones celulares complejas, como las células _Natural Killer_ (NK) y el microambiente tumoral en carcinomas de cabeza y cuello (**HNSC**: laringe y faringe). Uno de los pasos fundamentales en bioinformática consiste en el análisis de enriquecimiento funcional en rutas biológicas (como las anotadas en Gene Ontology o KEGG).

### El problema: la contradicción de enriquecimiento

En los métodos bioinformáticos convencionales, las anotaciones de las rutas son cualitativas (presencia o ausencia de un gen en la ruta), sin indicar si un gen concreto actúa como **activador** o **inhibidor/represor** de dicha ruta.

Esto genera contradicciones metodológicas directas: si en una ruta conformada por 100 genes encontramos 10 genes sobre-expresados (_up-regulated_) y 12 genes infra-expresados (_down-regulated_), las herramientas clásicas de enriquecimiento reportan que la ruta se encuentra simultáneamente activada e inhibida.

### La solución

Este proyecto desarrolla un pipeline asistido por **Inteligencia Artificial** que extrae de forma automatizada y contextualizada el rol mecanístico de cada gen discordante en la literatura biomédica y bases curadas. Mediante un sistema de extracción y razonamiento, el sistema determina el signo funcional de la contribución del gen (+1 si activa la ruta, -1 si la inhibe, o `UNKNOWN` ante incertidumbre) y calcula un **Net Pathway Score** integrado con el _log2 Fold-Change_ de scRNA-seq, transformando las discrepancias en una conclusión biológica cuantitativa y explicable.

## 2. Por qué hemos escogido este proyecto y qué queremos conseguir

### Motivación

Escogimos este proyecto por 2 motivos principales:

1. **Impacto biomédico real:** Los tumores de laringe y faringe presentan una elevada heterogeneidad y mecanismos sofisticados de evasión inmunitaria. Resolver las rutas de activación/agotamiento en células inmunitarias es crítico para identificar biomarcadores fiables y potenciales dianas de inmunoterapia. Nuestro equipo se caracteriza por el interés en este tipo de proyectos biomédicos en los que tenemos una ligera experiencia.
    
2. **Intersección interdisciplinar:** Combina ciencia de datos, bioinformática de célula única (_single-cell RNA-seq_) e ingeniería de IA moderna (modelos de lenguaje e inferencia semántica).

### Objetivo final

Al concluir el proyecto, queremos disponer de un **MVP funcional, reproducible y portable** que:

- Tome como entrada una matriz de expresión diferencial de scRNA-seq (células faríngeas/laríngeas).  
    
- Identifique automáticamente los genes en conflicto para rutas ambiguas.  
    
- Consulte la literatura en tiempo real mediante APIs abiertas (Europe PMC) y procese los _abstracts_ relevantes con un filtro semántico y un LLM determinista (temperatura 0) con justificación literal (citas trazables).
    
- Genere un _score_ neto de ruta mecanístico integrable directamente en el ecosistema bioinformático en R (`clusterProfiler`, `ggplot2`).

## 3. Alcance: qué entra y qué queda explícitamente fuera

Para garantizar la entrega en plazo y la robustez del sistema, el proyecto se acoge a la filosofía técnica de la **Opción A (RAG Stateless / In-Memory)**:

### Qué entra en el proyecto

- **Dominio específico:** Células inmunitarias/tumorales de laringe y faringe (HNSC).
    
- **Ingesta _stateless_:** Consultas HTTP asíncronas a la API de **Europe PMC** a partir de identificadores biológicos y PMIDs vinculados a Gene Ontology.
    
- **Filtrado y Re-Ranking:** Pre-filtrado léxico y re-ordenación semántica con un modelo Cross-Encoder ligero en CPU (`ms-marco-MiniLM`) para seleccionar el Top 3 de resúmenes científicos pertinentes. 
    
- **Inferencia estructurada:** Extracción determinista del signo funcional del gen mediante LLM (Llama-3 vía Groq) con _temperature=0_, salida bajo esquema JSON estricto y opción obligatoria de rescate (`UNKNOWN`) ante falta de evidencia concluyente.  
    
- **Métrica de resolución:** Integración matemática en R del signo inferido ponderado por el _log2 Fold-Change_ del dataset scRNA-seq original.
    
- **Entorno de pruebas y reproducibilidad:** _Test harness_ con respuestas emuladas (fixtures/mocks locales) para garantizar testing sin conexión ni dependencia de cuotas de red externas.

### Qué queda explícitamente fuera

- **Bases de datos persistentes y Data Lakes:** Cero bases de datos locales, sin PostgreSQL, bases vectoriales dedicadas ni Data Lakehouses (Delta Lake/Iceberg). Todo el procesamiento es en memoria RAM durante el tiempo de ejecución del pipeline.
    
- **Entrenamiento o Fine-Tuning de modelos propios:** No se entrenarán clasificadores BERT biomédicos desde cero ni se ajustarán pesos de LLMs. Se usan modelos ya preentrenados e inferencia vía API externa.
    
- **Acceso a artículos de pago (Paywalls):** La ingesta se limita exclusivamente a resúmenes y artículos _Open Access_ de acceso público.  
    
- **Modelado biológico no lineal / combinatorio:** No se contemplan interacciones génicas de orden superior complejas (efectos epistáticos o condicionales no lineales); el score se fundamenta en una agregación mecanicista sumativa y transparente.
    
- **Escalado al transcriptoma global (>20.000 genes simultáneos):** El pipeline está diseñado para resolver conjuntos acotados de genes en conflicto por ruta, no para reprocesar el genoma completo en una sola corrida.

## 4. Equipo y roles

| **Nombre y Apellidos** | **Rol principal** | **Correo de contacto**          |
| ---------------------- | ----------------- | ------------------------------- |
| Iria Varela Palmás     |                   | `iria.varela.palmas@rai.usc.es` |
| Luis Pérez Jiménez     |                   | `luis.perez2@rai.usc.es`        |
| Pablo Rey Mariño       |                   | `pablo.rey.marino@rai.usc.es`   |

## 5. Estructura del repositorio

La estructura del proyecto separa la documentación arquitectónica de soporte, las especificaciones de trabajo, el código fuente y las pruebas locales:


```Plaintext
.
├── README.md                      # Puerta de entrada: visión de conjunto, objetivos y estructura.
├── AGENTS.md                      # Instrucciones operativas para asistentes de IA y colaboradores.
├── ARCHITECTURE.md                # Diagrama de flujo de componentes y recorrido del dato (Opción A).
│
├── decisions/                     # Architecture Decision Records (ADRs) con decisiones ya tomadas:
│   ├── adr-001-rag-stateless.md   #   - Decisión: arquitectura sin base de datos ni lakehouse.
│   ├── adr-002-europe-pmc-api.md  #   - Decisión: ingesta asíncrona de abstracts vía Europe PMC.
│
├── specs/                         # Especificaciones de unidades de trabajo por implementar:
│   ├── descarga-evidencias-go-pmc.md        #   - Tarea y criterios de aceptación para el módulo de ingesta HTTP.
│   ├── limpieza-abstracts-particion-génica.md           #   - Criterios para la limpieza y preprocesado de abstracts.
│
├── src/                           # Código fuente del pipeline:
│
├── tests/                         # Pruebas unitarias y de integración:
│
├── .gitignore                     # Filtro de entornos (.venv), secretos (.env) y temporales.
└── .env.example                   # Plantilla de variables de entorno y claves de API (GROQ_API_KEY).
```
