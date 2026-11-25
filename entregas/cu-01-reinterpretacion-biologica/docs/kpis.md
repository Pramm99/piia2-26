# KPIs: una ruta, el Excel completo y a mano

El proyecto está acotado a **una única ruta**. Las cifras voluminosas que aparecen en el resto de la documentación
(920 llamadas, 2,63 M tokens, casi una hora de Fase 1…) corresponden al **Excel completo de CIMUS** (352 rutas), que
se procesa entero para el benchmark y para medir el sistema, no al alcance del proyecto.

Este documento separa tres columnas:

- **Una ruta:** ejecuciones en frío de GO:0072678 *T cell migration* (está en las dos listas de CIMUS), sin ninguna
  caché y solo con acceso a red. Hay dos: la del 2026-11-13 y la del 2026-11-25, esta con el código actual (estudio
  configurable, #51) en una copia con `codigo/data/` vacía salvo el OBO y el GAF de GO, que se descargan una sola vez y
  no son de ninguna ruta. Cada fila indica de cuál es.
- **Excel completo:** ejecución de referencia del 2026-11-13 sobre los dos Excels de CIMUS.
- **A mano:** lo que tendría que hacer una persona para llegar al mismo resultado. El volumen de trabajo es real
  (sale de las mismas ejecuciones); el tiempo **no está medido**, es una estimación con los supuestos indicados, y el
  acierto frente a una persona tampoco (ver el final).

## Tamaño de la entrada

| KPI | Una ruta | Excel completo |
|---|---|---|
| Rutas | 1 | 352 (314 de genes *up*, 78 de genes *down*; 40 en las dos) |
| Genes | 11 (5 *up*, 6 *down*) | 224 |
| Pares gen–ruta | 11 | 3.172 (103 de inmunoglobulinas) |

## Tiempo, recursos y coste

| KPI | Una ruta | Excel completo | A mano (estimación) |
|---|---|---|---|
| Tiempo total | **Entre 2,4 y 21,9 min**, según lo rápido que responda Europe PMC. 25/11: **21,9 min** (Fase 1: 17,3 min; Fase 2: 4,6 min; Fase 3: < 1 s). 13/11: 2,4 min (Fase 1: 90 s; Fase 2: 52 s; Fase 3: 1 s) | Fase 1 en frío: casi 1 h. Fase 2: unas 2–2,5 h de reloj (51 min de tiempo de modelo; 279 llamadas tardaron 42 min en el último relanzamiento). Fase 3: segundos | **1,5 h aprox.** para la ruta; **unas 350 h** para el Excel completo |
| Tiempo por gen (una ruta, en frío) | 25/11: **unos 2 min por gen** (119 s: 94 s de Fase 1 y 25 s de Fase 2). 13/11: 13 s por gen | Fase 1: unos 16 s por gen (224 genes en casi 1 h), porque las rutas comparten genes y cada artículo se descarga una vez | — |
| Llamadas al LLM | 8. 25/11: 3 a Gemini y 5 a gpt-oss, porque Gemini respondió cinco veces seguidas «modelo saturado» (HTTP 503) y se pasó al respaldo; 35 s de modelo, el resto de la Fase 2 fueron esperas entre reintentos. 13/11: 8 a Gemini | 920 a Gemini; 7 a gpt-oss como respaldo | — |
| Tokens | 25/11: **19.555**. 13/11: 16.724 (14.932 de entrada, 1.792 de salida) | 2,63 M en Gemini; unos 20 K en gpt-oss | — |
| Coste económico | 0 € | 0 € | horas de una persona experta |
| Peticiones HTTP (13/11) | 67, ninguna con error | no medidas | búsquedas manuales en PubMed |
| Descarga (13/11) | 58,9 MB (47 MB son el OBO y el GAF de GO, fijos) | el OBO y el GAF más unos 33.900 abstracts (57 MB en caché) | — |
| Disco (13/11) | 50 MB (47 MB del OBO y el GAF) | 127 MB entre cachés y salidas | — |
| Memoria máxima (13/11) | 777 MB (Fase 1, al cargar el GAF) | no medida | — |

**De qué depende el tiempo de una ruta.** No tanto del número de genes como de cuántos genes no tienen artículo en
la anotación de GO y de cuántos artículos tienen esos genes. En GO:0072678, los 5 genes con artículo de GO solo
necesitaron 5 abstracts; para los otros 6, GeneRIF dio 1.422 artículos candidatos, y la Fase 1 los descarga todos para
quedarse con los que hablan de la ruta. Los dos días se descargaron los mismos 1.422, pero el 25/11 Europe PMC sirvió
unos 1,4 abstracts por segundo y el 13/11 bastante más rápido: esa es casi toda la diferencia entre 2,4 y 21,9 min.
La Fase 2 depende de la cola de Gemini; con 503 seguidos, el respaldo añade unos minutos de esperas.
Con una sola medición por día, el tiempo por gen es orientativo; para una media fiable hay que medir más rutas en frío.

Una ejecución posterior de la misma ruta reutiliza las cachés: la red y el LLM solo se usan para lo nuevo. Desde la
interfaz web (Fase 4), con las cachés y el registro ya hechos, una ruta tarda entre 9 y 20 s y no hace ninguna llamada
al LLM (medido el 2026-11-13 con GO:0072678, GO:0001906, GO:0001909 y GO:0001774).

## Evidencia y resultado

| KPI | Una ruta | Excel completo | A mano |
|---|---|---|---|
| Artículos candidatos comprobados por el filtro | 1.422 (Europe PMC, para 6 genes) | unos 33.900 | habría que cribarlos leyendo títulos |
| Abstracts que llegan al análisis | 11 | 1.842 | 11 / 1.842 que leer y juzgar |
| Preguntas (gen, PMID, proceso) | 9; 8 al LLM y 1 cerrada sin LLM | 2.556; 2.464 al LLM y 92 cerradas | una decisión por pregunta |
| Genes o pares con signo (cobertura) | 8 de 11 (73 %): 5 activan, 3 inhiben | 1.693 de 3.172 resueltos | — |
| Lectura de la ruta | 13/11: NPS 0,25 → **mixta** (con log2FC: 0,31, mixta). 25/11: NPS 0,5 → **activada** (5 respuestas de gpt-oss) | 132 activadas, 29 inhibidas, 45 mixtas y 146 insuficientes | — |

**Supuestos de la estimación a mano:** unos 5 minutos por par para buscar en PubMed los artículos del gen en el
proceso y unos 3 minutos por abstract para leerlo, decidir el signo y anotar la cita. Para la ruta: 11 × 5 + 11 × 3 ≈
90 min. Para el Excel completo: 3.172 × 5 + 1.842 × 3 ≈ 350 h. No incluye cribar los candidatos, así que es una cota
baja.

## Estabilidad del resultado

La misma ruta da una lectura distinta según cómo se ejecute:

- En la ejecución del Excel completo, GPR183 (PMID 28052250) sale `+1` y la ruta queda en NPS 0,333 → **activada**
  (6 activan, 3 inhiben).
- En la ejecución en frío de la ruta sola, el mismo abstract sale `UNKNOWN` (confianza 65, *marker or correlation
  only*) y la ruta queda en NPS 0,25 → **mixta**.

- En la ejecución en frío del 25/11, con 5 de las 8 respuestas de gpt-oss (Gemini saturado), la ruta queda en NPS 0,5
  → **activada**.

En la del 13/11, las otras 8 respuestas coinciden con las del Excel completo. La causa es doble: el modelo no es determinista, y en el Excel completo las
preguntas de un gen van juntas en la misma llamada, con otras rutas, mientras que con una ruta van solas. Como el NPS
está justo en el umbral de 0,33, un solo gen cambia la lectura. **KPI: 1 de 9 respuestas del LLM cambió (89 % de
acuerdo) y la lectura de la ruta cambió.** Con una ruta conviene repetir la ejecución y fijarse en `Sensible_al_peso`
y en los pares de `evidencia_debil`: aquí son 5 de los 7 que dan signo por el LLM (un solo abstract cada uno); CCL3
e ITGAL no lo son porque su artículo lo cita la anotación de GO y pesa ×1,5 (`FACTOR_FUENTE_GO`).

**Decisión (#37, 23/11):** se acepta esta variación como una limitación de la arquitectura, que depende de un LLM
no determinista, y no se añade ninguna regla de estabilidad. Lo que la compensa es que la persona experta siempre
puede leer el abstract en la interfaz (artículo, cita y tipo de evidencia de cada gen) y fijar el signo en «Tu
criterio», que pasa a los dos Excels junto al resultado automático. Se descartan repetir cada ruta varias veces y
quedarse con la mayoría (multiplica las llamadas al LLM y el tiempo, con un cupo gratuito limitado) y mandar a
`revisar` los pares que cambian entre ejecuciones (exige esas mismas repeticiones para detectarlos).

## Acierto frente a una persona

No hay todavía una medida frente a una persona:

- El benchmark (ADR-005) mide a Gemini contra el gold set: exactitud del 84 %, precisión de los signos del 72 % y
  cobertura del 40 %. Pero el gold set lo etiquetaron anotadores Claude a ciegas, no expertos humanos, así que el
  acierto puede estar inflado.
- Los tiempos a mano de la tabla son estimaciones.

**Cómo convertirlo en KPI real** (encargado a CIMUS, sin fecha de entrega; #38): que una persona haga GO:0072678 a mano con cronómetro y sin ver el
resultado del sistema. Por cada uno de los 11 genes: buscar en PubMed, elegir los abstracts, decidir el signo (`+1`,
`−1` o sin signo) con su cita y apuntar los minutos. Con eso se obtienen el tiempo real por gen y por ruta, la
concordancia gen a gen con el sistema y el NPS a mano.
