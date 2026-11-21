# Módulo de generación y verificación de explicaciones de GSEA

## Qué construir
Un módulo que reciba los resultados del GSEA y devuelva una explicación en lenguaje natural generada por un LLM, verificada y corregida para minimizar errores y alucinaciones del LLM.

El modelo no debe realizar nuevos cálculos estadísticos ni formular interpretaciones biológicas que no estén justificadas por los datos proporcionados. Su función es explicar y resumir los resultados recibidos.

### Datos de entrada
El módulo recibe los **resultados del GSEA**: una serie de hechos derivados del análisis en formato JSON.

Al LLM se le proporciona esta información, transformada en un formato adecuado que maximice su rendimiento en la evaluación. En concreto, esta podrá consistir en:
1. Conjunto de vías biológicas enriquecidas junto con su dirección y magnitud.
2. Conjunto de genes que participan en el enriquecimiento de cada vía.
3. Descripciones de las funciones biológicas de las vías enriquecidas.

### Sistema de verificación y corrección
Recibe los mismos datos que el LLM junto con la explicación resultante.

Definición de dato relevante: nombres de vías y de genes que participan en el enriquecimiento de más de dos vías de diferentes células, entre otros.

#### Detección de errores en la explicación:
Determinista:
- Detección de menciones de **genes** y **vías** no presentes en los resultados del análisis.
- Detección de cifras no presentes en los resultados del análisis.
- Detección de omisiones de datos relevantes.

Con LLM Judges (limitados según la API disponible):
- Extracción de afirmaciones para su posterior evaluación según los siguientes criterios:
    - Fundamentación (Groundedness): las afirmaciones están justificadas por los resultados del análisis.
    - Coherencia (Consistency): las afirmaciones no se contradicen entre sí ni con los resultados originales.

- Completitud (Completeness): la explicación presenta todos los datos y hechos considerados previamente como relevantes.

#### Categorías de errores:
Clasificaremos los errores en:
- **Críticos**: errores de interpretación del GSEA o invención de hechos.
    
    Ej.: mencionar rutas o genes que no aparecen en los resultados; invertir la dirección del enriquecimiento; asociar genes a la ruta equivocada.
- **Graves**: errores que pueden causar una interpretación incorrecta por parte del usuario.

    Ej.: Afirmar que un pathway está activado o inhibido sin evidencia; presentar afirmaciones contradictorias; omitir rutas o relaciones entre genes previamente identificados como relevantes; atribuir relaciones causales o conclusiones biológicas no respaldadas por los datos.
- **Leves**: imprecisiones pequeñas u omisiones que no afectan al correcto entendimiento del resultado del análisis.

    Ej.: omitir genes secundarios o detalles poco relevantes; utilizar terminología ligeramente imprecisa; repetir información o emplear formulaciones poco claras

#### Corrección:
En caso de detectar **un error crítico** o **un error grave**, se corrige la explicación.

Para ello se realiza otra llamada al LLM proporcionando la información original junto con la respuesta y los errores detectados. Devuelve una respuesta actualizada que se vuelve a verificar.

Una explicación tendrá un límite de correcciones determinado según los límites de llamadas a LLMs. Si después de agotar el número máximo de correcciones persisten errores críticos o graves, la explicación se marcará como no verificada y se indicará que requiere revisión manual.

### Datos de salida
1. La explicación final.
2. Los errores encontrados en la explicación final, junto con su clasificación (crítico, grave, leve) y la sección de texto donde fueron detectados. 

## Por qué
Los resultados de un análisis GSEA pueden ser extensos y difíciles de interpretar directamente. El módulo busca facilitar su comprensión mediante una explicación resumida en lenguaje natural. Debido a la posibilidad de que los LLM introduzcan errores o afirmaciones no respaldadas por los datos, se incorpora un sistema de verificación y corrección.

## Restricciones y suposiciones
### Generales
- Máximo de llamadas de LLM según los límites de la API elegida.
- Límite de **dos** correcciones de la explicación.
### LLM generador
- No realiza nuevos cálculos estadísticos.
- No extrapola más allá de los datos.
- No utiliza conocimientos o información no disponibles en los datos proporcionados.
### LLM evaluador (Judge)
- Es opcional dependiendo del límite de llamadas al LLM.
- No acepta como válidas afirmaciones que no estén basadas únicamente en los datos.
- Detecta contradicciones internas de la explicación.
- Detecta omisiones relevantes.

## Criterios de aceptación
- Incluir al menos el 90% de los datos identificados previamente como relevantes para la explicación, medido determinísticamente.
- Groundedness, consistency y completeness superiores al 80%.
    Calculados con LLM judges en una evaluación separada de la ejecución normal, sobre un conjunto de prueba de N explicaciones (N ≥ 10, fijado antes de evaluar) y promediando el resultado de las N. Sea C el conjunto de afirmaciones atómicas que el juez extrae de la explicación, y R el conjunto de hechos relevantes del JSON de entrada:
    - **Groundedness** = |afirmaciones respaldadas por los datos| / |C|
    - **Consistency** = 1 − |afirmaciones contradictorias con otra afirmación o con los datos| / |C|
    - **Completeness** = |hechos presentes en la explicación| / |R|
    
- Detección del 90% de errores críticos, 80% de los graves y 60% de los leves, calculados con un conjunto de datos sintético de al menos 20 errores de cada categoría.
- Menos del 15% de explicaciones superan el límite de correciones en ejecuciones en el conjunto de N ejecuciones.
- Tiempo medio de ejecución inferior a 60 segundos, incluyendo generación, verificación y posibles correcciones.
