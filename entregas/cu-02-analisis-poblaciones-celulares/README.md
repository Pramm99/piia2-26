# CU-02: Integración de información transcriptómica para extrapolación de tendencias globales en poblaciones celulares

> **Entidad colaboradora:** CIMUS - Centro Singular de Investigación en Medicina Molecular e Enfermidades Crónicas (USC)
>
> **Tutora profesional:** Catarina Allegue Toscano (`catarina.allegue@usc.es`)
>
> **Asignatura:** Proyecto Integrador de IA II — Grado en Inteligencia Artificial (USC)

## ¿Qué es?

Este proyecto consiste en el desarrollo de una herramienta basada en Inteligencia Artificial diseñada para procesar e interpretar resultados de Gene Set Enrichment Analysis (GSEA), que permiten identificar y comparar el enriquecimiento de rutas biológicas en distintos tipos celulares de tumores de cabeza y cuello frente a controles sanos.

El análisis compara, para cada tipo celular, las células tumorales con las células del mismo tipo presentes en controles sanos, permitiendo identificar cambios asociados al contexto tumoral. La dirección del enriquecimiento (NES), refleja la tendencia de expresión de los genes de cada ruta: un NES positivo indica un enriquecimiento hacia genes con mayor expresión en el tumor, mientras que uno negativo indica un enriquecimiento hacia genes con mayor expresión en los controles sanos.

El proyecto aborda la dificultad que conlleva interpretar los resultados del análisis GSEA debido a su volumen y complejidad. Para facilitar esta tarea, se presentan los resultados mediante representaciones gráficas que permiten visualizar e identificar patrones de forma intuitiva. Además, mediante modelos de lenguaje (LLM), la herramienta transforma estos resultados en explicaciones en lenguaje natural, resumiendo los patrones y tendencias biológicas observados.


## Motivación

### ¿Por qué este proyecto?
El análisis de enriquecimiento de rutas biológicas mediante GSEA genera una gran cantidad de información sobre los procesos biológicos asociados a las diferencias de expresión génica entre distintas condiciones experimentales. Aunque estos datos ofrecen un valor científico enorme, su procesamiento e interpretación biológica manual resultan un reto considerable para los investigadores sin el soporte de modelos inteligentes de análisis automatizado.

### Objetivos al finalizar

* Desarrollar un sistema capaz de integrar los datos de enriquecimiento de rutas y extraer tendencias celulares globales.

* Proporcionar una interfaz accesible mediante una interfaz web que permita explorar los análisis y las explicaciones biológicas de forma sencilla e intuitiva.

* Facilitar la labor investigadora del equipo del CIMUS acelerando el flujo de trabajo desde la secuenciación hasta la extracción de conclusiones.

## Alcance

### Dentro del alcance:

* **Procesamiento e integración de datos**: Tratamiento de los resultados del GSEA y creación de sus gráficas asociadas (tumores de cabeza y cuello vs. controles).

* **Análisis de resultados**: Algoritmos dedicados a la extrapolación de tendencias globales en poblaciones celulares (`specs/analisis-datos-gsea.md`).

* **Módulo de explicación e interpretación**: Generación de explicaciones en lenguaje natural sobre las tendencias y rutas detectadas (`specs/modulo-explicacion.md`).

* **Interfaz visual**: Interfaz web en HTML para visualizar resultados, gráficas y explicaciones (`specs/frontend.md`).

* **Compatibilidad con distintos conjuntos de resultados GSEA**: Adaptación del módulo para procesar resultados de GSEA correspondientes a distintos tipos celulares y condiciones experimentales, manteniendo un formato homogéneo para su análisis y visualización. Interfaz optimizada específicamente para el conjunto de rutas HALLMARK.

### Fuera del alcance:

* Validación experimental *in vitro* o *in vivo* de las hipótesis biológicas generadas por el sistema.

* Optimización y validación para colecciones distintas de HALLMARK.

* Desarrollo de un sistema de chat interactivo con el LLM para realizar consultas abiertas sobre los resultados.

* Integración con sistemas de grado clínico o despliegue en producción hospitalaria.


## Equipo

| Nombre | Rol | Correo de Contacto | 
| ----- | ----- | ----- | 
| **Clara Álvarez Rodríguez** | Data Scientist | `clara.alvarez0@rai.usc.es` | 
| **Carla Piñeiro Santamaría** | Frontend Dev | `carla.pineiro.santamaria@rai.usc.es` | 
| **Gael Denise Soto Rodríguez** | AI Engineer | `gaeldenise.soto@rai.usc.es` | 
| **Daniel Souto Pazó** | Data Scientist | `daniel.souto.pazo@rai.usc.es` | 


## Estructura del Repositorio

```text
entregas/
└── cu-02-analisis-poblaciones-celulares/
    ├── README.md                  # Documento principal: qué es el proyecto, motivación, alcance y equipo.
    ├── specs/                     # Especificaciones detalladas por funcionalidad
    │   ├── frontend.md       # Especificación del prototipo de interfaz y visualización
    │   ├── analisis-datos-gsea.md       # Especificación del análisis de datos de GSEA
    │   └── modulo-explicacion.md    # Especificación del módulo de explicación en lenguaje natural
    ├── prototipo_frontend.html    # Prototipo en HTML para la interfaz web
    └── .gitignore                 # Archivos y carpetas omitidos por el control de versiones (datos sensibles, modelos, etc.)
```

### Descripción de directorios clave:

* **`README.md`**: Punto de entrada al proyecto donde se describe la visión general, contexto del CIMUS, alcance y datos del equipo.

* **`specs/`**: Contiene la documentación funcional y técnica detallada por cada módulo del sistema:

  * `frontend.md`: Define las gráficas, componentes visuales e interacción con la interfaz.

  * `analisis-datos-gsea.md`: Detalla los pipelines de datos GSEA, procesamiento y algoritmos utilizados en el análisis.

  * `modulo-explicacion.md`: Define el enfoque para traducir los descubrimientos del análisis en lenguaje natural.

* **`prototipo_frontend.html`**: Archivo HTML que contiene un prototipo navegable desarrollado para la demostración visual de la interfaz del sistema.