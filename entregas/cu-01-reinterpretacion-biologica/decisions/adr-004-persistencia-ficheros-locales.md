---
description: Persistencia mediante ficheros locales (cachés desechables y un registro JSONL de respuestas del LLM) en lugar de ejecución puramente en memoria o bases de datos.
state: Aceptado (registro implementado el 2026-11-08 en codigo/consulta_gen/registro.py; dos ficheros y salida de la Fase 2 desde el 2026-11-10)
---

# ADR 004 - Persistencia en Ficheros Locales: Cachés Desechables y Registro de Respuestas del LLM

## Decisión
El pipeline **no usa bases de datos ni servicios de almacenamiento**. Guarda su estado en ficheros locales dentro de `codigo/data/`, de dos tipos según se puedan reconstruir o no:

| Tipo | Ficheros | ¿Se puede borrar? |
|---|---|---|
| **Caché desechable** | `go-basic.obo`, `goa_human.gaf.gz`, `cache_abstracts.json` | Sí: el resultado no cambia, solo tarda más en reconstruirse. |
| **Artefacto intermedio regenerable** | `fase1_dataset_abstracts.xlsx` (salida de la Fase 1, entrada de la Fase 2) | Sí: se regenera a partir de las cachés. |
| **Artefacto de salida regenerable** | `fase2_resultados.xlsx` (salida de la Fase 2, entrada del scoring) | Sí: se regenera desde el registro sin llamar a ningún modelo. |
| **Registro de respuestas del LLM** | `respuestas_llm.jsonl` y `llamadas_llm.jsonl` | **No**: es el resultado del experimento y no puede reconstruirse de forma idéntica. |

El **registro de respuestas** sigue estas reglas:
* **Una línea JSON por pregunta** en `respuestas_llm.jsonl`, escrita en cuanto llega la respuesta (*append-only*). Si la ejecución se corta, como mucho se pierde la llamada en curso. En `v1_proceso_gen` una llamada lleva varias preguntas de un gen: la llamada (respuesta cruda completa, tokens, tiempo) va además a `llamadas_llm.jsonl`, y cada pregunta lleva el `id_llamada`.
* **Clave de caso:** (`version` del prompt, `gen`, `pmid`, `go_id`, `modelo`, huella del prompt). `go_id` es la ruta en `v0_original` y el proceso núcleo en `v1_proceso` y `v1_proceso_gen`. En `v1_proceso_gen` la huella es la de la parte del prompt de esa pregunta, así que una pregunta nueva (por ejemplo, un abstract más de la Fase 1) solo cuesta su llamada. Antes de llamar a un modelo se comprueba si esa clave ya existe; si existe, no se repite la llamada.
* **Trazabilidad** en cada línea: proveedor, nombre exacto del modelo, `system_fingerprint` cuando el proveedor lo da, tokens usados, fecha y hora, la huella (*hash*) del prompt enviado y el texto crudo de la respuesta, además de la salida ya validada según el ADR-003.
* **Fallo de red:** si un modelo no responde tras los reintentos, no se escribe ninguna línea: el caso queda pendiente y la siguiente ejecución lo retoma.
* **Invalidación:** si cambia el prompt, cambia su huella y el caso se vuelve a evaluar, sin mezclar respuestas a prompts distintos.
* **Revalidación:** al reutilizar una línea se vuelve a validar su respuesta cruda con el validador actual, así que un cambio del validador (por ejemplo, el umbral de confianza) no obliga a volver a llamar.

Las cachés desechables ya se escriben de forma atómica (fichero temporal y renombrado), de modo que una interrupción no deja ficheros corruptos.

## Motivación
1. **Ejecución repartida en varios días:** la restricción de coste cero obliga a usar planes gratuitos con límites diarios de peticiones y tokens. Con dos modelos por caso (ADR-003), la ejecución completa no cabe en un día, así que hay que poder pararla y reanudarla sin repetir llamadas.
2. **Las respuestas del LLM no son reproducibles volviendo a llamar:** temperatura 0 no garantiza salidas idénticas, y los modelos de los planes gratuitos cambian o desaparecen (el modelo `llama3-8b-8192` previsto inicialmente ya no está disponible). El registro es la única forma de conservar lo que respondió cada modelo.
3. **Auditoría:** los casos marcados como `revisar` (ADR-003) deben poder revisarse con la respuesta original de cada modelo.
4. **Lo que el ADR-001 quería evitar era la infraestructura**, no los ficheros: sin servidores de bases de datos, sin contenedores y sin esquemas que migrar. Los ficheros locales mantienen esa portabilidad: basta con clonar el repositorio.
5. **JSONL es suficiente para el volumen:** unos 738 casos (gen, PMID) en las rutas activadas, por dos modelos, dan del orden de 1.500 líneas. Se lee con `pandas.read_json(..., lines=True)` y se puede inspeccionar con cualquier editor.

Aceptamos los compromisos asociados: el registro crece con cada cambio de prompt (las respuestas antiguas se conservan con su huella) y no hay consultas complejas; los análisis se hacen cargando el fichero en `pandas`.

## Alternativas
* **Todo en memoria con `@lru_cache` (planteamiento original del ADR-001):**
  * *Motivo de descarte:* se pierde todo al terminar o interrumpirse la ejecución; incompatible con ejecuciones de varios días y con la auditoría de respuestas.
* **SQLite o DuckDB:**
  * *Motivo de descarte:* el volumen no requiere consultas ni índices, y añaden una dependencia y un formato binario que no se puede revisar a simple vista. DuckDB llegó a estar en `requirements.txt` pero el código no lo usaba; se elimina.
* **PostgreSQL o una base de datos vectorial:**
  * *Motivo de descarte:* exigen un servicio en ejecución y son desproporcionadas para unos pocos miles de registros; contradicen la portabilidad del ADR-001.
* **Parquet:**
  * *Motivo de descarte:* no admite añadir filas una a una de forma sencilla y requiere `pyarrow`; JSONL encaja mejor con un registro que crece llamada a llamada.
* **Usar el Excel de salida como registro:**
  * *Motivo de descarte:* reescribir un `.xlsx` tras cada llamada es lento y frágil ante interrupciones. El Excel se mantiene solo como interfaz entre la Fase 1 y la Fase 2.

## Referencias
* **Código del proyecto:**
  * `codigo/extraer_info/abstracts.py` (`cargar_cache` / `guardar_cache`, escritura atómica con `os.replace`).
  * `codigo/extraer_info/red.py` (`descargar_archivo`, descarga atómica del OBO y el GAF).
  * `codigo/extraer_info/config.py` (rutas de los ficheros en `data/`).
* **Formato JSON Lines:** [https://jsonlines.org/](https://jsonlines.org/)
* **Ejemplo de lectura y comprobación de casos ya evaluados:**

  ```python
  import pandas as pd

  registro = pd.read_json("data/respuestas_llm.jsonl", lines=True)
  hechos = set(zip(registro.gen, registro.pmid, registro.go_id_anotado, registro.modelo))
  ```
* **Decisiones relacionadas:** ADR-001 (sustituido parcialmente por este ADR en lo relativo a la persistencia) y ADR-003 (formato de la salida validada que se guarda en el registro).
