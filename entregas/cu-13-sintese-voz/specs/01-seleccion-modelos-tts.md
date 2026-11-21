# Selección de modelos de síntesis de voz

## Qué construir

Un proceso para comparar modelos de síntesis de voz y elegir el que se usará en cada idioma, español y gallego, a partir de la valoración de varias personas mediante el método Arena. Es la primera funcionalidad del sistema: el modelo elegido es el que generará el audio del dataset (spec 05) y el punto de partida para adaptar y clonar voces (spec 04).

**Entradas**

- La lista de modelos candidatos proporcionada por Balidea.
- Un conjunto de frases de prueba de temática médica en español y en gallego.
- Un grupo de personas evaluadoras.

**Salidas**

- Los audios de prueba generados por cada modelo.
- Los votos y las abstenciones de cada evaluación.
- Una clasificación de los modelos por idioma y el modelo elegido para cada idioma.

**Funcionamiento**

1. Se parte de la lista de modelos candidatos de Balidea.
2. Cada modelo sintetiza las mismas frases de prueba.
3. Cada persona evaluadora escucha parejas de audios con la misma frase generada por dos modelos distintos y vota el que suena mejor. También puede abstenerse si los dos suenan bien o si los dos suenan mal.
4. Se cuentan los votos por separado para cada idioma y se elige el modelo más votado.
5. Se guardan los audios, los votos, las abstenciones y la clasificación.

## Por qué

La calidad del dataset depende directamente de la calidad de la voz sintética: si el audio suena artificial o pronuncia mal, el reconocedor entrenado con él aprenderá de ejemplos poco realistas. Los resultados publicados de los modelos no siempre reflejan cómo suenan con vocabulario médico ni en gallego. Por eso queremos compararlos nosotros mismos, con frases de nuestro dominio y con el criterio de personas que los escuchan, y elegir el que mejor suena en cada idioma.

## Restricciones

- Solo se evalúan los modelos de la lista proporcionada por Balidea. Se da por supuesto que sus licencias están aprobadas para el uso que hará la empresa.
- Todos los modelos sintetizan exactamente las mismas frases.
- Las abstenciones se registran indicando su motivo (ambos suenan bien o ambos suenan mal), pero no suman votos a ningún modelo.
- Puede ganar un modelo distinto en cada idioma.
- Si un modelo solo admite uno de los dos idiomas, compite solo en ese idioma.
- No depende de otras funcionalidades: las frases de prueba se preparan a mano, sin esperar al corpus de la spec 02.

## Criterios de aceptación

- Se han usado al menos 10 frases de prueba por idioma.
- Han votado al menos cinco personas.
- Existe una clasificación para cada idioma con el número de votos de cada modelo.
- Hay un modelo elegido para cada idioma, y es el que más votos ha obtenido en ese idioma.
