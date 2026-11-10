# Gold set provisional: genes up y down (2026-11-10)

## Qué es
100 preguntas (gen, PMID, proceso núcleo) de las dos listas de CIMUS, porque la Fase 2 procesa las dos (1.123 preguntas de genes up y 571 de genes down con la Fase 1 del 2026-11-09). Las etiquetas son de anotadores Claude a ciegas; siguen haciendo falta las de CIMUS.

## Cómo se montó
1. **100 casos: 65 up y 35 down.**
   - **Up (65):**
     - una muestra aleatoria estratificada de 60 casos (11 con Polaridad_GO «+1», 10 con «−1» y 39 sin ella; máximo 5 por gen), con CD7 / PMID 10652336 (G11) dentro;
     - los 2 `NO_EFFECT` (G104 y G114), la clase rara, que salieron de los candidatos de `buscar_neutros.py`;
     - 3 sorteados entre los demás candidatos de esa búsqueda (G77, G96 y G116).
   - **Down (35, G128–G162):**
     - sorteados entre las preguntas de las rutas suprimidas;
     - mismos estratos de GO que la muestra up, en proporción (6 «+1», 6 «−1» y 23 sin signo);
     - máximo 5 por gen: salen 22 genes.
2. **Comprobación por código contra los Excels de CIMUS** (`codigo/tools_cimus/`):
   - cada gen up está en la lista de activadas y no en la de suprimidas, y al revés para los down;
   - todas las rutas de cada caso están enriquecidas con ese gen en su lista;
   - ningún gen aparece en las dos listas;
   - 0 errores.
3. **Etiquetado a ciegas** (`guia_etiquetado.md`):
   - **Anotadores:** dos Claude independientes (A y B) por caso, con ids anónimos y mezclados y sin ver al otro anotador, y un árbitro en los desacuerdos. Los down se etiquetaron además sin PMID ni polaridad de GO.
   - **Acuerdo:** la etiqueta final y la segunda coinciden en 99 de 100 casos (κ = 0,98; el desacuerdo es G52). En los 35 down, A y B coinciden en el efecto en 34 (κ = 0,96), y un caso más tiene el mismo efecto con distinto motivo.
   - **Árbitro de los down:** con las dos propuestas a la vista, resolvió los 2 desacuerdos y revisó los 5 casos con confianza baja en alguno de los anotadores y el único neutro. No cambió ninguna etiqueta de las revisadas.
   - **Citas de los down:** todas verificadas en su frase, con 6 palabras o más.

| Caso | Gen | A | B | Final | Motivo |
|---|---|---|---|---|---|
| G138 | GSN | INCREASES | NO_CLEAR_EFFECT (process_not_addressed) | NO_CLEAR_EFFECT (process_not_addressed) | El «capping» solo aparece en la frase de contexto; los resultados tratan de la unión a PPI (reglas 9, 11 y 12). |
| G130 | BCL9L | NO_CLEAR_EFFECT (process_not_addressed) | NO_CLEAR_EFFECT (effect_of_other_molecule) | NO_CLEAR_EFFECT (process_not_addressed) | El abstract no estudia la morfogénesis celular. |

## Resultado
- **100 casos:** NO_CLEAR_EFFECT 65, INCREASES 20, DECREASES 12 y NO_EFFECT 3.
  - **Up:** 49 / 9 / 5 / 2.
  - **Down:** 16 / 11 / 7 / 1.
- **Más signos en los down:** la proporción de signos es mayor entre los down (18 de 35) que entre los up (14 de 65).
- **Ficheros:**
  - `gold_provisional.jsonl`, con las etiquetas finales, congelado con SHA-256 `59158a2d…` (`gold_provisional.sha256`);
  - `doble.jsonl`, con la segunda etiqueta de cada caso;
  - `../gold_casos.jsonl` (la selección, con la información para evaluar) y `../plantilla_etiquetado.jsonl` (a ciegas).
- **Benchmark** (`codigo/data/benchmark/`, informe `../informe_gold_provisional.txt`), umbral 80:
  - Gemini 3.5 Flash-Lite: 100 de 100; exactitud 84 %, precisión de los signos 72 %, cobertura 40 % y recall de UNKNOWN 85 %; por lista, up 83 % / 61 % / 35 % / 82 % y down 86 % / 88 % / 49 % / 94 %;
  - gpt-oss-120b (Groq): 100 de 100, JSON válido 96/100; exactitud 85 %, precisión 79 %, cobertura 34 % y recall de UNKNOWN 89 %; por lista, up 85 % / 65 % / 31 % / 86 % y down 86 % / 100 % / 40 % / 100 %;
  - los dos modelos dan la misma clase en 87 de 100 casos, y solo en G133 dan signos opuestos.
- **Mantenimiento:** con una Fase 1 nueva, `python evaluacion/seleccionar_gold.py <excel> [datos]` rehace el gold sin volver a sortear; cualquier cambio de casos o etiquetas se anota aquí con su motivo.
