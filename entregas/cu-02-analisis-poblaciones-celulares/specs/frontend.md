# Frontend

## Qué construir

Una aplicación web para explorar resultados de GSEA (enriquecimiento de rutas) en comparaciones de tumor frente a normal, calculadas por separado dentro de cada tipo celular. Permite ver qué rutas se repiten entre tipos celulares, cuáles cambian en sentido opuesto y qué genes las explican. Está pensada para personas de investigación y bioinformática que quieren revisar patrones sin programar.

El frontend se encarga de pedir los datos, dibujarlos y dejar que la persona los revise. No recalcula ningún p valor ni NES. En el borrador todo corre en el navegador y la lógica de backend está simulada con funciones locales; en la app real el backend valida los archivos y calcula patrones, similitudes y genes comunes, y un LLM redacta la interpretación solo a partir de esos resultados.

## Por qué
Hoy los resultados GSEA se revisan a mano, tipo celular a tipo celular. Esta interfaz permite que una persona sin conocimientos de programación vea en una sola pantalla qué rutas se repiten entre tipos celulares, cuáles cambian en sentido opuesto y qué genes las explican, reduciendo el esfuerzo de revisión y el riesgo de pasar por alto patrones.

## Especificaciones de la interfaz

### Estructura general

- **Cabecera**: nombre de la app, subtítulo y una insignia que indica el origen de los datos: sin datos, simulados (demo), subidos por la persona, o reales con solo rutas significativas.
- **Panel lateral de filtros** (columna fija de unos 255 px, visible al hacer scroll): controla todas las vistas a la vez.
- **Área principal** con siete pestañas: Panorama, Comparar tipos, Ruta, Genes, Tabla, Datos e Interpretación.
- **Responsive**: por debajo de unos 960 px el panel de filtros pasa a ir encima del contenido y las rejillas de varias columnas se apilan en una sola.
- Idioma de la interfaz: español.

### Filtros globales

- **Colección de rutas**: lista desplegable con las colecciones presentes en los datos (por ejemplo Hallmark).
- **Tipos celulares**: casillas de verificación. Debe haber al menos 2 seleccionados; la interfaz impide desmarcar el último par. Junto a cada tipo se muestra entre paréntesis el número de rutas significativas con los filtros actuales; los tipos sin filas aparecen atenuados.
- **p ajustado máximo**: deslizador de 0.001 a 0.25, valor inicial 0.05.
- **|NES| mínimo**: deslizador de 0 a 3 con paso 0.1, valor inicial 0.
- **Sentido**: enriquecidas y suprimidas, solo enriquecidas (NES positivo) o solo suprimidas (NES negativo).
- **Filtrar por nombre de ruta**: texto libre, sin distinguir mayúsculas.
- **Rutas en el mapa**: 20, 40 (por defecto), 80 o todas, más una casilla para incluir rutas no significativas.

Cualquier cambio de filtro actualiza todas las vistas de inmediato y marca como desactualizada la interpretación ya generada.

### Vistas

#### Panorama

Cuatro indicadores: tipos con resultados, rutas significativas distintas, rutas que se repiten con el mismo sentido y rutas con sentido opuesto entre tipos. Debajo, un mapa de calor con una fila por ruta y una columna por tipo celular, coloreado por NES en una escala azul (suprimida), blanco, rojo (enriquecida). Las filas se agrupan por patrón: mismo sentido, sentido opuesto y específicas de un tipo. Los asteriscos indican nivel de significancia (\* menor de 0.05, \*\* menor de 0.01, \*\*\* menor de 0.001). Una celda tenue significa que la ruta está en la tabla pero no es significativa; una celda rayada, que no está en la tabla de ese tipo. Al lado, un gráfico de barras con las rutas significativas por tipo, separando enriquecidas y suprimidas. Hacer clic en una fila abre esa ruta en su pestaña de detalle. Un aviso recuerda que se compara cómo responde cada tipo al tumor, no niveles absolutos entre tipos.

#### Comparar tipos

Matriz de similitud entre tipos celulares con el índice de Jaccard con signo; la diagonal muestra cuántas rutas tiene cada tipo y hacer clic en una celda selecciona esa pareja. Dos selectores (Tipo A y Tipo B) permiten elegir la pareja a mano, con indicadores de rutas concordantes, opuestas y exclusivas de cada tipo. La vista incluye un gráfico de puntos con el NES en A y en B de las rutas compartidas, listas de rutas concordantes, opuestas y exclusivas, y los genes comunes del borde de enriquecimiento en las rutas compartidas.

#### Ruta

Buscador con autocompletado para elegir una ruta. Muestra el nombre con una etiqueta de patrón, un gráfico de barras con el NES en cada tipo seleccionado (las barras claras indican que la ruta está en la tabla pero no cumple los filtros), una tabla con NES, p ajustado, q, tamaño y número de genes core por tipo, y los genes comunes entre tipos como etiquetas. Hay una casilla para mostrar solo genes presentes en 2 o más tipos y una tabla de solapamiento por parejas con porcentaje sobre la unión y sobre el conjunto menor. Si la ruta es significativa en un solo tipo o falta la lista de genes, se explica por qué no hay comparación posible.

#### Genes

Tabla de genes recurrentes del borde de enriquecimiento de las rutas significativas, ordenada por el número de tipos celulares donde aparecen, con número de rutas y detalle. Incluye un buscador de genes y una nota que aclara que indica participación en la ruta, no expresión.

#### Tabla

Tabla plana con una fila por tipo celular y ruta: tipo, ruta, NES, p ajustado, q, tamaño, genes core y patrón. Todas las columnas son ordenables con clic en el encabezado. Una casilla permite incluir filas no significativas y un botón descarga el resultado visible en CSV. Hacer clic en una fila abre la ruta.

#### Datos

Zona de carga y gestión de archivos, con la metodología y las definiciones de cálculo. Se detalla en la sección de carga de datos.

#### Interpretación

Botón para generar un texto de interpretación que aparece progresivamente, con botón para copiarlo. Debajo se muestra el resultado de la verificación que indica si el texto ha sido verificado y los errores detectados. Después se listan los hechos enviados (ruta, patrón, tipos con NES, genes comunes) con acceso al JSON completo. Siempre se muestra un aviso: texto generado por IA, a revisar antes de usarlo, con comparaciones dentro de cada tipo celular y genes comunes que no son medidas de expresión.

### Carga de datos

- **Orígenes**: datos reales recibidos (solo rutas significativas), demo simulado con tabla completa y archivos propios. También se puede descargar una plantilla CSV de ejemplo.
- **Formatos**: .xlsx, .csv, .tsv y .txt, varios archivos a la vez, por arrastrar y soltar o con selector. Un archivo por tipo celular y colección.
- **Columnas mínimas**: nombre de la ruta, NES y p ajustado. Opcionales: p valor, q, tamaño y genes del core\_enrichment (separados por barra). El resto se ignora.
- **Detección automática**: de las columnas, del tipo celular (a partir del nombre del archivo) y de la colección (a partir de los nombres de ruta). La persona puede corregir las tres cosas desde la tabla de archivos cargados.
- **Estado por archivo**: filas leídas, filas significativas, estado (correcto, con avisos o con error) y columnas asignadas. Un error en un archivo no impide cargar los demás. Un aviso destacado señala los tipos sin ninguna fila.
- **Reemplazo**: al subir el primer archivo propio se descartan los datos de ejemplo.
- Tras cada cambio de datos, el modelo se reconstruye, se actualiza la insignia y se invalida la interpretación.

### Reglas de cálculo que muestra la interfaz

- **Patrón de una ruta**: mismo sentido si es significativa en 2 o más tipos con el mismo signo de NES; sentido opuesto si es significativa en 2 o más tipos con signos distintos; específica si lo es en un solo tipo.
- **Similitud entre dos tipos**: Jaccard con signo, igual a las rutas concordantes dividido entre (rutas de A + rutas de B - concordantes). Vale 0 si no hay nada en común y 1 si son idénticos.
- **Genes comunes**: genes del core\_enrichment presentes en todos los tipos donde la ruta es significativa. Se expresan como porcentaje sobre la unión y, por parejas, sobre el conjunto menor. Son porcentajes descriptivos, no un test estadístico.
- Una ruta es significativa si su p ajustado no supera el máximo elegido y su |NES| alcanza el mínimo y el sentido elegidos.

### Criterios visuales

- Rojo para enriquecida en tumor y azul para suprimida; nunca se usa solo el color para dar el dato, siempre va acompañado del valor numérico o de una etiqueta.
- Etiquetas de patrón en color: verde para mismo sentido, ámbar para sentido opuesto, gris para específica.
- Cuadros de mensaje diferenciados: informativo (azul), advertencia (ámbar), correcto (verde) y error (rojo).
- Gráficos dibujados en SVG propio, sin librerías externas, con descripción accesible.
- Interfaz sobria sobre fondo claro, con tarjetas, tablas con encabezado fijo en listas largas y tipografía del sistema.

### Estados y mensajes

- Sin datos cargados: la insignia lo indica y las vistas muestran un mensaje vacío.
- Tipo celular sin rutas significativas con los filtros actuales: se indica en los indicadores y en el filtro.
- Menos de 2 tipos seleccionados: no se permite.
- Ausencia de una ruta en un archivo con solo significativas: se avisa de que no equivale a que no cambie.
- Interpretación desactualizada tras cambiar filtros o datos: el texto se reemplaza por un aviso que invita a regenerarla.
- Errores de lectura de archivos: se listan por nombre con el motivo.


## Restricciones
- No recalcula p-valores ni NES; solo ordena, filtra y dibuja lo que devuelve el backend.
- Gráficos en SVG propio, sin librerías externas; cada gráfico con `<title>` y `aria-label`.
- Los tres avisos científicos (comparación intra-tipo, genes del borde de enriquecimiento, texto generado por IA) no pueden ocultarse.
- Volumen de diseño: hasta 10 tipos celulares × 50 rutas por tipo (Hallmark). En caso de cargar otro conjunto de rutas la visualización podrá verse afectada.

### Suposiciones del contrato con el backend

- El frontend envía los filtros activos: colección, tipos celulares seleccionados, p ajustado máximo, |NES| mínimo, sentido y filtro de nombre.
- El backend devuelve los datos ya calculados en JSON: tipos celulares con sus filas, patrones por ruta, similitudes por pareja y genes comunes. El frontend solo ordena, filtra y dibuja.
- Para la interpretación, el backend devuelve el texto redactado, los hechos usados y el resultado de la verificación (verificada / no verificada), incluyendo los errores encontrados y su gravedad. El frontend los muestra juntos.
- La carga de archivos se envía al backend para su validación; el frontend muestra el estado y las columnas detectadas que este le devuelva.

## Criterios de aceptación
1. Al cargar un CSV válido, la tabla de archivos muestra filas leídas, filas significativas, estado y columnas asignadas, y la insignia cambia a "subidos".
2. Si se cargan 3 archivos y uno carece de columna NES, ese archivo aparece con estado "error" y su motivo, y los otros 2 se cargan.
3. Con 2 tipos celulares seleccionados, la casilla de cualquiera de ellos queda deshabilitada: nunca puede haber menos de 2.
4. Mover "p ajustado máximo" de 0.05 a 0.01 actualiza indicadores, mapa de calor y tabla en menos de 300 ms con 10 tipos celulares y 50 rutas.
5. Con el dataset de prueba, los indicadores del Panorama (rutas mismo sentido / sentido opuesto) coinciden con los del JSON del backend.
6. Tras cualquier cambio de filtro o de datos, la interpretación generada se sustituye por el aviso "desactualizada".
7. Clic en una fila del mapa de calor o de la tabla abre la pestaña Ruta con esa ruta seleccionada.
8. El CSV descargado desde Tabla contiene exactamente las filas visibles con los filtros activos y las 8 columnas de la vista.
9. Las 7 pestañas son alcanzables solo con teclado (Tab/flechas) y Lighthouse Accessibility ≥ 90; contraste de texto ≥ 4.5:1.
10. A 900 px de ancho el panel de filtros queda sobre el contenido y no aparece scroll horizontal.