# Adaptación y clonación de voz

## Qué construir

Un proceso para crear voces sintéticas nuevas que cubran perfiles de hablantes poco representados en los modelos elegidos (spec 01), como las personas mayores. Se puede hacer de dos formas, según lo que admita cada modelo:

- **Clonación:** el modelo imita una voz a partir de una grabación corta de referencia de esa persona.
- **Adaptación:** el modelo recibe un prompt que sirve como instrucciones para hablar de una determinada forma. Por ejemplo: "voz de una mujer de unos 80 años, que habla despacio y con voz algo temblorosa".

Las voces creadas se suman a las que ya ofrecen los modelos y se usan para generar el dataset (spec 05).

**Entradas**

- El modelo elegido para cada idioma en la spec 01.
- Para la clonación: grabaciones de referencia de hablantes con los perfiles que se quieren cubrir, en español y en gallego.
- Para la adaptación: prompts que describen cómo debe hablar cada voz.

**Salidas**

- Las voces nuevas, listas para sintetizar.
- Un catálogo de voces que indica, para cada una, su idioma, su perfil (por ejemplo, franja de edad y sexo), el método usado y la grabación o el prompt del que procede.

**Funcionamiento**

1. Se revisan las voces que ofrece cada modelo elegido y se identifican los perfiles que faltan.
2. Para cada perfil se elige el método: clonación si se dispone de una grabación de referencia, o adaptación mediante un prompt si el modelo admite instrucciones.
3. Se reúnen las grabaciones de referencia o se redactan los prompts.
4. Se crea la voz nueva.
5. Se sintetizan con ella unas frases de prueba y se escuchan para comprobar que suena natural y que corresponde al perfil buscado.
6. Se añade la voz al catálogo.

## Por qué

Los modelos de síntesis suelen ofrecer pocas voces, normalmente de adultos de mediana edad grabados en estudio. Un reconocedor de voz entrenado solo con esas voces puede funcionar peor con personas cuya voz es distinta, como las personas mayores, que son una parte importante de los usuarios del ámbito sanitario. Crear voces de estos perfiles hace que el dataset sea más diverso y que el reconocedor funcione bien con más tipos de hablantes.

## Restricciones

- Depende del modelo elegido para cada idioma en la spec 01.
- Si el modelo elegido no admite clonación ni instrucciones, se usa para este fin otro modelo de la lista de Balidea que sí lo admita.
- Para cada voz se registran el método, la grabación de referencia o el prompt, y los parámetros usados.
- Cada voz pertenece a un solo idioma.

## Criterios de aceptación

- Existe al menos una voz nueva de persona mayor en español y otra en gallego.
- Cada voz nueva sintetiza correctamente las frases de prueba.
- Cada voz aparece en el catálogo con su idioma, perfil, método y la grabación o el prompt del que procede.
