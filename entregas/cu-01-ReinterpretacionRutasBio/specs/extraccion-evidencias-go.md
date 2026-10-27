# Spec: Pipeline de extracción de evidencias y polaridad GO (Biological Process)

## Qué hay que construir

Un módulo ejecutable por línea de comandos (CLI) y automatizable que, a partir de una lista de genes humanos (HGNC) procedentes del análisis transcriptómico de célula única (scRNA-seq de células epiteliales e inmunes de laringe y faringe), extraiga y relacione:

1. **Términos de regulación biológica en Gene Ontology (GO - Biological Process):** Anotaciones que definan activación o inhibición de procesos (`regulates`, `positively_regulates`, `negatively_regulates` o `\bregulation of\b`).


2. **Polaridad preliminar del término:** Asignación del sentido de regulación indicado formalmente por el término GO (+1 para positiva, -1 para negativa, 0 para no direccionada).


3. **Evidencias experimentales asociadas:** Identificadores PubMed (PMIDs) respaldados exclusivamente por códigos de evidencia de validación experimental en humanos (taxón 9606).


4. **Recuperación de abstracts científicos:** Descarga en lotes desde Europe PMC (con fallback a NCBI E-utilities) de los títulos y resúmenes de los artículos vinculados.


5. **Persistencia tabular en base de datos local:** Almacenamiento estructurado en un motor analítico embebido (DuckDB) con tablas normalizadas (`go_evidence`, `abstracts`) y generación de una vista/cola (`v_llm_queue` o JSONL) para la posterior ingesta por parte del módulo LLM.



Este módulo actúa como el **componente de ingesta y preprocesamiento de evidencias** dentro de la arquitectura global, situándose inmediatamente antes del sistema de razonamiento LLM encargado de dirimir la contradicción gen-ruta multiplicando la polaridad por el log2FoldChange transcriptómico.

---

## Por qué

El análisis transcriptómico estándar a nivel de célula única (scRNA-seq con DESeq2 y clusterProfiler) clasifica los genes diferencialmente expresados en listas independientes sobreexpresadas (Up) e infraexpresadas (Down). Sin embargo, las bases de datos de rutas biológicas (como Gene Ontology) habitualmente catalogan los genes de forma estática y cualitativa (simple presencia o ausencia), omitiendo el rol funcional específico y el signo regulatorio con el que cada gen opera dentro de la vía.

Dado que un gen concreto se encuentra sobreexpresado o infraexpresado en un tipo celular determinado —pero nunca en ambos estados de manera simultánea—, la aparente inconsistencia en el enriquecimiento de una ruta no es una contradicción real, sino una carencia de contexto funcional: un gen Up puede actuar como represor de la vía, o un gen Down puede ser un activador necesario. Para reflejar fielmente el impacto biológico global de cada ruta en las células de laringe y faringe, es imprescindible determinar de forma sistemática si cada gen actúa biológicamente como activador (+1) o inhibidor/represor (-1) del proceso. Esta funcionalidad automatiza la extracción estructurada de las evidencias experimentales y resúmenes científicos de la literatura que demuestran dicha función, entregando un corpus limpio y trazable que permite a los modelos de lenguaje asignar la direccionalidad regulatoria real a cada gen sin depender de curaciones manuales ni incurrir en alucinaciones.

---

## Restricciones

* **Procesamiento de ontologías fuera de línea:** Para evitar cuellos de botella por latencia o caídas de APIs externas, el parseo de la ontología GO (`go-basic.obo`) y las anotaciones (`goa_human.gaf.gz`) debe ejecutarse en streaming local sin consultar la API web de AmiGO en tiempo real.


* **Respeto a límites de rate-limiting:** La descarga online de abstracts debe consultar Europe PMC en lotes máximos de 40 artículos, implementando reintentos con *exponential backoff*, respeto de cabeceras `Retry-After` y fallback a NCBI E-utilities cumpliendo con la identificación por correo (`NCBI_EMAIL`) y clave de API (`NCBI_API_KEY`) sin superar las 10 peticiones/segundo.


* **Filtrado estricto de evidencia:** Descartar de forma determinista anotaciones computacionales automáticas o sin curación (IEA, IBA), anotaciones con calificador `NOT`, identificadores sin formato numérico estándar de PMID (ej. GO_REF, Reactome, DOI) y el PMID metodológico `21873635`.


* **Idempotencia de almacenamiento:** La inserción y actualización en DuckDB debe ser estrictamente idempotente; ejecutar el comando múltiples veces con los mismos genes no debe generar registros duplicados ni alterar el estado consistente de la base de datos.


* **Gestión de secretos y caché:** Las credenciales de acceso a APIs externas deben residir en variables de entorno (`.env` documentado vía `.env.example`), y los archivos masivos de descarga (`.gaf.gz`, `.obo`, `.duckdb`) deben ser ignorados por Git en `.gitignore` mediante un sistema de caché local con vigencia configurable (30 días por defecto).



---

## Criterios de aceptación

* [ ] **Resolución y filtrado de evidencias:** Dado un gen humano de prueba (ej. `GATA3`), el extractor procesa el archivo GAF en streaming y filtra únicamente registros con taxón 9606 y códigos de evidencia experimental (EXP, IDA, IPI, IMP, IGI, IEP, HTP, HDA, HMP, HGI, HEP), descartando el 100% de las anotaciones que contengan el calificador `NOT` o códigos IEA/IBA.


* [ ] **Determinación de polaridad en ontología:** Para todos los términos GO recuperados que contengan la relación o subcadena `\bregulation of\b`, el sistema asigna el valor `+1` a términos de *positive regulation*, `-1` a *negative regulation* y `0` al resto, resolviendo identificadores obsoletos mediante la directiva `alt_id` del OBO.


* [ ] **Integridad de descarga y caché:** La suite ejecuta la descarga en lotes de abstracts; si se interrumpe el proceso y se reanuda, el número de peticiones HTTP emitidas equivale exactamente a los PMIDs con estado pendiente (`not_found` o sin procesar), sin repetir peticiones para registros ya almacenados en la tabla `abstracts`.


* [ ] **Trazabilidad y esquema en DuckDB:** Tras la ejecución, la base de datos `data/pathways.duckdb` cuenta con las tablas `go_evidence` y `abstracts` debidamente pobladas, registrando en cada fila la versión del OBO y la fecha de release del GAF.


* [ ] **Generación de la cola LLM:** La ejecución del comando con `--jsonl <fichero>` genera un archivo JSONL válido donde el 100% de las líneas contiene la tupla `(gene, go_id, pmid, term_polarity, abstract)` lista para su inferencia, coincidiendo fila por fila con los registros expuestos por la vista `v_llm_queue`.


* [ ] **Calidad de código y tests:** El código pasa la suite de comprobaciones sin errores (`pytest` para el parser de GAF/OBO y linters configurados en el proyecto).



---