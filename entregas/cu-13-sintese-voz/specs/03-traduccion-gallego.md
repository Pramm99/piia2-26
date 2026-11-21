# Traducción del corpus al gallego

## Qué construir

Un proceso que traduce automáticamente al gallego el corpus de textos médicos en español (spec 02). El resultado es un corpus paralelo: cada frase en gallego queda enlazada con su frase original en español. El corpus en gallego es el que leerán los modelos de síntesis para generar la parte gallega del dataset (spec 05).

**Entradas**

- El corpus de frases médicas en español, ya limpio y normalizado.
- Un sistema de traducción automática del español al gallego.

**Salidas**

- Un corpus de frases en gallego, una por línea, cada una con el mismo identificador que su frase en español.

**Funcionamiento**

1. Se traduce cada frase del corpus en español al gallego.
2. Se aplican a las frases traducidas las mismas reglas de limpieza y normalización que al corpus en español.
3. Se descartan las traducciones vacías, las repetidas y las que quedan fuera del rango de longitud.
4. Se guarda el corpus en gallego, enlazado con el corpus en español mediante el identificador de cada frase.

## Por qué

El sistema se aplicará en Galicia, así que el dataset tiene que incluir audio en gallego. Sin embargo, apenas existen textos médicos en gallego. Traducir el corpus en español permite disponer de un volumen similar de frases en ambos idiomas, con el mismo contenido y vocabulario médico. Mantener el enlace entre cada frase y su original permite comparar ambos idiomas y localizar el origen de cualquier error de traducción.

## Restricciones

- Depende del corpus en español de la spec 02.
- Se usa el mismo sistema de traducción para todo el corpus.
- Se registra qué sistema de traducción se ha usado y su versión.
- Las frases traducidas siguen las mismas reglas de normalización que el corpus en español: números, abreviaturas y siglas escritos con palabras.
- Las frases traducidas tienen entre 3 y 30 palabras.

## Criterios de aceptación

- Cada frase en gallego tiene el mismo identificador que una frase del corpus en español.
- Ninguna frase en gallego contiene dígitos.
- No hay frases duplicadas.
- Todas las frases tienen entre 3 y 30 palabras.
- Está registrado el sistema de traducción usado y su versión.
