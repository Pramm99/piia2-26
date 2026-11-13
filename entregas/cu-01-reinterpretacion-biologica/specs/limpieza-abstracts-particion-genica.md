# Spec: Sanitización de Abstracts Biomédicos y Dirección de Expresión Génica (Up/Down)

## Qué hay que construir
Un componente de procesamiento y sanitización de texto que ejecute tres responsabilidades. Está repartido entre `limpiar_texto` de la Fase 1 (`codigo/fase1_ingesta/abstracts.py`), `codigo/fase2_inferencia/limpieza.py` y el filtro de mención del gen (`codigo/fase1_ingesta/relevancia.py`, usado por `fase2_inferencia/casos.py`):

1. **Sanitización del texto que lee el LLM (normalización conservadora, `limpiar_texto` y `limpiar_abstract`):** procesar el título y el abstract crudos descargados de la literatura científica.
   * **Pasos, en este orden:**
     1. Desescapar las entidades HTML (`&amp;`, `&lt;`, `&gt;`, `&plusmn;`…). Va primero porque algunos títulos traen la etiqueta escapada (`CD8&lt;sup&gt;+&lt;/sup&gt;`).
     2. Quitar **solo las etiquetas HTML conocidas**, no cualquier texto entre «<» y «>». Europe PMC mezcla etiquetas con signos del propio texto («p < 0.001», «(<20%)»), y una expresión genérica borraría el texto que hay entre ellos:
        * fin de título (`</h1>`…`</h6>`) → «: », para que el rótulo no se pegue a la frase («Conclusion: DOT1L»);
        * etiquetas de bloque (`h1-h6`, `p`, `br`, `div`, `li`, `ul`, `ol`, `table`, `tr`, `td`, `th`) → un espacio, para que no se peguen las palabras que separaban;
        * etiquetas de línea (`i`, `b`, `u`, `em`, `strong`, `sup`, `sub`, `span`, `a`, `sc`, `small`, `font`, `tt`, `big`, `inf`, `mml:*`) → nada, para no partir un nombre («IL-1<sup>β</sup>» → «IL-1β»).
     3. Colapsar los espacios y saltos de línea repetidos.
   * **Lo que no se toca:** la nomenclatura científica de genes, proteínas, mutaciones y complejos moleculares (ej. `p53`, `NF-κB`, `TGF-β`, `CD8+`, `STAT3`). No se cambian mayúsculas, guiones ni letras griegas.
   * **Dónde se aplica:** la caché de abstracts guarda el texto en crudo, y la limpieza se aplica al leerlo.
   * **Segmentación:** el abstract limpio se parte en frases numeradas (`segmentar_frases`, `[S1]…[Sn]`; el título es `[T]`). No se corta tras abreviaturas («et al.», «e.g.») ni en decimales.
2. **Forma de comparación (normalización fuerte, `forma_comparacion`):** una función independiente que produce una versión del texto **solo para comparar**, nunca para enviarla al LLM. Se usa en la verificación de la cita del LLM ([ADR-003](../decisions/adr-003-control-alucinaciones-unknown.md)). Aplica, en este orden:
   1. Normalización Unicode `NFKC` (unifica caracteres equivalentes, p. ej. `µ` y `μ`).
   2. Paso a minúsculas (`casefold`).
   3. Unificación de todos los guiones (`‐ ‑ ‒ – — −`) en `-`.
   4. Letras griegas escritas como palabras (`α`→`alpha`, `β`→`beta`, `γ`→`gamma`, `δ`→`delta`, `κ`→`kappa`, etc.).
   5. Sustitución de guiones y signos de puntuación por espacios, y colapso de espacios repetidos.
3. **Mención del gen (`patron_gen` y `menciona_gen`):** antes de llamar al LLM se comprueba que el título o el abstract nombran al gen. Si no lo hacen, la pregunta se cierra con `no_menciona_gen` sin coste. Esta comprobación no usa la forma de comparación, sino una propia que conserva las mayúsculas:
   * **Qué formas cuentan:** el símbolo oficial y hasta 8 alias de MyGene, de al menos 3 caracteres y no numéricos, buscados como **palabra completa** (`CD7` no cuenta dentro de `CD70`). Los guiones se ignoran (`CD-7` equivale a `CD7`), pero un guion no pega el gen a la palabra de al lado: también se mira el texto con los guiones como espacio (`CXCR3-mediated`, `HVEM-Ig`, `2,5-OAS1`, `IL-4R-dependent`). Las griegas se reducen a la letra que usa HGNC (`IL-4Rα` = `IL4Ra`, `IκBζ` = `IKBZ`, `PKCθ` = `PKCQ`; α β γ δ ε ζ θ κ λ). También cuenta el nombre completo del gen de MyGene.
   * **Mayúsculas:** una coincidencia escrita toda en minúsculas no cuenta como mención, porque muchos alias son también palabras corrientes.

**Dirección de expresión (Up / Down).** Un gen está en una sola de las dos listas de CIMUS: la de rutas enriquecidas con genes *up* («rutas activadas») o la de genes *down* («rutas suprimidas»). Cada fila conserva su lista de origen en la columna `Estado_Original` («Activada» o «Suprimida») en todas las hojas de la Fase 1. La salida de la Fase 2 (`fase2_resultados.xlsx`) no la copia: el scoring la recupera de `Triaje_polaridad` por el par (gen, ruta). De ella se deduce la dirección del gen (*up* o *down*), que usa el scoring (Fase 3). No hay una estructura `up_genes` / `down_genes` aparte, porque la Fase 2 no usa la dirección: el signo del gen sobre la ruta no depende de ella.

Este componente se sitúa como paso previo obligatorio a la inferencia, garantizando que se reciban abstracts limpios, que las comprobaciones de la salida del LLM toleren diferencias tipográficas mínimas y que se conozca la lista de origen de cada gen.

## Por qué
Los abstracts biomédicos extraídos de APIs como Europe PMC contienen marcado HTML de las maquetaciones editoriales: en la caché del 2026-11-09 (33.060 abstracts) aparecen sobre todo `<h4>` (rótulos de sección), `<i>`, `<sup>`, `<sub>` y `<b>`. Enviar etiquetas al modelo consume tokens y puede confundirlo. Sin embargo, un limpiador genérico destruiría símbolos fundamentales en genética (guiones, letras griegas, signos de adición en subtipos inmunes) o borraría texto: un filtro que quitara todo lo que hay entre «<» y «>» perdería texto en el 3 % de los abstracts, y quitar las etiquetas sin dejar separador pegaría los rótulos a la frase («ConclusionDOT1L») en el 18 %.

Por otro lado, el control de alucinaciones (ADR-003) compara la cita que devuelve el LLM con el abstract. Una comparación exacta fallaría por diferencias sin significado (un guion largo en lugar de uno corto, `NF-kappaB` en lugar de `NF-κB`, una coma omitida) y convertiría en `UNKNOWN` respuestas correctas. Por eso hacen falta **dos niveles**: uno conservador, que preserva la nomenclatura para el LLM, y otro fuerte, usado solo para comparar.

La dirección del gen se conserva porque el scoring la necesita: el efecto real del gen sobre la ruta es su dirección de expresión por su signo sobre la ruta. No se envía al LLM para no sesgar su respuesta.

## Restricciones
* **Integridad de nomenclatura biomédica en el texto para el LLM:** La sanitización conservadora no debe alterar subcadenas que correspondan a identificadores de genes o familias proteicas. No se aplica *lowercasing* ni eliminación de guiones o barras que forman parte de nombres reconocidos (ej. `HLA-A`, `IL-2R`, `miR-155`).
* **Solo etiquetas conocidas:** una etiqueta que no está en la lista (p. ej. `<jats:…>` o `<formula>`) se deja en el texto. En la caché actual no aparece ninguna etiqueta `jats`, y `formula` aparece 4 veces en 33.060 abstracts.
* **Sin recortes:** el abstract se envía completo al LLM. No se trunca por longitud, para no perder la frase que contiene la evidencia.
* **La forma de comparación nunca sale del componente de verificación:** no se envía al LLM, no se guarda como abstract y no sustituye al texto original en ninguna salida.
* **Reglas de uso de la forma de comparación:**
  * **Verificación de la cita:** la cita normalizada debe aparecer como palabras enteras en la frase indicada del texto enviado al LLM, también normalizada, y tener **al menos 6 palabras**. Una cita más corta no demuestra nada (p. ej. `CD7` aparecería dentro de `CD70`).
* **La dirección transcriptómica no se envía al LLM:** `Estado_Original` se conserva para el scoring, pero no forma parte del prompt, para no sesgar la respuesta del modelo.
* **Procesamiento local, sin red:** La limpieza y la normalización (`limpiar_texto`, `limpiar_abstract`, `forma_comparacion`, `segmentar_frases` y la mención del gen) solo usan la librería estándar (`html`, `re`, `unicodedata`). La única excepción es `pandas`, que se usa para reconocer las celdas vacías del Excel. No hacen ninguna petición de red ni llaman a ningún modelo.

## Criterios de aceptación
Los marcados están cubiertos por `codigo/tests/test_limpieza.py` (pytest, sin red).

* [x] ✅ **Sanitización de etiquetas sin pérdida de texto:**
  * dada una muestra con etiquetas HTML conocidas y entidades (`&amp;`, `&gt;`), el resultado no contiene esas etiquetas;
  * `<p>foo</p><p>bar</p>` da `foo bar` (no `foobar`);
  * `<h4>Conclusion</h4>DOT1L` da `Conclusion: DOT1L`;
  * `IL-1<sup>β</sup>` da `IL-1β`;
  * `p < 0.05` y `(<20%)` se conservan.
* [x] ✅ **Preservación de la nomenclatura:** Tras la sanitización conservadora, `NF-κB`, `TGF-β`, `CD8+`, `HLA-A`, `IL-2R` y `miR-155` aparecen sin ningún cambio. (`test_nomenclatura_intacta`)
* [x] ✅ **Tolerancia de la verificación de citas:** Sobre el abstract de prueba *"Human K12-Fc stimulated the up-regulation of CD25, CD54, and CD69 on human NK cells. NF-κB activation required IL-4Rα and CD70 binding."*, se verifican como presentes las citas de al menos 6 palabras que solo difieren del texto original en:
  * mayúsculas o espacios;
  * un guion cambiado por un espacio (`K12 Fc`) o por otro tipo de guion (`K12–Fc`);
  * letras griegas escritas (`NF-kappaB`, `IL-4Ralpha`);
  * una coma omitida.

  Un guion suprimido sin espacio (`K12Fc`) **no** se verifica.
* [x] ✅ **Rechazo de citas no válidas:** Sobre el mismo abstract, se rechazan una paráfrasis (*"K12-Fc increased CD25 and CD69 on NK cells"*) y cualquier cita de menos de 6 palabras (p. ej. `CD7`). (`test_cita_rechazada`)
* [x] ✅ **Mención del gen por palabra completa:** En un texto que solo menciona `CD70`, el gen `CD7` no se detecta; en uno que menciona `CD-7`, sí; `cd7` en minúsculas no cuenta. `CXCR3-mediated`, `HVEM-Ig` e `IL-4R-dependent` nombran a CXCR3, TNFRSF14 e IL4R; `IκBζ`, `PKCθ` y `CD3ε`, a NFKBIZ, PRKCQ y CD3E. (`test_mencion_por_palabra_completa`, `test_mencion_con_guion_pegado_a_otra_palabra`, `test_mencion_con_griegas`)
* [x] ✅ **Sin red:** `fase2_inferencia/limpieza.py` y la parte de limpieza de `fase1_ingesta/abstracts.py` no usan la red: ninguna de sus funciones llama a `requests` ni a un cliente de LLM (comprobado leyendo el código; `test_limpieza.py` no necesita conexión).
* [x] ✅ **Dirección conservada:** todas las filas de `Con_abstract` llevan `Estado_Original` con «Activada» o «Suprimida», ningún gen aparece con los dos valores y cada fila de `Por_ruta` de la Fase 2 se puede unir con su `Estado_Original` por (gen, ruta). (`tests/test_fase1_e2e.py::test_direccion_conservada_en_con_abstract` y `::test_fases_2_y_3_sobre_la_salida_de_la_fase1`.)
* [x] ✅ **Cobertura de tests unitarios:** La suite de `pytest` (`codigo/tests/test_limpieza.py`) valida estos criterios y algunos casos límite (valores vacíos del Excel, idempotencia). La cobertura, que debe ser $\ge 90\%$ sobre el módulo de limpieza, es del 97 % en `fase2_inferencia/limpieza.py` (`python -m pytest --cov=fase2_inferencia` desde `codigo/`, con `pytest-cov`).
* [x] ✅ **Frases tras «et al.»:** `segmentar_frases` no corta la frase después de «et al.» (compara las dos últimas palabras con las abreviaturas). `"As shown by Smith et al. NK cells rose. End."` da dos frases: `"As shown by Smith et al. NK cells rose."` y `"End."`. (`tests/test_limpieza.py`.)
