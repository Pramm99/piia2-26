# Spec: Sanitización de Abstracts Biomédicos y Partición de Expresión Génica (Up/Down)

## Qué hay que construir
Un componente de procesamiento, sanitización de texto y particionado lógico de datos transcriptómicos (`codigo/consulta_gen/limpieza.py` y `esquema.py`, apoyado en `limpiar_texto` de la Fase 1) que ejecute las siguientes tres responsabilidades:
1. **Sanitización del texto que lee el LLM (normalización conservadora):** Procesar las cadenas de texto crudas descargadas de la literatura científica, eliminando etiquetas estructurales (HTML como `<b>`, `<i>`, `<p>`, `<sup>`, `<sub>`, `<jats:...>`), caracteres de escape XML/HTML (`&amp;`, `&lt;`, `&gt;`, `&plusmn;`) y espacios en blanco anómalos o saltos de línea repetitivos. Cada etiqueta eliminada se sustituye por un espacio, para que no se peguen las palabras que separaba. Debe asegurar la preservación íntegra de la nomenclatura científica de genes, proteínas, mutaciones y complejos moleculares (ej. `p53`, `NF-κB`, `TGF-β`, `CD8+`, `STAT3`): no cambia mayúsculas, guiones ni letras griegas.
2. **Forma de comparación (normalización fuerte):** Una función independiente que produce una versión del texto **solo para comparar**, nunca para enviarla al LLM. Se usa en las dos comprobaciones automáticas del [ADR-003](../decisions/adr-003-control-alucinaciones-unknown.md): verificar que la cita del LLM aparece en el abstract y detectar si el abstract menciona el gen. Aplica, en este orden:
   1. Normalización Unicode `NFKC` (unifica caracteres equivalentes, p. ej. `µ` y `μ`).
   2. Paso a minúsculas (`casefold`).
   3. Unificación de todos los guiones (`‐ ‑ ‒ – — −`) en `-`.
   4. Letras griegas escritas como palabras (`α`→`alpha`, `β`→`beta`, `γ`→`gamma`, `δ`→`delta`, `κ`→`kappa`, etc.).
   5. Sustitución de guiones y signos de puntuación por espacios, y colapso de espacios repetidos.
3. **Aislamiento y partición de listas de expresión (Up vs. Down):** Mantener de forma segregada y trazable el origen transcriptómico de los genes asociados a una ruta, asegurando que los genes clasificados como sobreexpresados (*Up*) y los clasificados como infraexpresados (*Down*) nunca se fusionen en un mismo contenedor no etiquetado, preservando en todo momento el atributo explícito de dirección (`direction: "UP" | "DOWN"`). La dirección se deriva del fichero de origen (rutas activadas → `UP`; rutas suprimidas → `DOWN`).

Este componente se sitúa como paso previo obligatorio a la inferencia, garantizando que se reciban abstracts limpios, que las comprobaciones de la salida del LLM toleren diferencias tipográficas mínimas y que se conozca exactamente el origen transcriptómico del gen a evaluar.

## Por qué
Los abstracts biomédicos extraídos de APIs como Europe PMC frecuentemente contienen formatos mixtos de marcado XML/HTML correspondientes a maquetaciones editoriales. Enviar etiquetas de formateo al modelo de lenguaje consume tokens innecesarios de la ventana de contexto y puede provocar fallos de análisis sintáctico si el LLM devuelve formatos estructurados como JSON. Sin embargo, un limpiador de texto genérico (como una expresión regular agresiva de sustitución de caracteres alfanuméricos) destruiría símbolos fundamentales en genética (guiones, letras griegas, signos de adición en subtipos inmunes), alterando el significado biológico de los genes diana.

Por otro lado, el control de alucinaciones (ADR-003) compara textos: la cita que devuelve el LLM frente al abstract, y el símbolo del gen frente al abstract. Una comparación exacta fallaría por diferencias sin significado (un guion largo en lugar de uno corto, `NF-kappaB` en lugar de `NF-κB`, una coma omitida) y convertiría en `UNKNOWN` respuestas correctas. Por eso hacen falta **dos niveles**: uno conservador, que preserva la nomenclatura para el LLM, y otro fuerte, usado solo para comparar.

Asimismo, dado que un gen en una condición celular concreta está únicamente sobreexpresado (*Up*) o infraexpresado (*Down*) —pero nunca en ambos estados a la vez—, es indispensable preservar intacta esta clasificación por separado para que el sistema de scoring posterior calcule con precisión matemática el impacto regulatorio ponderado por el *log2 Fold-Change*.

## Restricciones
* **Integridad de nomenclatura biomédica en el texto para el LLM:** La sanitización conservadora no debe alterar subcadenas que correspondan a identificadores de genes o familias proteicas. No se aplica *lowercasing* ni eliminación de guiones o barras que forman parte de nombres reconocidos (ej. `HLA-A`, `IL-2R`, `miR-155`).
* **Sin recortes:** el abstract se envía completo al LLM. No se trunca por longitud, para no perder la frase que contiene la evidencia.
* **La forma de comparación nunca sale del componente de verificación:** no se envía al LLM, no se guarda como abstract y no sustituye al texto original en ninguna salida.
* **Reglas de uso de la forma de comparación:**
  * **Verificación de la cita:** la cita normalizada debe ser una subcadena del abstract normalizado (el texto efectivamente enviado al LLM) y tener **al menos 6 palabras**. Una cita más corta no demuestra nada (p. ej. `CD7` aparecería dentro de `CD70`).
  * **Mención del gen:** el símbolo o alguno de sus alias debe aparecer como **palabra completa** (`CD7` no cuenta dentro de `CD70` ni de `CD74`). Se compara también una variante sin guiones, para que `CD-7` equivalga a `CD7`.
* **La dirección transcriptómica no se envía al LLM:** el atributo `UP`/`DOWN` se conserva para el scoring, pero no forma parte del prompt, para no sesgar la respuesta del modelo.
* **Preservación inmutable de polaridad de entrada:** El contenedor de salida debe garantizar la separación estricta mediante estructuras inmutables o esquemas tipados (`dataclasses` congeladas o modelos `Pydantic`) donde cada gen esté indefectiblemente vinculado a su condición `UP` o `DOWN`.
* **Procesamiento puramente local en CPU:** La limpieza y la normalización se ejecutan con librerías estándar (`html`, `re`, `unicodedata`), sin invocar APIs de IA ni dependencias externas lentas.
* **Consumo de memoria RAM acotado:** El pipeline debe operar por lotes de abstracts y genes en memoria, liberando referencias intermedias para no retener cadenas de texto duplicadas.

## Criterios de aceptación
* [ ] **Sanitización exhaustiva de etiquetas sin pérdida de texto:** Dada una muestra sintética de abstract que contenga etiquetas anidadas (`<jats:title>`, `<b>`, `<i>`, `<p>`) y entidades HTML (`&amp;`, `&gt;`), el resultado tras la limpieza no contiene ninguna etiqueta delimitada por `<...>`, el texto biológico legible permanece íntegro y `<p>foo</p><p>bar</p>` da `foo bar` (no `foobar`).
* [ ] **Preservación de la nomenclatura:** Tras la sanitización conservadora, `NF-κB`, `TGF-β`, `CD8+`, `HLA-A`, `IL-2R` y `miR-155` aparecen sin ningún cambio.
* [ ] **Tolerancia de la verificación de citas:** Sobre el abstract de prueba *"Human K12-Fc stimulated the up-regulation of CD25, CD54, and CD69 on human NK cells. NF-κB activation required IL-4Rα and CD70 binding."*, se verifican como presentes las citas de al menos 6 palabras que solo difieren del texto original en mayúsculas, espacios, guion añadido o quitado (`K12 Fc`), tipo de guion (`K12–Fc`), letras griegas escritas (`NF-kappaB`, `IL-4Ralpha`) o una coma omitida.
* [ ] **Rechazo de citas no válidas:** Sobre el mismo abstract, se rechazan una paráfrasis (*"K12-Fc increased CD25 and CD69 on NK cells"*) y cualquier cita de menos de 6 palabras (p. ej. `CD7`).
* [ ] **Mención del gen por palabra completa:** En un abstract que solo menciona `CD70`, el gen `CD7` no se detecta; en uno que menciona `CD-7` o `cd7`, sí.
* [ ] **Inmutabilidad y segregación de listas Up/Down:** Para una ruta de prueba con 4 genes *Up* y 3 genes *Down*, la estructura resultante expone interfaces separadas o propiedades de filtrado deterministas (`resultado.up_genes` y `resultado.down_genes`), confirmando que la intersección entre ambos conjuntos en una misma condición celular es vacía (`len(set(up) & set(down)) == 0`).
* [ ] **Validación tipada de contratos:** Cada abstract y gen asociado cumple al 100 % el esquema de datos definido: el texto del abstract no está vacío y la dirección transcriptómica es estrictamente `"UP"` o `"DOWN"`.
* [ ] **Cobertura de tests unitarios:** La suite de pruebas unitarias (`pytest codigo/tests/test_processing.py`) valida los casos límite (abstracts nulos, abstracts sin etiquetas, cadenas con caracteres no UTF-8) alcanzando una cobertura de código $\ge 90\%$ sobre el módulo de limpieza.
