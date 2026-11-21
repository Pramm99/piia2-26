# Voz sintética para mejorar el reconocimiento del habla médica en español y gallego

## Qué es

Este proyecto estudia cómo usar voz sintética de alta calidad para entrenar y mejorar modelos de reconocimiento automático del habla (ASR) en español y gallego. Los sistemas ASR necesitan muchas horas de audio transcrito, y grabarlo es caro y lento; en gallego, además, los recursos disponibles son escasos. Proponemos aprovechar modelos abiertos de síntesis de voz (TTS), adaptados a ambos idiomas, para generar grandes volúmenes de audio de dominio médico con su transcripción exacta, variando voces, estilos de habla y ruido. El resultado será un dataset sintético en ambos idiomas y una metodología reproducible para seguir generando estos datos.

## Motivación

Este proyecto retoma la línea de trabajo de la asignatura PIIA I, en la que desarrollamos un agente conversacional por voz: un sistema que reconocía lo que decía el usuario (ASR), generaba una respuesta con un modelo de lenguaje (LLM) y la leía en voz alta mediante síntesis de voz (TTS), con un detector de turnos para gestionar la conversación. No continuamos aquel proyecto, sino su temática. Trabajar con tecnologías del habla nos gustó mucho, y ahora queremos profundizar en la síntesis de voz y en cómo puede ayudar a mejorar el reconocimiento.

Lo que más nos atrae es la generación de datos sintéticos: poder crear de forma controlada los datos que necesita un modelo, en lugar de depender solo de los que ya existen.

Aplicaremos el proyecto al ámbito médico, un área que también nos resulta muy interesante. En sanidad, el reconocimiento de voz tiene usos claros, como el dictado de informes clínicos. Sin embargo, el vocabulario es muy específico y las grabaciones reales son difíciles de conseguir, porque contienen información sensible de los pacientes. La voz sintética permite generar audio con terminología médica sin recurrir a datos de pacientes.

El gallego tiene un papel central en el proyecto: los datos se generarán tanto en español como en gallego, y el gallego es imprescindible para que el resultado sea útil en el contexto en el que se aplicará.

Al terminar el proyecto queremos:

- Comparar distintos modelos abiertos de síntesis de voz mediante un método tipo Arena: varias personas escuchan los modelos por parejas, votan cuál suena mejor y seleccionamos el más votado.
- Generar un dataset sintético con el volumen y la calidad necesarios para entrenar modelos de reconocimiento del habla.
- Definir una metodología que permita repetir la generación tantas veces como haga falta para aumentar el volumen de datos.
- Si el tiempo lo permite, aportar evidencia experimental de en qué casos la voz sintética mejora un ASR.

## Alcance

### Qué entra en el proyecto

- Selección y comparación de modelos abiertos de síntesis de voz en español y gallego mediante el método Arena.
- Preparación de un corpus de textos médicos en español a partir de fuentes abiertas.
- Traducción automática del corpus de textos del español al gallego.
- Adaptación y clonación de voz para cubrir perfiles de hablantes poco representados en los modelos disponibles, como las personas mayores.
- Generación del dataset sintético en español y gallego, con variación de voces, estilos de habla y ruido.
- Documentación del dataset y de una metodología que permita repetir la generación.
- De forma opcional, si el tiempo lo permite: entrenamiento y evaluación de un modelo de reconocimiento del habla con los datos generados.

### Qué queda fuera

- El diseño de nuevas arquitecturas de síntesis o reconocimiento: trabajaremos con modelos abiertos existentes.
- El uso de servicios comerciales cerrados de síntesis.
- El despliegue en producción, las aplicaciones para usuario final y el reconocimiento en tiempo real.
- Dominios distintos del médico.

## Caso de uso

**Generar datos de voz médica en español y gallego para entrenar sistemas de reconocimiento del habla.**

Balidea quiere entrenar un sistema de reconocimiento de voz para el ámbito sanitario en Galicia, como el dictado de informes clínicos. Para ello necesita audio médico transcrito en español y en gallego. Las grabaciones reales de este tipo son escasas, y en gallego prácticamente no existen. Balidea usa nuestro sistema para generar ese audio de forma sintética.

**Flujo**

1. Se eligen los modelos de síntesis de voz mediante el método Arena.
2. Se reúne un corpus de textos médicos en español y se traduce al gallego.
3. Se adaptan o clonan voces para cubrir perfiles poco representados, como las personas mayores.
4. Se sintetiza el audio con distintas voces y estilos de habla.
5. Se añade ruido y otros efectos acústicos para acercar el audio a condiciones reales.
6. Se obtiene un dataset de audio con su transcripción, listo para entrenar un ASR.
7. El proceso se repite tantas veces como haga falta para aumentar el volumen de datos.
8. Opcionalmente, si el tiempo lo permite, se entrena y evalúa un ASR con los datos generados.

**Criterios de éxito**

- El dataset contiene audio en español y en gallego con su transcripción exacta.
- Las voces elegidas son las mejor valoradas en el método Arena.
- Otra persona puede repetir la generación siguiendo la documentación.

## Equipo

| Nombre | Rol | Contacto |
| --- | --- | --- |
| Javier Arrojo | Tech Lead | javier.arrojo@rai.usc.es |
| Mara Barreiro | Voice AI Engineer | mara.barreiro@rai.usc.es |
| Yara Costas | Voice AI Engineer | yara.costas@rai.usc.es |
| Elena Couto | Project Manager | elena.couto@rai.usc.es |

## Estructura de la entrega

En esta primera entrega solo hay documentación: este README y una especificación funcional por cada funcionalidad del proyecto.

```
entregas/
  cu-xx-voz-sintetica-asr-medico/
    README.md
    specs/
      01-seleccion-modelos-tts.md
      02-corpus-textos-medicos.md
      03-traduccion-gallego.md
      04-adaptacion-clonacion-voz.md
      05-generacion-dataset.md
      06-aumento-ruido.md
      07-entrenamiento-evaluacion-asr.md
```

| Fichero | Contenido |
| --- | --- |
| `README.md` | Qué es el proyecto, motivación, alcance, caso de uso, equipo y estructura de la entrega. |
| `specs/01-seleccion-modelos-tts.md` | Búsqueda de modelos abiertos de síntesis y comparación mediante el método Arena. |
| `specs/02-corpus-textos-medicos.md` | Recopilación y preparación de los textos médicos en español. |
| `specs/03-traduccion-gallego.md` | Traducción automática del corpus al gallego. |
| `specs/04-adaptacion-clonacion-voz.md` | Adaptación y clonación de voces para perfiles poco representados, como personas mayores. |
| `specs/05-generacion-dataset.md` | Síntesis del audio con variación de voces y estilos de habla, y formato final del dataset. |
| `specs/06-aumento-ruido.md` | Aplicación de ruido y otros efectos acústicos al audio generado. |
| `specs/07-entrenamiento-evaluacion-asr.md` | Funcionalidad opcional: entrenar y evaluar un ASR con los datos generados. |
