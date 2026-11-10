# Gold set provisional v3: 4 clases y casos neutros (2026-11-10)

## Por qué
El gold v2 no tenía ningún caso neutro (efecto `NO_EFFECT`, «el gen no cambia el proceso»): cualquier neutro de un
modelo contaba como fallo y la clase no se podía medir.

## Qué se hizo
1. **Guía a 4 clases** (`guia_etiquetado.md`): `INCREASES` (+1), `DECREASES` (−1), `NO_EFFECT` (neutro) y
   `NO_CLEAR_EFFECT` (UNKNOWN). La negación de un resultado sobre este gen y este proceso pasa a ser `NO_EFFECT`.
2. **Candidatos a neutro** (`buscar_neutros.py`), entre las preguntas de las rutas activadas que no estaban en el
   gold ni en el conjunto de desarrollo:
   - 1.ª ronda: frases con negación que nombran al gen, máx. 2 por gen → 51 candidatos;
   - 2.ª ronda (`--amplia`, más formas de negación, sin máximo por gen) → 123 candidatos, cribados por 4 subagentes
     («¿el abstract dice que este gen no cambia este proceso?»): 1 «sí» y 12 «dudosos» pasan al etiquetado.
3. **Reetiquetado a ciegas de todo** (los 60 del v2 + 51 + 13 = 124 casos), con ids anónimos y mezclados, de modo
   que los anotadores no sabían qué casos eran candidatos. Dos anotadores Claude independientes por caso (A y B);
   los desacuerdos, un tercero (árbitro) con las dos propuestas a la vista.
   - Acuerdo A-B en el efecto: 119/124; desacuerdos resueltos por el árbitro: 5.
   - Todas las citas verificadas en su frase.
4. **Entran todos los casos con doble etiqueta**, no solo los neutros, para no elegir casos por su etiqueta.
5. **Revisión final** de todas las etiquetas con confianza media o baja y de los neutros (L084/G104 y L123 se
   confirman). Dos correcciones de coherencia con la regla 11 (un signo que sale solo de una frase de contexto no
   cuenta):

| Caso | Gen | Etiqueta A=B | Final | Motivo |
|---|---|---|---|---|
| G90 | ICOS | INCREASES | NO_CLEAR_EFFECT (process_not_addressed) | El papel de ICOS en el cambio de isotipo solo aparece como contexto (ratones deficientes); el resultado propio no lo mide (regla 11). Revisión de coherencia con G32, G49 y G53. |
| G123 | SOX4 | INCREASES | NO_CLEAR_EFFECT (process_not_addressed) | La diferenciación B solo aparece en una frase de contexto (S1); los resultados tratan proliferación y viabilidad (regla 11). Revisión de coherencia con G32, G49 y G53. |

## Resultado
- {len(finales)} casos: {dict(cuenta)}.
- Los candidatos se eligieron por contener una negación: el gold v3 tiene más abstracts con negaciones que el
  universo, y sigue habiendo muy pocos neutros, porque en los abstracts casi nunca se informa de que un gen NO
  cambie un proceso.
- Etiquetas PROVISIONALES de anotadores Claude: hacen falta las de CIMUS.
- Congelado con SHA-256 `{sha[:8]}…` antes de calcular métricas.

## Casos del v2 cuya etiqueta cambia
| Caso | Gen | v2 | v3 | Decisión |
|---|---|---|---|---|
| G36 | KLRC1 | NO_CLEAR_EFFECT (effect_of_other_molecule) | DECREASES (none) | A=B |
| G52 | SOX4 | INCREASES (none) | NO_CLEAR_EFFECT (process_not_addressed) | árbitro |
