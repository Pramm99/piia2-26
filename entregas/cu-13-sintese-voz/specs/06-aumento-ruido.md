# Aumento del dataset con ruido

> **Nota:** antes de implementar esta funcionalidad hay que estudiarla y comprobar si es posible llevarla a cabo.

## Qué construir

Un proceso que toma los audios del dataset sintético (spec 05) y les añade ruido y otros efectos acústicos para que se parezcan más a grabaciones reales. Por ejemplo, el ruido de fondo de una consulta o de un pasillo de hospital, o el eco de una sala. El resultado es una versión del dataset con ruido, en el mismo formato y con las mismas transcripciones, que puede usarse sola o junto al dataset original.

**Entradas**

- El dataset sintético de la spec 05: los audios y su fichero de metadatos.
- Una colección de ruidos de fondo.
- Una configuración del aumento: qué efectos aplicar, con qué intensidad y a qué proporción de los audios.

**Salidas**

- Un audio con ruido por cada audio procesado.
- Un fichero de metadatos con las mismas columnas que el original y, además, el efecto aplicado, el ruido usado, su intensidad y el identificador del audio original.

**Funcionamiento**

1. Se lee la configuración del aumento.
2. Para cada audio seleccionado se eligen el efecto, el ruido y la intensidad según la configuración.
3. Se aplica el efecto y se guarda el audio resultante.
4. Se añade su fila al fichero de metadatos, enlazada con el audio original.
5. Se guarda la configuración usada junto al dataset con ruido.

## Por qué

Los modelos de síntesis producen audio muy limpio, como grabado en estudio. En cambio, el reconocedor de voz funcionará en consultas y hospitales, con conversaciones de fondo, aparatos médicos, eco o micrófonos de distinta calidad. Si solo aprende con audio limpio, es probable que falle en esas condiciones. Añadir ruido acerca el dataset al entorno real. Separarlo de la generación permite aplicar distintos niveles de ruido al mismo dataset sin volver a sintetizarlo.

## Restricciones

- Depende del dataset de la spec 05.
- El ruido no cambia la transcripción: cada audio con ruido conserva la de su audio original.
- El dataset original no se modifica.
- Los audios con ruido se guardan en el mismo formato que los originales.
- Los ruidos de fondo solo se usan si su licencia permite este uso.
- Cada ejecución genera una versión nueva sin sobrescribir las anteriores.

## Criterios de aceptación

- Cada audio con ruido tiene una fila en el fichero de metadatos, enlazada con su audio original.
- Cada audio con ruido tiene la misma transcripción que su original.
- El dataset original queda igual que antes de aplicar el proceso.
- Los metadatos indican para cada audio el efecto, el ruido y la intensidad aplicados.
- El dataset con ruido incluye la configuración con la que se generó.
