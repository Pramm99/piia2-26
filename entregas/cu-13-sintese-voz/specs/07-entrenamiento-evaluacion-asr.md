# Entrenamiento y evaluación de un ASR con el dataset sintético

> **Nota:** esta funcionalidad es opcional y solo se desarrollará si el tiempo lo permite.

## Qué construir

Un proceso que entrena un modelo abierto de reconocimiento del habla (ASR) con el dataset sintético (specs 05 y 06) y mide si reconoce mejor el habla médica que el mismo modelo sin entrenar. Es la última etapa del sistema: comprueba si los datos generados sirven para lo que se crearon.

**Entradas**

- Un modelo ASR abierto con soporte para español y gallego.
- El dataset sintético, con y sin ruido.
- Un conjunto de test de habla médica real, en español y en gallego, con su transcripción.

**Salidas**

- Los modelos ASR entrenados.
- Las métricas de cada modelo sobre el conjunto de test, por idioma.
- Una comparación de los resultados frente al modelo sin entrenar.

**Funcionamiento**

1. Se evalúa el modelo ASR sin entrenar sobre el conjunto de test. Este resultado es la línea base.
2. Se entrena el modelo con el dataset sintético.
3. Se evalúa el modelo entrenado sobre el mismo conjunto de test.
4. Se repiten los pasos 2 y 3 cambiando un solo factor cada vez, por ejemplo con o sin ruido, o con o sin las voces creadas en la spec 04.
5. Se comparan los resultados de cada modelo con la línea base.

## Por qué

Que el audio sintético suene bien no garantiza que sirva para entrenar un reconocedor. La única forma de saberlo es entrenar un modelo con él y medir si reconoce mejor el habla real. Comparar con la línea base dice si los datos ayudan, y cambiar un factor cada vez dice qué parte del dataset es la que ayuda.

## Restricciones

- Depende de las specs 05 y 06.
- El conjunto de test es siempre habla real, nunca sintética.
- Ninguna frase del conjunto de test aparece en los corpus usados para sintetizar.
- Todos los modelos se evalúan sobre el mismo conjunto de test.
- Se registran el modelo, su versión, los datos y los parámetros de cada entrenamiento.

## Criterios de aceptación

- Existe una línea base: las métricas del modelo sin entrenar en cada idioma.
- Cada modelo entrenado tiene sus métricas en cada idioma, medidas sobre el mismo conjunto de test.
- Los resultados indican, para cada modelo, la diferencia de sus métricas respecto a la línea base.
- Cada experimento puede repetirse a partir de lo registrado.
