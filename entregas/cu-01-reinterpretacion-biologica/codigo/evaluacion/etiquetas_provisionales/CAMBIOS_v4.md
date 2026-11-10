# Gold set provisional v4: genes up y down (2026-11-10)

## Por qué
El gold v3 solo tenía casos de las rutas activadas (genes upregulados): `seleccionar_gold.py` y `buscar_neutros.py`
filtraban `Estado_Original == "Activada"`. La Fase 2 procesa las dos listas de CIMUS (1.123 preguntas up y 571 down
con la Fase 1 del 2026-11-09), así que el benchmark no medía nada sobre los genes downregulados.

## Qué se hizo
1. **100 casos: 65 up y 35 down** (`python evaluacion/seleccionar_gold.py <Excel Fase 1> <datos> --v4`).
   - **Up (65, del gold v3, con sus etiquetas):**
     - los 60 de la muestra aleatoria del v2;
     - los 2 `NO_EFFECT` (G104 y G114), la clase rara;
     - 3 sorteados entre los demás añadidos del v3 (G77, G96 y G116).

     Salen 59 casos añadidos en el v3, que se habían buscado por contener una negación. CD7 / PMID 10652336 (G11) sigue dentro.
   - **Down (35, nuevos, G128–G162):**
     - sorteados entre las preguntas de las rutas suprimidas;
     - mismos estratos de GO que la muestra original, en proporción (6 «+1», 6 «−1» y 23 sin signo);
     - máximo 5 por gen: salen 22 genes.
2. **Comprobación por código contra los Excels de CIMUS** (`codigo/tools_cimus/`):
   - cada gen up está en la lista de activadas y no en la de suprimidas, y al revés para los down;
   - todas las rutas de cada caso están enriquecidas con ese gen en su lista;
   - ningún gen aparece en las dos listas;
   - 0 errores.
3. **Etiquetado a ciegas de los 35 down**, como en el v3:
   - **Anotadores:** dos Claude independientes (A y B) con ids anónimos y mezclados (D01–D35), sin PMID, sin polaridad de GO y sin ver al otro anotador.
   - **Acuerdo A-B en el efecto:** 34/35 (κ = 0,96). Un caso más con el mismo efecto y distinto motivo.
   - **Árbitro:** un tercer anotador, con las dos propuestas a la vista, resolvió los 2 desacuerdos y revisó los 5 casos con confianza baja en alguno de los anotadores y el único neutro. No cambió ninguna etiqueta de las revisadas.
   - **Citas:** todas verificadas en su frase, con 6 palabras o más.

| Caso | Gen | A | B | Final | Motivo |
|---|---|---|---|---|---|
| G138 | GSN | INCREASES | NO_CLEAR_EFFECT (process_not_addressed) | NO_CLEAR_EFFECT (process_not_addressed) | El «capping» solo aparece en la frase de contexto; los resultados tratan de la unión a PPI (reglas 9, 11 y 12). |
| G130 | BCL9L | NO_CLEAR_EFFECT (process_not_addressed) | NO_CLEAR_EFFECT (effect_of_other_molecule) | NO_CLEAR_EFFECT (process_not_addressed) | El abstract no estudia la morfogénesis celular. |

## Resultado
- **100 casos:** NO_CLEAR_EFFECT 65, INCREASES 20, DECREASES 12 y NO_EFFECT 3.
  - **Up:** 49 / 9 / 5 / 2.
  - **Down:** 16 / 11 / 7 / 1.
- **Más signos en los down:** la proporción de signos es mayor entre los down (18 de 35) que entre los up (14 de 65).
- **Etiquetas provisionales:** son de anotadores Claude; siguen haciendo falta las de CIMUS.
- **Ficheros:**
  - `gold_provisional_v4.jsonl`, con las etiquetas finales, congelado con SHA-256 `59158a2d…`;
  - `doble_v4.jsonl`, con la segunda etiqueta: la del v3 para los up y la del anotador B para los down;
  - el gold v3 completo (casos, plantilla e informe v5), archivado en `evaluacion/v3/`.
- **Benchmark v6** (`codigo/data/benchmark_v6/`, informe `informe_gold_provisional_v6.txt`):
  - Gemini, con `v2_veredicto`, responde 100 de 100. El registro parte de una copia del de Gemini del v5: se reutilizaron las 65 respuestas up y se llamó solo para los 35 down (22 llamadas);
  - exactitud 84 %, precisión de los signos 72 %, cobertura 40 % y recall de UNKNOWN 85 %;
  - por lista: up 83 % / 61 % / 35 % / 82 % y down 86 % / 88 % / 49 % / 94 %;
  - gpt-oss-120b (Groq) responde 100 de 100, con 60 llamadas y 4 respuestas reutilizadas del v5:
    - exactitud 85 %, precisión 79 %, cobertura 34 % y recall de UNKNOWN 89 %;
    - JSON válido 96/100;
    - por lista: up 85 % / 65 % / 31 % / 86 % y down 86 % / 100 % / 40 % / 100 %;
  - los dos modelos dan la misma clase en 87 de 100 casos, y solo en G133 dan signos opuestos.
- **Corrección en `evaluar_gold.py`:** `construir_preguntas` solo cargaba el universo de las rutas activadas, así que fallaba con los casos down. Ahora carga las dos listas.
- **Pendiente:**
  - `buscar_neutros.py` sigue mirando solo las rutas activadas.
