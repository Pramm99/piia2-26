# Spec: Interfaz web para ejecutar una ruta (Fase 4)

## Qué hay que construir
Una interfaz web (Fase 4, `codigo/fase4_frontend/`) con la que una persona sin línea de comandos ejecuta **una ruta GO** de principio a fin y entiende el resultado. Tiene tres piezas (componentes 17, 18 y 19 de [`ARCHITECTURE.md`](../ARCHITECTURE.md)):

1. **Interfaz** (`src/App.tsx`, React + Vite, `npm run dev` desde `codigo/fase4_frontend/`, en `http://localhost:5173/`): subir los Excels de rutas, elegir la ruta, ejecutarla y leer el resultado.
2. **Puente HTTP local** (`api_puente.py`, `python fase4_frontend/api_puente.py` desde `codigo/`, en `http://127.0.0.1:8000`): ejecuta seguidas las Fases 1 → 2 → 3 para la ruta elegida.
3. **Excel de resultados** (`src/ExcelResultados.tsx`): acumula en un mismo Excel las rutas que se van ejecutando.

No se pueden lanzar las fases por separado ni el Excel entero: para eso está la línea de comandos ([`AGENTS.md`](../AGENTS.md)). El uso paso a paso está en las [instrucciones](../codigo/fase4_frontend/instrucciones_uso_frontend.md).

### Entradas
| Entrada | Qué se usa |
|---|---|
| Excel de **rutas sobreexpresadas** (upregulated), subido por la persona | Primera hoja, columnas `ID` (GO_ID), `Description` y `geneID` (genes separados por `/`). Es el formato de `codigo/tools_cimus/NK_rutas_activadas_GO.xlsx`. |
| Excel de **rutas infraexpresadas** (downregulated), subido por la persona | Las mismas columnas. Es el formato de `codigo/tools_cimus/NK_rutas_suprimidas_GO.xlsx`. |
| `codigo/.env` | Las claves que necesitan las Fases 1 y 2 (`GEMINI_API_KEY`, `GROQ_API_KEY`, `NCBI_EMAIL`). |
| `codigo/tools_cimus/NK_cells_DESeq2_results.xlsx` (opcional) | Tabla de log2FC que usa la Fase 3 si existe, como en la línea de comandos. |

* No hay nada precargado. Vale con uno de los dos Excels o con los dos, y hay uno por lista a la vez: **Cambiar** sustituye el de esa lista y **Quitar** lo elimina.
* Si falta alguna de las tres columnas, la interfaz lo dice y no carga el fichero.
* Una ruta que está en los dos Excels se ejecuta **con todos sus genes**: los de la lista sobreexpresada como *up* y los de la infraexpresada como *down*, igual que la Fase 3 junta las dos listas en un solo término GO.

### Paso 1 · Elegir y lanzar la ruta
* La persona busca la ruta por GO_ID, nombre o gen, la marca (se ven sus genes sobreexpresados e infraexpresados) y pulsa **Ejecutar GO:…**. Hay un paso de confirmación antes de lanzar nada, porque la ejecución en frío consume cupo del LLM.
* La interfaz consulta `GET /salud` cada 5 s y muestra **● Motor Python conectado** cuando el puente responde. Sin puente, no deja ejecutar y dice cómo arrancarlo.

### Paso 2 · Puente con las fases
| Petición | Qué hace | Respuesta |
|---|---|---|
| `GET /salud` | Comprueba que el puente está vivo. | `{"ok": true}` |
| `POST /ejecutar-ruta` con `{"GO_ID", "Descripcion", "Genes_up", "Genes_down"}` | Valida la petición y lanza las tres fases en un hilo. | `202` si arranca; `400` si el GO_ID no tiene la forma `GO:` + 7 cifras, si la ruta no tiene genes o si el JSON está mal formado; `409` si ya hay una ruta en marcha. |
| `GET /estado` | Fase en curso (1, 2 o 3) y, al terminar, el resultado o el error. | `estado` ∈ {`libre`, `ejecutando`, `terminado`, `error`}. |

* **Fase 1:** escribe dos Excels de entrada reducidos a la ruta (una fila cada uno, o ninguna si la lista no tiene genes) y ejecuta la Fase 1 sobre ellos. Redirige sus rutas de entrada y de salida desde fuera, igual que `tests/test_fase1_e2e.py`, **sin tocar `fase1_ingesta/`**. Si la Fase 1 no encuentra ninguna evidencia, la ejecución acaba en `error` con ese mensaje.
* **Fase 2:** Gemini como principal y gpt-oss solo como respaldo ([ADR-005](../decisions/adr-005-eleccion-modelo-coste-cero.md)), con el registro de siempre (`codigo/data/respuestas_llm.jsonl`): lo ya preguntado no se vuelve a pedir. Si ningún par llega al LLM, escribe un `fase2_resultados.xlsx` con las hojas vacías para que la Fase 3 funcione igual.
* **Fase 3:** con la tabla de log2FC de CIMUS si existe.
* **Resultado:** las filas de `Por_ruta` y `Por_par` de la Fase 3, el Excel de la Fase 3 (en base64, para descargarlo), los tiempos de cada fase, el uso del LLM (llamadas, reutilizadas, pendientes y tokens) y, por gen, el detalle que explica el signo:
  * los artículos que leyó el LLM, uno por PMID, con su título, signo, estado, motivos, `Confianza_final`, la frase citada y lo que contestó el modelo (efecto, confianza y tipo de evidencia), aunque el código lo dejara en `UNKNOWN`;
  * los votos de cada artículo, uno por subproceso de la ruta, con su organismo, tipo celular y el peso que les da la Fase 3 (`casos_con_peso` de `fase3_scoring/nps.py`);
  * si el signo sale de Gene Ontology, sus códigos de evidencia y PMIDs.
* La interfaz consulta `/estado` cada 1,5 s y muestra la fase en curso y el tiempo transcurrido.

### Paso 3 · Resultado en lenguaje llano
Sin códigos internos a la vista (`+1:15811952(0.36)`, `evidencia_debil`…): todo se explica con palabras.

* **Veredicto:** si la ruta está activada, inhibida, mixta o sin evidencia suficiente; la escala del NPS de −1 a +1 con sus tres zonas (±`UMBRAL_NPS`); cuántos genes la sostienen, con evidencia directa de GO o por artículos, y cuántos tienen evidencia débil (peso a su favor < 1); cuántos genes tendrían que dejar de contar para que perdiera la lectura, y los genes repartidos en «empujan hacia activada», «empujan hacia inhibida» y «no cuentan».
* **Una tarjeta por fase**, con los mismos tres niveles de texto (título, resultado y notas):
  * Fase 1: genes, inmunoglobulinas, signos de GO, genes con artículos, artículos y genes sin ninguno;
  * Fase 2: artículos leídos, los que no mencionan el gen, los que dan signo y los que quedan sin conclusión;
  * Fase 3: la lectura con la cuenta del NPS y el NPS pesado por log2FC.
* **Una fila por gen:** si está sobreexpresado o infraexpresado en NK, qué hace en el proceso, hacia dónde empuja la ruta, de dónde sale el signo (Gene Ontology, N artículos, inmunoglobulina o criterio experto) y por qué. Al abrirla:
  * cada artículo con el título enlazado a PubMed, su conclusión, su confianza y la frase citada;
  * el peso de la evidencia con una barra y la cuenta de cada voto (p. ej. 0,36 = confianza 73 % × 0,5 por ser en ratón);
  * en los artículos sin conclusión, el tipo de evidencia y hacia dónde se inclinaba el LLM.
* **Descargar Excel de la Fase 3:** siempre el resultado automático.
* Si quedaron preguntas `pendiente` (cupo del LLM agotado), un aviso lo dice y pide volver a ejecutar la ruta más tarde.

### Paso 4 · Criterio de la persona experta («Tu criterio»)
* A la derecha de la tabla de genes, un desplegable por gen: **Automático**, **Activa**, **Inhibe** o **No lo cambia**.
* Elegir uno fija el signo del gen (`+1`, `−1` o `neutro`) como `resuelto` con origen `Experto`, y la contribución vuelve a ser signo × dirección.
* El veredicto, la tarjeta de la Fase 3 y la tabla se recalculan al momento con **las mismas reglas que `fase3_scoring/nps.py`** (`tabla_rutas` y `_lectura`): NPS, `NPS_log2FC`, `Lectura`, `Lectura_log2FC`, `Sensible_al_peso`, `Cobertura` y recuentos. Los umbrales son los de `fase3_scoring/config.py` (`UMBRAL_NPS` 0,33, `MIN_PARES_CON_SIGNO` 3 y `MIN_COBERTURA` 0,30), copiados en `App.tsx`.
* Un aviso compara la lectura automática con la que lleva los cambios, y **Deshacer mis cambios** los quita.
* Los cambios **no se guardan**: no pasan al Excel de la Fase 3 ni al Excel de resultados, y una nueva ejecución vuelve al resultado automático.

### Paso 5 · Excel de resultados
Para juntar varias rutas en un mismo Excel sin copiarlas a mano.

* **Abrir Excel** pone uno vacío o uno con rutas ya buscadas, y **Crear Excel nuevo** empieza uno (`resultados_rutas.xlsx`). Si ya se había ejecutado una ruta, se añade en ese momento.
* Cada ruta ejecutada se añade sola, con el resultado automático:

  | Hoja | Una fila por | Columnas |
  |---|---|---|
  | `Rutas` | ruta ejecutada | `Fecha`, `GO_ID`, `Ruta_Nombre`, `Listas`, `Lectura`, `NPS`, `NPS_log2FC`, `Lectura_log2FC`, `Sensible_al_peso`, `n_total`, `n_activan`, `n_inhiben`, `n_neutros`, `n_no_concluyente`, `n_sin_evidencia`, `n_pendiente`, `Cobertura`, `Genes_activan`, `Genes_inhiben` (las de `Por_ruta` de la Fase 3, más la fecha). |
  | `Genes` | par (gen, ruta) de las rutas ejecutadas | `GO_ID`, `Ruta_Nombre`, `Gen`, `Direccion`, `Log2FC`, `Signo_par`, `Estado_par`, `Origen`, `Contribucion`, `Motivos`, `Votos`, `PMIDs_consultados` (las de `Por_par`). |

* Si la ruta ya estaba, sus filas se **sustituyen**, no se duplican. Las demás hojas del libro se conservan tal cual.
* Un Excel cuya hoja `Rutas` no tiene la columna `GO_ID` se rechaza, porque no es un Excel de resultados.
* En Chrome y Edge (API de acceso a ficheros) los cambios se escriben en el fichero elegido; en los demás navegadores, con **Descargar**.
* **Limpiar Excel** (con confirmación) borra todas sus rutas, **Quitar** deja de usarlo sin borrarlo y la papelera de una fila quita solo esa ruta.
* La vista previa muestra cada ruta con su lectura, una barra del NPS, los genes que activan e inhiben y la fecha; al abrirla, sus genes en colores (verde: empuja hacia activada; rojo: hacia inhibida; gris: no cuenta).

### Salida
| Dónde | Qué |
|---|---|
| `codigo/data/frontend/<GO_ID>/` (no se versiona) | `entrada_activadas.xlsx` y `entrada_suprimidas.xlsx` (reducidos a la ruta), `fase1_dataset_abstracts.xlsx`, `fase2_resultados.xlsx` y `fase3_scoring.xlsx` de esa ruta. |
| Navegador | `fase3_scoring_<GO_ID>.xlsx` al pulsar **Descargar Excel de la Fase 3**. |
| Fichero elegido por la persona | El Excel de resultados, con las hojas `Rutas` y `Genes`. |

## Por qué
* **El usuario final es una persona de CIMUS, no un programador.** La línea de comandos y un Excel de cuatro hojas con códigos como `+1:15811952(0.36)` no se entienden sin conocer el pipeline. La interfaz dice si la ruta está activada o inhibida y por qué, gen a gen, con los artículos y la frase que lo sostienen.
* **Una ruta cada vez:** es la pregunta real de CIMUS («¿esta ruta está activada o inhibida?») y el alcance del proyecto. Con las cachés y el registro hechos tarda entre 9 y 20 s y en frío unos 2–3 minutos ([`docs/kpis.md`](../docs/kpis.md)); el Excel entero en frío consume horas y cupo del LLM, y se ejecuta por la línea de comandos.
* **Las tres fases seguidas y sin fases sueltas:** el resultado solo tiene sentido completo, y así nadie puede mezclar la Fase 3 de una ruta con la Fase 2 de otra.
* **Puente propio sobre `http.server`, sin servidor web nuevo:** solo escucha en `127.0.0.1`, solo hace tres cosas y no añade dependencias a `requirements.txt`. Llama a las funciones de las fases y redirige sus rutas de entrada y salida, así que la Fase 4 no duplica lógica ni cambia el comportamiento de la línea de comandos.
* **Un hilo y consulta del estado:** la ejecución en frío dura minutos, más que el tiempo de espera normal de una petición HTTP. Lanzarla en un hilo y consultar `/estado` deja ver la fase en curso.
* **Carpeta propia por ruta y registro compartido** ([ADR-004](../decisions/adr-004-persistencia-ficheros-locales.md)): no pisa las salidas del Excel completo, y una ruta ya consultada no vuelve a gastar llamadas al LLM.
* **«Tu criterio» solo en pantalla:** el experto tiene que poder ver qué pasaría si un gen tuviera otro signo, porque muchos genes de NK tienen funciones duales. Pero el resultado del pipeline tiene que seguir siendo reproducible y trazable a sus artículos; un signo fijado a mano que se guardara se confundiría con uno inferido.
* **Excel de resultados en el navegador:** CIMUS ya trabaja con Excel. Acumular las rutas en un fichero que elige la persona evita una base de datos (ADR-004) y que tenga que copiar resultados a mano entre ejecuciones.

**Alternativas descartadas:**
* **Streamlit o Gradio:** dan una interfaz rápida, pero con poco control del diseño del veredicto, la tabla gen a gen y el desplegable por gen, y ejecutan la lógica en cada interacción.
* **FastAPI o Flask para el puente:** añaden dependencias para tres rutas que la librería estándar ya cubre.
* **Llamar a las fases desde el navegador o reescribirlas en TypeScript:** duplicaría la lógica de las Fases 1–3 y dejaría dos versiones que mantener. Solo se copian en `App.tsx` las reglas de lectura del NPS, que son cortas, para recalcular «Tu criterio» al momento.
* **Guardar el criterio del experto:** se descartó para no mezclar signos inferidos con signos fijados a mano (ver arriba).

## Restricciones
* **No modifica las fases:** no cambia `fase1_ingesta/`, `fase2_inferencia/` ni `fase3_scoring/`; solo redirige sus rutas de entrada y salida.
* **Local:** el puente solo escucha en `127.0.0.1:8000` y la interfaz en `localhost:5173`. Las claves se quedan en `codigo/.env`, que no se versiona, y no pasan por el navegador.
* **Una ruta a la vez:** una segunda petición mientras hay otra en marcha recibe `409`.
* **Mismo resultado que la línea de comandos:** con las mismas entradas, cachés y registro, la lectura y el NPS de la ruta coinciden con los de `python -m fase3_scoring`.
* **Mismas reglas en «Tu criterio»:** el recálculo en pantalla sigue `fase3_scoring/nps.py` y `fase3_scoring/config.py`. Si cambian los umbrales o la regla de lectura, hay que cambiarlos también en `App.tsx`.
* **Cupo del LLM agotado:** la ejecución termina igual, con las preguntas `pendiente` y el aviso en pantalla. No falla.
* **SheetJS desde el CDN** (`xlsx@0.18.5`): la interfaz lo carga al leer o escribir un Excel, así que necesita conexión para eso.
* **Comprobación del código:** desde `codigo/fase4_frontend/`, `npx tsc -b` y `npx eslint src` sin errores. La Fase 4 aún no tiene pruebas automáticas (#40).

## Criterios de aceptación
La Fase 4 no tiene pruebas en `codigo/tests/` (#40): estos criterios se comprueban a mano en el navegador, salvo los de `tsc` y `eslint`.

* [x] ✅ **Ruta completa** (a mano, #42): con GO:0072678 y los dos Excels de `codigo/tools_cimus/`, la ejecución pasa por las Fases 1, 2 y 3 y da `activada` con NPS 0,333, igual que la ejecución de referencia, y escribe sus ficheros en `codigo/data/frontend/GO_0072678/`.
* [x] ✅ **Sin nada precargado** (a mano, #42): la interfaz arranca sin rutas; acepta un Excel por lista, **Cambiar** lo sustituye y **Quitar** lo elimina.
* [x] ✅ **Peticiones no válidas** (a mano con `curl`, 14/11): un GO_ID sin la forma `GO:` + 7 cifras, una ruta sin genes o un JSON mal formado reciben `400`, y una segunda ruta mientras GO:0072678 está en marcha, `409`. Esa ejecución, con las cachés y el registro hechos, da `activada` y NPS 0,333 sin ninguna llamada al LLM (12 respuestas reutilizadas).
* [x] ✅ **Resultado en lenguaje llano** (a mano, #43): veredicto, tarjetas por fase y tabla de genes sin códigos internos; el peso de cada voto con su cuenta, y en CX3CR1 el tipo de evidencia y la inclinación del LLM («activa», 60 %, pero solo correlación).
* [x] ✅ **Tu criterio** (a mano, #44): en GO:0072678, GPR183 en «No lo cambia» da `mixta` y NPS 0,25; **Deshacer mis cambios** vuelve a `activada` y 0,333. El Excel de la Fase 3 descargado sigue siendo el automático.
* [x] ✅ **Excel de resultados** (a mano con un fichero simulado, #45): crear uno, añadir dos rutas, repetir una sin duplicarla, abrir uno incompleto y completarlo, y limpiarlo.
* [ ] **Excel de resultados con el diálogo real** (#39): las mismas operaciones con el diálogo de ficheros de Chrome y con **Descargar** en otro navegador.
* [x] ✅ **Fondo blanco** (a mano, #46): el botón de la cabecera cambia de tema, los textos se leen sobre blanco y el navegador recuerda la elección.
* [x] ✅ **Código** (14/11): `npx tsc -b` y `npx eslint src` sin errores, y `python -m pytest` en verde (148 pruebas, todas de las Fases 1–3).
* [ ] **Pruebas automáticas** (#40): pruebas del puente (`/salud`, `/ejecutar-ruta` y `/estado`, con las fases simuladas) y del recálculo de «Tu criterio» frente a `fase3_scoring/nps.py`.
