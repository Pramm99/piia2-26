"""Fase 2 desde la línea de comandos.

Ejecución completa (llama a los modelos; reanudable, el registro va a codigo/data/):
  python -m consulta_gen ejecutar [principal|-] [secundario|-|ninguno] [gen|-] [GO:XXXXXXX|-] [ruta_excel|-]
  Escribe codigo/data/fase2_resultados.xlsx (hojas Por_ruta, Preguntas y Resumen). Los modelos son los
  nombres de cliente.MODELOS; por defecto, la pareja propuesta (pendiente de confirmar en el ADR-005).
Demo: imprime el primer prompt generado para un gen (sin llamar a ningún modelo):
  python -m consulta_gen CD7 [GO:XXXXXXX|-] [ruta_excel|-] [v0_original|v1_proceso]
Se puede lanzar también como script (python consulta_gen/__main__.py …, p. ej. el botón Run del IDE).
Un «-» deja ese argumento por defecto.
"""
import sys
from pathlib import Path

# Si se ejecuta como script suelto no hay paquete padre: ponemos codigo/ en sys.path
# (y quitamos consulta_gen/ para que sus módulos no tapen a otros con el mismo nombre).
if not __package__:
    _aqui = Path(__file__).resolve().parent
    sys.path = [p for p in sys.path if Path(p or ".").resolve() != _aqui]
    sys.path.insert(0, str(_aqui.parent))

from consulta_gen import CONFIG_V0, CONFIG_V1, V1_PROCESO, preparar_prompts
from consulta_gen._extraer_info import DIR_EXTRAER_INFO, SALIDA

PRINCIPAL, SECUNDARIO = "groq-gpt-oss-120b", "gemini-3.5-flash-lite"  # propuesta del benchmark (ADR-005)


def localizar_excel(ruta=None) -> Path:
    """SALIDA es relativa al directorio desde el que se ejecutó la Fase 1: probamos varios sitios."""
    candidatos = [Path(ruta)] if ruta else [Path(SALIDA), DIR_EXTRAER_INFO / SALIDA]
    for c in candidatos:
        if c.exists():
            return c
    raise FileNotFoundError("No encuentro el Excel de la Fase 1. Probé: "
                            + ", ".join(str(c) for c in candidatos))


def ejecutar_cli(arg) -> None:
    from consulta_gen.cliente import MODELOS, ClienteOpenAICompatible
    from consulta_gen.pipeline import ejecutar_fase2
    from consulta_gen.resultados import FICHERO_RESULTADOS
    nombres = [arg(2) or PRINCIPAL] + ([] if arg(3) == "ninguno" else [arg(3) or SECUNDARIO])
    clientes = [ClienteOpenAICompatible(MODELOS[n]) for n in nombres]
    df_p, df_r, resumen, cuenta = ejecutar_fase2(str(localizar_excel(arg(6))), clientes, arg(4), arg(5))
    print(f"Casos: {cuenta}")
    print(f"Llamadas {resumen.llamadas} | reutilizadas {resumen.reutilizadas} | pendientes {resumen.pendientes} "
          f"| tokens {resumen.tokens}")
    if not df_r.empty:
        print(df_r.groupby(["Estado", "Signo_ruta"]).size().to_string())
        print(f"Resultados en {FICHERO_RESULTADOS}")


if __name__ == "__main__":
    arg = lambda i: sys.argv[i] if len(sys.argv) > i and sys.argv[i] != "-" else None
    if arg(1) == "ejecutar":
        ejecutar_cli(arg)
        sys.exit(0)
    gen, go_id, ruta = arg(1) or "CD7", arg(2), arg(3)
    cfg = CONFIG_V1 if arg(4) == V1_PROCESO else CONFIG_V0
    prompts, cuenta = preparar_prompts(str(localizar_excel(ruta)), cfg, gen, go_id)
    print(f"{len(prompts)} prompts {cfg.version} para {gen} | {cuenta}")
    if prompts:
        print("--- SYSTEM ---\n" + prompts[0].system + "\n--- USER ---\n" + prompts[0].user)
