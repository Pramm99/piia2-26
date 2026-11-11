"""Fase 3 desde la línea de comandos (sin red ni LLM; se puede repetir cuantas veces se quiera):
  python -m scoring [excel_fase1|-] [excel_fase2|-] [log2fc.xlsx|.csv]
Escribe codigo/data/fase3_scoring.xlsx (hojas Por_ruta, Por_par y Resumen). Por defecto lee
codigo/extraer_info/fase1_dataset_abstracts.xlsx y codigo/data/fase2_resultados.xlsx. Un «-» deja ese
argumento por defecto.
"""
import sys
from pathlib import Path

# Como script suelto (python scoring/__main__.py): codigo/ en sys.path para importar los paquetes.
if not __package__:
    _aqui = Path(__file__).resolve().parent
    sys.path = [p for p in sys.path if Path(p or ".").resolve() != _aqui]
    sys.path.insert(0, str(_aqui.parent))

from scoring import config
from scoring.nps import calcular, escribir


def main(argv) -> None:
    arg = lambda i: argv[i] if len(argv) > i and argv[i] != "-" else None
    pares, rutas, res = calcular(arg(1) or config.FICHERO_FASE1, arg(2) or config.FICHERO_FASE2, arg(3))
    print(pares.groupby(["Estado_par", "Signo_par"]).size().to_string())
    print(rutas["Lectura"].value_counts().to_string())
    afectadas = int((rutas["n_pendiente"] > 0).sum())
    if afectadas:
        print(f"⏸️ {int(rutas['n_pendiente'].sum())} pares pendientes de la Fase 2 en {afectadas} rutas: "
              "relanza la Fase 2 y repite el scoring.")
    print(f"Resultados en {escribir(pares, rutas, res)}")


if __name__ == "__main__":
    main(sys.argv)
