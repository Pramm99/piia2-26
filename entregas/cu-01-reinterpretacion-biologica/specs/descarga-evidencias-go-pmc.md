# Spec: Ingesta de Evidencias de Regulación GO y Descarga de Abstracts desde Europe PMC

## Qué hay que construir
Un módulo de ingesta (Fase 1, `codigo/fase1_ingesta/`, `python codigo/fase1_ingesta/main.py`) que tome como entrada los resultados de enriquecimiento funcional de Gene Ontology (ontología *Biological Process*) proporcionados por CIMUS, obtenidos a partir de los genes diferencialmente expresados en células NK de tumores de cabeza y cuello (HNSC). Hay dos listas: rutas enriquecidas con genes *up* («rutas activadas») y con genes *down* («rutas suprimidas»). El módulo realiza este flujo automatizado, en el orden de `main.py`:

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
8. **Salida** (`salida.py`): el embudo por consola y un Excel, `codigo/fase1_ingesta/fase1_dataset_abstracts.xlsx`, que es la entrada de la Fase 2. Tiene siete hojas:
   * `Con_abstract`: una fila por (gen, ruta, PMID) con abstract.
   * `PMID_sin_abstract`: evidencias cuyo PMID no tiene abstract disponible.
   * `Anotado_sin_PMID`: pares gen–ruta anotados en GO pero sin ningún PMID (se conservan por su polaridad).
   * `Genes_no_encontrados`: genes de la entrada que no aparecen en el GAF ni como símbolo ni como sinónimo (columna `Gen_no_encontrado_en_GAF`).
   * `Triaje_polaridad`: una fila por par con su `Destino`, `Motivo`, `Signo_GO`, `Profundidad`, evidencias y PMIDs del signo, `Contribucion` y `Freno_retroalimentacion`.
   * `Inmunoglobulinas`: los pares de inmunoglobulinas, con signo `neutro` y la función de la Ig completa.
   * `Sin_evidencia`: los pares sin ningún abstract, con su `Causa` (`anotado_sin_PMID`, `sin_anotacion_GAF` o `PMID_sin_abstract`).

   Las tres primeras hojas llevan además la columna `Destino` del triaje.

Cifras de la ejecución completa del 2026-11-13:
* **Entrada y triaje:** 3.172 pares de entrada, de los que 103 son de inmunoglobulinas. Destinos: 332 `aceptar_GO`, 2.013 `LLM`, 66 `LLM_y_revision` y 658 `sin_evidencia`.
* **PMIDs:** 1.547 pares con PMID en el GAF y 865 con PMID externo.
* **Salida:** 1.463 PMIDs únicos y 5.092 filas en `Con_abstract`.

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
* **Control de tasa de peticiones (*Rate Limiting*):**
  * **Lotes:** 40 PMIDs por petición en Europe PMC y 100 en NCBI (valores fijos en `abstracts.py`).
  * **Pausas:**
    * entre lotes de Europe PMC, 0,2 s;
    * entre lotes de NCBI, 0,35 s sin `NCBI_API_KEY` y 0,12 s con ella, por debajo del límite de NCBI (3 peticiones/s sin clave y 10 con clave);
    * entre consultas de la búsqueda dirigida de Europe PMC, 0,1 s.
  * **Reintentos con espera exponencial (*exponential backoff*):** todas las peticiones a las APIs usan la sesión de `red.configurar_sesion` (Europe PMC, NCBI, MyGene, HGNC y UniProt).
    * Esa sesión reintenta hasta **5 veces** (`Retry(total=5, backoff_factor=1)`) ante HTTP `429`, `500`, `502`, `503` y `504`, tanto en GET como en POST.
    * Con urllib3 2.x, la espera antes de cada reintento es de 0, 2, 4, 8 y 16 s, unos 30 s como máximo. Si el servidor envía la cabecera `Retry-After`, se respeta.
  * **Aviso de progreso:** las descargas largas (abstracts de Europe PMC y NCBI, y búsquedas dirigidas de Europe PMC) escriben por consola lo que llevan, su porcentaje, el tiempo transcurrido y una estimación de lo que falta (`red.Progreso`), cada 5 % y como mucho una vez cada 10 s. En frío, la descarga de los abstracts de GeneRIF dura unos 30 min y, sin el aviso, parecería colgada. Una descarga de menos de 10 s no escribe nada.
  * **Tiempos de espera por petición:**
    * Europe PMC (abstracts): 30 s;
    * NCBI, búsqueda dirigida, HGNC y UniProt: 60 s;
    * MyGene: 120 s, porque pide hasta 1.000 genes a la vez.
  * **Si se agotan los reintentos:**
    * el lote de Europe PMC se salta y sus PMIDs pasan a NCBI;
    * un lote de NCBI fallido se repite PMID a PMID;
    * un PMID que sigue fallando no se guarda en la caché, así que se vuelve a pedir en la siguiente ejecución.
  * **Guardado parcial:** la caché de abstracts se guarda cada 25 lotes, para que un corte no obligue a repetir lo ya descargado.
  * **OBO y GAF:** su descarga no tiene reintentos (15 s de conexión y 120 s de lectura). Si falla, se relanza la ejecución, y como la escritura es atómica no queda ningún fichero a medias.
* **Solo referencias PubMed:** Se descartan las referencias que no sean `PMID` (p. ej. `GO_REF`, `DOI`, `Reactome`), las anotaciones con calificador `NOT` y las de taxón distinto de humano (`9606`).
* **Códigos de evidencia:** Se aceptan **todos los códigos de evidencia** que lleven `PMID`. Las anotaciones automáticas `IEA` quedan fuera de forma natural, porque nunca llevan PMID. Cada fila indica en la columna `Experimental` si su evidencia es experimental (`EXP`, `IDA`, `IPI`, `IMP`, `IGI`, `IEP` y sus equivalentes de alto rendimiento). El filtro estricto (`SOLO_EXPERIMENTAL`) es configurable y está desactivado por defecto.
* **Resolución de genes:** Un gen se identifica por su símbolo oficial y, solo si no hay ambigüedad, por un sinónimo del GAF (un sinónimo que sea el símbolo oficial de otro gen no se usa).
* **Formatos de entrada heterogéneos:** El módulo debe aceptar ficheros `.xlsx` y `.csv`, verificando la existencia de las columnas obligatorias (`ID`, `Description`, `geneID`) antes de iniciar las llamadas de red. `entrada_excel.leer_tabla` elige el lector por la extensión (en `.csv`, el separador `,` o `;` se detecta solo) y `main.py` lee y valida los dos ficheros antes de descargar el OBO y el GAF. Cualquier otra extensión se rechaza con `ValueError`.
* **Ubicación de la entrada:** `config.py` lee directamente los Excels originales de CIMUS, versionados en `codigo/tools_cimus/` (`NK_rutas_activadas_GO.xlsx` y `NK_rutas_suprimidas_GO.xlsx`), así que un clon limpio del repositorio tiene ya la entrada.
* **Gestión de credenciales y red:** El correo de contacto y la clave de API de NCBI (`NCBI_EMAIL`, `NCBI_API_KEY`) se leen de las variables de entorno o del fichero `codigo/.env` (documentado en `codigo/.env.example`), sin escribir datos privados en el código. `codigo/.env` no se sube al repositorio. Si no hay correo, no se envía ninguno.

## Criterios de aceptación
* [x] ✅ **Carga de la entrada:** Dado un Excel con una sola ruta, `GO:0000001` (obsoleta, sustituida por `GO:0000002`), y `geneID` = `CD7/gzmb/PRF1/NKG7/KLRD1`, el parser devuelve exactamente estas 5 filas, en este orden y todas con `Estado_Original = "Activada"`: `(GO:0000002, CD7)`, `(GO:0000002, GZMB)`, `(GO:0000002, PRF1)`, `(GO:0000002, NKG7)` y `(GO:0000002, KLRD1)`. (`tests/test_fase1.py::test_entrada_extrae_pares_y_traduce_ids_obsoletos`)
* [x] ✅ **Entrada de CIMUS:** Con los dos Excels de `codigo/tools_cimus/`, la carga da 3.172 pares y 224 genes, y ningún gen aparece en las dos listas. (`tests/test_fase1.py::test_entrada_lee_los_excels_de_cimus`)
* [x] ✅ **Validación de columnas:** Un fichero (`.xlsx` o `.csv`) al que le falte `ID`, `Description` o `geneID` se rechaza con un `ValueError` que nombra la columna que falta, antes de ninguna petición de red: `ejecutar_fase_1` no llega a llamar a `descargar_archivo`. (`tests/test_entrada.py::test_columna_ausente_da_value_error_con_su_nombre`, `::test_la_entrada_se_valida_antes_de_descargar`)
* [x] ✅ **Entrada `.csv`:** Un `.csv` con las mismas columnas y el mismo contenido que un `.xlsx`, separado por `,` o por `;`, da exactamente las mismas filas. (`tests/test_entrada.py::test_csv_da_los_mismos_pares_que_xlsx`)
* [x] ✅ **Reintentos:** La sesión de `red.configurar_sesion` reintenta 5 veces con `backoff_factor` 1 ante los códigos `429`, `500`, `502`, `503` y `504`, en GET y POST, y sus esperas son 0, 2, 4, 8 y 16 s. (`tests/test_red.py::test_reintentos_con_espera_exponencial`)
* [x] ✅ **Aviso de progreso:** `red.Progreso` avisa al cruzar cada paso de porcentaje con lo que lleva, el porcentaje, el tiempo transcurrido y lo que falta, da una última línea al 100 % y no escribe nada en una descarga corta. (`tests/test_red.py::test_progreso_avisa_con_porcentaje_y_tiempo`, `::test_progreso_no_avisa_en_una_descarga_corta`)
* [x] ✅ **Credenciales:**
  * `NCBI_EMAIL` y `NCBI_API_KEY` se leen de `codigo/.env`, que ignora los comentarios y las líneas sin `=`;
  * una variable de entorno tiene prioridad sobre el fichero;
  * sin fichero ni variable, el valor es `None` (`tests/test_fase1.py`);
  * `git check-ignore codigo/.env` confirma que no se versiona.
* [x] ✅ **Resolución gen–ruta → PMID:** Para el par de referencia (`CD7`, `GO:0002443` *leukocyte mediated immunity*), la salida contiene el `PMID` `10652336`, anotado en el término descendiente `GO:0002726` con evidencia `IDA` y `Polaridad_GO = +1`. Ninguna fila de la hoja `Con_abstract` contiene un `PMID` no numérico. (El par, comprobado en la ejecución del 2026-11-13; el PMID numérico, `tests/test_fase1_e2e.py::test_con_abstract_fuentes_y_limpieza`.)
* [x] ✅ **Composición de la polaridad en el grafo:** Para un término alcanzado a través de una única relación `negatively_regulates`, `Polaridad_GO` es `-1`; a través de dos relaciones `negatively_regulates` encadenadas, es `+1`; si el término se alcanza por caminos de signo opuesto, es `conflicto`. (`tests/test_fase1.py::test_polaridad_compuesta_por_el_grafo`, con un OBO mínimo.)
* [x] ✅ **Inmunoglobulinas:** los pares de genes de inmunoglobulina (p. ej. IGKC, IGHM) aparecen en la hoja `Inmunoglobulinas` con signo `neutro` y no aparecen en `Con_abstract`; IGFBP7, que empieza por «IG» pero no es una inmunoglobulina, no se aparta. (`tests/test_fase1_e2e.py::test_inmunoglobulinas_neutras_y_fuera_de_con_abstract`.)
* [x] ✅ **Triaje:** cada par de la entrada que no es inmunoglobulina tiene exactamente un `Destino` en `Triaje_polaridad`, y todo par sin ninguna fila en `Con_abstract` tiene una fila en `Sin_evidencia` con su causa y `Destino = sin_evidencia`, salvo los `aceptar_GO`: su signo no depende del abstract, así que conservan `aceptar_GO` y salen en `Sin_evidencia` con el signo GO, `Estado = resuelto_GO` y `Motivo = aceptar_GO` ([limitación de pares sin abstract](../docs/limitacion-pares-sin-abstract.md)). (`tests/test_fase1_e2e.py::test_triaje_un_destino_por_par`, `::test_pares_sin_abstract_cerrados_con_su_causa` y `::test_aceptar_go_sin_abstract_conserva_el_signo_go`.)
* [x] ✅ **Consumo y tolerancia a fallos en Europe PMC:** La función de descarga procesa un lote de hasta 40 `PMID`s en una sola petición HTTP. Ante un `PMID` inexistente o sin abstract, ese PMID no aparece entre los abstracts descargados (en la caché queda con el abstract vacío) y su fila pasa a `PMID_sin_abstract`, sin interrumpir el resto del lote. (`tests/test_fase1.py::test_descarga_por_lotes_con_respaldo_y_cache`, `tests/test_fase1_e2e.py::test_pares_sin_abstract_cerrados_con_su_causa`)
* [x] ✅ **Reutilización de la caché:** Una segunda ejecución sobre la misma entrada, con la caché de abstracts completa, no realiza ninguna petición a Europe PMC ni a NCBI para descargar abstracts. (`tests/test_fase1.py::test_descarga_por_lotes_con_respaldo_y_cache`, `tests/test_fase1_e2e.py::test_segunda_ejecucion_sin_peticiones`)
* [x] ✅ **Pruebas unitarias desacopladas de red (Mocks/Fixtures):** La suite de pruebas en `pytest` (`codigo/tests/`) ejecuta la descarga emulando las respuestas HTTP de Europe PMC y NCBI con respuestas simuladas, sin conexión a internet. `tests/test_fase1_e2e.py` ejecuta la Fase 1 completa (y su paso por las Fases 2 y 3) con los datos de `codigo/tests/fixtures/`: un OBO y un GAF mínimos, las dos listas de CIMUS y las respuestas grabadas de HGNC, UniProt, MyGene.info, Europe PMC y NCBI, con los sockets bloqueados. Una segunda ejecución sale de las cachés. La suite completa tarda unos 3 s.
