# Spec: Interfaz web para ejecutar una ruta (Fase 4)

## Qué hay que construir
Una interfaz web (Fase 4, `codigo/fase4_frontend/`) con la que una persona sin línea de comandos ejecuta **una ruta GO** de principio a fin y entiende el resultado. Tiene tres piezas (componentes 17, 18 y 19 de [`ARCHITECTURE.md`](../ARCHITECTURE.md)), y se reparte además como programa de Windows con instalador (componente 20; ver «Programa de escritorio» y el [ADR-006](../decisions/adr-006-programa-de-escritorio.md)):

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
| La tabla de log2FC de `codigo/estudio.json` (opcional; en CIMUS, `codigo/tools_cimus/NK_cells_DESeq2_results.xlsx`) | Tabla de log2FC que usa la Fase 3 si existe, como en la línea de comandos. |
| `codigo/estudio.json` (#51), vía `GET /estudio` | Tipo celular y tejido del estudio: la cabecera («Células NK · Laringe y faringe (HNSC)»), los textos «en células NK» y la explicación del peso (qué tipos celulares pesan entero) los toman de aquí. Sin respuesta del puente, se muestra el estudio de CIMUS. |

* No hay nada precargado. Vale con uno de los dos Excels o con los dos, y hay uno por lista a la vez: **Cambiar** sustituye el de esa lista y **Quitar** lo elimina.
* Si falta alguna de las tres columnas, la interfaz lo dice y no carga el fichero.
* Una ruta que está en los dos Excels se ejecuta **con todos sus genes**: los de la lista sobreexpresada como *up* y los de la infraexpresada como *down*, igual que la Fase 3 junta las dos listas en un solo término GO.

### Paso 1 · Elegir y lanzar la ruta
* La persona busca la ruta por GO_ID, nombre o gen, la marca (se ven sus genes sobreexpresados e infraexpresados) y pulsa **Ejecutar GO:…**. Hay un paso de confirmación antes de lanzar nada, porque la ejecución en frío consume cupo del LLM.
* **Versión 2, congelada** (#52): debajo de los Excels hay una franja «Versión 2» con un selector de **tipo celular** (las células de `estudio.CELULAS_DISPONIBLES`: NK, T, T CD4+, T CD8+, T reguladoras, B, macrófagos, monocitos, dendríticas, neutrófilos, mastocitos, tumorales, epiteliales, fibroblastos y endoteliales, cada una con su término de Cell Ontology) y un botón para **subir una tabla de log2FC** (`Gen` y `log2FC`, o la de DESeq2 tal cual). En esta versión se ven desactivados, con un candado, y la ejecución usa el estudio de `codigo/estudio.json`. Se activan con `VERSION_2 = true` en `src/estudio.ts`. El puente ya los admite: `POST /ejecutar-ruta` acepta `Celula` (un CL de la lista) y `Log2FC` (`{gen: valor}`), que valen solo para esa ruta. Los guarda en su carpeta (`estudio_ruta.json` y `log2fc.csv`) para que «Tu criterio» use los mismos, y rechaza con 400 una célula que no está en la lista o un log2FC cuyo signo contradice la lista del gen. El prompt y la Fase 2 no cambian: la célula solo cambia qué anotaciones de GO son de otra célula (Fase 1) y qué artículos pesan entero (Fase 3).
* La interfaz consulta `GET /salud` cada 5 s y muestra **● Motor Python conectado** cuando el puente responde. Sin puente, no deja ejecutar y dice cómo arrancarlo.

### Paso 2 · Puente con las fases
| Petición | Qué hace | Respuesta |
|---|---|---|
| `GET /salud` | Comprueba que el puente está vivo. | `{"ok": true}` |
| `POST /ejecutar-ruta` con `{"GO_ID", "Descripcion", "Genes_up", "Genes_down"}` | Valida la petición y lanza las tres fases en un hilo. | `202` si arranca; `400` si el GO_ID no tiene la forma `GO:` + 7 cifras, si la ruta no tiene genes o si el JSON está mal formado; `409` si ya hay una ruta en marcha. |
| `GET /estado` | Fase en curso (1, 2 o 3) y, al terminar, el resultado o el error. | `estado` ∈ {`libre`, `ejecutando`, `terminado`, `error`}. |
| `POST /criterio` con `{"GO_ID", "criterio": {gen: signo}}` (`+1`, `-1` o `neutro`) | Recalcula la Fase 3 de una ruta ya ejecutada con los signos de «Tu criterio», sin llamar al LLM (ver Paso 4). | `200` con `rutas`, `pares` y el Excel; `400` si el GO_ID o un signo no son válidos o el JSON está mal formado; `409` si esa ruta se está ejecutando; `500` si no están las salidas de la ruta. |
| `GET /claves` | Las claves del LLM de cada proveedor (Gemini, principal; Groq, respaldo), en el orden en que se usan y enmascaradas (cuatro primeras y cuatro últimas letras). | `proveedores`: `id`, `modelo`, `papel`, `variable`, `claves` y `de_entorno`. `403` si la petición trae el `Origin` de otra web. |
| `GET /` y el resto de rutas | Si existe `fase4_frontend/dist` (`npm run build`), la interfaz compilada: así el programa de escritorio no necesita Node ni Vite. | El fichero, comprimido con gzip si el navegador lo acepta; `404` si no existe o queda fuera de `dist/`. |
| `POST /claves` con `{"proveedor", "accion": "anadir", "clave"}` o `{"proveedor", "accion": "quitar", "indice"}` | Añade una clave al final de las de su proveedor o quita una, y lo guarda en `codigo/.env` (ver Paso 6). | `200` con `proveedores` y `ejecutando`; `400` si el proveedor, la acción o la clave no valen (repetida, con espacios, de otro proveedor), o si la variable está en el entorno del sistema; `403` si trae el `Origin` de otra web. |

* **Fase 1:** escribe dos Excels de entrada reducidos a la ruta (una fila cada uno, o ninguna si la lista no tiene genes) y ejecuta la Fase 1 sobre ellos. Redirige sus rutas de entrada y de salida desde fuera, igual que `tests/test_fase1_e2e.py`, **sin tocar `fase1_ingesta/`**. Si la Fase 1 no encuentra ninguna evidencia, la ejecución acaba en `error` con ese mensaje.
* **Fase 2:** Gemini como principal y gpt-oss solo como respaldo ([ADR-005](../decisions/adr-005-eleccion-modelo-coste-cero.md)), con el registro de siempre (`codigo/data/respuestas_llm.jsonl`): lo ya preguntado no se vuelve a pedir. Si ningún par llega al LLM, escribe un `fase2_resultados.xlsx` con las hojas vacías para que la Fase 3 funcione igual.
* **Fase 3:** con la tabla de log2FC de CIMUS si existe.
* **Resultado:** las filas de `Por_ruta` y `Por_par` de la Fase 3, el Excel de la Fase 3 (en base64, para descargarlo), los tiempos de cada fase, el uso del LLM (llamadas, reutilizadas, pendientes —preguntas sin ninguna respuesta—, tokens y, en `agotados`, qué proveedor dejó de responder y por qué: `cupo`, `clave`, `sin_clave` o `fallo`) y, por gen, el detalle que explica el signo:
  * los artículos que leyó el LLM, uno por PMID, con su título, signo, estado, motivos, `Confianza_final`, la frase citada y lo que contestó el modelo (efecto, confianza y tipo de evidencia), aunque el código lo dejara en `UNKNOWN`;
  * las respuestas de cada artículo, una por subproceso de la ruta, con su organismo, tipo celular, el peso que les da la Fase 3 (`casos_con_peso` de `fase3_scoring/nps.py`) y `Factor_GO` (`FACTOR_FUENTE_GO` si el artículo lo cita la anotación de GO; si no, vacío). El artículo vota una sola vez por gen (#41): `Cuenta` marca la respuesta que vale (la de más peso) y `Se_contradice`, que no vota porque sus respuestas se contradicen; la interfaz lo dice con palabras;
  * si el signo sale de Gene Ontology, sus códigos de evidencia y PMIDs.
* La interfaz consulta `/estado` cada 1,5 s. Mientras dura la ejecución muestra una rueda de carga animada, la fase en curso, una barra con el porcentaje y un contador de tiempo (total y de la fase), además de las tres fases con su estado (`src/Progreso.tsx`). El porcentaje es **estimado**: el puente solo informa de la fase, así que cada fase tiene su tramo de la barra (Fase 1 hasta el 40 %, Fase 2 hasta el 92 %, Fase 3 hasta el 99 %) y, dentro de él, avanza cada vez más despacio sin llegar al final; salta al tramo siguiente cuando el puente cambia de fase y marca 100 % solo al terminar, con el tiempo total que midió el puente.

### Paso 3 · Resultado en lenguaje llano
Sin códigos internos a la vista (`+1:15811952(0.36)`, `evidencia_debil`…): todo se explica con palabras.

* **Veredicto:** si la ruta está activada, inhibida, mixta o sin evidencia suficiente; la escala del NPS de −1 a +1 con sus tres zonas (±`UMBRAL_NPS`); cuántos genes la sostienen, con evidencia directa de GO o por artículos, y cuántos tienen evidencia débil (peso a su favor < `MIN_PESO_EVIDENCIA`, 0,7); cuántos genes tendrían que dejar de contar para que perdiera la lectura, y los genes repartidos en «empujan hacia activada», «empujan hacia inhibida» y «no cuentan».
* **Una tarjeta por fase**, con los mismos tres niveles de texto (título, resultado y notas):
  * Fase 1: genes, inmunoglobulinas, signos de GO, genes con artículos, artículos y genes sin ninguno;
  * Fase 2: artículos leídos, los que no mencionan el gen, los que dan signo y los que quedan sin conclusión;
  * Fase 3: la lectura con la cuenta del NPS y el NPS pesado por log2FC.
* **Una fila por gen:** si está sobreexpresado o infraexpresado en NK, qué hace en el proceso, hacia dónde empuja la ruta, de dónde sale el signo (Gene Ontology, N artículos, inmunoglobulina o criterio experto) y por qué. Al abrirla:
  * cada artículo con el título enlazado a PubMed, su conclusión, su confianza y la frase citada;
  * el peso de la evidencia con una barra y la cuenta de cada voto (p. ej. 0,36 = confianza 73 % × 0,5 por ser en ratón, o 1,20 = confianza 80 % × 1,5 por citarlo la anotación de GO);
  * en los artículos sin conclusión, el tipo de evidencia y hacia dónde se inclinaba el LLM.
* **Descargar Excel de la Fase 3:** el resultado automático o, si hay cambios en «Tu criterio», el que los lleva (Paso 4).
* Si quedaron preguntas `pendiente`, un aviso lo dice con el motivo de cada proveedor y un botón **Añadir token** que abre ⚙ → token-api (Paso 6). Si es porque no queda ninguna clave con cupo, el aviso dice que se ha acabado el límite diario de llamadas al LLM: que añada el token de otra cuenta o espere al día siguiente. Si Gemini dejó de responder pero respondió Groq, el aviso solo lo menciona.

### Paso 4 · Criterio de la persona experta («Tu criterio»)
* A la derecha de la tabla de genes, un desplegable por gen: **Automático**, **Activa**, **Inhibe** o **No lo cambia**.
* Elegir uno fija el signo del gen (`+1`, `−1` o `neutro`) como `resuelto` con origen `Experto`, y la contribución vuelve a ser signo × dirección.
* El veredicto, la tarjeta de la Fase 3 y la tabla se recalculan al momento con **las mismas reglas que `fase3_scoring/nps.py`** (`tabla_rutas` y `_lectura`): NPS, `NPS_log2FC`, `Lectura`, `Lectura_log2FC`, `Sensible_al_peso`, `Cobertura` y recuentos. Los umbrales son los de `fase3_scoring/config.py` (`UMBRAL_NPS` 0,33, `MIN_PARES_CON_SIGNO` 3 y `MIN_COBERTURA` 0,30), copiados en `App.tsx`.
* Un aviso compara la lectura automática con la que lleva los cambios, y **Deshacer mis cambios** los quita.
* Los cambios **pasan a los dos Excels**. Con cada cambio, la interfaz llama a `POST /criterio` y el puente recalcula la Fase 3 de la ruta con `fase3_scoring.nps.calcular(..., criterio=...)` (`aplicar_criterio`), a partir de las salidas de las Fases 1 y 2 de su carpeta y sin llamar al LLM:
  * el **Excel de la Fase 3** que se descarga es `fase3_scoring_criterio.xlsx`, con las cuatro hojas recalculadas y, al lado, el resultado automático: en `Por_ruta`, `Lectura_automatica`, `NPS_automatico` y `Cambios_experto` (p. ej. `IRF4: UNKNOWN → -1`); en `Por_par`, `Signo_automatico`. `fase3_scoring.xlsx` sigue siendo el automático;
  * en el **Excel de resultados**, la fila de la ruta y sus genes se sustituyen por los recalculados, con las mismas columnas del resultado automático (Paso 5).
* Los genes cambiados quedan con `Origen` = `Experto` y `Motivos` = `criterio_experto`. **Deshacer mis cambios** devuelve los dos Excels al resultado automático, y una nueva ejecución de la ruta también.

### Paso 5 · Excel de resultados
Para juntar varias rutas en un mismo Excel sin copiarlas a mano.

* **Abrir Excel** pone uno vacío o uno con rutas ya buscadas, y **Crear Excel nuevo** empieza uno (`resultados_rutas.xlsx`). Si ya se había ejecutado una ruta, se añade en ese momento.
* Cada ruta ejecutada se añade sola, con el resultado automático o, si hay cambios en «Tu criterio», con el que los lleva:

  | Hoja | Una fila por | Columnas |
  |---|---|---|
  | `Rutas` | ruta ejecutada | `Fecha`, `GO_ID`, `Ruta_Nombre`, `Listas`, `Lectura`, `NPS`, `Lectura_automatica`, `NPS_automatico`, `Cambios_experto`, `NPS_log2FC`, `Lectura_log2FC`, `Sensible_al_peso`, `n_total`, `n_activan`, `n_inhiben`, `n_neutros`, `n_no_concluyente`, `n_sin_evidencia`, `n_pendiente`, `Cobertura`, `Genes_activan`, `Genes_inhiben` (las de `Por_ruta` de la Fase 3, más la fecha). Sin cambios a mano, `Lectura_automatica` y `NPS_automatico` repiten `Lectura` y `NPS`, y `Cambios_experto` queda vacía. |
  | `Genes` | par (gen, ruta) de las rutas ejecutadas | `GO_ID`, `Ruta_Nombre`, `Gen`, `Direccion`, `Log2FC`, `Signo_par`, `Signo_automatico`, `Estado_par`, `Origen`, `Contribucion`, `Motivos`, `Votos`, `PMIDs_consultados` (las de `Por_par`). |

* Si la ruta ya estaba, sus filas se **sustituyen**, no se duplican. Las demás hojas del libro se conservan tal cual.
* Un Excel cuya hoja `Rutas` no tiene la columna `GO_ID` se rechaza, porque no es un Excel de resultados.
* En Chrome y Edge (API de acceso a ficheros) los cambios se escriben en el fichero elegido; en los demás navegadores, con **Descargar**.
* **Limpiar Excel** (con confirmación) borra todas sus rutas, **Quitar** deja de usarlo sin borrarlo y la papelera de una fila quita solo esa ruta.
* La vista previa muestra cada ruta con su lectura, una barra del NPS, los genes que activan e inhiben y la fecha; al abrirla, sus genes en colores (verde: empuja hacia activada; rojo: hacia inhibida; gris: no cuenta).

### Paso 6 · Claves del LLM (⚙ → token-api)
* Arriba a la derecha, una rueda abre un mini-menú con la opción **token-api**. Abre un panel con las claves de **Gemini** (principal) y de **Groq** (respaldo), cada una con sus claves numeradas en el orden en que se usan.
* Se pega una clave en el campo de su proveedor (de tipo contraseña) y **Añadir** la pone al final; el icono de papelera, con una segunda confirmación, la quita. Cada cambio se guarda al momento en `codigo/.env` (`GEMINI_API_KEY=clave1,clave2`) y vale desde la siguiente ejecución. El panel solo muestra las cuatro primeras y las cuatro últimas letras.
* **Rotación** (`fase2_inferencia/cliente.py`, también en la línea de comandos): Si una clave se queda sin cupo (un `429` del límite diario, o un `429` que sigue tras los reintentos), se pasa a la siguiente del **mismo proveedor**; es el único fallo que cambia de clave. Una clave no válida, un `5xx` o la red, o quedarse sin cupo en todas las claves, hacen que el modelo deje de llamarse en esa ejecución y responda el respaldo (Groq), que también usa sus claves en orden. Sin ninguna clave con cupo, las preguntas quedan `pendiente`.
* Si la variable está en las variables de entorno del sistema, que mandan sobre `codigo/.env`, el panel lo dice y no deja cambiarla.

### Programa de escritorio (`codigo/empaquetado/`, [ADR-006](../decisions/adr-006-programa-de-escritorio.md))
* **Construir:** desde `codigo/`, `python empaquetado/construir.py` (necesita Node.js y `pip install pyinstaller`). Deja en `codigo/empaquetado/salida/` (no se versiona) la carpeta del programa y `Instalar PathwayPulse.exe`. Con `--sin-datos-cimus` no lleva la tabla de log2FC de CIMUS, que no es pública.
* **Instalar:** el asistente instala solo para el usuario en `%LOCALAPPDATA%\Programs\PathwayPulse`, sin permisos de administrador; crea los accesos directos del escritorio (opcional) y del menú Inicio y lo registra en «Aplicaciones instaladas». Si ya estaba, lo actualiza conservando `codigo/data` y `codigo/.env`, y si está abierto ofrece cerrarlo. Intro pulsa el botón principal y Esc cancela.
* **Abrir:** el doble clic enseña una pantalla de carga mientras arranca el puente, que también sirve la interfaz compilada, en `127.0.0.1:47613`, y la abre en una ventana de Edge en modo aplicación, con su propio botón en la barra de tareas. Al cerrar la ventana se apaga todo. Un segundo doble clic con el programa abierto abre otra ventana.
* **Desinstalar:** desde «Aplicaciones instaladas» o con `Desinstalar.exe`, borra la carpeta (con las claves y las cachés), los accesos directos y el registro. Solo borra una carpeta llamada `PathwayPulse` que tenga el programa.
* **Datos:** lleva las cachés de la Fase 1 y el registro de respuestas del LLM, pero nunca `codigo/.env`.

### Salida
| Dónde | Qué |
|---|---|
| `codigo/data/frontend/<GO_ID>/` (no se versiona) | `entrada_activadas.xlsx` y `entrada_suprimidas.xlsx` (reducidos a la ruta), `fase1_dataset_abstracts.xlsx`, `fase2_resultados.xlsx` y `fase3_scoring.xlsx` de esa ruta. |
| Navegador | `fase3_scoring_<GO_ID>.xlsx` al pulsar **Descargar Excel de la Fase 3**. |
| Fichero elegido por la persona | El Excel de resultados, con las hojas `Rutas` y `Genes`. Los diálogos de abrir y guardar empiezan en Descargas, no en Documentos, que puede estar dentro de OneDrive. |

## Por qué
* **El usuario final es una persona de CIMUS, no un programador.** La línea de comandos y un Excel de cuatro hojas con códigos como `+1:15811952(0.36)` no se entienden sin conocer el pipeline. La interfaz dice si la ruta está activada o inhibida y por qué, gen a gen, con los artículos y la frase que lo sostienen.
* **Una ruta cada vez:** es la pregunta real de CIMUS («¿esta ruta está activada o inhibida?») y el alcance del proyecto. Con las cachés y el registro hechos tarda entre 9 y 20 s y en frío unos 2–3 minutos ([`docs/kpis.md`](../docs/kpis.md)); el Excel entero en frío consume horas y cupo del LLM, y se ejecuta por la línea de comandos.
* **Las tres fases seguidas y sin fases sueltas:** el resultado solo tiene sentido completo, y así nadie puede mezclar la Fase 3 de una ruta con la Fase 2 de otra.
* **Puente propio sobre `http.server`, sin servidor web nuevo:** solo escucha en `127.0.0.1`, solo hace tres cosas y no añade dependencias a `requirements.txt`. Llama a las funciones de las fases y redirige sus rutas de entrada y salida, así que la Fase 4 no duplica lógica ni cambia el comportamiento de la línea de comandos.
* **Un hilo y consulta del estado:** la ejecución en frío dura minutos, más que el tiempo de espera normal de una petición HTTP. Lanzarla en un hilo y consultar `/estado` deja ver la fase en curso.
* **Carpeta propia por ruta y registro compartido** ([ADR-004](../decisions/adr-004-persistencia-ficheros-locales.md)): no pisa las salidas del Excel completo, y una ruta ya consultada no vuelve a gastar llamadas al LLM.
* **«Tu criterio» pasa a los Excels, junto al automático:** el experto tiene que poder ver qué pasaría si un gen tuviera otro signo, porque muchos genes de NK tienen funciones duales, y quedarse con ese resultado en sus Excels. Para que no se confunda un signo fijado a mano con uno inferido, el gen cambiado lleva `Origen` = `Experto`, y cada Excel guarda al lado el resultado automático (`Lectura_automatica`, `NPS_automatico`, `Cambios_experto` y `Signo_automatico`). El automático de la Fase 3 sigue en `fase3_scoring.xlsx`, reproducible y trazable a sus artículos.
* **Los Excels con «Tu criterio» los recalcula `fase3_scoring`, no la interfaz:** la copia de las reglas en `App.tsx` solo recalcula la lectura y el NPS para la pantalla. Las hojas completas (recuentos, `Genes_activan`, `Resumen`…) salen de la Fase 3 real, que tarda menos de un segundo con una ruta.
* **Claves en la interfaz y varias por proveedor:** el cupo gratuito diario de una cuenta se acaba con unas pocas rutas en frío. Con varias claves, la persona de CIMUS puede seguir con la clave de otra cuenta sin editar `codigo/.env` a mano. Solo el cupo cambia de clave: un fallo de otro tipo no lo arregla otra clave del mismo proveedor, así que pasa al respaldo, como hasta ahora.
* **Excel de resultados en el navegador:** CIMUS ya trabaja con Excel. Acumular las rutas en un fichero que elige la persona evita una base de datos (ADR-004) y que tenga que copiar resultados a mano entre ejecuciones.

**Alternativas descartadas:**
* **Streamlit o Gradio:** dan una interfaz rápida, pero con poco control del diseño del veredicto, la tabla gen a gen y el desplegable por gen, y ejecutan la lógica en cada interacción.
* **FastAPI o Flask para el puente:** añaden dependencias para tres rutas que la librería estándar ya cubre.
* **Llamar a las fases desde el navegador o reescribirlas en TypeScript:** duplicaría la lógica de las Fases 1–3 y dejaría dos versiones que mantener. Solo se copian en `App.tsx` las reglas de lectura del NPS, que son cortas, para recalcular «Tu criterio» al momento.
* **Recalcular los Excels de «Tu criterio» en el navegador:** obligaría a copiar en TypeScript toda la Fase 3 (recuentos, `Resumen`), no solo la regla de lectura.
* **Guardar las claves en el navegador (`localStorage`) y enviarlas con cada ejecución:** las dejaría al alcance de cualquier script de la página y no valdrían para la línea de comandos. Tampoco un fichero aparte: las claves viven solo en `codigo/.env`.
* **Probar cada clave al añadirla con una llamada al modelo:** gastaría cupo y tarda; una clave no válida se detecta en la primera llamada y pasa al respaldo.

## Restricciones
* **No modifica las fases:** no cambia `fase1_ingesta/` ni la lógica de `fase2_inferencia/`; solo redirige sus rutas de entrada y salida. De `fase3_scoring/` usa el parámetro opcional `criterio` de `calcular`, que la línea de comandos no usa, así que su resultado no cambia. La rotación de claves vive en `fase2_inferencia/cliente.py` y vale igual en la línea de comandos.
* **Local:** el puente solo escucha en `127.0.0.1:8000` y la interfaz en `localhost:5173`; el programa de escritorio, en `127.0.0.1:47613`. Las claves se guardan solo en `codigo/.env`, que no se versiona. Una clave pasa por el navegador solo al pegarla en ⚙ → token-api, y va directa al puente local; el puente nunca la devuelve entera ni la escribe en el log, y `/claves` rechaza las peticiones con el `Origin` de otra web, para que una página abierta en el navegador no pueda cambiarlas.
* **Una ruta a la vez:** una segunda petición mientras hay otra en marcha recibe `409`.
* **Mismo resultado que la línea de comandos:** con las mismas entradas, cachés y registro, la lectura y el NPS de la ruta coinciden con los de `python -m fase3_scoring`.
* **Mismas reglas en «Tu criterio»:** el recálculo en pantalla sigue `fase3_scoring/nps.py` y `fase3_scoring/config.py`. Si cambian los umbrales o la regla de lectura, hay que cambiarlos también en `App.tsx`.
* **Cupo del LLM agotado o sin claves:** la ejecución termina igual, con las preguntas `pendiente` y el aviso en pantalla. No falla, tampoco sin ninguna clave: una ruta con todo en el registro se ejecuta sin llamar al LLM.
* **SheetJS desde el CDN** (`xlsx@0.18.5`): la interfaz lo carga al leer o escribir un Excel, así que necesita conexión para eso.
* **Comprobación del código:** desde `codigo/fase4_frontend/`, `npx tsc -b`, `npx eslint src` y `npm test` sin errores. La lógica de la interfaz que se puede probar sin navegador vive fuera de React (`src/lectura.ts`, `src/acumulado.ts`) y se prueba con node; `python -m pytest` lo lanza (`tests/test_interfaz.py`).

## Criterios de aceptación
Los que llevan una prueba entre paréntesis la tienen en `codigo/tests/` (o en `codigo/fase4_frontend/pruebas/`, que lanza `tests/test_interfaz.py`); los demás se comprueban a mano en el navegador.

* [x] ✅ **Ruta completa** (a mano, #42): con GO:0072678 y los dos Excels de `codigo/tools_cimus/`, la ejecución pasa por las Fases 1, 2 y 3 y da `activada` con NPS 0,333, igual que la ejecución de referencia, y escribe sus ficheros en `codigo/data/frontend/GO_0072678/`.
* [x] ✅ **Sin nada precargado** (a mano, #42): la interfaz arranca sin rutas; acepta un Excel por lista, **Cambiar** lo sustituye y **Quitar** lo elimina.
* [x] ✅ **Peticiones no válidas** (a mano con `curl`, 14/11): un GO_ID sin la forma `GO:` + 7 cifras, una ruta sin genes o un JSON mal formado reciben `400`, y una segunda ruta mientras GO:0072678 está en marcha, `409`. Esa ejecución, con las cachés y el registro hechos, da `activada` y NPS 0,333 sin ninguna llamada al LLM (12 respuestas reutilizadas).
* [x] ✅ **Resultado en lenguaje llano** (a mano, #43): veredicto, tarjetas por fase y tabla de genes sin códigos internos; el peso de cada voto con su cuenta, y en CX3CR1 el tipo de evidencia y la inclinación del LLM («activa», 60 %, pero solo correlación).
* [x] ✅ **Tu criterio** (a mano, #44): en GO:0072678, GPR183 en «No lo cambia» da `mixta` y NPS 0,25; **Deshacer mis cambios** vuelve a `activada` y 0,333.
* [x] ✅ **Tu criterio en los Excels** (a mano con un fichero simulado, 22/11): en GO:0001773, IRF4 en «Inhibe el proceso» da `activada` y NPS 0,333 en pantalla, en `fase3_scoring_criterio.xlsx` y en la fila del Excel de resultados, que se reescribe al momento con `insuficiente` y 1,00 como resultado automático y `Cambios_experto` = `IRF4: UNKNOWN → -1`; **Deshacer mis cambios** devuelve el Excel de resultados al automático. `fase3_scoring.xlsx` no cambia. `test_criterio_experto` (`tests/test_scoring.py`) comprueba el recálculo de la Fase 3.
* [x] ✅ **Excel de resultados** (a mano con un fichero simulado, #45): crear uno, añadir dos rutas, repetir una sin duplicarla, abrir uno incompleto y completarlo, y limpiarlo.
* [x] ✅ **Excel de resultados con el diálogo real** (a mano en Chrome, 23/11, #39): las mismas operaciones con el diálogo de ficheros de Chrome y con **Descargar** en otro navegador.
* [x] ✅ **Fondo blanco** (a mano, #46): el botón de la cabecera cambia de tema, los textos se leen sobre blanco y el navegador recuerda la elección.
* [x] ✅ **Claves del LLM** (`tests/test_puente_claves.py`): añadir dos claves de Gemini las guarda en `codigo/.env` en ese orden (`GEMINI_API_KEY=clave1,clave2`) sin tocar las demás líneas, y quitar la primera deja la segunda; ninguna respuesta lleva una clave entera (`AIza…xxxx`). Una clave corta, con comas, repetida o de otro proveedor, un índice que no existe o una acción desconocida dan `400` sin cambiar el fichero, y una variable del entorno del sistema no se puede cambiar. Por HTTP, con el `Origin` de otra web, `403` y sin cambios; desde `localhost:5173`, `200`. El aviso cuenta como pendientes solo las preguntas sin ninguna respuesta y pasa el motivo de cada proveedor (`test_aviso_de_la_fase2`).
* [x] ✅ **Rotación de claves** (`tests/test_cliente.py`): con dos claves de Gemini, un `429` del límite diario pasa a la segunda sin reintentar y las siguientes llamadas siguen con ella; un `429` que sigue tras los reintentos también; sin cupo en todas, `ErrorTransitorio` con motivo `cupo` y responde Groq (`test_sin_cupo_en_todas_las_claves_de_gemini_responde_groq`). Una clave no válida (`400` «API key not valid» o `403`), un `5xx` o la red no cambian de clave. Sin ninguna clave, el cliente falla al llamar con `sin_clave`, no al crearse.
* [x] ✅ **Progreso en el navegador** (a mano en Chrome, 23/11): con GO:0072678 (cachés y registro hechos, sin llamadas al LLM), la rueda gira durante toda la ejecución, el porcentaje no retrocede nunca, la barra sube dentro de la Fase 1 (hasta un 33 % a los 24 s), salta al 40 % al empezar la Fase 2 y al 92 % en la Fase 3, el contador corre segundo a segundo y al terminar marca 100 % en verde con el tiempo total (00:26) y el de cada fase. No se probó en frío de verdad: todas las rutas de CIMUS están ya en las cachés y el registro.
* [x] ✅ **Panel token-api en el navegador** (a mano en Chrome, 23/11): la rueda abre el menú y token-api el panel, con las claves numeradas y enmascaradas; una clave de prueba se añade como «2.», una clave de Groq pegada en Gemini se rechaza con «Parece una clave de Groq», y la papelera, tras «Sí, quitarla», la quita. Después, `codigo/.env` queda idéntico byte a byte (también sus saltos de línea). El aviso del límite diario con **Añadir token** no se vio en pantalla (haría falta agotar el cupo de verdad): lo cubren `test_aviso_de_la_fase2` y `test_sin_cupo_en_todas_las_claves_de_gemini_responde_groq`.
* [x] ✅ **Código** (25/11): `npx tsc -b`, `npx eslint src` y `npm test` (15 pruebas) sin errores, y `python -m pytest` en verde (215 pruebas).
* [x] ✅ **Interfaz compilada servida por el puente** (`tests/test_puente_web.py`): `/` da `index.html` y el JS sale como `text/javascript`, sin `charset`, comprimido con gzip si el navegador lo acepta; nada fuera de `dist/` (`..`, `%2e%2e`) ni con otra extensión; sin `dist/`, `404`. Solo lo de `assets/` se guarda en caché para siempre. Las rutas de la API siguen igual.
* [x] ✅ **Programa de escritorio** (a mano, 23/11): el `.exe` empaquetado ejecuta GO:0072678 por las Fases 1, 2 y 3 y da `activada` con NPS 0,333 en 13 s (12 respuestas reutilizadas). La ventana carga la interfaz aunque el JS se corte (en el registro, tres intentos), tiene su botón «PathwayPulse» en la barra de tareas con el icono nítido y, al cerrarla, el programa se apaga.
* [x] ✅ **Instalador** (a mano, 23/11): instalar crea la carpeta, los dos accesos directos y la entrada de «Aplicaciones instaladas»; actualizar con el programa abierto lo cierra y conserva `codigo/data`; «Abrir ahora» lo abre; desinstalar borra carpeta, accesos y registro, y la copia temporal del desinstalador se borra sola.
* [x] ✅ **Puente por HTTP** (`tests/test_puente_ejecucion.py`, #40), con las fases simuladas: una ruta va de `libre` a `ejecutando` y `terminado` con el resultado (Excel de la Fase 3 en base64, tiempos, resumen del LLM y la carpeta `GO_xxxxxxx`); una segunda ruta, o «Tu criterio» de la que está en marcha, recibe `409`; un fallo en una fase queda en `/estado` como `error` con la fase y el mensaje; un GO_ID mal formado, una ruta sin genes o un JSON roto dan `400` sin lanzar nada; una ruta que no existe, `404` (también por POST). `POST /criterio` recalcula de verdad la Fase 3 de una ruta sintética (`inhibida`, NPS −0,333, con el automático y `Cambios_experto` al lado, y su Excel), y un signo no válido, un GO_ID mal formado o una ruta sin salidas dan `400` o `500`.
* [x] ✅ **Versión 2 congelada** (`tests/test_puente_ejecucion.py` y `pruebas/estudio.test.ts`, #52): `GET /estudio` da las 15 células; con `Celula` = `CL:0001064` y una tabla de log2FC, las Fases 1 y 3 ven la célula tumoral durante la ejecución y al acabar vuelve la del estudio; la siguiente ejecución sin ellas borra `estudio_ruta.json` y `log2fc.csv`; «Tu criterio» usa la célula y la tabla de la ruta (un artículo en NK pesa 0,5 con la célula tumoral); una célula fuera de la lista o un log2FC que contradice la lista dan 400. Con `VERSION_2 = false`, la ejecución no lleva ni célula ni log2FC. A mano (25/11), GO:0072678 con la célula tumoral y el log2FC de CIMUS: misma lectura (activada, NPS 0,333), 7 genes con evidencia débil en vez de 5, NPS_log2FC 0,385 y 0 llamadas al LLM.
* [x] ✅ **Estudio configurable** (`pruebas/estudio.test.ts` y `tests/test_estudio.py`, #51): la cabecera sale de `GET /estudio` («Células T · Pulmón» con un estudio de células T); un artículo pesa la mitad si su tipo celular es de otra clase que la del estudio, y sin respuesta del puente se muestra el estudio de CIMUS.
* [x] ✅ **«Tu criterio» en pantalla = Fase 3** (`tests/test_interfaz.py`, #40): para cada gen y cada signo, y para combinaciones de varios genes, `src/lectura.ts` da el mismo NPS, lectura, NPS por log2FC, `Sensible_al_peso`, cobertura y recuentos que `fase3_scoring/nps.py`, en una ruta sintética con y sin log2FC y en las rutas reales ya ejecutadas en `codigo/data/frontend/`. La comparación encontró que la pantalla redondeaba 0,5625 a 0,563 y la Fase 3 a 0,562; ahora redondea igual.
* [x] ✅ **Excel de resultados** (`pruebas/acumulado.test.ts`, #40): añadir dos rutas da una fila por ruta y sus genes, con las columnas exactas del Excel y el automático igual al guardado; repetir una ruta la sustituye sin duplicarla, con los cambios del experto; quitar una ruta y vaciar el Excel.
