---
description: Ingesta de evidencias a partir del fichero GAF de Gene Ontology y descarga de abstracts por lotes desde Europe PMC, con NCBI E-utilities como respaldo.
state: Aceptado
---

# ADR 002 - Ingesta de Evidencias: GAF de Gene Ontology + Europe PMC con Respaldo en NCBI

## Decisión
La ingesta de evidencias (Fase 1, `codigo/extraer_info/`) se resuelve en dos etapas:

1. **Mapeo gen–ruta → PMID a partir de ficheros oficiales de Gene Ontology**, descargados una sola vez:
   * `go-basic.obo` (ontología) para construir el grafo de términos, resolver identificadores obsoletos o alternativos (`alt_id`, `replaced_by`) y propagar cada ruta del Excel a sus términos descendientes mediante las relaciones `is_a`, `part_of`, `regulates`, `positively_regulates` y `negatively_regulates`, componiendo el signo a lo largo del camino (`Polaridad_GO`).
   * `goa_human.gaf.gz` (anotaciones humanas) leído en **una sola pasada**, descartando anotaciones con calificador `NOT` y de taxón distinto de `9606`. De cada anotación se extraen los identificadores `PMID:` de la columna de referencias. Los genes se resuelven por símbolo oficial y, solo si no hay ambigüedad, por sinónimo.
2. **Descarga de título y abstract de cada PMID** con peticiones HTTP **síncronas y por lotes**:
   * **Europe PMC** (servicio REST `search`, formato JSON) en lotes de **40 PMIDs** por petición.
   * **NCBI E-utilities** (`efetch`, XML) como **respaldo** para los PMIDs que Europe PMC no devuelve, en lotes de 100. Si un lote falla, se reintenta PMID a PMID.

La comunicación HTTP usa una sesión `requests` con **reintentos automáticos y espera exponencial** ante `429`, `500`, `502`, `503` y `504`, y pausas de cortesía entre lotes (0,2 s en Europe PMC; 0,35 s en NCBI, o 0,12 s con clave de API).

## Motivación
1. **Un solo fichero frente a miles de llamadas:** el GAF humano (~15 MB comprimido) contiene todas las anotaciones de todos los genes. Leerlo localmente sustituye a una consulta por gen y término a una API, elimina los *rate limits* en esta etapa y permite trabajar sin conexión una vez descargado.
2. **Reproducibilidad:** el GAF y el OBO son instantáneas fechadas (la versión actual del GAF se generó el 2026-05-21). Una ejecución puede repetirse sobre exactamente los mismos datos, algo que una API viva no garantiza.
3. **La polaridad sale del grafo, no del texto:** al propagar por `positively_regulates` y `negatively_regulates`, la Fase 1 obtiene ya un signo curado por GO para muchos pares (en la ruta de prueba *leukocyte mediated immunity*, las 20 filas de genes activados con abstract tienen signo: 9 positivas y 7 negativas). Ese signo sirve después para contrastar la salida del LLM.
4. **Europe PMC primero por su formato:** devuelve el abstract como un campo JSON (`abstractText`), más sencillo de procesar que el XML de PubMed. NCBI se mantiene como respaldo porque cubre PMIDs cuyo abstract no está en Europe PMC.
5. **Síncrono es suficiente:** para los 126 genes de las rutas activadas, el GAF da como máximo **697 PMIDs únicos** de proceso biológico, es decir, unos **18 lotes** en Europe PMC. Con ese volumen el cuello de botella son los límites de las APIs, no la concurrencia; un cliente asíncrono añadiría complejidad sin acelerar la descarga.
6. **Filtrado implícito de evidencia no informativa:** al exigir un `PMID`, las referencias `GO_REF`, `Reactome` u otras quedan fuera. Las anotaciones automáticas `IEA` nunca llevan PMID en el GAF actual (0 de 194.927), así que tampoco llegan al LLM. El resto de códigos se conservan y se marcan con la columna `Experimental`; el filtro estricto (`SOLO_EXPERIMENTAL`) queda como opción configurable en `config.py`.
7. **Tolerancia a fallos:** un PMID que no existe o no tiene abstract no interrumpe el lote; los confirmados sin abstract se registran como cadena vacía y los que fallan por red se reintentan en la siguiente ejecución.

Aceptamos los compromisos asociados: el GAF debe actualizarse a mano para incorporar anotaciones nuevas; la cobertura queda limitada a los artículos que los curadores de GO han asociado a cada gen (en la ruta de prueba, solo **12 de los 26 pares** de genes activados tienen al menos un abstract); y la ingesta se limita a abstracts de acceso abierto, sin texto completo.

## Alternativas
* **API REST de QuickGO por gen y término (plan inicial):**
  * *Motivo de descarte:* exige una petición por combinación gen–término, multiplica la exposición a *rate limits* y depende del estado del servicio en cada ejecución. El GAF ofrece la misma información de anotación en un único fichero versionable.
* **AmiGO / GOlr (prototipo `codigo/ApiREST_OFICIAL.py`):**
  * *Motivo de descarte:* se probó al inicio del proyecto para obtener las referencias de cada gen. Requiere dos consultas por lote (entidades y anotaciones) y no aporta la estructura del grafo necesaria para propagar la polaridad.
* **Solo NCBI / PubMed:**
  * *Motivo de descarte:* la respuesta XML exige un parseo más complejo (secciones etiquetadas, `PubmedBookArticle`) y los límites sin clave de API son estrictos. Se conserva como respaldo, no como fuente principal.
* **Solo Europe PMC:**
  * *Motivo de descarte:* algunos PMIDs no tienen abstract en Europe PMC; sin respaldo se perderían evidencias.
* **Cliente asíncrono (`aiohttp` / `httpx`):**
  * *Motivo de descarte:* con unos 18 lotes el beneficio es mínimo y lanzar peticiones en paralelo aumenta el riesgo de `429`.
* **Búsqueda libre de literatura (gen + nombre de la ruta en Europe PMC):**
  * *Motivo de descarte por ahora:* aumentaría la cobertura, pero introduce artículos no curados y mucho ruido. Queda como posible mejora si la cobertura resulta insuficiente.

## Referencias
* **Código del proyecto:**
  * `codigo/extraer_info/grafo_go.py` (OBO, propagación y composición de signos), `cruce_gaf.py` (lectura del GAF), `abstracts.py` (Europe PMC + NCBI), `red.py` (sesión con reintentos y descarga atómica) y `config.py` (URLs, lotes y opciones de filtrado).
* **Fuentes de datos:**
  * Ficheros de anotación de GO: [https://current.geneontology.org/annotations/](https://current.geneontology.org/annotations/)
  * Formato GAF 2.2: [https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/](https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/)
  * Códigos de evidencia de GO: [https://geneontology.org/docs/guide-go-evidence-codes/](https://geneontology.org/docs/guide-go-evidence-codes/)
  * Ontología `go-basic.obo`: [https://purl.obolibrary.org/obo/go/go-basic.obo](https://purl.obolibrary.org/obo/go/go-basic.obo)
* **APIs:**
  * Europe PMC REST: [https://europepmc.org/RestfulWebService](https://europepmc.org/RestfulWebService)
  * NCBI E-utilities: [https://www.ncbi.nlm.nih.gov/books/NBK25499/](https://www.ncbi.nlm.nih.gov/books/NBK25499/)
* **Ejemplo de consulta por lotes a Europe PMC** (`abstracts.py`):

  ```python
  query = "(" + " OR ".join(f"EXT_ID:{p}" for p in lote) + ") AND SRC:MED"
  params = {"query": query, "resultType": "core", "format": "json", "pageSize": 100}
  ```
