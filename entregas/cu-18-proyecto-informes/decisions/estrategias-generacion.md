
# ADR 1 - Estrategias de generación de informes clínicos

## Decisión

Se ha decidido utilizar y comparar diferentes estrategias de generación de informes clínicos sintéticos mediante modelos de lenguaje: prompting, few-shot prompting y generación en dos fases.

Estas estrategias se aplican a los modelos seleccionados según los experimentos realizados y sus resultados.

## Motivación

La calidad de los informes clínicos generados depende tanto del modelo utilizado como de las instrucciones que recibe.

Durante las primeras pruebas se observaron problemas de coherencia clínica, errores en diagnósticos y tratamientos y diferencias en la estructura de los documentos.

Por este motivo, se decidió experimentar con diferentes estrategias:

- Prompting: generar informes utilizando únicamente instrucciones.
- Few-shot prompting: incorporar tres informes reales de referencia para mejorar la estructura y el estilo.
- Generación en dos fases: generar primero la información clínica del paciente ficticio y utilizarla después para redactar el informe completo.

El objetivo es comprobar si estas estrategias permiten mejorar la calidad de los informes y reducir los errores detectados.

## Alternativas consideradas

- Utilizar únicamente prompting: es la opción más sencilla, pero limita el estudio de otras estrategias que podrían mejorar los resultados.
- Utilizar únicamente few-shot: ayuda a reproducir la estructura de los informes reales, pero no garantiza la coherencia clínica.
- Utilizar únicamente generación en dos fases: permite separar la construcción del caso clínico y su redacción, pero requiere un proceso más complejo y debe evaluarse experimentalmente.

Se decidió comparar varias estrategias en lugar de seleccionar una única opción desde el principio.

## Referencias

- [Especificación de estrategias de generación](../specs/estrategias-generacion.md)
- [Arquitectura de la solución](../ARCHITECTURE.md)
- [Documentación de Hugging Face Transformers](https://huggingface.co/docs/transformers/index)
- [Investigación sobre few-shot prompting - Language Models are Few-Shot Learners](https://arxiv.org/abs/2005.14165)

## Consecuencias

Esta decisión permite comparar cómo influyen las instrucciones, los ejemplos y la división del proceso de generación en la calidad de los informes.

Como contrapartida, aumenta el número de experimentos y requiere mantener un registro de los prompts, modelos y configuraciones utilizados.
