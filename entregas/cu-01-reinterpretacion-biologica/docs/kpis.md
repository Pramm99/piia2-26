# KPIs: una ruta, el Excel completo y a mano

El proyecto está acotado a **una única ruta**. Las cifras voluminosas que aparecen en el resto de la documentación
(920 llamadas, 2,63 M tokens, casi una hora de Fase 1…) corresponden al **Excel completo de CIMUS** (352 rutas), que
se procesa entero para el benchmark y para medir el sistema, no al alcance del proyecto.

Este documento separa tres columnas:

- **Una ruta:** ejecución en frío de GO:0072678 *T cell migration* (está en las dos listas de CIMUS) del 2026-11-13,
  con el código actual, sin ninguna caché y solo con acceso a red.
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
| Tiempo total | **2,4 min** (Fase 1: 90 s; Fase 2: 52 s; Fase 3: 1 s) | Fase 1 en frío: casi 1 h. Fase 2: unas 2–2,5 h de reloj (51 min de tiempo de modelo; 279 llamadas tardaron 42 min en el último relanzamiento). Fase 3: segundos | **1,5 h aprox.** para la ruta; **unas 350 h** para el Excel completo |
| Llamadas al LLM | 8 (Gemini); 0 a gpt-oss | 920 a Gemini; 7 a gpt-oss como respaldo | — |
| Tokens | **16.724** (14.932 de entrada, 1.792 de salida) | 2,63 M en Gemini; unos 20 K en gpt-oss | — |
| Coste económico | 0 € | 0 € | horas de una persona experta |
| Peticiones HTTP | 67, ninguna con error | no medidas | búsquedas manuales en PubMed |
| Descarga | 58,9 MB (47 MB son el OBO y el GAF de GO, fijos) | el OBO y el GAF más unos 33.900 abstracts (57 MB en caché) | — |
| Disco | 50 MB (47 MB del OBO y el GAF) | 127 MB entre cachés y salidas | — |
| Memoria máxima | 777 MB (Fase 1, al cargar el GAF) | no medida | — |

Una ejecución posterior de la misma ruta reutiliza las cachés: la red y el LLM solo se usan para lo nuevo.

## Evidencia y resultado

| KPI | Una ruta | Excel completo | A mano |
|---|---|---|---|
| Artículos candidatos comprobados por el filtro | 1.422 (Europe PMC, para 6 genes) | unos 33.900 | habría que cribarlos leyendo títulos |
| Abstracts que llegan al análisis | 11 | 1.842 | 11 / 1.842 que leer y juzgar |
| Preguntas (gen, PMID, proceso) | 9; 8 al LLM y 1 cerrada sin LLM | 2.556; 2.464 al LLM y 92 cerradas | una decisión por pregunta |
| Genes o pares con signo (cobertura) | 8 de 11 (73 %): 5 activan, 3 inhiben | 1.693 de 3.172 resueltos | — |
| Lectura de la ruta | NPS 0,25 → **mixta** (con log2FC: 0,31, mixta) | 132 activadas, 29 inhibidas, 45 mixtas y 146 insuficientes | — |

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

Las otras 8 respuestas coinciden. La causa es doble: el modelo no es determinista, y en el Excel completo las
preguntas de un gen van juntas en la misma llamada, con otras rutas, mientras que con una ruta van solas. Como el NPS
está justo en el umbral de 0,33, un solo gen cambia la lectura. **KPI: 1 de 9 respuestas del LLM cambió (89 % de
acuerdo) y la lectura de la ruta cambió.** Con una ruta conviene repetir la ejecución y fijarse en `Sensible_al_peso`
y en los pares de `evidencia_debil`, que aquí son todos los que dan signo por el LLM (un solo abstract cada uno).

## Acierto frente a una persona

No hay todavía una medida frente a una persona:

- El benchmark (ADR-005) mide a Gemini contra el gold set: exactitud del 84 %, precisión de los signos del 72 % y
  cobertura del 40 %. Pero el gold set lo etiquetaron anotadores Claude a ciegas, no expertos humanos, así que el
  acierto puede estar inflado.
- Los tiempos a mano de la tabla son estimaciones.

**Cómo convertirlo en KPI real:** que una persona del equipo haga GO:0072678 a mano con cronómetro y sin ver el
resultado del sistema. Por cada uno de los 11 genes: buscar en PubMed, elegir los abstracts, decidir el signo (`+1`,
`−1` o sin signo) con su cita y apuntar los minutos. Con eso se obtienen el tiempo real por gen y por ruta, la
concordancia gen a gen con el sistema y el NPS a mano.
