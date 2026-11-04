# Spec: Ingesta de Evidencias de Regulación GO y Descarga de Abstracts desde Europe PMC

## Qué hay que construir
Un módulo de ingesta (Fase 1, `codigo/extraer_info/`) que tome como entrada los resultados de enriquecimiento funcional de Gene Ontology (ontología *Biological Process*) proporcionados por CIMUS y obtenidos a partir de los genes diferencialmente expresados en células NK de tumores de cabeza y cuello (HNSC), y realice el siguiente flujo automatizado:
1. **Extracción de identificadores:** Leer los ficheros de rutas activadas y suprimidas y, de cada fila, extraer el identificador de la ruta en Gene Ontology (columna `ID`), su nombre (`Description`) y los símbolos oficiales de los genes asociados (columna `geneID`, separados por `/`, nomenclatura HGNC). Los identificadores obsoletos o alternativos de GO se traducen a su término vigente.
2. **Mapeo gen–ruta → evidencia bibliográfica (PMID):** A partir de los ficheros oficiales de Gene Ontology (`go-basic.obo` y `goa_human.gaf.gz`, ver [ADR-002](../decisions/adr-002-europe-pmc-api.md)):
   * Propagar cada ruta a sus términos descendientes a través de las relaciones `is_a`, `part_of`, `regulates`, `positively_regulates` y `negatively_regulates`, calculando la polaridad de cada camino (`Polaridad_GO`: `+1`, `-1`, `conflicto` o vacía).
   * Recuperar del GAF las anotaciones de cada gen a la ruta o a cualquiera de sus descendientes, junto con sus identificadores PubMed (`PMID`) y su código de evidencia.
3. **Descarga de literatura científica:** Recuperar el título y el abstract de cada `PMID` desde la API REST de **Europe PMC** y, para los que no devuelva, desde **NCBI E-utilities** como respaldo.
4. **Salida:** Un Excel (`fase1_dataset_abstracts.xlsx`), que es la entrada de la Fase 2, con cuatro hojas:
   * `Con_abstract`: una fila por (gen, ruta, PMID) con abstract.
   * `PMID_sin_abstract`: evidencias cuyo PMID no tiene abstract disponible.
   * `Anotado_sin_PMID`: pares gen–ruta anotados en GO pero sin ningún PMID (se conservan por su polaridad).
   * `Genes_no_encontrados`: genes de la entrada que no aparecen en el GAF ni como símbolo ni como sinónimo.

## Por qué
El análisis transcriptómico a nivel de célula única clasifica los genes diferencialmente expresados en listas independientes sobreexpresadas (*Up*) e infraexpresadas (*Down*). Las bases de datos convencionales catalogan los genes de forma cualitativa (presencia o ausencia en la ruta), provocando que una misma ruta aparezca enriquecida en ambos sentidos sin explicar el efecto neto.

Para que podamos inferir si un gen concreto activa (+1) o reprime (-1) una ruta biológica en las células NK del microambiente tumoral, se necesita recopilar los estudios científicos originales que sustentan dicha interacción. Este módulo automatiza la recopilación sistemática de esa evidencia a partir de identificadores inequívocos de ontología y literatura abierta, reduciendo sesgos y evitando consultas manuales. Además, la polaridad del grafo de GO aporta una señal curada con la que contrastar después la salida del LLM ([ADR-003](../decisions/adr-003-control-alucinaciones-unknown.md)).

## Restricciones
* **Sin bases de datos ([ADR-004](../decisions/adr-004-persistencia-ficheros-locales.md)):** No se levantan bases de datos ni servicios de almacenamiento. El estado se guarda en ficheros locales dentro de `codigo/data/`: los ficheros de GO y una caché de abstracts (`cache_abstracts.json`) que se reutilizan entre ejecuciones y se pueden borrar sin cambiar el resultado. Las escrituras son atómicas (fichero temporal y renombrado) para que una interrupción no deje ficheros corruptos.
* **Control de tasa de peticiones (*Rate Limiting*):** Las llamadas a Europe PMC se realizan en lotes configurables de **40 identificadores** por petición, y las de NCBI en lotes de 100. Todas usan reintentos con espera exponencial (*exponential backoff*) ante respuestas HTTP `429`, `500`, `502`, `503` y `504`, y pausas entre lotes.
* **Solo referencias PubMed:** Se descartan las referencias que no sean `PMID` (p. ej. `GO_REF`, `DOI`, `Reactome`), las anotaciones con calificador `NOT` y las de taxón distinto de humano (`9606`).
* **Códigos de evidencia:** Se aceptan **todos los códigos de evidencia** que lleven `PMID`. Las anotaciones automáticas `IEA` quedan fuera de forma natural, porque nunca llevan PMID. Cada fila indica en la columna `Experimental` si su evidencia es experimental (`EXP`, `IDA`, `IPI`, `IMP`, `IGI`, `IEP` y sus equivalentes de alto rendimiento). El filtro estricto (`SOLO_EXPERIMENTAL`) es configurable y está desactivado por defecto.
* **Resolución de genes:** Un gen se identifica por su símbolo oficial y, solo si no hay ambigüedad, por un sinónimo del GAF (un sinónimo que sea el símbolo oficial de otro gen no se usa).
* **Formatos de entrada heterogéneos:** El módulo debe aceptar ficheros `.xlsx` y `.csv`, verificando la existencia de las columnas obligatorias (`ID`, `Description`, `geneID`) antes de iniciar las llamadas de red.
* **Gestión de credenciales y red:** El correo de contacto y la clave de API de NCBI (`NCBI_EMAIL`, `NCBI_API_KEY`) se leen de variables de entorno definidas en `.env` (documentadas en `.env.example`), sin escribir datos privados en el código.

## Criterios de aceptación
* [ ] **Carga y validación de la entrada:** Dado un fichero de prueba con al menos una ruta y 5 genes, el parser extrae correctamente la lista de pares `(GO_ID, GENE_SYMBOL)` y rechaza con un error descriptivo (`ValueError`) cualquier fichero al que le falte alguna de las columnas obligatorias.
* [ ] **Resolución gen–ruta → PMID:** Para el par de referencia (`CD7`, `GO:0002443` *leukocyte mediated immunity*), la salida contiene el `PMID` `10652336`, anotado en el término descendiente `GO:0002726` con evidencia `IDA` y `Polaridad_GO = +1`. Ninguna fila de la hoja `Con_abstract` contiene un `PMID` no numérico.
* [ ] **Composición de la polaridad en el grafo:** Para un término alcanzado a través de una única relación `negatively_regulates`, `Polaridad_GO` es `-1`; a través de dos relaciones `negatively_regulates` encadenadas, es `+1`; si el término se alcanza por caminos de signo opuesto, es `conflicto`.
* [ ] **Consumo y tolerancia a fallos en Europe PMC:** La función de descarga procesa un lote de hasta 40 `PMID`s en una sola petición HTTP. Ante un `PMID` inexistente o sin abstract, el campo del abstract queda vacío (la fila pasa a `PMID_sin_abstract`) sin interrumpir el resto del lote.
* [ ] **Reutilización de la caché:** Una segunda ejecución sobre la misma entrada, con la caché de abstracts completa, no realiza ninguna petición a Europe PMC ni a NCBI.
* [ ] **Pruebas unitarias desacopladas de red (Mocks/Fixtures):** La suite de pruebas en `pytest` ejecuta la descarga emulando las respuestas HTTP de Europe PMC y NCBI mediante *fixtures* locales en `codigo/tests/fixtures/`, con un tiempo total de test inferior a 2 segundos y sin conexión a internet.
