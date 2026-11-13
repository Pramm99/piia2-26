# Spec: Agregación de Evidencias y Net Pathway Score (Fase 3)

## Qué hay que construir
Un módulo de scoring (Fase 3, `codigo/fase3_scoring/`, `python -m fase3_scoring [excel_fase1] [excel_fase2] [log2fc|ninguno]` desde `codigo/`) que, a partir de las salidas de las Fases 1 y 2, haga dos cosas:

1. **Agregar** los signos de todos los artículos de cada par (gen, ruta) en un único signo del par, con su estado.
2. **Calcular** para cada ruta GO un *Net Pathway Score* (NPS) que combine el signo de cada gen sobre la ruta con la dirección de expresión del gen en las células NK.

El módulo **no llama a ningún modelo ni a la red**: solo lee ficheros locales y es determinista.

### Entradas
| Fichero | Hoja | Qué se usa |
|---|---|---|
| `codigo/data/fase2_resultados.xlsx` | `Por_ruta` | Una fila por (gen, ruta, PMID, proceso): `Signo_ruta`, `Estado`, `Motivos`, `Confianza_final`. |
| `codigo/data/fase2_resultados.xlsx` | `Preguntas` | `Organismo` y `Tipo_celular` de cada pregunta (gen, PMID, proceso), unidos a `Por_ruta` por (`Gen`, `PMID`, `Proceso_ID`). |
| `codigo/fase1_ingesta/fase1_dataset_abstracts.xlsx` | `Triaje_polaridad` | Todos los pares (gen, ruta) que no son inmunoglobulinas, con `Destino`, `Signo_GO` y `Estado_Original`. |
| `codigo/fase1_ingesta/fase1_dataset_abstracts.xlsx` | `Inmunoglobulinas` | Pares de inmunoglobulinas, ya con signo `neutro`. |
| `codigo/tools_cimus/NK_cells_DESeq2_results.xlsx` (opcional; no se versiona: se reparte dentro del equipo) | primera | Tabla de expresión diferencial de CIMUS: el gen en la primera columna, sin nombre, y `log2FoldChange` (log2 Fold-Change de NK en HNSC). También vale un `.xlsx` o `.csv` con columnas `Gen` y `log2FC`. El CLI la usa sola si existe; `ninguno` calcula sin ella. Sin la tabla, `NPS_log2FC`, `Lectura_log2FC` y `Sensible_al_peso` quedan vacías. Solo cambia la sensibilidad (`NPS_log2FC`), nunca el `NPS`. |

`Estado_Original` da la **dirección del gen**: `Activada` (lista de genes *up*) → `d = +1`; `Suprimida` (lista de genes *down*) → `d = −1`. «Activada» y «suprimida» son solo los nombres de las listas de CIMUS, no una conclusión sobre la ruta.

### Paso 1 · Voto de cada artículo
Cada fila de `Por_ruta` es un caso. Su signo sobre la ruta (`Signo_ruta`) ya viene compuesto por la Fase 2 (efecto × signo del camino GO × polaridad de la ruta).

* **Quién vota:** solo los casos con `Estado = resuelto` y `Signo_ruta` ∈ {`+1`, `−1`, `neutro`}. Los `UNKNOWN`, `revisar` y `pendiente` no votan, pero se cuentan.
* **Peso del voto:** `w = Confianza_final / 100 × f_contexto`.
  * `f_contexto` = 1,0 si el experimento es en humano (`Organismo` = `human`, `not_stated` o vacío) y en células inmunes (`Tipo_celular` ∈ {`NK`, `T`, `other_immune`, `not_stated`} o vacío).
  * Vale 0,5 por cada condición que no se cumpla: ratón u otro organismo, o tumor u otro tipo celular. Si fallan las dos, 0,25.
  * El tipo de evidencia (afirmación de fondo, correlación…), la posición de la frase y el acuerdo entre modelos **ya están dentro de `Confianza_final`** (`fase2_inferencia/confianza.py`), así que no se vuelven a penalizar aquí.
  * Si `Confianza_final` falta en una fila resuelta, se toma 0,5 y la fila lleva la marca `peso_por_defecto`.

### Paso 2 · Signo del par (gen, ruta)
Para cada par se suman los pesos por clase: `W(+1)`, `W(−1)` y `W(neutro)`. Sean `W_total` la suma y `W_max` el peso de la clase ganadora. Las reglas se aplican en este orden:

| # | Situación del par | Signo del par | Estado del par | Motivo |
|---|---|---|---|---|
| 1 | Inmunoglobulina (hoja `Inmunoglobulinas`) | `neutro` | `resuelto` | `inmunoglobulina` |
| 2 | `Destino = aceptar_GO` | `Signo_GO` | `resuelto` | `aceptado_por_GO` |
| 3 | `Destino = sin_evidencia` | `UNKNOWN` | `no_concluyente` | `sin_evidencia` |
| 4 | Hay votos y `(W_total − W_max) / W_total < 1/3` | la clase ganadora | `resuelto` (o `revisar` si el par era `LLM_y_revision`) | `minoria_discrepante` si la minoría pesa más de 0 (y `LLM_y_revision` si va a revisar) |
| 5 | Hay votos y la minoría pesa ⅓ del total o más (también un empate en cabeza) | `UNKNOWN` | `revisar` | `conflicto_entre_abstracts` |
| 6 | Sin votos y algún caso `revisar` | `UNKNOWN` | `revisar` | los motivos de esos casos |
| 7 | Sin votos y algún caso con el motivo `contradictorio` | `UNKNOWN` | `revisar` | `contradictorio` |
| 8 | Sin votos y algún caso `pendiente`, o ningún caso en la Fase 2 (se ejecutó solo para un gen o una ruta) | `UNKNOWN` | `pendiente` | `pendiente_fase2` o `sin_fase2` |
| 9 | Solo casos `UNKNOWN` | `UNKNOWN` | `no_concluyente` | los motivos de esos casos |

Además:

* **Conflicto sin anulación:** en la regla 5 se guardan los dos recuentos (`W(+1)`, `W(−1)`, `W(neutro)` y el número de PMIDs de cada clase, `n_PMIDs_pos`, `n_PMIDs_neg` y `n_PMIDs_neutro`). El conflicto se expresa con el estado y el motivo, nunca con un signo nuevo.
* **Evidencia débil:** un par resuelto por la regla 4 (o que pasa a `revisar` por `LLM_y_revision`) con `W_total < 1` lleva además `evidencia_debil`. Es el caso, por ejemplo, de un único artículo en ratón.
* **Contradicción dentro de un abstract:** va a `revisar` (regla 7) y no a `no_concluyente`, porque un abstract que da las dos direcciones suele describir una función dual real (p. ej. KIR2DL4 o la galectina-9). Eso es información para el experto, no una ausencia de evidencia.
* **Votos sin peso:** si todos los votos pesan 0 (`Confianza_final = 0`), el par se trata como si no tuviera votos y lleva `votos_sin_peso`.
* **Trazabilidad:** cada par guarda la lista de votos en el formato `signo:PMID(peso)`, p. ej. `+1:10652336(0.86); -1:29988376(0.45)`.

### Paso 3 · Contribución del par y Net Pathway Score
* **Contribución:** `c = s × d`, donde:
  * `s` es el signo del par (`+1`, `−1` o 0 si es `neutro`);
  * `d` es la dirección del gen (+1 *up*, −1 *down*).

  Todos los genes pesan igual: el log2FC no entra en `c` (ver «Por qué»).
* **Lectura de `c`:** `c > 0` significa que el gen empuja la ruta hacia la activación; `c < 0`, hacia la inhibición. Un `c < 0` en un gen *up*, por ejemplo un regulador negativo que sube, es un **freno o retroalimentación**, no un error. Se marca `Freno_retroalimentacion` en todo par con `c < 0`, igual que en el triaje de la Fase 1.
* **Unidad de la ruta: el término GO.** Si un término aparece en las dos listas de CIMUS, sus pares de genes *up* y *down* se juntan en la misma ruta. Precisamente ahí está la contradicción de enriquecimiento que el proyecto resuelve.
* **Score:**

  `NPS = Σ c / n`, sumando solo sobre los `n` pares `resuelto` con signo `+1` o `−1`.

  * El NPS va de −1 (todos los genes que empujan lo hacen hacia la inhibición) a +1 (todos hacia la activación).
  * Los pares `neutro` no entran en el cociente, porque no empujan la ruta en ningún sentido. Se informan como `Fraccion_neutros`.
  * Los pares `revisar`, `no_concluyente`, `pendiente` y `sin_evidencia` aportan 0 y se cuentan aparte.
* **Sensibilidad:** se calcula también `NPS_con_revisar`, que incluye los pares en `revisar` con la clase de mayor peso, para que el experto vea cuánto cambiaría el score si se confirmaran. Esa clase va en `Signo_revisar`: la de los votos resueltos o, si no hay, la de los casos `revisar` de la Fase 2; con empate o sin signo, el par no cuenta.
* **Sensibilidad al peso del gen:** si hay log2FC, se calcula también `NPS_log2FC = Σ c·|log2FC| / Σ |log2FC|` sobre los mismos pares (un gen sin log2FC pesa 1 y lleva `sin_log2FC`), con su `Lectura_log2FC`. Si las dos lecturas difieren, la ruta lleva `Sensible_al_peso = sí`: su conclusión depende de cuánto cambie cada gen y conviene revisarla a mano.
* **Conclusión de la ruta** (`Lectura`), con umbrales en `fase3_scoring/config.py`:
  * `insuficiente` si `n_con_signo < MIN_PARES_CON_SIGNO` (3) o `Cobertura < MIN_COBERTURA` (0,30);
  * si no: `activada` si `NPS ≥ UMBRAL_NPS` (+0,33), `inhibida` si `NPS ≤ −UMBRAL_NPS` y `mixta` en el resto.
  * Son umbrales provisionales: los fijará el equipo con CIMUS al revisar las primeras rutas.
* **Cobertura:** `Cobertura = n_resueltos / n_total`, donde `n_resueltos` incluye los neutros y `n_total` todos los pares de la ruta, también las inmunoglobulinas y los `sin_evidencia`.

### Salida
`codigo/data/fase3_scoring.xlsx`, con cuatro hojas:

| Hoja | Una fila por | Columnas |
|---|---|---|
| `Por_ruta` | término GO | `GO_ID`, `Ruta_Nombre`, `Listas` (activadas / suprimidas / ambas), `NPS`, `NPS_con_revisar`, `Lectura`, `NPS_log2FC`, `Lectura_log2FC`, `Sensible_al_peso` (sí/no; vacías sin log2FC), `n_total`, `n_activan` (c > 0), `n_inhiben` (c < 0), `n_neutros`, `n_revisar`, `n_no_concluyente`, `n_sin_evidencia`, `n_pendiente`, `Cobertura`, `Fraccion_neutros`, `Genes_activan`, `Genes_inhiben`, `Genes_revisar`. |
| `Por_par` | par (gen, ruta) | `Gen`, `GO_ID`, `Ruta_Nombre`, `Direccion` (up/down), `Log2FC`, `Signo_par`, `Estado_par`, `Motivos`, `Origen` (`GO`, `LLM`, `Ig`, `ninguno`), `W_pos`, `W_neg`, `W_neutro`, `n_PMIDs`, `n_PMIDs_pos`, `n_PMIDs_neg`, `n_PMIDs_neutro`, `Votos`, `PMIDs_consultados` (todos los artículos que la Fase 2 leyó para el par, también los que no votaron), `Signo_revisar`, `Contribucion`, `Freno_retroalimentacion`. |
| `Abstracts_sin_signo` | artículo de un par `UNKNOWN` con evidencia | `Gen`, `GO_ID`, `Ruta_Nombre`, `Direccion`, `Estado_par`, `PMID` (enlace a PubMed), `Enlace`, `Proceso`, `Veredicto_LLM`, `Confianza_modelo`, `Estado`, `Motivos`, `Cita`, `Titulo` y `Abstract`. Son los artículos de los pares sin signo que sí tienen casos en la Fase 2 (no concluyentes, en revisión o pendientes), para leerlos a mano; los `sin_evidencia` no tienen artículo y no salen. El título y el abstract salen de la hoja `Con_abstract` de la Fase 1. |
| `Resumen` | — | Recuentos por estado, por lectura y por `Lectura_log2FC`, número de rutas `Sensible_al_peso`, artículos y pares de `Abstracts_sin_signo`, ficheros de entrada con su fecha de modificación y valores de los parámetros usados. |

Las rutas se ordenan por `|NPS|` descendente y, a igualdad, por `GO_ID`; los pares, por `GO_ID` y `Gen`.

## Por qué
* **El problema de CIMUS es la ruta, no el gen:** el enriquecimiento dice qué rutas tienen genes alterados, pero no si quedan activadas o inhibidas. Cuando una ruta tiene genes *up* y *down* a la vez, la lectura ingenua es contradictoria. El NPS da una respuesta con signo que se puede explicar gen a gen.
* **Hace falta agregar porque un par tiene varios artículos** (mediana de 1 abstract por par y p90 de 4), y no siempre dicen lo mismo. Una regla transparente de pesos y mayorías es auditable. Un noisy-OR (como el *belief engine* de INDRA) daría una confianza falsa, porque supone errores independientes, y aquí se repiten el mismo laboratorio, la misma revisión y la misma forma de leer mal del modelo.
* **Un conflicto no es necesariamente un error:** muchos genes de NK tienen funciones duales reales. Por eso el conflicto no se promedia a 0, sino que se manda a revisión con los dos recuentos visibles.
* **`Confianza_final` como peso:** es el porcentaje que ya se muestra junto a cada signo. Usarlo como peso evita tener dos sistemas de pesos distintos. Solo se añade el contexto biológico (especie y tipo celular), que `Confianza_final` no recoge porque no habla de lo bien que se lee el abstract, sino de si vale para células NK humanas.
* **Dirección × signo:** que un gen suba no basta para que la ruta se active. Un inhibidor que sube frena la ruta. Por eso el score multiplica el signo funcional (Fases 1 y 2) por la dirección de expresión.
* **Todos los genes pesan igual; el log2FC es solo sensibilidad** (#30). Con la tabla de expresión diferencial de CIMUS:
  * los 224 genes de las dos listas están en ella, ninguno contradice su lista y todos tienen `padj` < 0,05 y |log2FC| ≥ 1. Es decir, todos ya pasaron el corte de CIMUS: estar en la lista ya dice que el cambio es real;
  * el |log2FC| va de 1 a 7,7 (mediana 1,85), y los más grandes son los menos precisos. Entre los 153 genes con algún par resuelto con signo, la correlación de Spearman entre |log2FC| y su error estándar (`lfcSE`) es 0,56. El gen que más pesaría, CX3CR1 (−7,7), tiene un `baseMean` de 3,3 y un `lfcSE` de 2,6;
  * pesar por |log2FC| cambia la lectura de 16 de 352 rutas (Fase 1 del 09/11 y Fase 2 completa): 10 pasan de activada o inhibida a mixta y 6 de mixta a activada o inhibida. Ninguna pasa de activada a inhibida ni al revés. Esas 16 son justo las que marca `Sensible_al_peso`.

  **Alternativas descartadas:**
  * **Peso `|log2FC|`:** da más voto a los genes poco expresados, cuyo log2FC se infla, y no cambia ninguna conclusión de signo.
  * **`|log2FC|` con tope o en escala logarítmica** (`min(|log2FC|, 3)`, `log2(1 + |log2FC|)`): cambian 14 y 11 rutas, pero el tope es arbitrario y la conclusión es la misma.
  * **`|log2FC| − 1,96 · lfcSE`:** penaliza la imprecisión, pero cambia 34 rutas y le da la vuelta a una de activada a inhibida. Depende demasiado del error estándar, que es grande justo en los genes poco expresados.

## Restricciones
* **Sin red, sin LLM y sin bases de datos:** solo lee ficheros locales ([ADR-004](../decisions/adr-004-persistencia-ficheros-locales.md)), así que se puede repetir cuantas veces se quiera sin gastar cupo.
* **Determinista:** con las mismas entradas, el Excel de salida tiene exactamente el mismo contenido.
* **No modifica las fases anteriores:** no reescribe signos de la Fase 2 ni el triaje de la Fase 1. Si una regla de scoring necesita un dato nuevo, se añade en su fase de origen.
* **Fase 2 incompleta:** si `fase2_resultados.xlsx` tiene filas `pendiente` (cupo gratuito agotado), el scoring se ejecuta igual, marca esos pares como `pendiente` y avisa por consola del número de rutas afectadas. No falla.
* **Validación de la entrada:**
  * si falta `fase2_resultados.xlsx` o alguna de las hojas o columnas usadas, `ValueError` con el nombre de lo que falta;
  * si el fichero de log2FC trae un gen cuyo signo de log2FC contradice su lista (log2FC < 0 en la lista de genes *up*, o > 0 en la de *down*), `ValueError` con el gen;
  * un gen sin log2FC en el fichero pesa 1 en `NPS_log2FC` y lleva la marca `sin_log2FC`.
* **Parámetros en un único sitio:** los pesos de contexto, el umbral de minoría (⅓) y los umbrales de lectura viven en `fase3_scoring/config.py`, para que el equipo los ajuste sin tocar la lógica.
* **Sin modelado no lineal:** el score es una suma ponderada y explicable. No modela interacciones entre genes ni epistasia (fuera de alcance, ver README).

## Criterios de aceptación
Las pruebas están en `codigo/tests/test_scoring.py`, con tablas sintéticas y sin red.

* [x] ✅ **Mayoría con minoría por encima de ⅓** (`tests/test_scoring.py::test_mayoria_y_conflicto`): un par con tres votos resueltos, `+1` en humano (peso 1,0), `+1` en ratón (0,5) y `−1` en humano (1,0), tiene una minoría de 1,0/2,5 = 40 %. Sale `Signo_par = UNKNOWN`, `Estado_par = revisar`, motivo `conflicto_entre_abstracts`, `W_pos = 1.5` y `W_neg = 1.0`.
* [x] ✅ **Mayoría con minoría por debajo de ⅓** (`tests/test_scoring.py::test_mayoria_y_conflicto`): el mismo par con el `−1` en ratón (0,5) tiene una minoría de 0,5/2,5 = 20 %. Sale `+1`, `resuelto`, con el motivo `minoria_discrepante`.
* [x] ✅ **Pesos** (`tests/test_scoring.py::test_pesos`): `Confianza_final = 80`, `Organismo = mouse` y `Tipo_celular = tumor` dan `w = 0,8 × 0,5 × 0,5 = 0,2`.
* [x] ✅ **Evidencia débil** (`tests/test_scoring.py::test_evidencia_debil`): un único voto `−1` con `w = 0,4` da `−1`, `resuelto`, con `evidencia_debil`.
* [x] ✅ **Solo UNKNOWN** (`tests/test_scoring.py::test_solo_unknown_no_entra_en_el_nps`): un par cuyos casos son todos `UNKNOWN` sale `no_concluyente`, con `Contribucion = 0`, y no entra en el cociente del NPS.
* [x] ✅ **Contradicción** (`tests/test_scoring.py::test_contradiccion_va_a_revisar`): un par sin votos con un caso `contradictorio` sale `revisar`, no `no_concluyente`.
* [x] ✅ **Pendiente** (`tests/test_scoring.py::test_pendiente`): un par sin votos con algún caso `pendiente` sale `pendiente`. Un par del LLM sin ningún caso en la Fase 2 sale `pendiente` con `sin_fase2`, y la ruta cuenta los dos en `n_pendiente` (2).
* [x] ✅ **GO y dirección** (`tests/test_scoring.py::test_go_y_direccion`): un par `aceptar_GO` con `Signo_GO = −1` de un gen *down* tiene `Contribucion = (−1) × (−1) = +1`.
* [x] ✅ **Freno** (`tests/test_scoring.py::test_freno`): un par `−1` de un gen *up* tiene `Contribucion = −1` y `Freno_retroalimentacion = True`.
* [x] ✅ **Inmunoglobulinas** (`tests/test_scoring.py::test_inmunoglobulinas_no_cambian_el_nps`): un par de la hoja `Inmunoglobulinas` sale `neutro` y `resuelto`, suma en `n_neutros` y `n_total`, y no cambia el NPS.
* [x] ✅ **NPS** (`tests/test_scoring.py::test_nps_y_lectura`): una ruta con cuatro pares resueltos con contribuciones +1, +1, −1 y `neutro`, y otro `sin_evidencia`, da `NPS = (1 + 1 − 1) / 3 = 0,33`, `Fraccion_neutros = 1/4`, `Cobertura = 4/5 = 0,8` y `Lectura = activada`. Con solo dos pares con signo, `Lectura = insuficiente`.
* [x] ✅ **Sensibilidad** (`tests/test_scoring.py::test_revisar_cuenta_solo_en_nps_con_revisar`): un par `LLM_y_revision` con un único voto `−1` de un gen *up* sale `−1` en `revisar`, con `Signo_revisar = −1` y `Contribucion = 0`. No cambia el `NPS` (0,33) y sí `NPS_con_revisar`, que pasa a (1 + 1 − 1 − 1) / 4 = 0.
* [x] ✅ **Rutas en las dos listas** (`tests/test_scoring.py::test_ruta_en_las_dos_listas_es_una_fila`): un término GO con pares de genes *up* y *down* sale en **una sola fila** de `Por_ruta`, con `Listas = ambas` y todos sus pares.
* [x] ✅ **log2FC** (`tests/test_scoring.py::test_log2fc`): con un fichero de log2FC donde el gen tiene −2,0 y está en la lista *down*, su contribución con signo `+1` es −1 (el NPS no pesa por log2FC) y entra en `NPS_log2FC` con peso 2. Con log2FC = +1,5 en la lista *down*, el módulo lanza `ValueError` nombrando el gen.
* [x] ✅ **Sensibilidad al peso** (`tests/test_scoring.py::test_log2fc_solo_cambia_la_sensibilidad`): con la tabla de expresión diferencial tal cual, dos genes *up* que activan con |log2FC| = 1 y uno *down* que activa con |log2FC| = 4 dan `NPS = 0,333` (`activada`) y `NPS_log2FC = −0,333` (`inhibida`), y la ruta sale `Sensible_al_peso = sí`. Sin log2FC, esas tres columnas quedan vacías.
* [x] ✅ **Tabla de CIMUS** (`tests/test_scoring.py::test_tabla_de_log2fc_de_cimus`, que se salta si falta el fichero): los 224 genes de las dos listas tienen log2FC y ninguno contradice su lista.
* [x] ✅ **Entrada incompleta** (`tests/test_scoring.py::test_entrada_incompleta`): sin la hoja `Por_ruta` (o sin la columna `Confianza_final`), `ValueError` que nombra lo que falta.
* [x] ✅ **Determinismo y ausencia de red** (`tests/test_scoring.py::test_determinista_y_sin_red`): dos ejecuciones con las mismas entradas dan las mismas hojas celda a celda; la prueba bloquea `socket.socket` y `socket.create_connection` y no falla.
* [x] ✅ **Abstracts de los pares sin signo** (`tests/test_scoring.py::test_abstracts_de_los_pares_sin_signo`): el artículo de un par `UNKNOWN` con un caso `no_concluyente` sale en `Abstracts_sin_signo` con su título, su abstract, sus motivos y el PMID enlazado a `https://pubmed.ncbi.nlm.nih.gov/<PMID>/`; los de un par resuelto o `sin_evidencia`, no. `PMIDs_consultados` de un par con un voto `+1` y un caso `UNKNOWN` lista los dos PMIDs.
* [x] ✅ **Recuento completo** (`tests/test_scoring.py::test_recuento_completo_con_las_salidas_reales`, que se salta si faltan las salidas): con las salidas de las Fases 1 y 2 de `config.py`, `Por_par` tiene una fila por cada par del Excel de la Fase 1 y `Por_ruta` una por cada término GO distinto. Con la Fase 1 completa del 2026-11-09 son 3.172 pares (103 de inmunoglobulinas) y 352 rutas (`codigo/data/fase3_scoring.xlsx`); la prueba no fija esas cifras.
