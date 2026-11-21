# Motor de análisis bioinformático, cruce multivariante e interpretación vía LLM

## Qué construir
El núcleo lógico y de procesamiento del sistema (orientado al backend y a la integración con el LLM) que abarca cuatro procesos:
### 1. Ingesta y normalización
Lectura de archivos en formato diverso ('.xlsx', '.csv', '.tsv', '.txt'), mapeo automático de columnas mediante diccionarios de sinónimos, inferencia del tipo celular (limpiando términos genéricos y prefijos del nombre del archivo) y de la colección (Hallmark, KEGG, Reactome, GO) cuando al menos el 50 % de las rutas compartan el prefijo correspondiente (asignando 'Colección 1' por defecto en caso contrario), y división de la cadena de genes de 'core_enrichment'.
### 2. Clasificación de patrones:
Filtrado de las rutas según los umbrales activos ('p ajustado' máximo, '|NES|' mínimo, sentido y búsqueda por texto) y clasificación de cada ruta significativa en 'mismo sentido' (significativa en 2 o más tipos celulares, todos con el mismo signo de NES), 'sentido opuesto' (significativa en 2 o más tipos celulares donde al menos uno presenta signo de NES distinto a los demás) o 'específica' (significativa en un único tipo celular).
### 3. Similitud, solapamiento y recurrencia génica:
   - Cálculo del Índice de Jaccard con signo entre cada pareja de tipos celulares.
   - Cálculo de la intersección de genes del 'core_enrichment' (tanto global entre todos los tipos donde la ruta es significativa como por parejas), obteniendo el porcentaje sobre la unión y sobre el conjunto menor, así como una matriz de presencia/ausencia por gen y tipo celular vinculada al signo del NES.
   - Agregación transversal de genes recurrentes en todas las rutas significativas, contabilizando en cuántos tipos celulares distintos y en cuántas rutas participa cada gen.
### 4. Creación de datos para la explicación:
Generación de un objeto JSON estructurado con los hechos matemáticos redondeados que alimenta al módulo de explicación.

## Por qué
Este tipo de análisis son útiles en diferentes investigaciones y hasta el momento estaban siendo llevadas a cabo de forma artesanal para cada grupo de ejemplos. El cumplimiento de esta especificación implicaría la automatización de dichos análisis, suponiendo un apoyo a la hora de extraer patrones estadísticos que ahorra tiempo de la persona investigadora.

## Restricciones
- **Inmutabilidad estadística:** El motor nunca recalcula ningún p-valor, q-valor ni NES; emplea estrictamente los valores numéricos ya calculados en los archivos de origen. Los porcentajes de genes comunes son descriptivos y no representan un test estadístico.
- **Reglas de validación y suplencia en archivos:**
  - Un archivo requiere obligatoriamente columnas para ruta, 'NES' y una métrica de significancia. Las filas sin estos datos se ignoran.
  - La métrica de significancia sigue una jerarquía estricta de prioridad: busca primero 'p ajustado' ('padj'/'fdr'); si no existe, emplea 'q-valor'; y como último recurso 'p-valor' nominal, generando una advertencia explícita de que el valor puede no estar corregido por tests múltiples.
  - Si hay rutas duplicadas en un mismo archivo o al combinar varios archivos de un mismo tipo celular y colección, se sobrescribe el índice conservando estrictamente la última aparición.
  - La columna de genes se divide con prioridad por el carácter '/' si está presente en la cadena; solo en ausencia de '/' se divide por comas, puntos y comas o espacios en blanco.
- **Fórmula de Jaccard y casos límite:** La similitud entre los tipos A y B se calcula como J(A,B) = concordantes / (nA + nB - concordantes). Si nA = 0 o nB = 0, el resultado debe ser 'null' (no calculable) para evitar divisiones por cero o falsos ceros.
- **Redondeo en el JSON de hechos:**
  - Al construir el objeto JSON para el LLM, los valores de 'NES' y 'Jaccard' se exportan redondeados a 2 decimales, el 'p ajustado' a 2 cifras significativas, y los porcentajes de solapamiento génico se redondean al entero más próximo.

## Criterios de aceptación
- Al procesar un archivo '.csv' con cabeceras 'Description', 'NormalizedEnrichmentScore', 'FDR' y 'core_enrichment' (con genes separados por '/'), el motor mapea automáticamente los campos sin errores, infiere la colección 'Hallmark' si al menos la mitad de las rutas comienzan por 'HALLMARK_' y extrae la lista de genes. Si el archivo solo trajese 'pvalue' en lugar de 'FDR', lo usa como métrica de significancia y registra un aviso.
- Dadas tres listas de rutas filtradas donde HALLMARK_MYOGENESIS tiene NES -2.12, -1.77 y -2.36, y HALLMARK_TNFA_SIGNALING_VIA_NFKB tiene NES +1.49, +1.63 y -1.65, el motor clasifica la primera como 'mismo sentido' y la segunda como 'sentido opuesto'.
- Si el Tipo A tiene 10 rutas significativas y el Tipo B tiene 13, compartiendo 3 rutas con el mismo signo de NES, el cálculo de similitud devuelve exactamente 0.15 (3 / (10 + 13 - 3)); si un tercer Tipo C tiene 0 rutas significativas, su similitud con A y B devuelve 'null'.
- En la agregación transversal de genes, si el gen 'IRF7' aparece en el 'core_enrichment' de 3 rutas significativas distribuidas en 4 tipos celulares, el motor registra 'IRF7' con presencia en 4 tipos y 3 rutas, ordenando la tabla global primero por número de tipos celulares (descendente) y después por número de rutas.