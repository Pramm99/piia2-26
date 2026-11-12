# AGENTS.md · CU-01 Reinterpretación de rutas biológicas

Este fichero contiene las instrucciones operativas para asistentes de IA (Claude Code, Codex, Copilot…) y para cualquier persona que se incorpore al equipo. Indica cómo está montado el proyecto, cómo se ejecuta y qué reglas hay que respetar. El *qué* y el *porqué* están en [`README.md`](README.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`decisions/`](decisions/) y [`specs/`](specs/). Léelos antes de cambiar el comportamiento de una fase.

## El proyecto en tres líneas
* Para cada par (gen, ruta GO) de los dos Excels de CIMUS (células NK en cáncer de cabeza y cuello) se decide si el gen **activa** (`+1`), **inhibe** (`−1`) o **no cambia** (`neutro`) la ruta, o si **no se sabe** (`UNKNOWN`).
* El signo sale de Gene Ontology cuando basta y, si no, de **dos LLM gratuitos** que leen los abstracts de PubMed, con una cita literal verificada.
* Con esos signos y la dirección de expresión de cada gen se calcula el *Net Pathway Score* de cada ruta.

## Dónde está cada cosa
Todo el trabajo del equipo vive en esta carpeta (`entregas/cu-01-reinterpretacion-biologica/`). Las rutas de este fichero son relativas a ella.

| Ruta | Contenido |
|---|---|
| `codigo/fase1_ingesta/` | **Fase 1 · Ingesta.** Excels de CIMUS → pares → GAF de GO → PMIDs → abstracts → `fase1_dataset_abstracts.xlsx`. Usa imports planos (`import config`). |
| `codigo/fase2_inferencia/` | **Fase 2 · Inferencia.** Preguntas (gen, PMID, proceso núcleo) → dos LLM → validación → contraste → `codigo/data/fase2_resultados.xlsx`. Es un paquete: se ejecuta con `python -m fase2_inferencia` desde `codigo/`. Lee la Fase 1 a través del puente `_fase1.py`. |
| `codigo/fase3_scoring/` | **Fase 3 · Scoring.** Fases 1 y 2 → signo de cada par (gen, ruta) → *Net Pathway Score* de cada ruta → `codigo/data/fase3_scoring.xlsx` ([spec](specs/scoring-net-pathway-score.md)). Sin red ni LLM. Es un paquete: `python -m fase3_scoring` desde `codigo/`; los umbrales están en `fase3_scoring/config.py`. |
| `codigo/evaluacion/` | Benchmark: gold set, guía de etiquetado, `evaluar_gold.py`, `seleccionar_gold.py` y `buscar_neutros.py`. |
| `codigo/tests/` | Pruebas `pytest`, todas sin red. |
| `codigo/tools_cimus/` | Entrada original de CIMUS: rutas enriquecidas (únicos Excels versionados) y tabla de log2FC (`NK_cells_DESeq2_results.xlsx`, se reparte dentro del equipo y no se sube). |
| `codigo/data/` | Cachés, registro de respuestas del LLM y salidas. **No se versiona.** |
| `decisions/`, `specs/`, `docs/` | ADRs, specs funcionales, limitaciones conocidas y plantillas de issue. |
| `DOR.md`, `DOD.md`, `TABLERO.md` | Cuándo empieza y cuándo termina una tarea, y cómo se gestionan el tablero y los bloqueos. |
| `PlanesViables/` | Análisis previo de alternativas (opciones A y B). Es histórico: no se toca. |

## Cómo se ejecuta
Desde `codigo/`. Está probado con Python 3.14. El entorno virtual es `codigo/pia_venv/`, aunque también vale el Python del sistema con `requirements.txt`.

```bash
pip install -r requirements.txt
cp .env.example .env          # y rellena las claves que vayas a usar

python fase1_ingesta/main.py   # Fase 1 (unos 58 min en frío, unos minutos con caché)
python -m fase2_inferencia CD7    # Fase 2 en modo demo: imprime la primera llamada, sin llamar a nadie
python -m fase2_inferencia ejecutar [principal] [secundario|ninguno] [gen] [GO] [excel] [--contraste]   # Fase 2 real, reanudable
python -m fase3_scoring [excel_fase1] [excel_fase2] [log2fc|ninguno]   # Fase 3, sin red (segundos)
python -m pytest              # pruebas (sin red ni claves)
python evaluacion/evaluar_gold.py ...   # benchmark (ver specs/benchmark-gold-set.md)
```

* **Fase 2:** es reanudable. Cada respuesta se guarda en `codigo/data/respuestas_llm.jsonl` en cuanto llega. Si un modelo agota su cupo diario, sus preguntas quedan `pendiente` (nunca `UNKNOWN`); se relanza el mismo comando otro día y solo se pregunta lo que falta.
* **Modelos** (ADR-005): principal `gemini-3.5-flash-lite` y secundario `groq-gpt-oss-120b`. **gpt-oss es solo el respaldo de Gemini:** solo recibe una pregunta si Gemini no responde o su JSON no vale, y entonces decide él (`respaldo_secundario`). Si Gemini responde, la pregunta no va a gpt-oss, y una respuesta suya que esté en el registro no se usa. `--contraste` (envía todo a los dos y los contrasta) es solo para experimentos. Los nombres válidos son las claves de `fase2_inferencia/cliente.py:MODELOS`. `qwen3.8` está descartado: no se vuelve a usar.

## Reglas que no se negocian
1. **Coste cero.** Solo planes gratuitos. No propongas ningún servicio, modelo ni API de pago.
2. **Sin bases de datos.** El estado va en ficheros locales: cachés desechables y registro JSONL ([ADR-004](decisions/adr-004-persistencia-ficheros-locales.md)). Nada de SQLite, DuckDB, Postgres ni bases vectoriales.
3. **Las claves nunca llegan a GitHub.** Viven solo en `codigo/.env`, que está en `.gitignore`.
   * No escribas una clave en el código, la documentación, los logs ni la salida de un comando: para comprobarla, mira solo si existe o está vacía.
   * Antes de cada commit, comprueba que `.env` no está en `git status` y busca los patrones de clave (`gsk_`, `AIza`, `AQ.`, `csk-`) en lo que se va a subir.
4. **Solo se toca esta carpeta.** El resto del repositorio (README raíz, `evaluacion/`, `cu00-ejemplo`) es de la asignatura. Antes de un push, `git diff --name-status upstream-main HEAD -- . ':!entregas/cu-01-reinterpretacion-biologica'` debe salir vacío.
5. **No se versionan Excels ni CSV**, salvo los de `codigo/tools_cimus/`. Las salidas nuevas van a `codigo/data/`. Ojo: `git add` de un fichero que ya estaba seguido se salta el `.gitignore`.
6. **R está fuera del proyecto.** No propongas clusterProfiler, Script.R ni ggplot en el código ni en la documentación.

## Convenciones de dominio
* **Terminología:**
  * «genes *up*/*down*» es la dirección de expresión del gen en NK (un gen está en una sola lista);
  * «rutas activadas/suprimidas» es solo el **nombre de las dos listas** de CIMUS: la lectura ingenua que el proyecto pone en duda, no una conclusión.
  * En el código, `Estado_Original` vale `Activada` o `Suprimida`, y de ahí sale *up* o *down*. **Se procesan las dos listas.**
* **Signos:** `+1`, `-1`, `neutro`, `UNKNOWN` (constantes de `fase2_inferencia/esquema.py`). Los estados son `resuelto`, `revisar`, `no_concluyente` y `pendiente`, y los motivos son los del [ADR-003](decisions/adr-003-control-alucinaciones-unknown.md). No inventes un signo `CONTRADICCION`: el conflicto se expresa con estado y motivo.
* **Inmunoglobulinas:** se detectan con la lista de HGNC `immunoglobulin gene`, más JCHAIN y PIGR, y **no por el prefijo «IG»** (IGFBP7 no es una Ig). Salen como `neutro`, evaluando la Ig completa.
* **Subárbol GO:** el gen casi nunca está anotado a la ruta misma, así que la búsqueda recorre todo el subárbol. Las rutas «regulation of X» sin dirección se tratan como X (`SIN_DIRECCION_COMO_PROCESO`, común a las dos fases).
* **Prompt** (`fase2_inferencia/prompt.py`):
  * es el mismo para todos los modelos, en inglés y con claves JSON en español;
  * **no** incluye la dirección del gen, ni `Polaridad_GO`, ni el contexto del tumor, ni ningún umbral o cifra de corte de la confianza. El umbral (`UMBRAL_VEREDICTO`) solo lo conoce el código;
  * el modelo siempre da un veredicto, y el `UNKNOWN` lo decide el código;
  * el abstract no se recorta.
* **El registro es la memoria de la Fase 2:** la clave de cada respuesta incluye `VERSION_PROMPT` y la huella de la pregunta. Si cambias el prompt, la limpieza o el corte en frases, cambian las huellas y esas preguntas se vuelven a pagar. Avísalo antes de hacerlo.

## Cómo trabajar en este repositorio
* **Idioma:** el código, los comentarios, la documentación y los commits van en español. Solo el prompt al LLM va en inglés.
* **Estilo:** imita el código que lo rodea: nombres en español, docstrings cortas que dicen el *porqué*, sin capas de abstracción innecesarias. Los parámetros ajustables van en `fase1_ingesta/config.py`, `fase2_inferencia/esquema.py` (los modelos y sus límites, en `cliente.py:MODELOS`) o `fase3_scoring/config.py`, no repartidos por el código.
* **Pruebas:** todo cambio de comportamiento lleva su prueba en `codigo/tests/`, sin red: las APIs se simulan con `monkeypatch` y los modelos con `ClienteSimulado`. `python -m pytest` tiene que pasar antes de cualquier commit.
* **Specs:** los criterios de aceptación son verificables y llevan `[x] ✅` y la prueba que los cubre cuando se cumplen. Si cambias el comportamiento, actualiza la spec, el ADR y `ARCHITECTURE.md` en el mismo commit.
* **Documentación:** describe solo el estado actual, sin versiones antiguas ni históricos. Las cifras de la Fase 1 son las de la ejecución de referencia del 2026-11-09, indicando la fecha.
* **No toques una fase que no te han pedido:** un cambio en la Fase 1 altera el Excel del que dependen la Fase 2, el gold set y el benchmark.
* **No afirmes decisiones** que solo aparecen en un comentario del código: compruébalas en los ADR o pregunta.
* **Commits:** el título lleva la fase que cambia, p. ej. `Fase 1 (INGESTA): …`, `Fase 2: …` o `Fase 3 (SCORING): …`. Si toca varias, nómbralas todas. Añade los ficheros con rutas explícitas, nunca con `git add -A`. El push va a `main` del fork `Pramm99/piia2-26`, que alimenta el PR #19 (Entrega 2) de `usc-gria/piia2-26`.
* **Tareas del tablero:** al abrir un issue usa la plantilla de [`docs/plantillas-issue/tarea.md`](docs/plantillas-issue/tarea.md). Al cerrar trabajo, comenta el issue con el commit y déjalo en REVISION: lo cierra otra persona contra el [DoD](DOD.md). Si algo te bloquea, sigue [`TABLERO.md`](TABLERO.md#bloqueos).
* **Varios asistentes a la vez:** si otra sesión tiene cambios sin commit en la misma carpeta, no los incluyas en tu commit ni edites sus ficheros hasta que termine.

## Estado y pendientes
El estado de cada componente está en la tabla de [`ARCHITECTURE.md`](ARCHITECTURE.md). Los grandes pendientes son:

* los umbrales definitivos del scoring y la revisión de las rutas `Sensible_al_peso`;
