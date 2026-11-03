"""Demo: imprime el primer prompt generado para un gen.

Se puede lanzar de dos formas (ambas equivalentes):
  - desde codigo/:   python -m consulta_gen CD7 [GO:XXXXXXX] [ruta_excel]
  - como script:     python consulta_gen/__main__.py CD7   (p. ej. el botón Run del IDE)
"""
import sys
from pathlib import Path

# Si se ejecuta como script suelto no hay paquete padre: ponemos codigo/ en sys.path
# (y quitamos consulta_gen/ para que sus módulos no tapen a otros con el mismo nombre).
if not __package__:
    _aqui = Path(__file__).resolve().parent
    sys.path = [p for p in sys.path if Path(p or ".").resolve() != _aqui]
    sys.path.insert(0, str(_aqui.parent))

from consulta_gen import generar_prompts
from consulta_gen._extraer_info import DIR_EXTRAER_INFO, SALIDA


def localizar_excel(ruta=None) -> Path:
    """SALIDA es relativa al directorio desde el que se ejecutó la Fase 1: probamos varios sitios."""
    candidatos = [Path(ruta)] if ruta else [Path(SALIDA), DIR_EXTRAER_INFO / SALIDA]
    for c in candidatos:
        if c.exists():
            return c
    raise FileNotFoundError("No encuentro el Excel de la Fase 1. Probé: "
                            + ", ".join(str(c) for c in candidatos))


if __name__ == "__main__":
    gen = sys.argv[1] if len(sys.argv) > 1 else "CD7"
    go_id = sys.argv[2] if len(sys.argv) > 2 else None
    ruta = sys.argv[3] if len(sys.argv) > 3 else None
    prompts = generar_prompts(str(localizar_excel(ruta)), gen, go_id)
    print(f"{len(prompts)} prompts para {gen}")
    if prompts:
        print("--- SYSTEM ---\n" + prompts[0].system + "\n--- USER ---\n" + prompts[0].user)
