
# ADR 2 - Evaluación de informes clínicos sintéticos

## Decisión

Se ha decidido combinar métricas automáticas, evaluación mediante modelos de lenguaje y revisión por una especialista médica para analizar la calidad de los informes clínicos sintéticos.

El objetivo es evaluar tanto la similitud con los informes reales como la coherencia y calidad del contenido clínico.

## Motivación

Los informes generados pueden presentar una estructura y un lenguaje adecuados, pero contener errores médicos relacionados con los diagnósticos, las pruebas, los tratamientos o las dosis de radioterapia.

Por este motivo, se utilizan diferentes métodos de evaluación:

- BLEU-4: compara la similitud textual entre los informes sintéticos y los reales.
- BERTScore F1: analiza la similitud semántica de los textos.
- Evaluación médica: permite identificar errores clínicos y valorar el realismo de los informes.

La combinación de estos métodos permite obtener una evaluación más completa que utilizando una única métrica.

## Alternativas consideradas

- Utilizar únicamente métricas automáticas: permite realizar comparaciones rápidas, pero no garantiza que el contenido sea médicamente correcto.
- Utilizar únicamente evaluación médica: aporta conocimiento clínico especializado, pero requiere tiempo y limita la cantidad de informes que pueden revisarse.

Se decidió combinar los tres métodos para aprovechar sus ventajas y compensar sus limitaciones.

## Referencias

- [Especificación de evaluación de informes](../specs/evaluacion-informes.md)
- [Arquitectura de la solución](../ARCHITECTURE.md)
- [Documentación de SacreBLEU](https://github.com/mjpost/sacrebleu)
- [BERTScore](https://github.com/Tiiiger/bert_score)

## Consecuencias

Esta decisión permite comparar los informes desde diferentes perspectivas e identificar errores que no se reflejan en las métricas textuales.

Como limitación, solo se dispone de seis informes clínicos reales: tres utilizados como ejemplos y tres reservados para evaluación. Esto reduce la representatividad de los resultados.

Además, las puntuaciones automáticas y las valoraciones de los modelos evaluadores deben interpretarse con cautela y contrastarse con la revisión clínica.
