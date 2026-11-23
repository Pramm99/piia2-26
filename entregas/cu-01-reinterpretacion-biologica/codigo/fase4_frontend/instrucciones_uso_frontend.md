# Instrucciones de uso · Fase 4 (frontend)

Interfaz web para ejecutar **una ruta** de principio a fin: se suben los Excels de rutas, se elige la ruta, se confirma
y se ejecutan seguidas las Fases 1, 2 y 3. Al terminar muestra el veredicto de la ruta (NPS), cómo se llegó a él y la
aportación de cada gen; una persona experta puede corregir el signo de un gen en pantalla, y el «Excel de resultados»
va acumulando las rutas ejecutadas. No se pueden lanzar las fases por separado: para eso está la línea de comandos
(`AGENTS.md`).

## 0. Programa de escritorio (sin instalar nada más)

Para quien no use la terminal: **`Instalar CU-01 PathScore Studio.exe`** instala el programa con un asistente, sin
permisos de administrador, y deja un acceso directo en el escritorio y en el menú Inicio. No hace falta Python ni Node.
Al abrirlo sale una pantalla de carga y luego la aplicación en su propia ventana; al cerrarla se apaga todo. Las claves
se añaden en ⚙ → token-api, y se desinstala desde «Aplicaciones instaladas» de Windows. Como el instalador no está
firmado, Windows puede avisar al abrirlo: «Más información» → «Ejecutar de todas formas».

Para construirlo, desde `codigo/` (necesita Node.js y `pip install pyinstaller`):

```bash
python empaquetado/construir.py      # deja empaquetado/salida/Instalar CU-01 PathScore Studio.exe
python empaquetado/iconos.py         # solo si cambia empaquetado/icono.svg (necesita Pillow)
```

Lleva las cachés y el registro de respuestas del LLM, pero nunca `codigo/.env`. Incluye la tabla de log2FC de CIMUS,
que no es pública: para repartirlo fuera del equipo, `--sin-datos-cimus`. Cómo está hecho y por qué: ADR-006.

## 1. Requisitos

1. **Python** con las dependencias de `codigo/requirements.txt` (el entorno `codigo/pia_venv/` sirve).
2. **Node.js y npm**, para la interfaz (React + Vite).
3. **Claves** en `codigo/.env` (copia de `codigo/.env.example`): `GEMINI_API_KEY`, `GROQ_API_KEY` y `NCBI_EMAIL`.
   El `.env` está en el `.gitignore` y nunca se sube a GitHub. Las de Gemini y Groq también se pueden pegar desde la
   interfaz (⚙ → token-api, ver «Claves del LLM»).

Dependencias de la interfaz, una sola vez, desde `codigo/fase4_frontend/`:

```bash
npm install
```

## 2. Arranque

Hacen falta dos terminales.

**Puente con las fases** (desde `codigo/`):

```bash
python fase4_frontend/api_puente.py
```

Escucha en `http://127.0.0.1:8000`.

**Interfaz** (desde `codigo/fase4_frontend/`):

```bash
npm run dev
```

Se abre en `http://localhost:5173/`. Arriba aparece **● Motor Python conectado** cuando el puente responde. El botón
**Fondo blanco / Fondo oscuro** de la cabecera cambia el tema, y el navegador lo recuerda para la próxima vez.

**Claves del LLM.** La rueda ⚙ de arriba a la derecha abre un mini-menú; en **token-api** se pegan las claves de
**Gemini** (el modelo principal) y de **Groq** (el respaldo), varias de cada una si se tienen de varias cuentas:
pega la clave en el campo de su proveedor y pulsa **Añadir**; la papelera la quita. Se usan en el orden de la lista:

* si una clave de Gemini se queda sin su cupo diario, se pasa a la siguiente clave de Gemini;
* si Gemini falla por otro motivo (clave no válida, servicio o red caídos) o se acaban todas sus claves, responde
  Groq, que también usa sus claves en orden;
* si no queda ninguna clave con cupo, la ruta termina con las preguntas pendientes y un aviso: se ha acabado el
  límite diario de llamadas al LLM, así que añade el token de otra cuenta (botón **Añadir token**) o espera al día
  siguiente, y vuelve a ejecutar la ruta.

Se guardan en `codigo/.env` y valen desde la siguiente ejecución; el panel solo enseña sus primeras y últimas letras.

## 3. Uso

1. Sube los Excels de rutas (columnas `ID`, `Description` y `geneID`). No hay nada precargado. Hay un hueco para el
   de **rutas sobreexpresadas (upregulated)** y otro para el de **rutas infraexpresadas (downregulated)**; vale con
   uno o con los dos. Solo hay un Excel por lista a la vez: **Cambiar** sube otro en su lugar (el anterior se olvida)
   y **Quitar** lo elimina. Los de CIMUS están en `codigo/tools_cimus/` (`NK_rutas_activadas_GO.xlsx` y
   `NK_rutas_suprimidas_GO.xlsx`).
2. Busca la ruta por GO_ID, nombre o gen y márcala. Se ve con sus genes sobreexpresados e infraexpresados: una ruta
   que está en los dos Excels se ejecuta con todos sus genes.
3. Pulsa **Ejecutar GO:…** y confirma. Mientras se ejecuta, una rueda de carga, la fase en curso, una barra con el
   porcentaje y un contador de tiempo muestran cómo va. El porcentaje es aproximado: el puente solo dice en qué fase
   va, y la barra avanza dentro de cada fase hasta que pasa a la siguiente; el 100 % llega al terminar.
4. Al terminar aparece el resultado, explicado en lenguaje llano:
   * arriba, el veredicto: si la ruta está activada, inhibida, mixta o sin evidencia suficiente, la escala del NPS
     con sus tres zonas, cuántos genes la sostienen (con evidencia directa de Gene Ontology o por artículos, y cuántos
     débiles: menos de 1 de peso a su favor; el artículo que cita la anotación de Gene Ontology del gen pesa ×1,5),
     cuántos tendrían que cambiar para perder la lectura y los genes repartidos en «empujan hacia activada»,
     «empujan hacia inhibida» y «no cuentan» (al pulsar uno se abre su detalle);
   * una tarjeta por fase: qué encontró la Fase 1 (genes, signos de Gene Ontology, artículos), qué dicen los
     artículos según el LLM en la Fase 2 y la lectura de la Fase 3 (activada, inhibida, mixta o insuficiente) con la
     cuenta del NPS y el NPS pesado por log2FC;
   * una fila por gen: si está sobreexpresado o infraexpresado en NK, qué hace en el proceso, hacia dónde empuja la ruta, de dónde sale el signo
     y por qué. Al pulsarla se ven sus artículos (título con enlace a PubMed, conclusión, confianza y la frase citada);
   * a la derecha de la tabla de genes, la columna **Tu criterio**: una persona experta puede decir que un gen activa,
     inhibe o no cambia el proceso. La lectura, el NPS, el veredicto y la tarjeta de la Fase 3 se recalculan al momento
     con las mismas reglas que `fase3_scoring/nps.py`, y un aviso compara el resultado automático con el que tiene los
     cambios (**Deshacer mis cambios** los quita). Los cambios pasan al momento a los dos Excels (el de la Fase 3 y
     el de resultados), que guardan también el resultado automático; una nueva ejecución vuelve al automático;
   * el botón **Descargar Excel de la Fase 3**: el resultado automático o, si has cambiado genes, el que lleva tus
     cambios, con el automático al lado (`Lectura_automatica`, `NPS_automatico`, `Cambios_experto` y, por gen,
     `Signo_automatico`).
5. **Excel de resultados.** Para ir juntando varias rutas en un mismo Excel:
   * **Abrir Excel** pone uno vacío o uno con rutas ya buscadas, y **Crear Excel nuevo** empieza uno. Si ya habías
     ejecutado una ruta, se añade en ese momento (así se completa un Excel al que le faltaba).
   * Cada ruta que se ejecuta se añade sola: una fila en la hoja `Rutas` y sus genes en la hoja `Genes`. Si la ruta ya
     estaba, se actualiza. Las demás hojas del Excel no se tocan. Si cambias genes en «Tu criterio», la ruta se
     guarda con tus cambios (marcada con «✎ a mano» en la vista previa) y, al lado, el resultado automático.
   * En Chrome y Edge los cambios se escriben directamente en el fichero elegido; en otros navegadores hay que pulsar
     **Descargar**.
   * **Limpiar Excel** (pide confirmación) borra todas sus rutas para empezar de cero; **Quitar** deja de usarlo sin
     borrarlo, y el icono de papelera de una fila quita solo esa ruta.
   * La vista previa muestra cada ruta con su lectura, una barra del NPS, los genes que activan e inhiben, la fecha y,
     al pulsarla, sus genes en colores (verde: empuja hacia activada; rojo: hacia inhibida; gris: no cuenta).

## 4. Qué hace el puente

* **Fase 1** con los Excels subidos reducidos a la ruta elegida.
* **Fase 2** con Gemini como principal y gpt-oss solo como respaldo (ADR-005). Usa el registro de siempre
  (`codigo/data/respuestas_llm.jsonl`): lo que ya se preguntó no se vuelve a pedir. Si una clave se queda sin cupo, pasa a la
  siguiente; si no queda ninguna, las preguntas quedan `pendiente` y la interfaz lo avisa: basta con añadir otra clave
  o volver a ejecutar la ruta al día siguiente.
* **Claves** (`GET` y `POST /claves`): lista enmascaradas, añade y quita las claves de ⚙ → token-api en
  `codigo/.env`. Solo acepta peticiones desde la propia interfaz (localhost).
* **Fase 3** con la tabla de log2FC de CIMUS si existe.
* **«Tu criterio»** (`POST /criterio`): recalcula la Fase 3 de la ruta con los signos cambiados a mano, sin llamar al
  LLM, y escribe `fase3_scoring_criterio.xlsx` en su carpeta; `fase3_scoring.xlsx` sigue siendo el automático.

Tarda unos segundos con las cachés y unos 2–3 minutos en frío (`docs/kpis.md`). Solo se ejecuta una ruta a la vez.

## 5. Ficheros

| Fichero | Contenido |
|---|---|
| `api_puente.py` | Puente HTTP con las Fases 1 → 2 → 3 (`/salud`, `/ejecutar-ruta`, `/estado`), el recálculo de «Tu criterio» (`/criterio`), las claves del LLM (`/claves`) y, si existe `dist/` (`npm run build`), la interfaz compilada en `/`. |
| `src/App.tsx` | Interfaz: Excels de rutas, elección y ejecución de la ruta, veredicto, tarjetas por fase, tabla de genes y «Tu criterio». |
| `src/ExcelResultados.tsx` | Excel de resultados que acumula las rutas ejecutadas, con su vista previa. |
| `src/TokenApi.tsx` | Rueda ⚙ de la cabecera y panel token-api para añadir y quitar las claves de Gemini y Groq. |
| `src/Progreso.tsx` | Rueda de carga, barra con el porcentaje (estimado por fases) y contador de tiempo de la ejecución. |
| `src/comun.ts` | Utilidades compartidas: carga de SheetJS (desde el CDN, para leer y escribir Excel) y formatos. |
| `src/index.css` | Paletas de colores del tema oscuro y del claro. |
| `src/lectura.ts` | Lectura de la ruta con «Tu criterio», la misma cuenta que `fase3_scoring/nps.py` (sin React, para probarla). |
| `src/acumulado.ts` | Lo que se acumula en el Excel de resultados: añadir, sustituir, quitar y vaciar (sin React ni SheetJS). |
| `pruebas/` | Pruebas con node (`npm test`) y `recalcular.ts`, que usa `tests/test_interfaz.py` para comparar con la Fase 3. |
| `src/Logo.tsx` | Logo de la cabecera: el mismo dibujo que el icono del programa (`codigo/empaquetado/icono.svg`). |
| `vite.config.ts` | Al compilar, el `index.html` carga el JS y el CSS con un tiempo límite y reintentos (las descargas locales se cortaban a veces con un antivirus). |
| `public/` | `favicon.ico` e `iconos/`, generados por `codigo/empaquetado/iconos.py`. |
| `../empaquetado/` | Programa de escritorio e instalador: `lanzador.py`, `instalador.py`, `barra_tareas.py`, `construir.py` e `iconos.py`. |

Para comprobar el código antes de un commit, desde `codigo/fase4_frontend/`: `npx tsc -b`, `npx eslint src` y `npm test`
(pruebas de `pruebas/` con node; `python -m pytest` desde `codigo/` también las lanza).

**Salidas de cada ejecución.** Cada ruta escribe en `codigo/data/frontend/<GO_ID>/` (ignorado por git): los dos Excels de entrada reducidos,
`fase1_dataset_abstracts.xlsx`, `fase2_resultados.xlsx`, `fase3_scoring.xlsx` y, si se cambian genes en «Tu criterio»,
`fase3_scoring_criterio.xlsx`. No pisa las salidas del Excel completo.
Las cachés de la Fase 1 (`codigo/data/`) son compartidas.
