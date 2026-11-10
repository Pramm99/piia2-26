# Spec: Ingesta de Evidencias de Regulación GO y Descarga de Abstracts desde Europe PMC

## Qué hay que construir
Un módulo de ingesta (Fase 1, `codigo/extraer_info/`, `python codigo/extraer_info/main.py`) que tome como entrada los resultados de enriquecimiento funcional de Gene Ontology (ontología *Biological Process*) proporcionados por CIMUS, obtenidos a partir de los genes diferencialmente expresados en células NK de tumores de cabeza y cuello (HNSC). Hay dos listas: rutas enriquecidas con genes *up* («rutas activadas») y con genes *down* («rutas suprimidas»). El módulo realiza este flujo automatizado, en el orden de `main.py`:

1. **Descarga de Gene Ontology** (`red.py`): `go-basic.obo` y `goa_human.gaf.gz` ([ADR-002](../decisions/adr-002-europe-pmc-api.md)), solo la primera vez.
2. **Extracción de identificadores** (`entrada_excel.py`): leer los dos ficheros y, de cada fila, extraer el identificador de la ruta en Gene Ontology (columna `ID`), su nombre (`Description`) y los símbolos oficiales de los genes asociados (columna `geneID`, separados por `/`, nomenclatura HGNC).
   * Los identificadores obsoletos o alternativos de GO se traducen a su término vigente.
   * Cada fila guarda en `Estado_Original` la lista de la que viene («Activada» o «Suprimida»), y de ella sale la dirección del gen (*up* o *down*).
   * Si `geneID` parece ENTREZID en lugar de símbolos, se avisa.
3. **Inmunoglobulinas** (`inmunoglobulinas.py`): los genes con `locus_type = "immunoglobulin gene"` en HGNC, más JCHAIN y PIGR, salen antes del cruce. Se evalúa la Ig completa, que no activa ni inhibe la ruta: sus pares van a la hoja `Inmunoglobulinas` con signo `neutro` y la función de la Ig completa según UniProt Swiss-Prot. No llegan al LLM.
4. **Mapeo gen–ruta → evidencia bibliográfica** (`grafo_go.py`, `cruce_gaf.py`):
   * **Propagación por el grafo.** Cada ruta se propaga a todo su subárbol a través de `is_a`, `part_of`, `regulates`, `positively_regulates` y `negatively_regulates`. Para cada descendiente se guardan la profundidad y el signo del camino (`Polaridad_GO`: `+1`, `-1`, `conflicto` o vacía).
   * **Reglas de signo:**
     * en las rutas «positive/negative regulation of X», un término de X cuenta con el signo de la ruta (signo por pertenencia);
     * las rutas «regulation of X» sin dirección se tratan como X (`SIN_DIRECCION_COMO_PROCESO`, en `config.py`);
     * la regulación no se propaga después de un `part_of` ni por las aristas sin signo.
   * **Cruce con el GAF.** Se recuperan las anotaciones de cada gen a la ruta o a cualquiera de sus descendientes, con su `PMID`, su código de evidencia, su calificador y su extensión. Los calificadores `acts_upstream_of_*_effect` componen el signo, y `occurs_in` con una célula distinta de NK queda marcado.
5. **Triaje del signo GO** (`polaridad.py`): para cada par (gen, ruta) se decide el `Destino`:
   * `aceptar_GO`: el signo de GO se acepta sin LLM, con revisión ligera. Exige un camino corto (profundidad ≤ `PROFUNDIDAD_MAX_ACEPTAR` = 2, o signo por pertenencia) y una anotación experimental con PMID que no ocurre en otra célula ni es indirecta.
   * `LLM`: la decide la Fase 2.
   * `LLM_y_revision`: además, revisión humana (p. ej. conflictos entre anotaciones).
   * `sin_evidencia`: el par no tiene ningún abstract, ni del GAF ni de las fuentes externas. Al final se cierra de forma determinista como `UNKNOWN` (`no_concluyente`), con su causa ([limitación documentada](../docs/limitacion-pares-sin-abstract.md)).

   Cada par lleva también su motivo, la profundidad, la contribución y la bandera de freno o retroalimentación.
6. **Fuentes externas** (`pmid_externos.py`, `relevancia.py`, `fuentes/`): para los pares sin abstract utilizable en el GAF (sin PMID, o con PMIDs sin abstract en PubMed):
   * **NCBI GeneRIF**, vía MyGene.info: solo se acepta si el texto del GeneRIF nombra al gen.
   * **Búsqueda dirigida en Europe PMC**, para los que siguen vacíos: el gen y un término del subárbol de la ruta en la misma frase. Los alias en minúsculas no cuentan como mención.
   * Como máximo `MAX_PMIDS_EXTERNOS_POR_PAR` = 10 PMIDs por par.

   Estas filas guardan su `Fuente`, la `Frase_fuente`, el `Termino_coincidente` y dónde coincide (`Coincide_en`).
7. **Descarga de literatura científica** (`abstracts.py`): recuperar el título y el abstract de cada `PMID` desde la API REST de **Europe PMC** y, para los que no devuelva, desde **NCBI E-utilities** como respaldo. La caché guarda el texto en crudo, y `limpiar_texto` (desescapado y etiquetas HTML conocidas, sin borrar texto entre «<» y «>») se aplica al leerlo.
8. **Salida** (`salida.py`): el embudo por consola y un Excel, `codigo/extraer_info/fase1_dataset_abstracts.xlsx`, que es la entrada de la Fase 2. Tiene siete hojas:
   * `Con_abstract`: una fila por (gen, ruta, PMID) con abstract.
   * `PMID_sin_abstract`: evidencias cuyo PMID no tiene abstract disponible.
   * `Anotado_sin_PMID`: pares gen–ruta anotados en GO pero sin ningún PMID (se conservan por su polaridad).
   * `Genes_no_encontrados`: genes de la entrada que no aparecen en el GAF ni como símbolo ni como sinónimo (columna `Gen_no_encontrado_en_GAF`).
   * `Triaje_polaridad`: una fila por par con su `Destino`, `Motivo`, `Signo_GO`, `Profundidad`, evidencias y PMIDs del signo, `Contribucion` y `Freno_retroalimentacion`.
   * `Inmunoglobulinas`: los pares de inmunoglobulinas, con signo `neutro` y la función de la Ig completa.
   * `Sin_evidencia`: los pares sin ningún abstract, con su `Causa` (`anotado_sin_PMID`, `sin_anotacion_GAF` o `PMID_sin_abstract`).

   Las tres primeras hojas llevan además la columna `Destino` del triaje.

Cifras de la ejecución completa del 2026-11-09:
* **Entrada y triaje:** 3.172 pares de entrada, de los que 103 son de inmunoglobulinas. Destinos: 332 `aceptar_GO`, 2.003 `LLM`, 66 `LLM_y_revision` y 668 `sin_evidencia`.
* **PMIDs:** 1.547 pares con PMID en el GAF y 855 con PMID externo.
* **Salida:** 1.420 PMIDs únicos y 5.014 filas en `Con_abstract`.

## Por qué
El análisis transcriptómico a nivel de célula única clasifica los genes diferencialmente expresados en listas independientes sobreexpresadas (*Up*) e infraexpresadas (*Down*). Las bases de datos convencionales catalogan los genes de forma cualitativa (presencia o ausencia en la ruta), provocando que una misma ruta aparezca enriquecida en ambos sentidos sin explicar el efecto neto.

Para que podamos inferir si un gen concreto activa (+1) o reprime (-1) una ruta biológica en las células NK del microambiente tumoral, se necesita recopilar los estudios científicos originales que sustentan dicha interacción. Este módulo automatiza la recopilación sistemática de esa evidencia a partir de identificadores inequívocos de ontología y literatura abierta, reduciendo sesgos y evitando consultas manuales.

La polaridad del grafo de GO cumple dos papeles. Cuando es fiable, da el signo sin necesidad de un LLM (`aceptar_GO`). En el resto de casos, es una señal curada con la que contrastar la salida del LLM ([ADR-003](../decisions/adr-003-control-alucinaciones-unknown.md)).

Las fuentes externas existen porque muchos pares no tienen ningún artículo en el GAF. Sin ellas, esos pares no tendrían evidencia que leer.

## Restricciones
* **Sin bases de datos ([ADR-004](../decisions/adr-004-persistencia-ficheros-locales.md)):** No se levantan bases de datos ni servicios de almacenamiento. El estado se guarda en ficheros locales dentro de `codigo/data/`:
  * los ficheros de GO (`go-basic.obo`, `goa_human.gaf.gz`);
  * las cachés de abstracts (`cache_abstracts.json`), MyGene y GeneRIF (`cache_mygene.json`), búsquedas de Europe PMC (`cache_epmc_busquedas.json`), UniProt (`cache_uniprot.json`) y la lista de inmunoglobulinas de HGNC (`hgnc_inmunoglobulinas.json`).

  Se reutilizan entre ejecuciones. Borrar la caché de abstracts o los ficheros de GO solo alarga la ejecución; borrar las de GeneRIF o Europe PMC puede cambiar el resultado, porque esas APIs cambian con el tiempo y Europe PMC ordena por relevancia. Las cachés y las descargas del OBO y el GAF se escriben de forma atómica (fichero temporal y renombrado) para que una interrupción no deje ficheros corruptos. El Excel de salida no se escribe de forma atómica.
* **Control de tasa de peticiones (*Rate Limiting*):** Las llamadas a Europe PMC se hacen en lotes de **40 identificadores** por petición y las de NCBI en lotes de 100 (valores fijos en `abstracts.py`), con pausas entre lotes, más cortas en NCBI si hay `NCBI_API_KEY`. Las peticiones a las APIs usan reintentos con espera exponencial (*exponential backoff*) ante respuestas HTTP `429`, `500`, `502`, `503` y `504`. La descarga del OBO y el GAF no tiene reintentos.
* **Solo referencias PubMed:** Se descartan las referencias que no sean `PMID` (p. ej. `GO_REF`, `DOI`, `Reactome`), las anotaciones con calificador `NOT` y las de taxón distinto de humano (`9606`).
* **Códigos de evidencia:** Se aceptan **todos los códigos de evidencia** que lleven `PMID`. Las anotaciones automáticas `IEA` quedan fuera de forma natural, porque nunca llevan PMID. Cada fila indica en la columna `Experimental` si su evidencia es experimental (`EXP`, `IDA`, `IPI`, `IMP`, `IGI`, `IEP` y sus equivalentes de alto rendimiento). El filtro estricto (`SOLO_EXPERIMENTAL`) es configurable y está desactivado por defecto.
* **Resolución de genes:** Un gen se identifica por su símbolo oficial y, solo si no hay ambigüedad, por un sinónimo del GAF (un sinónimo que sea el símbolo oficial de otro gen no se usa).
* **Formatos de entrada heterogéneos:** El módulo debe aceptar ficheros `.xlsx` y `.csv`, verificando la existencia de las columnas obligatorias (`ID`, `Description`, `geneID`) antes de iniciar las llamadas de red. **No implementado:** hoy solo lee `.xlsx`, una columna ausente da `KeyError` y la entrada se lee después de descargar el OBO y el GAF.
* **Ubicación de la entrada:** `config.py` lee directamente los Excels originales de CIMUS, versionados en `codigo/tools_cimus/` (`NK_rutas_activadas_GO.xlsx` y `NK_rutas_suprimidas_GO.xlsx`), así que un clon limpio del repositorio tiene ya la entrada.
* **Gestión de credenciales y red:** El correo de contacto y la clave de API de NCBI (`NCBI_EMAIL`, `NCBI_API_KEY`) se leen de las variables de entorno o del fichero `codigo/.env` (documentado en `codigo/.env.example`), sin escribir datos privados en el código. `codigo/.env` no se sube al repositorio. Si no hay correo, no se envía ninguno.

## Criterios de aceptación
* [ ] **Carga y validación de la entrada:** Dado un fichero de prueba con al menos una ruta y 5 genes, el parser extrae correctamente la lista de pares `(GO_ID, GENE_SYMBOL)` y rechaza con un error descriptivo (`ValueError`) cualquier fichero al que le falte alguna de las columnas obligatorias. (La extracción funciona; falta el `ValueError`.)
* [x] ✅ **Resolución gen–ruta → PMID:** Para el par de referencia (`CD7`, `GO:0002443` *leukocyte mediated immunity*), la salida contiene el `PMID` `10652336`, anotado en el término descendiente `GO:0002726` con evidencia `IDA` y `Polaridad_GO = +1`. Ninguna fila de la hoja `Con_abstract` contiene un `PMID` no numérico. (Comprobado en la ejecución del 2026-11-09.)
* [x] ✅ **Composición de la polaridad en el grafo:** Para un término alcanzado a través de una única relación `negatively_regulates`, `Polaridad_GO` es `-1`; a través de dos relaciones `negatively_regulates` encadenadas, es `+1`; si el término se alcanza por caminos de signo opuesto, es `conflicto`. (`tests/test_fase1.py`, con un OBO mínimo.)
* [ ] **Inmunoglobulinas:** los pares de genes de inmunoglobulina (p. ej. IGKC, IGHM) aparecen en la hoja `Inmunoglobulinas` con signo `neutro` y no aparecen en `Con_abstract`; IGFBP7, que empieza por «IG» pero no es una inmunoglobulina, no se aparta.
* [ ] **Triaje:** cada par de la entrada que no es inmunoglobulina tiene exactamente un `Destino` en `Triaje_polaridad`, y todo par sin ninguna fila en `Con_abstract` tiene `Destino = sin_evidencia` y una fila en `Sin_evidencia` con su causa.
* [x] ✅ **Consumo y tolerancia a fallos en Europe PMC:** La función de descarga procesa un lote de hasta 40 `PMID`s en una sola petición HTTP. Ante un `PMID` inexistente o sin abstract, el campo del abstract queda vacío (la fila pasa a `PMID_sin_abstract`) sin interrumpir el resto del lote.
* [x] ✅ **Reutilización de la caché:** Una segunda ejecución sobre la misma entrada, con la caché de abstracts completa, no realiza ninguna petición a Europe PMC ni a NCBI para descargar abstracts.
* [x] ✅ **Pruebas unitarias desacopladas de red (Mocks/Fixtures):** La suite de pruebas en `pytest` (`codigo/tests/`) ejecuta la descarga emulando las respuestas HTTP de Europe PMC y NCBI con respuestas simuladas, sin conexión a internet; la suite completa tarda menos de un segundo.
