---
description: Persistencia mediante ficheros locales (cachés desechables y un registro JSONL de respuestas del LLM) en lugar de ejecución puramente en memoria o bases de datos.
state: Aceptado (registro implementado el 2026-11-08 en codigo/fase2_inferencia/registro.py; dos ficheros y salida de la Fase 2 desde el 2026-11-10)
---

# ADR 004 - Persistencia en Ficheros Locales: Cachés Desechables y Registro de Respuestas del LLM

## Decisión
El pipeline **no usa bases de datos ni servicios de almacenamiento**. Guarda su estado en ficheros locales, de cuatro tipos según se puedan reconstruir o no. Salvo que se indique otra carpeta, están en `codigo/data/`, que no se sube a GitHub:

| Tipo | Ficheros | ¿Se puede borrar? |
|---|---|---|
| **Caché desechable** | Fase 1: `go-basic.obo`, `goa_human.gaf.gz`, `cache_abstracts.json` (título y abstract en crudo), `cache_mygene.json` (alias, nombre y GeneRIF), `cache_epmc_busquedas.json` (búsqueda dirigida en Europe PMC), `cache_uniprot.json` (función de las inmunoglobulinas) y `hgnc_inmunoglobulinas.json`. La Fase 2 reutiliza `cache_mygene.json` para los alias del gen | Sí: el resultado no cambia, solo tarda más en reconstruirse. |
| **Artefacto intermedio regenerable** | `codigo/fase1_ingesta/fase1_dataset_abstracts.xlsx` (salida de la Fase 1, entrada de la Fase 2) | Sí: se regenera a partir de las cachés. |
| **Artefacto de salida regenerable** | `fase2_resultados.xlsx` (salida de la Fase 2, entrada del scoring) | Sí: se regenera desde el registro sin llamar a ningún modelo. |
| **Registro de respuestas del LLM** | `respuestas_llm.jsonl` y `llamadas_llm.jsonl` | **No**: es el resultado del experimento y no puede reconstruirse de forma idéntica. |

El benchmark usa el mismo registro, uno por modelo, en `codigo/data/benchmark*/<modelo>/` (`respuestas_llm.jsonl` y `llamadas_llm.jsonl`). Al lado escribe `claves.json` (la clave de registro de cada caso del *gold set*), `prompts.json` (las frases de cada abstract) y `ejecuciones.jsonl` (una línea por ejecución, con llamadas, pendientes y tokens). Con ellos el informe se regenera sin la Fase 1 y sin llamar a los modelos.

El **registro de respuestas** sigue estas reglas:
* **Dos ficheros, solo de añadido (*append-only*)**, escritos y volcados a disco en cuanto llega cada respuesta. Si la ejecución se corta, como mucho se pierde la llamada en curso. Una llamada lleva las preguntas de un gen, en las dos versiones del prompt:
  * `llamadas_llm.jsonl`: **una línea por llamada**, con `id_llamada`, `version`, `modelo` (nombre corto), `fecha`, `proveedor`, el ID exacto del modelo que devuelve el proveedor, `system_fingerprint` cuando lo da, `tokens` (el `usage` completo, con los de caché y razonamiento), `fin` (`finish_reason`), `segundos`, `huella_llamada`, las claves de sus `preguntas` y la `respuesta_cruda` completa.
  * `respuestas_llm.jsonl`: **una línea por pregunta respondida**, con `clave`, `version`, `modelo`, `fecha`, `id_llamada`, `q` (su posición en la llamada), `huella_prompt`, `respuesta_cruda` (solo el fragmento JSON de esa pregunta) y `salida` (la validación del momento, según el ADR-003).
* **Clave de una pregunta:** la lista `clave` = [`version` del prompt, `gen`, `pmid`, `go_id`, `modelo`, huella]. `go_id` es siempre el **proceso núcleo** por el que se pregunta, no la ruta. La huella es la de la parte del prompt de esa pregunta (`prompt.construir_pregunta_gen`), así que una pregunta nueva (por ejemplo, un abstract más de la Fase 1) solo cuesta su llamada. Antes de llamar a un modelo se comprueba si esa clave ya existe; si existe, no se repite la llamada.
* **Pregunta saltada:** si el modelo no responde a una de las preguntas de la lista, no se escribe su línea y queda pendiente para la siguiente ejecución.
* **Salida cortada:** si la respuesta se corta por `max_completion_tokens` (`fin = "length"`), la llamada se registra en `llamadas_llm.jsonl` sin ninguna respuesta, y la lista se parte en dos y se repite.
* **Fallo de red:** si un modelo no responde tras los reintentos, no se escribe ninguna línea. Sus preguntas quedan pendientes, ese modelo deja de llamarse en esa ejecución (casi siempre es el límite diario) y la siguiente ejecución retoma lo pendiente.
* **Invalidación:** si cambia el prompt, cambia su huella y la pregunta se vuelve a evaluar, sin mezclar respuestas a prompts distintos.
* **Revalidación:** al reutilizar una línea se vuelve a validar su `respuesta_cruda` con el validador actual (`ejecucion.py`), así que un cambio del validador (por ejemplo, el umbral de confianza del ADR-003) no obliga a volver a llamar.

Las cachés desechables se escriben de forma atómica (fichero temporal y renombrado), de modo que una interrupción no deja ficheros corruptos. El registro no se reescribe nunca: una línea a medio escribir por un corte se ignora con un aviso al leerlo.

## Motivación
1. **Ejecución repartida en varios días:** la restricción de coste cero obliga a usar planes gratuitos con límites diarios de peticiones y tokens. Con dos modelos por pregunta (ADR-003), la ejecución completa no cabe en un día, así que hay que poder pararla y reanudarla sin repetir llamadas.
2. **Las respuestas del LLM no son reproducibles volviendo a llamar:** temperatura 0 no garantiza salidas idénticas, y los modelos de los planes gratuitos cambian o desaparecen (el modelo `llama3-8b-8192` previsto inicialmente ya no está disponible). El registro es la única forma de conservar lo que respondió cada modelo.
3. **Auditoría:** los casos marcados como `revisar` (ADR-003) deben poder revisarse con la respuesta original de cada modelo.
4. **Lo que el ADR-001 quería evitar era la infraestructura**, no los ficheros: sin servidores de bases de datos, sin contenedores y sin esquemas que migrar. Los ficheros locales mantienen esa portabilidad: basta con clonar el repositorio.
5. **JSONL es suficiente para el volumen:** con la Fase 1 del 2026-11-09 hay 1.694 preguntas (1.123 de las rutas de genes *up* y 571 de las de genes *down*). Con dos modelos son unas 3.400 líneas en `respuestas_llm.jsonl` y unos cientos de llamadas por modelo. Se lee con `pandas.read_json(..., lines=True)` y se puede inspeccionar con cualquier editor.

Aceptamos los compromisos asociados: el registro crece con cada cambio de prompt (las respuestas antiguas se conservan con su huella) y no hay consultas complejas; los análisis se hacen cargando el fichero en `pandas`.

## Alternativas
* **Todo en memoria con `@lru_cache` (planteamiento original del ADR-001):**
  * *Motivo de descarte:* se pierde todo al terminar o interrumpirse la ejecución; incompatible con ejecuciones de varios días y con la auditoría de respuestas.
* **SQLite o DuckDB:**
  * *Motivo de descarte:* el volumen no requiere consultas ni índices, y añaden una dependencia y un formato binario que no se puede revisar a simple vista. DuckDB llegó a estar en `requirements.txt` pero el código no lo usaba; se eliminó.
* **PostgreSQL o una base de datos vectorial:**
  * *Motivo de descarte:* exigen un servicio en ejecución y son desproporcionadas para unos pocos miles de registros; contradicen la portabilidad del ADR-001.
* **Parquet:**
  * *Motivo de descarte:* no admite añadir filas una a una de forma sencilla y requiere `pyarrow`; JSONL encaja mejor con un registro que crece llamada a llamada.
* **Usar el Excel de salida como registro:**
  * *Motivo de descarte:* reescribir un `.xlsx` tras cada llamada es lento y frágil ante interrupciones. Los Excel se mantienen solo como interfaz entre fases.

## Referencias
* **Código del proyecto:**
  * `codigo/fase2_inferencia/registro.py` (`Registro`, `clave`, `huella`; escritura con `fsync` línea a línea).
  * `codigo/fase2_inferencia/ejecucion.py` (ejecución reanudable, revalidación, preguntas saltadas y salidas cortadas).
  * `codigo/fase2_inferencia/cliente.py` (metadatos de cada llamada: proveedor, modelo, `system_fingerprint`, `tokens`, `fin`, `segundos`).
  * `codigo/fase2_inferencia/resultados.py` (`fase2_resultados.xlsx`).
  * `codigo/evaluacion/evaluar_gold.py` (registro por modelo del benchmark, `claves.json`, `prompts.json` y `ejecuciones.jsonl`).
  * `codigo/fase1_ingesta/abstracts.py` (`cargar_cache` / `guardar_cache`) y `codigo/fase1_ingesta/fuentes/cache.py` (`guardar_json`): escritura atómica con `os.replace`.
  * `codigo/fase1_ingesta/red.py` (`descargar_archivo`, descarga atómica del OBO y el GAF).
  * `codigo/fase1_ingesta/config.py` (rutas de los ficheros).
* **Formato JSON Lines:** [https://jsonlines.org/](https://jsonlines.org/)
* **Ejemplo de lectura del registro y de las preguntas ya evaluadas:**

  ```python
  import pandas as pd

  registro = pd.read_json("data/respuestas_llm.jsonl", lines=True, dtype={"clave": object})
  registro[["version", "gen", "pmid", "go_id", "modelo", "huella"]] = pd.DataFrame(
      registro["clave"].tolist(), index=registro.index)
  hechos = set(map(tuple, registro["clave"]))  # misma clave que fase2_inferencia.registro.clave(prompt, modelo)
  ```

  Para comprobar una pregunta concreta desde el código basta con `clave(prompt, modelo) in Registro()`.
* **Decisiones relacionadas:** ADR-001 (sustituido parcialmente por este ADR en lo relativo a la persistencia) y ADR-003 (formato de la salida validada que se guarda en el registro).
