---
description: Ingesta de evidencias a partir del fichero GAF de Gene Ontology, con GeneRIF y búsqueda dirigida en Europe PMC para los pares sin artículo, y descarga de abstracts por lotes desde Europe PMC con NCBI E-utilities como respaldo.
state: Aceptado (fuentes externas añadidas el 2026-11-08; cifras de la ejecución completa del 2026-11-13)
---

# ADR 002 - Ingesta de Evidencias: GAF de Gene Ontology + Europe PMC con Respaldo en NCBI

## Decisión
La ingesta de evidencias (Fase 1, `codigo/fase1_ingesta/`) se resuelve en tres etapas:

1. **Mapeo gen–ruta → PMID a partir de ficheros oficiales de Gene Ontology**, descargados una sola vez:
   * `go-basic.obo` (ontología): sirve para construir el grafo de términos, resolver identificadores obsoletos o alternativos (`alt_id`, `replaced_by`) y propagar cada ruta del Excel a todo su subárbol mediante las relaciones `is_a`, `part_of`, `regulates`, `positively_regulates` y `negatively_regulates`. A lo largo del camino se componen el signo (`Polaridad_GO`) y la profundidad.
   * `goa_human.gaf.gz` (anotaciones humanas), leído en **una sola pasada**:
     * se descartan las anotaciones con calificador `NOT` y las de taxón distinto de `9606`;
     * de cada anotación se extraen los identificadores `PMID:` de la columna de referencias, el código de evidencia, el calificador y la extensión;
     * los genes se resuelven por símbolo oficial y, solo si no hay ambigüedad, por sinónimo.
2. **Fuentes externas para los pares sin abstract utilizable en el GAF** (sin PMID, o con PMIDs que no tienen abstract en PubMed):
   * **NCBI GeneRIF**, vía MyGene.info: frases curadas por NCBI, cada una con su PMID. Solo se acepta si la frase del GeneRIF o el abstract nombran al gen y a la ruta (o a un término de su subárbol).
   * **Búsqueda dirigida en Europe PMC**, para los pares que siguen vacíos: se buscan el gen (con sus alias) y los nombres de la ruta y de su subárbol hasta 2 niveles, y solo se acepta un abstract si el gen y un término del subárbol aparecen **en la misma frase**. Los alias en minúsculas no cuentan como mención del gen.
   * Como máximo 10 PMIDs por par, y cada fila guarda su `Fuente` y la frase que la justifica.
3. **Descarga de título y abstract de cada PMID** con peticiones HTTP **síncronas y por lotes**:
   * **Europe PMC** (servicio REST `search`, formato JSON) en lotes de **40 PMIDs** por petición.
   * **NCBI E-utilities** (`efetch`, XML) como **respaldo** para los PMIDs que Europe PMC no devuelve, en lotes de 100. Si un lote falla, se reintenta PMID a PMID.

La comunicación HTTP usa una sesión `requests` con **reintentos automáticos y espera exponencial** ante `429`, `500`, `502`, `503` y `504`, y pausas de cortesía entre lotes: 0,2 s en Europe PMC, y 0,35 s en NCBI (0,12 s con clave de API, que se lee de `codigo/.env`). Todas las respuestas se guardan en cachés locales ([ADR-004](adr-004-persistencia-ficheros-locales.md)).

Los genes de inmunoglobulina (lista de HGNC) se apartan antes del cruce y no siguen este camino: se tratan como neutros, con la función de la Ig completa según UniProt.

## Motivación
1. **Un solo fichero frente a miles de llamadas:** el GAF humano (~15 MB comprimido) contiene todas las anotaciones de todos los genes. Leerlo localmente sustituye a una consulta por gen y término a una API, elimina los *rate limits* en esta etapa y permite trabajar sin conexión una vez descargado.
2. **Reproducibilidad:** el GAF y el OBO son instantáneas fechadas (la versión actual del GAF se generó el 2026-05-21). Una ejecución puede repetirse sobre exactamente los mismos datos, algo que una API viva no garantiza.
3. **La polaridad sale del grafo, no del texto:** al propagar por `positively_regulates` y `negatively_regulates`, la Fase 1 obtiene ya un signo curado por GO para muchos pares. En la ejecución del 2026-11-13, el 25 % de las 5.176 filas con abstract tiene `Polaridad_GO` +1 o −1. Ese signo sirve después para contrastar la salida del LLM, y en 332 pares basta para aceptarlo sin LLM (triaje `aceptar_GO`, [spec de ingesta](../specs/descarga-evidencias-go-pmc.md)).
4. **El GAF no basta para muchos pares:**
   * De los 3.069 pares (sin inmunoglobulinas) de las dos listas de CIMUS, solo 1.547 tienen algún PMID en el GAF. Sin otra fuente, la mitad de los pares no tendría ningún artículo que leer.
   * Para elegir las fuentes externas se siguió el criterio de usar el menor número posible de bases, gratuitas y con los abstracts más fiables y claros. GeneRIF es curado y da el PMID directamente. La búsqueda dirigida en Europe PMC cubre lo que GeneRIF no tiene, con un filtro (gen y proceso en la misma frase) que limita el ruido de una búsqueda libre.
   * En la ejecución del 2026-11-13, de los 1.523 pares sin abstract del GAF, **881** consiguen PMID con estas fuentes. Los **642** que siguen sin ninguno se cierran como `UNKNOWN` ([limitación documentada](../docs/limitacion-pares-sin-abstract.md)).
5. **Europe PMC primero por su formato:** devuelve el abstract como un campo JSON (`abstractText`), más sencillo de procesar que el XML de PubMed. NCBI se mantiene como respaldo porque cubre PMIDs cuyo abstract no está en Europe PMC.
6. **Síncrono es suficiente:**
   * El GAF da 383 PMIDs únicos (ejecución del 2026-11-13). Las fuentes externas, en cambio, descargan unos 32.700 abstracts candidatos para comprobar si nombran al gen y al proceso, y al final quedan 1.489 PMIDs en total (GAF y fuentes externas).
   * La primera ejecución completa tarda casi una hora, sobre todo por esa comprobación. Las siguientes reutilizan la caché y tardan unos minutos.
   * El cuello de botella son los límites de las APIs, no la concurrencia: lanzar peticiones en paralelo aumentaría el riesgo de `429` sin acelerar la descarga.
7. **Filtrado implícito de evidencia no informativa:** al exigir un `PMID`, las referencias `GO_REF`, `Reactome` u otras quedan fuera. Las anotaciones automáticas `IEA` nunca llevan PMID en el GAF actual (0 de 194.927), así que tampoco llegan al LLM. El resto de códigos se conservan y se marcan con la columna `Experimental`; el filtro estricto (`SOLO_EXPERIMENTAL`) queda como opción configurable en `config.py`.
8. **Tolerancia a fallos:** un PMID que no existe o no tiene abstract no interrumpe el lote; los confirmados sin abstract se registran como cadena vacía y los que fallan por red se reintentan en la siguiente ejecución.

Aceptamos los compromisos asociados:
* **El GAF se actualiza a mano** para incorporar anotaciones nuevas.
* **Las fuentes externas no son instantáneas fechadas:** GeneRIF y Europe PMC cambian con el tiempo, y Europe PMC ordena por relevancia. Volver a descargarlas puede cambiar los PMIDs elegidos, así que sus cachés no son del todo desechables.
* **Una mención en la misma frase no garantiza que el abstract trate el efecto del gen.** Eso lo decide la Fase 2.
* **Solo título y abstract:** la ingesta se limita al título y el abstract de PubMed, sin texto completo.

## Alternativas
* **API REST de QuickGO por gen y término (plan inicial):**
  * *Motivo de descarte:* exige una petición por combinación gen–término, multiplica la exposición a *rate limits* y depende del estado del servicio en cada ejecución. El GAF ofrece la misma información de anotación en un único fichero versionable.
* **AmiGO / GOlr (prototipo `ApiREST_OFICIAL.py`, ya eliminado; queda en el historial de git, commits `7859082` y `e0c5b70`):**
  * *Motivo de descarte:* se probó al inicio del proyecto para obtener las referencias de cada gen. Requiere dos consultas por lote (entidades y anotaciones) y no aporta la estructura del grafo necesaria para propagar la polaridad.
* **Solo NCBI / PubMed:**
  * *Motivo de descarte:* la respuesta XML exige un parseo más complejo (secciones etiquetadas, `PubmedBookArticle`) y los límites sin clave de API son estrictos. Se conserva como respaldo, no como fuente principal.
* **Solo Europe PMC:**
  * *Motivo de descarte:* algunos PMIDs no tienen abstract en Europe PMC; sin respaldo se perderían evidencias.
* **Cliente asíncrono (`aiohttp` / `httpx`):**
  * *Motivo de descarte:* el límite lo ponen las APIs; lanzar peticiones en paralelo aumenta el riesgo de `429`, y con la caché solo se paga una vez.
* **Búsqueda libre de literatura (gen + nombre de la ruta en Europe PMC, sin más filtro):**
  * *Motivo de descarte:* introduce artículos no curados y mucho ruido. Se usa en su lugar la búsqueda dirigida, que exige el gen y el proceso en la misma frase.
* **UniProt FUNCTION como fuente de PMIDs:**
  * *Motivo de descarte:* se probó el 2026-11-08 y aportaba pocos pares. UniProt se sigue usando solo para describir la función de las inmunoglobulinas.
* **GeneCards:**
  * *Motivo de descarte:* sus condiciones de uso prohíben el acceso automatizado.
* **OmniPath y otras bases:**
  * *Aplazadas.* Para los pares que siguen sin abstract (642), se probó gene2pubmed + MeSH (#31, sobre los 668 de la Fase 1 del 2026-11-09): con el MeSH buscado de forma automática solo gana abstract el 3,9 % de los pares; con una tabla ruta GO → MeSH hecha a mano, el 51 % (326 de 642), pero con una precisión del 53 % en una muestra leída, por debajo de GeneRIF y Europe PMC (documento de la limitación).

## Referencias
* **Código del proyecto** (`codigo/fase1_ingesta/`):
  * `grafo_go.py`: OBO, propagación y composición de signos.
  * `cruce_gaf.py`: lectura del GAF.
  * `pmid_externos.py`, `relevancia.py` y `fuentes/` (`generif.py`, `europepmc.py`, `uniprot.py`, `cache.py`): fuentes externas.
  * `inmunoglobulinas.py`: genes de inmunoglobulina.
  * `polaridad.py`: triaje del signo GO y cierre `sin_evidencia`.
  * `abstracts.py`: Europe PMC y NCBI.
  * `red.py`: sesión con reintentos y descarga atómica.
  * `config.py`: URLs, límites y opciones de filtrado.
* **Informe:** `reports/Bases gratuitas para pares sin PMID.md` (fuera del repositorio): comparación de fuentes gratuitas y mejoras propuestas.
* **Fuentes de datos:**
  * Ficheros de anotación de GO: [https://current.geneontology.org/annotations/](https://current.geneontology.org/annotations/)
  * Formato GAF 2.2: [https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/](https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/)
  * Códigos de evidencia de GO: [https://geneontology.org/docs/guide-go-evidence-codes/](https://geneontology.org/docs/guide-go-evidence-codes/)
  * Ontología `go-basic.obo`: [https://purl.obolibrary.org/obo/go/go-basic.obo](https://purl.obolibrary.org/obo/go/go-basic.obo)
  * NCBI GeneRIF: [https://www.ncbi.nlm.nih.gov/gene/about-generif](https://www.ncbi.nlm.nih.gov/gene/about-generif) · MyGene.info: [https://mygene.info/](https://mygene.info/)
* **APIs:**
  * Europe PMC REST: [https://europepmc.org/RestfulWebService](https://europepmc.org/RestfulWebService)
  * NCBI E-utilities: [https://www.ncbi.nlm.nih.gov/books/NBK25499/](https://www.ncbi.nlm.nih.gov/books/NBK25499/)
* **Ejemplo de consulta por lotes a Europe PMC** (`abstracts.py`):

  ```python
  query = "(" + " OR ".join(f"EXT_ID:{p}" for p in lote) + ") AND SRC:MED"
  params = {"query": query, "resultType": "core", "format": "json", "pageSize": 100}
  ```
