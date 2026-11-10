# Limitación: pares (gen, ruta) sin ningún abstract

> Estado: **vigente** (2026-11-08; cifras actualizadas con la ejecución completa del 2026-11-09). Afecta a la Fase 1 (ingesta) y a cómo la Fase 2 y el Net Pathway Score
> tratan estos pares. Código: `codigo/extraer_info/polaridad.py` (`cerrar_sin_evidencia`).

## 1. El problema

La Fase 2 decide el signo de cada par leyendo abstracts de PubMed. Si un par no tiene ningún abstract,
no hay texto que leer ni cita que verificar. Por eso **no se puede enviar al LLM**.

La Fase 1 busca abstracts en tres fuentes, en cascada:

1. **GO GAF:** los PMIDs de las anotaciones del gen a la ruta o a cualquier término de su subárbol.
2. **NCBI GeneRIF:** frases curadas sobre el gen, a través de MyGene.info.
3. **Europe PMC dirigida:** el gen y un término de la ruta en la misma frase.

Aun así, en la ejecución completa sobre los Excels de CIMUS (`fase1_ejecucion_completa/`, 2026-11-09)
quedan sin evidencia **668 de 3.069 pares** (22 %, sin contar las inmunoglobulinas), que afectan a 124 genes y
261 rutas. Las columnas son las dos listas de CIMUS: rutas de genes *up* («activadas») y de genes *down*
(«suprimidas»).

| | Activadas | Suprimidas | Total |
|---|---|---|---|
| Pares sin ningún abstract | 488 (de 2.386) | 180 (de 683) | 668 |
| `anotado_sin_PMID`: el gen solo está en la ruta por anotaciones GO sin artículo | 272 | 123 | 395 |
| `sin_anotacion_GAF`: el gen no tiene anotación a la ruta en el GAF actual | 216 | 57 | 273 |
| `PMID_sin_abstract`: el par tiene PMIDs, pero ninguno tiene abstract en PubMed | 0 | 0 | 0 |
| Con signo GO (solo como pista; ver § 2) | 100 | 38 | 138 |

La tercera causa existe en el código, pero en esta ejecución no aparece: las fuentes externas encontraron otro
abstract para todos los pares cuyos PMIDs no lo tenían.

Códigos de evidencia de las anotaciones de esos pares:
- IEA (electrónica): 234
- ISS (por similitud, casi siempre heredada de ratón, rata o vaca): 200
- IBA (filogenética): 93
- TAS de Reactome (la referencia es un ID de Reactome, no un PMID): 14

Un par puede tener varias de estas anotaciones.

**Por qué no tienen evidencia.** Hay tres razones de fondo:

- **Anotación sin artículo detrás.** Es una consecuencia de cómo se construyen las anotaciones. Una IEA, una ISS o
  una IBA trasladan una función desde otra especie o desde un árbol filogenético, sin ningún artículo humano detrás.
- **Anotación que ya no está en el GAF.** Probablemente vienen de una versión antigua de `org.Hs.eg.db`, que es la que
  usó CIMUS en `enrichGO`. En ella había anotaciones que el GAF vigente ya no tiene. Es un artefacto de versión,
  no una relación biológica.
- **El artículo existe, pero no se encuentra.** Los autores describen el proceso con otras palabras: *Fas/CD95/TRAIL*
  en vez de *extrinsic apoptotic signaling pathway*, *LPS* en vez de *response to molecule of bacterial origin*.
  Ni el GAF ni la búsqueda con los nombres GO llegan a ese artículo.

## 2. Cómo se gestionan hoy

Estos pares se cierran de forma determinista en la Fase 1 y nunca generan prompts:

- **`Resultado = UNKNOWN`**, **`Estado = no_concluyente`** y **`Motivo = sin_evidencia:<causa>`**. Así encajan en el
  esquema de motivos del ADR-003.
- **`Detalle`**: el motivo en lenguaje claro, por ejemplo *«Solo hay anotación GO sin artículo (ISS (por similitud de
  secuencia, a menudo de otra especie)). No se envía al LLM.»*
- **`Pista_GO`**: el signo GO del par, si tiene. Es solo informativo, porque viene de anotaciones sin experimento.
  El triaje (informe «Polaridad GO como signo directo») solo acepta el signo GO con evidencia experimental
  y PMID.
- **`Evidencias_GO`, `Referencias_GO` y `With_From_GO`**: las anotaciones de origen. Permiten auditar el par y
  son la entrada de la resolución del § 3. Por ejemplo, `Reactome:R-HSA-…` o la proteína de ratón de una ISS.
- En la hoja `Triaje_polaridad`, estos pares tienen `Destino = sin_evidencia` (y «sin_evidencia» añadido a su
  `Motivo`), sin `Contribucion` y sin bandera de freno. **No cuentan en el Net Pathway Score.** Cada ruta debe
  informar su cobertura (`n_con_signo / n_total`) para que se vea qué parte de la ruta queda sin evidencia. Esto
  lo tendrá que calcular la Fase 3, que está pendiente.

**Excepción: pares `aceptar_GO` sin abstract.** Si el triaje ya había aceptado el signo GO de un par (una anotación
experimental con PMID, a poca profundidad) y ese PMID no tiene abstract, el par no se cierra como `UNKNOWN`: sale
con `Resultado` = el signo GO, `Estado = resuelto_GO` y `Motivo = aceptar_GO`, porque su signo no depende de leer
el abstract. En la ejecución del 2026-11-09 no hay ningún caso así.

Opciones descartadas:
- **Enviar al LLM la función general del gen** (UniProt o el resumen de NCBI) en lugar del abstract. El texto no
  habla del efecto del gen en la ruta. El LLM tendería a responder de memoria y no habría ninguna frase que
  verificar como cita.
- **Usar la `Pista_GO` como resultado.** Ese signo sale de IEA, ISS o IBA, que es justo lo que el triaje no acepta.

## 3. Posible resolución para reducir los 668

La investigación «Bases gratuitas para pares sin PMID» se probó con los 12 genes que no tenían ningún PMID en la
ejecución del 2026-11-08 (está en `PIA2/reports/`, fuera del repo). Su conclusión es que **falta sobre todo vocabulario, no bases**.
Con los nombres GO, Europe PMC devolvía 0 resultados para esos genes. Con palabras clave de autor sí aparecían
los artículos buenos.

Juntando todas las fuentes, hubo evidencia humana aceptable para 6 de los 12 genes (unos 8 de sus 33 pares).
Propone tres pasos, todos gratuitos, sobre abstracts de PubMed y compatibles con una Fase 1 determinista.
Cada uno sería una etapa más de `pmid_externos.py`, y solo actuaría sobre los pares que siguen vacíos.

### Paso 1. Reactome: convertir las anotaciones TAS en PMIDs

- **Qué:** algunas anotaciones del GAF no citan un PMID sino una reacción o vía de Reactome (`Reactome:R-HSA-…`
  en `Referencias_GO`). Para cada una se piden a Reactome los artículos de esa reacción, que tienen PMID.
- **Cómo:** con la API ContentService, `https://reactome.org/ContentService/data/query/<stId>`, que devuelve los
  PMIDs en `literatureReference`. La alternativa es el fichero masivo `ReactionPMIDS.txt`, quedándose solo
  con los IDs `R-HSA`. Los datos de Reactome son CC0.
- **Filtro:** se acepta el PMID solo si su abstract nombra el gen. Por ejemplo, las referencias de la vía de
  SEC11A no lo nombran y se descartan.
- **Alcance:** 14 pares de los 668, pocos pero muy limpios. En la prueba resolvió CTSZ → procesamiento de hormonas
  peptídicas (PMID 19800993).
- **Coste:** una petición por ID de Reactome distinto, con caché. Es el paso más barato.

### Paso 2. NCBI gene2pubmed + MeSH de la ruta + «Humans»

- **Qué:** se buscan los artículos que NCBI ya liga al gen humano y que tienen asignado el MeSH del proceso.
  Así lo hace NCBI dos veces: liga el gen al artículo y el indexador de MeSH juzga el tema. Fue la fuente
  **más precisa** de la prueba.
- **Cómo:** con NCBI E-utilities:
  1. `elink dbfrom=gene linkname=gene_pubmed` da los PMIDs del gen. Otra opción es el fichero `gene2pubmed.gz`,
     de 291 MB, que se actualiza a diario.
  2. `esearch` restringe esos PMIDs con `"<MeSH>"[MeSH] AND "Humans"[MeSH]`.

  Ejemplo: `BCL2A1[tiab] AND "Apoptosis"[MeSH]`.
- **Requisito:** una **tabla ruta GO → MeSH**, que no está publicada. Hay que construirla una vez para las rutas
  afectadas (261, o menos si se agrupan por ancestro común). Se guardaría como un TSV versionado junto al código,
  con una persona revisándola.
- **Alcance en la prueba:** 3 de los 12 genes (ACP5, BCL2A1, MAP2K3).
- **Coste:** unas 2 peticiones por gen y ruta, con caché. Sin clave de NCBI, el límite es de 3 por segundo;
  con `NCBI_API_KEY`, de 10 por segundo.

### Paso 3. Diccionario ruta → palabras clave para la búsqueda de Europe PMC

- **Qué:** la búsqueda dirigida que ya existe se amplía con las palabras que usan los autores para cada ruta.
  Por ejemplo:

  | Ruta | Palabras clave |
  |---|---|
  | *extrinsic apoptotic signaling pathway* | Fas, CD95, TRAIL, death receptor, caspase-8 |
  | *response to lipopolysaccharide* | LPS, endotoxin, TLR4 |
  | *peptide hormone processing* | bradykinin, angiotensin |

  No añade ninguna base.
- **Cómo:** un TSV `ruta → palabras clave`, versionado. Esas palabras se suman a las frases GO de la consulta
  y a la comprobación local de la misma frase.
- **Para que la Fase 1 siga siendo determinista:** el diccionario se genera una sola vez, a mano o con un LLM
  y revisado por una persona, y después no cambia. Nunca se genera en tiempo de ejecución.
- **Alcance en la prueba:** fue **lo que más rindió**, 5 de los 12 genes (ACP5, BCL2A1, CTSZ, MAP2K3 y SEC11A).
- **Riesgo:** las palabras clave cortas son ambiguas (TRAP, LIGHT, A1…). Se mantienen los filtros actuales:
  el gen en la misma frase, los alias en minúsculas no cuentan y las siglas de una sola palabra se excluyen.
  Además hay que marcar los resultados de **dirección inversa** (*NF-κB induce LTB* no dice que LTB active NF-κB).

### Qué no se resolverá

En varios pares, la falta de evidencia humana es **real**, porque solo existe la transferencia desde otra especie:

- **Sin evidencia humana:** ADGRG3, FAM89B, KDM6B y TBCD.
- **Probable error de anotación:** ITM2C. Su artículo de origen trata de *Bri3*, otro gen de ratón.
- **Rutas concretas sin evidencia humana:** LTB → producción de IL-12, CTSZ → morfogénesis de tubo epitelial y
  ACP5 → respuesta a molécula bacteriana.

Para estos pares, lo correcto es el UNKNOWN actual con su `Detalle`, no forzar un resultado.

## 4. Cómo medirlo

Antes de dar por buena cada etapa, conviene hacer un piloto sobre los 668 pares y medir dos cosas:

1. **Cobertura:** cuántos pares pasan de `sin_evidencia` a tener un abstract.
2. **Precisión:** en una muestra de unos 30 pares por etapa, leída a mano, si el abstract trata del gen en el
   proceso, en humano y en la dirección correcta.

Una etapa solo se queda si su precisión es comparable a la de GeneRIF y Europe PMC (en las revisiones manuales
de 2026-11-08, unos 8 de cada 10 abstracts trataban del gen en el proceso). Si no la alcanza, sus PMIDs pasan
a revisión humana en vez de ir directamente al LLM.

Orden recomendado:
1. Reactome, porque es inmediato.
2. El diccionario de palabras clave, porque es lo que más rinde.
3. gene2pubmed + MeSH, porque exige la tabla de MeSH.
