# Limitación: pares (gen, ruta) sin ningún abstract

> Estado: **vigente**. Cifras de la ejecución de referencia de la Fase 1 del 2026-11-13. Afecta a la Fase 1 (ingesta) y a cómo la Fase 2 y el Net Pathway Score
> tratan estos pares. Código: `codigo/fase1_ingesta/polaridad.py` (`cerrar_sin_evidencia`).

## 1. El problema

La Fase 2 decide el signo de cada par leyendo abstracts de PubMed. Si un par no tiene ningún abstract,
no hay texto que leer ni cita que verificar. Por eso **no se puede enviar al LLM**.

La Fase 1 busca abstracts en cuatro fuentes, en cascada:

1. **GO GAF:** los PMIDs de las anotaciones del gen a la ruta o a cualquier término de su subárbol.
2. **NCBI GeneRIF:** frases curadas sobre el gen, a través de MyGene.info.
3. **Europe PMC dirigida:** el gen y un término de la ruta en la misma frase.
4. **NCBI gene2pubmed + MeSH:** los artículos que NCBI liga al gen con el MeSH de la ruta y «Humans» (§ 3).

Aun así, en la ejecución completa sobre los Excels de CIMUS (ejecución de referencia de la Fase 1, 2026-11-13)
quedan sin evidencia **310 de 3.069 pares** (10 %, sin contar las inmunoglobulinas), que afectan a 89 genes y
154 rutas. Las columnas son las dos listas de CIMUS: rutas de genes *up* («activadas») y de genes *down*
(«suprimidas»).

| | Activadas | Suprimidas | Total |
|---|---|---|---|
| Pares sin ningún abstract | 202 (de 2.386) | 108 (de 683) | 310 |
| `anotado_sin_PMID`: el gen solo está en la ruta por anotaciones GO sin artículo | 133 | 74 | 207 |
| `sin_anotacion_GAF`: el gen no tiene anotación a la ruta en el GAF actual | 69 | 34 | 103 |
| `PMID_sin_abstract`: el par tiene PMIDs, pero ninguno tiene abstract en PubMed | 0 | 0 | 0 |
| Con signo GO (solo como pista; ver § 2) | 45 | 22 | 67 |

La tercera causa existe en el código, pero en esta ejecución no aparece: las fuentes externas encontraron otro
abstract para todos los pares cuyos PMIDs no lo tenían.

Códigos de evidencia de las anotaciones de esos pares:
- IEA (electrónica): 134
- ISS (por similitud, casi siempre heredada de ratón, rata o vaca): 105
- IBA (filogenética): 39
- TAS de Reactome (la referencia es un ID de Reactome, no un PMID): 12

Un par puede tener varias de estas anotaciones.

**Por qué no tienen evidencia.** Hay tres razones de fondo:

- **Anotación sin artículo detrás.** Es una consecuencia de cómo se construyen las anotaciones. Una IEA, una ISS o
  una IBA trasladan una función desde otra especie o desde un árbol filogenético, sin ningún artículo humano detrás.
- **Anotación que ya no está en el GAF.** Probablemente vienen de una versión antigua de `org.Hs.eg.db`, que es la que
  usó CIMUS en su análisis de enriquecimiento. En ella había anotaciones que el GAF vigente ya no tiene. Es un artefacto de versión,
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
- **`Evidencias_GO`, `Referencias_GO` y `With_From_GO`**: las anotaciones de origen. Permiten auditar el par, por
  ejemplo, ver que una ISS viene de la proteína de ratón.
- En la hoja `Triaje_polaridad`, estos pares tienen `Destino = sin_evidencia` (y «sin_evidencia» añadido a su
  `Motivo`), sin `Contribucion` y sin bandera de freno. **No cuentan en el Net Pathway Score.** La Fase 3
  informa la cobertura de cada ruta (columna `Cobertura` de `Por_ruta`), para que se vea qué parte de la ruta
  queda sin evidencia.

**Excepción: pares `aceptar_GO` sin abstract.** Si el triaje ya había aceptado el signo GO de un par (una anotación
experimental con PMID, a poca profundidad) y ese PMID no tiene abstract, el par no se cierra como `UNKNOWN`: sale
con `Resultado` = el signo GO, `Estado = resuelto_GO` y `Motivo = aceptar_GO`, porque su signo no depende de leer
el abstract. En la ejecución del 2026-11-13 no hay ningún caso así.

Opciones descartadas:
- **Enviar al LLM la función general del gen** (UniProt o el resumen de NCBI) en lugar del abstract. El texto no
  habla del efecto del gen en la ruta. El LLM tendería a responder de memoria y no habría ninguna frase que
  verificar como cita.
- **Usar la `Pista_GO` como resultado.** Ese signo sale de IEA, ISS o IBA, que es justo lo que el triaje no acepta.

## 3. Resolución de los pares sin abstract: gene2pubmed + MeSH

La investigación «Bases gratuitas para pares sin PMID» se probó con los 12 genes que no tenían ningún PMID en la
ejecución del 2026-11-08: juntando todas las fuentes, hubo evidencia humana aceptable para 6 de ellos (unos 8 de
sus 33 pares). El equipo decidió probar sobre los pares sin evidencia la fuente más precisa de esa prueba, gene2pubmed +
MeSH (#31). Sería una etapa más de `pmid_externos.py`, gratuita, sobre abstracts de PubMed y compatible con una
Fase 1 determinista, y solo actuaría sobre los pares que siguen vacíos.

### NCBI gene2pubmed + MeSH de la ruta + «Humans»

- **Qué:** se buscan los artículos que NCBI ya liga al gen humano y que tienen asignado el MeSH del proceso.
  Así lo hace NCBI dos veces: liga el gen al artículo y el indexador de MeSH juzga el tema. Fue la fuente
  **más precisa** de la prueba.
- **Cómo:** con NCBI E-utilities:
  1. `elink dbfrom=gene linkname=gene_pubmed` da los PMIDs del gen. Otra opción es el fichero `gene2pubmed.gz`,
     de 291 MB, que se actualiza a diario.
  2. `esearch` restringe esos PMIDs con `"<MeSH>"[MeSH] AND "Humans"[MeSH]`.

  Ejemplo: `BCL2A1[tiab] AND "Apoptosis"[MeSH]`.
- **Requisito:** una **tabla ruta GO → MeSH**, que no está publicada. Hay que construirla una vez para las rutas
  afectadas (252, o menos si se agrupan por ancestro común). Se guardaría como un TSV versionado junto al código,
  con una persona revisándola.
- **Alcance en la prueba:** 3 de los 12 genes (ACP5, BCL2A1, MAP2K3).
- **Coste:** unas 2 peticiones por gen y ruta, con caché. Sin clave de NCBI, el límite es de 3 por segundo;
  con `NCBI_API_KEY`, de 10 por segundo.
- **Piloto sobre los 668 pares de la Fase 1 del 2026-11-09 (hecho el 2026-11-13), con el MeSH buscado de forma automática** (nombre de la ruta, sus
  sinónimos, el proceso núcleo y, si no, el primer resultado de una búsqueda libre):
  - Solo 81 de las 261 rutas tienen MeSH, y 72 de ellas por la búsqueda libre, que suele fallar
    («T cell differentiation» → *Interleukin-5*, «B cell proliferation» → *Antigens, CD19*).
  - 35 pares tienen algún artículo ligado al gen con ese MeSH y «Humans»; en 26 (3,9 %) el abstract nombra el gen
    (55 PMIDs).
  - En una primera lectura de esos 26, solo unos 10 tratan del gen en el proceso (alrededor del 40 %, frente a
    unos 8 de cada 10 de GeneRIF y Europe PMC). Falta confirmarlo con una lectura a mano.
  - Para que rinda hace falta una tabla GO → MeSH hecha a mano.
- **Piloto con la tabla GO → MeSH hecha a mano (2026-11-13), sobre los 642 pares que quedaban sin evidencia antes de integrarlo:**
  - La tabla cubre las 252 rutas: 134 con un MeSH equivalente (confianza alta), 86 con una combinación de célula y
    proceso (media), 28 con una aproximación amplia (baja) y 4 sin MeSH porque son demasiado generales. «Regulation
    of X» se mapea como X. Las 139 consultas se comprobaron en PubMed sin avisos.
  - **326 pares (51 %) ganan algún abstract** (703 PMIDs), frente a 26 con el MeSH automático.
  - **Precisión en una muestra de 30 pares: 16 tratan del gen en el proceso (53 %; 60 % con los dudosos)**, por debajo
    del listón del § 4. Los fallos no dependen de la confianza del mapeo: son artículos que NCBI liga al gen pero en
    los que el gen es solo un marcador o un locus de asociación (biomarcadores, GWAS, metilación).
  - Exigir además el gen y un término de la ruta en la misma frase, como en Europe PMC, deja solo 1 par: estos pares
    son precisamente los que esa búsqueda no resolvió, porque los autores no usan el vocabulario de GO.
  - **Decisión (2026-11-13): se integra como tercera fuente externa** (`fuentes/gene2pubmed.py`), con la tabla en
    `codigo/fase1_ingesta/tabla_go_mesh.tsv` (hecha a mano; falta que la revise una persona) y como mucho 3 artículos
    por par, los más recientes que nombran el gen. Con 3 en vez de 10, los 326 pares siguen ganando abstract y las
    preguntas nuevas al LLM bajan de unas 1.150 a unas 630.
- **Por qué hace falta el MeSH:** gene2pubmed liga cada gen a todos los artículos que lo tratan, sea cual sea el
  tema. Sin filtro, un gen de estos pares tiene una mediana de 242 artículos humanos (p90 738; HIF1A, 9.765), y
  serían los mismos para todas sus rutas (mediana de 2 rutas por gen, hasta 24). Con el MeSH de la ruta y
  «Humans», la mediana baja a 1 artículo por par (p90 21) y el 41 % de los pares no tiene ninguno: el MeSH es lo
  que convierte «artículos del gen» en «artículos del gen en este proceso».
- **Coste medido (Fase 1 y Fase 2 del 2026-11-13):** esta fuente aporta 725 preguntas al LLM, de las que 177 (24 %)
  dan signo; 129 pares pasan a tener signo. Una ejecución completa de la Fase 2 hace 920 llamadas a Gemini con
  2,63 M tokens, de los que unas 275 llamadas y 0,71 M tokens corresponden a estas preguntas. A NCBI le hace una
  petición por par (gen, consulta MeSH), con caché.
- **Mantenimiento de la tabla:** una ruta que no está en `tabla_go_mesh.tsv` no se consulta. Con un Excel nuevo de
  CIMUS, las rutas nuevas deben añadirse a la tabla (con su consulta MeSH comprobada en PubMed) antes de lanzar la
  Fase 1; si no, sus pares sin evidencia se quedan así, sin aviso de error.

### Qué no se resolverá

En varios pares, la falta de evidencia humana es **real**, porque solo existe la transferencia desde otra especie:

- **Sin evidencia humana:** ADGRG3, FAM89B, KDM6B y TBCD.
- **Probable error de anotación:** ITM2C. Su artículo de origen trata de *Bri3*, otro gen de ratón.
- **Rutas concretas sin evidencia humana:** LTB → producción de IL-12, CTSZ → morfogénesis de tubo epitelial y
  ACP5 → respuesta a molécula bacteriana.

Para estos pares, lo correcto es el UNKNOWN actual con su `Detalle`, no forzar un resultado.

## 4. Cómo medirlo

Antes de dar por buena cada etapa, conviene hacer un piloto sobre los 310 pares y medir dos cosas:

1. **Cobertura:** cuántos pares pasan de `sin_evidencia` a tener un abstract.
2. **Precisión:** en una muestra de unos 30 pares por etapa, leída a mano, si el abstract trata del gen en el
   proceso, en humano y en la dirección correcta.

Una etapa solo se queda si su precisión es comparable a la de GeneRIF y Europe PMC (en las revisiones manuales
de 2026-11-08, unos 8 de cada 10 abstracts trataban del gen en el proceso). Si no la alcanza, sus PMIDs pasan
a revisión humana en vez de ir directamente al LLM, salvo que el propio LLM sirva de filtro: es el caso de
gene2pubmed + MeSH, porque sus fallos son artículos donde el gen es solo marcador o asociación, que el LLM ya
deja en `UNKNOWN` (`marcador_correlacion`, `contexto_ajeno`).

Para gene2pubmed + MeSH, el piloto del § 3 da, con la tabla hecha a mano, una cobertura del 51 % de los pares y una
precisión del 53 %, por debajo de ese listón; se integró con el LLM como filtro y un tope de 3 artículos por par.
