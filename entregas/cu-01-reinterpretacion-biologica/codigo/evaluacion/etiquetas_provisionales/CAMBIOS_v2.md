# Cambios del gold set provisional v1 → v2 (2026-11-09)

Motivo general: la Fase 1 se volvió a ejecutar con el arreglo de `limpiar_texto` (texto entre «<» y «>» y rótulos pegados) y con el código de los commits 62cbc14 y 32cef10. La plantilla se regeneró con `seleccionar_gold.py --actualizar` (mismos ids). Las etiquetas v1 siguen en `gold_provisional.jsonl` (sha f89d78f2…).

| Caso | Cambio | Etiqueta | Motivo |
|---|---|---|---|
| G14 | re-etiquetado (claude_E, a ciegas) | NO_CLEAR_EFFECT → NO_CLEAR_EFFECT | texto recuperado por el arreglo de limpiar_texto |
| G34 | re-etiquetado (claude_E, a ciegas) | NO_CLEAR_EFFECT → NO_CLEAR_EFFECT | texto recuperado por el arreglo de limpiar_texto |
| G61 | caso nuevo (claude_E, a ciegas) | — → NO_CLEAR_EFFECT | sustituye a un caso que ya no existe en la Fase 1 nueva |
| G62 | caso nuevo (claude_E, a ciegas) | — → INCREASES | sustituye a un caso que ya no existe en la Fase 1 nueva |
| G63 | caso nuevo (claude_E, a ciegas) | — → NO_CLEAR_EFFECT | sustituye a un caso que ya no existe en la Fase 1 nueva |
| G49 | corrección de la verificación (2 re-etiquetados ciegos y adjudicación) | INCREASES → NO_CLEAR_EFFECT | el signo salía solo de la frase de introducción S1 (regla 11) |
| G53 | corrección de la verificación (2 re-etiquetados ciegos y adjudicación) | INCREASES → NO_CLEAR_EFFECT | el signo salía solo de la frase de introducción S1 (regla 11) |
| G01 | eliminado | NO_CLEAR_EFFECT → — | el caso ya no existe en la Fase 1 nueva |
| G47 | eliminado | NO_CLEAR_EFFECT → — | el caso ya no existe en la Fase 1 nueva |
| G56 | eliminado | INCREASES → — | el caso ya no existe en la Fase 1 nueva |

Doble etiquetado: G47 y G56 salen; G62 y G63 los etiqueta claude_F a ciegas (`anotador_F_doble_v2.jsonl`). Fichero `doble_v2.jsonl`, 12 casos.

Congelado: `gold_provisional_v2.sha256` (8453e04adbc2ce18…), antes de calcular ninguna métrica de la v2.
