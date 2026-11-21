# Corpus de textos médicos en español

## Qué construir

Un proceso que reúne textos médicos en español y los prepara para que puedan sintetizarse. Su resultado es el corpus que se traducirá al gallego (spec 03) y que leerán los modelos de síntesis para generar el dataset (spec 05).

**Entradas**

- Textos médicos en español procedentes de una de estas dos fuentes, o de ambas:
    - Corpus de texto médico disponibles en la red.
    - Textos generados con modelos de lenguaje (LLM) a partir de instrucciones sobre temas y especialidades médicas.

**Salidas**

- Un corpus de frases, una por línea, cada una con un identificador y la fuente de la que procede.

**Funcionamiento**

1. Se reúnen los textos: se descargan corpus de la red, se generan con un LLM, o ambas cosas.
2. Se dividen en frases.
3. Se limpian: se eliminan referencias bibliográficas, tablas, direcciones web y caracteres extraños.
4. Se normalizan: los números, las abreviaturas y las siglas se escriben con palabras, tal como se leen. Por ejemplo, "5 mg" pasa a "cinco miligramos".
5. Se descartan las frases demasiado cortas, demasiado largas y las repetidas.
6. Se guarda el corpus con el identificador y la fuente de cada frase.

## Por qué

Los modelos de síntesis leen exactamente el texto que reciben. Si el texto contiene abreviaturas, cifras o restos de formato, el modelo puede pronunciarlos mal, y además la transcripción del audio dejaría de coincidir con lo que realmente se oye. Un corpus limpio y normalizado garantiza que cada audio del dataset tenga una transcripción exacta. Usar textos médicos hace que el vocabulario del dataset sea el que encontrará después el reconocedor de voz.

## Restricciones

- Los corpus de la red solo se usan si su licencia permite este uso.
- Para cada frase se registra si procede de un corpus de la red, indicando cuál, o de un LLM, indicando qué modelo la generó.
- Las frases tienen entre 3 y 30 palabras.
- No hay frases duplicadas.
- Todas las frases siguen las mismas reglas de normalización: números, abreviaturas y siglas escritos con palabras.

## Criterios de aceptación

- Ninguna frase contiene dígitos.
- No hay frases duplicadas.
- Todas las frases tienen entre 3 y 30 palabras.
- Cada frase tiene un identificador único y su fuente.
