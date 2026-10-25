# go_reg_pipeline: regulación GO → PMID → abstract → DuckDB

Herramienta de línea de comandos (un solo fichero Python) para el proyecto de resolución de vías
transcriptómicas de CiMUS (células NK, cáncer de cabeza y cuello).

Para cada gen humano obtiene **las rutas de Gene Ontology (Biological Process) que implican
regulación**, los **PMIDs con evidencia experimental** que respaldan cada anotación y el **abstract**
de cada paper. Todo queda en una base de datos DuckDB lista para que un LLM confirme la
direccionalidad (+1 / -1) de cada par gen–ruta.

## Qué problema resuelve

Separar los genes significativos en listas "Up" y "Down" (DESeq2 + clusterProfiler) hace que una
misma ruta aparezca activada y reprimida a la vez, porque se ignora si el gen **activa o inhibe** la
ruta. Este programa aporta la parte que falta: el **signo de la relación gen → ruta**, extraído de la
literatura. Ese signo (+1/-1) se multiplicará después por el Log2FoldChange del gen.

> Este programa cubre la extracción y el almacenamiento de evidencias. La clasificación +1/-1 por el
> LLM y la multiplicación por el Log2FoldChange **no están incluidas**; la tabla `llm_direction` y la
> vista `v_llm_queue` están preparadas para ese paso.

## Flujo de búsqueda

```
 Genes (HGNC)
     │
     ▼
 [1] Descarga (una vez, caché 30 días)
     goa_human.gaf.gz  ← anotaciones GO humanas (GOA)
     go-basic.obo      ← ontología (nombres y relaciones de regulación)
     │
     ▼
 [2] Lectura del GAF en streaming, línea a línea. Se conserva una anotación si:
     · el símbolo coincide con tu gen
     · aspecto = P (biological_process) y taxón 9606 (humano)
     · el calificador no contiene NOT
     · el código de evidencia es experimental (EXP, IDA, IPI, IMP, IGI, IEP, HTP, HDA, HMP, HGI, HEP)
     │
     ▼
 [3] Filtro de regulación con el OBO
     · el término tiene relación regulates / positively_regulates / negatively_regulates,
       o su nombre contiene "regulation of"
     · se registra la polaridad del término: +1 (positive regulation), -1 (negative), 0 (sin signo)
     · se descartan términos obsoletos (se resuelven los alt_id)
     │
     ▼
 [4] Extracción de PMIDs reales (solo referencias con formato PMID:número)
     · se descartan GO_REF, Reactome, DOI, etc.
     · se descarta el PMID 21873635 (paper metodológico de PAINT/IBA)
     │
     ▼
 [5] Abstracts (online): Europe PMC en lotes de 40 → fallback NCBI E-utilities (lotes de 100)
     · reintentos con backoff, respeta Retry-After y los límites de NCBI
     │
     ▼
 [6] DuckDB: go_evidence · abstracts · llm_direction · vista v_llm_queue
```

Gene Ontology **no se consulta por API**: solo se descargan dos ficheros estáticos y todo el
filtrado ocurre en local. La única parte "online" son los abstracts.

## Capacidades

- Menú interactivo (se lanza sin argumentos) y modo comando para automatizar.
- Entrada de genes escritos a mano, desde una lista orientativa de genes inmunes/NK o desde un fichero.
- Estadísticas de filtrado: cuántas anotaciones se descartan y por qué.
- Caché y reanudación: si se interrumpe, al relanzar solo se piden los abstracts que faltan.
- Escritura idempotente: repetir una búsqueda no duplica filas.
- Trazabilidad: cada fila guarda la fecha de la release del GAF y la versión del OBO.
- Visor de resultados integrado: resumen, rutas, papers, estado de abstracts, SQL libre y exportación a CSV.
- Exportación de la cola para el LLM en JSONL.

## Requisitos e instalación

- Python 3.9 o superior (Ubuntu/WSL o Windows con PowerShell).
- Conexión a internet en la primera ejecución (descarga de GAF/OBO, unos 40 MB, y abstracts).

```bash
pip install requests duckdb
```

(En Ubuntu recientes, si `pip` se queja, usa un entorno virtual: `python3 -m venv .venv && source .venv/bin/activate`.)

## Uso

### Modo interactivo

```powershell
python go_reg_pipeline.py
```

Menú principal:

1. **Nueva búsqueda:** pregunta los genes, el tipo de evidencia, un email opcional y el archivo de
   resultados (pulsa Enter para aceptar `data/pathways.duckdb`).
2. **Ver resultados ya guardados.**

Al terminar una búsqueda ofrece abrir el visor de resultados.

### Modo comando

```bash
# Búsqueda completa
python go_reg_pipeline.py run --genes GATA3 STAT3 TBX21 --email tu@correo \
       --db data/pathways.duckdb --jsonl data/llm_queue.jsonl

# Genes desde un fichero (un símbolo por línea, # para comentarios)
python go_reg_pipeline.py run --genes-file mis_genes.txt

# Por fases
python go_reg_pipeline.py prepare            # solo descarga GAF y OBO
python go_reg_pipeline.py extract --genes GATA3
python go_reg_pipeline.py abstracts          # descarga los abstracts pendientes

# Ver resultados
python go_reg_pipeline.py report                       # resumen y estado
python go_reg_pipeline.py report --gene GATA3          # rutas y papers de un gen
python go_reg_pipeline.py report --csv data/res.csv    # exportar todo a CSV
python go_reg_pipeline.py report --sql "SELECT gene, count(*) FROM go_evidence GROUP BY gene"
```

### Opciones principales de `run` / `extract`

| Opción | Efecto |
|---|---|
| `--genes G1 G2 ...` / `--genes-file F` | Genes a consultar (símbolos HGNC). |
| `--include-curated` | Añade evidencia TAS e IC. |
| `--all-evidence` | No filtra por código de evidencia (incluye IEA/IBA: mucho ruido). |
| `--match-synonyms` | También busca el gen entre los sinónimos del GAF. |
| `--term-regex REGEX` | Cambia el criterio por nombre de término (defecto: `\bregulation of\b`). |
| `--pmid-blacklist P1 P2` | PMIDs adicionales a ignorar. |
| `--db RUTA` | Base de datos DuckDB (defecto `data/pathways.duckdb`). |
| `--workdir DIR` | Carpeta de GAF/OBO (defecto `data`). |
| `--force` | Vuelve a descargar GAF/OBO aunque haya caché. |
| `--email`, `--ncbi-api-key` | Identificación para NCBI/Europe PMC (también variables `NCBI_EMAIL`, `NCBI_API_KEY`). |
| `--jsonl FICHERO` | Exporta la cola para el LLM. |
| `-v` | Log detallado. |

## Archivos que genera

| Archivo | Contenido |
|---|---|
| `data/goa_human.gaf.gz` | Anotaciones GO humanas (descarga). |
| `data/go-basic.obo` | Ontología GO (descarga). |
| `data/pathways.duckdb` | Resultados. Puede aparecer un `.wal` temporal mientras se usa. |
| `data/llm_queue.jsonl` | Pares gen–ruta–PMID con abstract, pendientes de veredicto (si usas `--jsonl`). |

## Esquema de la base de datos

**`go_evidence`**: una fila por gen, ruta, PMID, evidencia y calificador.
`gene, uniprot, go_id, go_name, term_polarity (+1/-1/0), qualifier, evidence_code, pmid, assigned_by, annot_date, gaf_release, go_version`

**`abstracts`**: `pmid, title, abstract, journal, year, source (europepmc/ncbi), status, fetched_at`.
`status`: `ok` (descargado), `no_abstract` (el paper no tiene abstract) o `not_found` (no localizado; se reintenta en la siguiente ejecución).

**`llm_direction`**: tabla vacía para que se escriba el veredicto: `gene, go_id, pmid, direction (+1/-1/0), confidence, rationale, context, model, created_at`.

**`v_llm_queue`** (vista): pares con abstract disponible y sin veredicto aún.

Consulta de ejemplo:

```sql
SELECT gene, go_name, term_polarity, evidence_code, pmid
FROM go_evidence WHERE gene = 'GATA3' ORDER BY go_name;
```

## Cómo verificar un resultado

Elige una fila, abre `https://pubmed.ncbi.nlm.nih.gov/<PMID>/` y comprueba que el paper trata de ese gen
y esa ruta. Para ver las anotaciones crudas de un gen:

```bash
zcat data/goa_human.gaf.gz | grep -P "\tGATA3\t" | head
```

## Limitaciones y cosas a tener en cuenta

- **El GAF se publica por releases**, así que puede no incluir anotaciones muy recientes.
- **Anotación humana no implica experimento en vuestro contexto.** Algunos papers pueden usar otras
  especies, líneas celulares o sobreexpresión. Por eso existe el paso de revisión por LLM.
- **Un PMID puede respaldar varias rutas** y una ruta tener muchos PMIDs; ambas relaciones se guardan.
- **La polaridad `term_polarity` viene del término GO**, no del tipo celular. Es una pista, no el veredicto final.
- **Con la evidencia por defecto (solo experimental) hay menos anotaciones** pero más fiables. Si un gen
  devuelve 0 filas, prueba `--include-curated`, `--match-synonyms` o revisa el símbolo HGNC.
- **La lista de genes inmunes/NK del menú es orientativa**, no validada. Edita `IMMUNE_PRESET` en el
  script con los genes que salgan de vuestro scRNA-seq.
- **Respetad los límites de Europe PMC y NCBI**: usad `--email` y, para lotes grandes, `--ncbi-api-key`.

## Solución de problemas

| Síntoma | Causa probable |
|---|---|
| `ModuleNotFoundError: duckdb` o `requests` | Falta `pip install requests duckdb`. |
| `No se pudo descargar ...` | Sin internet o proxy; si ya hay copia local antigua, se usa. |
| `Fichero gzip corrupto/truncado` | Descarga interrumpida; relanza con `--force`. |
| 0 filas para un gen | Símbolo incorrecto, o sin evidencia experimental de regulación; ver estadísticas de filtrado. |
| `not_found` en abstracts | Servicio caído o PMID sin registro; relanza `abstracts`. |
| `python` no se reconoce (Windows) | Usa `py go_reg_pipeline.py`. |
