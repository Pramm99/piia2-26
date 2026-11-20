## Descripción del proyecto

Este proyecto tiene como objetivo estudiar y comparar diferentes modelos de lenguaje (LLMs) para la generación automática de informes clínicos sintéticos de pacientes adultos con cáncer de cabeza y cuello, dentro del ámbito de la Oncología Radioterápica.

Para ello, utilizaremos modelos como Llama, Qwen, GPT y Mistral, probando distintas estrategias de generación, como el uso de instrucciones (*prompting*), la incorporación de informes de ejemplo (*few-shot prompting*) y la generación en dos fases.

El principal reto es conseguir informes que no solo tengan una estructura y un lenguaje similares a los utilizados en un entorno hospitalario, sino que también mantengan la coherencia entre los síntomas, las pruebas diagnósticas, el diagnóstico, los tratamientos y la evolución del paciente.

Con este trabajo buscamos identificar qué modelos y estrategias ofrecen mejores resultados y cuáles son sus principales limitaciones. Los informes generados podrán servir como material sintético para investigación y experimentación, sin sustituir documentación clínica real ni utilizarse para tomar decisiones médicas.

## Motivación

Los modelos de lenguaje han demostrado ser capaces de generar textos cada vez más elaborados, pero su aplicación en el ámbito médico sigue presentando dificultades importantes. Aunque pueden producir informes con una estructura y un vocabulario aparentemente correctos, también pueden introducir errores en los diagnósticos, los tratamientos o la información clínica del paciente.

Por este motivo, nos interesa estudiar hasta qué punto diferentes modelos de lenguaje son capaces de generar informes clínicos sintéticos que resulten realistas y coherentes. También queremos comprobar cómo influyen las instrucciones que proporcionamos a los modelos y el uso de informes de ejemplo en la calidad de los resultados.

Al finalizar el proyecto, esperamos identificar las estrategias que ofrecen mejores resultados, analizar los errores más frecuentes y conocer las principales ventajas y limitaciones de los modelos estudiados. Con ello, buscamos contribuir al estudio de la generación de documentación clínica sintética que pueda utilizarse en entornos de investigación y experimentación.

## Alcance del proyecto

El proyecto se centra en la generación y evaluación de informes clínicos sintéticos de pacientes adultos con cáncer de cabeza y cuello, dentro del ámbito de la Oncología Radioterápica.

### Qué incluye el proyecto

- **Generación de informes sintéticos:** utilizaremos distintos modelos de lenguaje, como Llama, Qwen, GPT y Mistral, para generar informes clínicos ficticios siguiendo una estructura similar a la utilizada en un entorno hospitalario.
- **Comparación de estrategias de generación:** probaremos diferentes versiones de prompts, la incorporación de informes de referencia mediante *few-shot prompting* y la generación en dos fases, separando la construcción de la información clínica de la redacción del informe.
- **Evaluación de los informes:** analizaremos la estructura, el realismo, la coherencia clínica y las posibles contradicciones de los informes generados. Utilizaremos criterios de evaluación definidos previamente y estudiaremos el uso de métricas automáticas y la revisión por expertos.
- **Comparación de resultados:** compararemos los modelos y las estrategias utilizadas para identificar sus principales ventajas, limitaciones y errores frecuentes.
- **Análisis y mejora:** revisaremos los errores detectados e introduciremos modificaciones en los prompts para estudiar cómo afectan a los resultados.

### Qué queda fuera del proyecto

- **Uso clínico real:** los informes generados serán completamente sintéticos y no se utilizarán para diagnosticar pacientes ni tomar decisiones médicas.
- **Desarrollo de nuevos modelos desde cero:** trabajaremos con modelos de lenguaje existentes, sin entrenar una arquitectura propia desde cero.
- **Integración hospitalaria:** no desarrollaremos una aplicación conectada a los sistemas de información de un hospital.
- **Otras especialidades médicas:** el proyecto se limitará a casos de pacientes adultos con cáncer de cabeza y cuello en el ámbito de la Oncología Radioterápica.
- **Validación para uso asistencial:** aunque se contempla la revisión de informes por profesionales sanitarios, no se pretende certificar que el sistema sea seguro para utilizarlo en la práctica clínica.

## Equipo

El equipo está formado por tres integrantes, que trabajamos de forma conjunta en el desarrollo y evaluación del proyecto. Para organizar el trabajo, cada una se encarga principalmente de experimentar con diferentes modelos de lenguaje, aunque compartimos las tareas de análisis de resultados, comparación de estrategias y mejora de los prompts.

| Integrante | Responsabilidad principal |
|---|---|
| Claudia Mein | Experimentación y generación de informes con Llama |
| María Mira | Experimentación y generación de informes con Qwen |
| María de Miguel | Experimentación y generación de informes con GPT y Mistral |

Las tres participamos en la evaluación de los informes generados, la identificación de errores y el análisis de los resultados. Además, contaremos con la colaboración de un profesional sanitario para realizar la valoración clínica de una selección de informes.

**Correos de contacto:**
- Claudia Mein: claudia.mein@rai.usc.es
- María Mira: maria.mira.calvete@rai.usc.es
- María de Miguel: maria.de.miguel@rai.usc.es


## Estructura del proyecto

La documentación del proyecto se encuentra en la carpeta `entregas/cu-18-proyecto-informes/` del repositorio de GitHub.

Su organización es la siguiente:

```text
cu-18-proyecto-informes/
├── README.md
├── ARCHITECTURE.md
├── specs/
│   ├── generacion-informes.md
│   ├── estrategias-generacion.md
│   ├── evaluacion-informes.md
│   └── comparacion-modelos.md
└── decisions/
    ├── estrategias-generacion.md
    └── evaluacion-informes.md
```

### Documentación de arquitectura

- [Arquitectura de la solución](ARCHITECTURE.md): diagrama, componentes y flujo de funcionamiento del sistema.

### Decisiones de implementación

- [ADR 1 - Estrategias de generación](decisions/estrategias-generacion.md): justificación de las estrategias utilizadas.
- [ADR 2 - Evaluación de informes](decisions/evaluacion-informes.md): justificación de los métodos de evaluación seleccionados.

### Especificaciones funcionales

- [Generación de informes](specs/generacion-informes.md)
- [Estrategias de generación](specs/estrategias-generacion.md)
- [Evaluación de informes](specs/evaluacion-informes.md)
- [Comparación de modelos](specs/comparacion-modelos.md)
```
