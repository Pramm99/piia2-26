---
description: Control de alucinaciones mediante un esquema de salida con signo, estado y motivos, reglas automáticas de verificación y contraste con Gene Ontology y entre dos modelos.
state: Aceptado (pendiente de implementación)
---

# ADR 003 - Control de Alucinaciones: Signo, Estado y Motivos en Lugar de Predicciones Forzadas

## Decisión
El sistema **nunca fuerza un signo** cuando la evidencia no lo sostiene. Cada par evaluado (gen, PMID, término) produce una salida con tres campos:

| Campo | Valores |
|---|---|
| `signo` | `+1` / `-1` / `UNKNOWN` |
| `estado` | `resuelto` / `revisar` / `no_concluyente` |
| `motivos` | lista de cero o más motivos (tabla siguiente) |

| Motivo | Origen | Estado | Signo |
|---|---|---|---|
| `no_menciona_gen` | LLM o filtro previo | `no_concluyente` | `UNKNOWN` |
| `efecto_indirecto` | LLM | `no_concluyente` | `UNKNOWN` |
| `contradictorio` | LLM | `no_concluyente` | `UNKNOWN` |
| `contexto_ajeno` | LLM | `no_concluyente` | `UNKNOWN` |
| `cita_no_verificada` | Regla automática | `no_concluyente` | `UNKNOWN` |
| `json_invalido` | Regla automática | `no_concluyente` | `UNKNOWN` |
| `discrepancia_polaridad_GO` | Contraste con GO | `revisar` | Se mantiene |
| `discrepancia_entre_modelos` | Contraste entre modelos | `revisar` | El del modelo principal |

`UNKNOWN` queda reservado para los casos **sin evidencia utilizable**. Cuando hay evidencia pero otra fuente la contradice (Gene Ontology o el modelo secundario), se conserva el signo y el caso se marca para revisión experta.

El control se organiza en tres capas:

1. **Prompt:** el modelo puede responder `UNKNOWN` indicando uno de los cuatro motivos semánticos. La justificación literal y el razonamiento se piden **antes** del signo.
2. **Reglas automáticas**, que no dependen del juicio del modelo:
   * **Filtro previo:** si ni el gen ni sus alias del GAF aparecen en el abstract como palabra completa (`CD7` no cuenta dentro de `CD70`; `CD-7` equivale a `CD7`), la salida es `no_menciona_gen` sin llamar al LLM.
   * **Verificación de la cita:** la justificación debe aparecer literalmente en el abstract tras una normalización solo para comparar (minúsculas, todos los guiones unificados, letras griegas escritas como palabras: α→alpha, κ→kappa…, y sin puntuación). Debe tener **al menos 6 palabras**. Si no se verifica, el signo pasa a `UNKNOWN` con `cita_no_verificada`, y se conserva el signo original del modelo (`signo_llm`) para auditoría.
   * **Formato:** un JSON no interpretable o un signo fuera de los valores válidos da `json_invalido`.
3. **Contraste con fuentes independientes:**
   * **Gene Ontology:** si el signo del modelo difiere de `Polaridad_GO` (cuando esta existe), se añade `discrepancia_polaridad_GO`.
   * **Dos modelos:** cada caso se evalúa con un **modelo principal** y un **modelo secundario**, ambos gratuitos. El `signo` final es el del principal y se registran las respuestas de los dos. Cualquier diferencia entre ellos (signos opuestos, o uno `UNKNOWN` y el otro no) añade el motivo `discrepancia_entre_modelos` y deja el caso en `revisar`. Qué modelo es el principal y cuál el secundario se fija en el [ADR-005](adr-005-eleccion-modelo-coste-cero.md), a partir del benchmark.

La normalización de comparación nunca se aplica al texto que lee el LLM: este recibe el abstract limpio pero con la nomenclatura intacta, como exige la spec de limpieza.

Ejemplo de salida:

```json
{
  "gen": "CD7", "pmid": "10652336", "go_id": "GO:0002443",
  "signo": "+1",
  "estado": "revisar",
  "motivos": ["discrepancia_entre_modelos"],
  "signo_modelo_principal": "+1", "signo_modelo_secundario": "UNKNOWN",
  "justificacion_literal": "Human K12-Fc stimulated the up-regulation of CD25, CD54, and CD69 on human NK cells in vitro.",
  "cita_verificada": true,
  "polaridad_go": "+1"
}
```

## Motivación
1. **Un signo falso es peor que un `UNKNOWN`:** el signo entra en el *Net Pathway Score*; un error invierte la contribución del gen a la ruta, mientras que un `UNKNOWN` solo lo deja sin resolver.
2. **El LLM no sabe cuándo se equivoca:** pedirle que diga `UNKNOWN` si duda solo cubre los casos en que detecta su propia duda. Los errores peligrosos son los que comete con seguridad. Ejemplo real del dataset: en el PMID 10652336 el efecto sobre CD25/CD69 lo produce el ligando K12-Fc, no CD7; un modelo complaciente responde `+1` sin dudar. Por eso hacen falta comprobaciones externas al modelo.
3. **Los motivos hacen el sistema auditable:** un `UNKNOWN` sin motivo no indica si falla la recuperación, el modelo o la propia evidencia. Elegir entre motivos concretos es además una tarea más fiable para un LLM que estimar su propia confianza.
4. **Las discrepancias son información, no ruido:** la polaridad de GO es curada por expertos y el segundo modelo es independiente del primero. Convertir sus desacuerdos en `UNKNOWN` descartaría justo los casos que más interesa que revise el experto. Cuando discrepan los dos modelos, se conserva el signo del principal, se registran ambas respuestas y el caso queda marcado para que el experto lo resuelva con toda la información.
5. **La conclusión es del experto:** el sistema extrae y verifica evidencia; los casos `revisar` se entregan al profesional biomédico con la cita y los motivos.

**Validación:** sobre el *gold set* etiquetado por expertos se medirán la **precisión de las respuestas dadas** (cuando el sistema da `+1` o `-1`, cuántas acierta), la **cobertura** (porcentaje de casos con estado `resuelto`) y el **recall de `UNKNOWN`** (cuántos casos no concluyentes según el experto detecta el sistema). Los umbrales mínimos se acordarán con CIMUS.

Aceptamos los compromisos asociados: duplicar las llamadas (dos modelos) alarga la ejecución en los planes gratuitos; el filtro previo puede descartar abstracts que nombran el gen de forma no recogida en los alias (un error en la dirección segura, que se medirá en el benchmark); y la cobertura bajará frente a un sistema que siempre responde.

## Alternativas
* **`UNKNOWN` simple, sin motivo:**
  * *Motivo de descarte:* no permite saber por qué falla el sistema ni priorizar mejoras.
* **Confianza declarada por el propio modelo (p. ej. "estoy seguro al 80 %"):**
  * *Motivo de descarte:* la confianza verbalizada de los LLM está mal calibrada y tiende a ser excesiva.
* **Marcar `revisar` cuando la cita no se verifica, en lugar de `UNKNOWN`:**
  * *Motivo de descarte:* una cita que no está en el abstract es justo la señal de alucinación que se quiere bloquear; el equipo decidió tratarla como falta de evidencia.
* **Convertir en `UNKNOWN` cualquier discrepancia (con GO o entre modelos):**
  * *Motivo de descarte:* se perderían los casos con evidencia en conflicto, que son los más valiosos para la revisión experta.
* **Signo `CONTRADICCION` sin preferencia por ningún modelo cuando los dos discrepan:**
  * *Motivo de descarte:* deja sin signo casos que sí tienen evidencia. El equipo prefirió conservar el signo del modelo principal, guardar las dos respuestas y marcar el caso como `revisar`, de modo que la discrepancia queda igualmente visible para el experto.
* **Comparar modelos solo en el benchmark:**
  * *Motivo de descarte:* el equipo prefirió el contraste en todos los casos; con dos planes gratuitos es viable a coste cero, a cambio de más días de ejecución.
* **Responder siempre `+1`/`-1` (sin opción `UNKNOWN`):**
  * *Motivo de descarte:* obliga al modelo a inventar un signo cuando el abstract no lo sostiene.

## Referencias
* **Código del proyecto (estado actual):**
  * `codigo/consulta_gen/respuesta.py`: ya calcula `cita_verificada`, pero todavía no fuerza `UNKNOWN`; `normalizar_signo` ya convierte valores no válidos en `UNKNOWN`.
  * `codigo/consulta_gen/prompt.py` y `limpieza.py`: lugar previsto para los motivos del prompt y la normalización de comparación.
* **Salidas estructuradas:**
  * Groq: [https://console.groq.com/docs/structured-outputs](https://console.groq.com/docs/structured-outputs)
  * Gemini API: [https://ai.google.dev/gemini-api/docs/structured-output](https://ai.google.dev/gemini-api/docs/structured-output)
* **Literatura:**
  * Xiong et al. (2024), *Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs*, ICLR 2024 (sobreconfianza de la confianza verbalizada).
  * Geifman & El-Yaniv (2017), *Selective Classification for Deep Neural Networks*, NeurIPS 2017 (compromiso entre cobertura y precisión al abstenerse).
* **Decisiones relacionadas:** [ADR-001](adr-001-rag-stateless.md) (arquitectura RAG), [ADR-004](adr-004-persistencia-ficheros-locales.md) (registro de respuestas) y [ADR-005](adr-005-eleccion-modelo-coste-cero.md) (elección de los modelos).
