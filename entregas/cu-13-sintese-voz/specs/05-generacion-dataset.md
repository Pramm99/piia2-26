# Generación del dataset sintético

## Qué construir

Un proceso que sintetiza los corpus de textos médicos en español (spec 02) y en gallego (spec 03) con los modelos elegidos (spec 01) y las voces del catálogo (spec 04). Cada frase se sintetiza con distintas voces y estilos de habla, y el resultado se guarda como un dataset de audio con su transcripción, listo para entrenar un reconocedor de voz. Es el producto principal del proyecto: la spec 06 le añade ruido y la spec 07 lo usa, opcionalmente, para entrenar un ASR.

**Entradas**

- Los corpus de frases en español y en gallego.
- El modelo elegido para cada idioma.
- El catálogo de voces: las que ofrece cada modelo y las creadas en la spec 04.
- Una configuración de la generación: qué voces y estilos usar y cuántas veces se sintetiza cada frase.

**Salidas**

- Un fichero de audio por cada frase sintetizada.
- Un fichero de metadatos con una fila por audio que recoge: identificador del audio, identificador de la frase, transcripción, idioma, voz, perfil de la voz, estilo de habla, modelo y duración.
- Un resumen del dataset: número de audios y horas totales por idioma, voz y estilo.

**Funcionamiento**

1. Se lee la configuración de la generación.
2. Para cada frase se eligen la voz y el estilo de habla según la configuración.
3. Se sintetiza el audio con el modelo del idioma correspondiente.
4. Se guarda el audio y se añade su fila al fichero de metadatos.
5. Al terminar, se calcula el resumen del dataset.
6. Se guarda la configuración usada junto al dataset, con una versión que lo identifique.

## Por qué

Un reconocedor de voz necesita muchas horas de audio con su transcripción exacta, y en el ámbito médico, sobre todo en gallego, esas grabaciones apenas existen. La síntesis permite producirlas a partir de texto. Variar las voces y los estilos evita que el reconocedor aprenda solo una forma de hablar. Guardar la configuración y los metadatos hace posible repetir la generación, aumentar el volumen con nuevas ejecuciones y saber exactamente cómo se obtuvo cada audio.

## Restricciones

- Depende de las specs 01, 02, 03 y 04.
- La transcripción de cada audio es exactamente la frase del corpus que se sintetizó.
- Todos los audios se guardan en el mismo formato.
- Cada frase se sintetiza en el idioma de su corpus y solo con voces de ese idioma.
- El volumen de audio es el mismo en español y en gallego.
- Cada ejecución genera una versión nueva del dataset sin sobrescribir las anteriores.

## Criterios de aceptación

- Cada audio tiene una fila en el fichero de metadatos, y cada fila tiene su audio.
- Todos los audios están en el mismo formato.
- El dataset contiene audio en español y en gallego, con el mismo número de horas en cada idioma.
- Se usan todas las voces del catálogo, incluidas las creadas en la spec 04.
- El resumen indica el número de audios y las horas por idioma, voz y estilo.
- El dataset incluye la configuración con la que se generó.
