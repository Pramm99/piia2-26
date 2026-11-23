"""Fase 4: la lógica de la interfaz (TypeScript), probada con node (sin navegador ni red).

* Las pruebas de fase4_frontend/pruebas/ (node --test): «Tu criterio» y el Excel de resultados.
* «Tu criterio» en pantalla (src/lectura.ts) da lo mismo que fase3_scoring/nps.py con los mismos signos: rutas
  reales ya ejecutadas en codigo/data/frontend/ (si están) y una sintética, cambiando cada gen a cada signo y varios
  genes a la vez.
Sin node, se saltan.
"""
import itertools
import json
import random
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from fase3_scoring import config, nps
from fase3_scoring.nps import aplicar_criterio, tabla_rutas

WEB = Path(__file__).resolve().parents[1] / "fase4_frontend"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="hace falta node (el de la interfaz)")

SIGNOS = ("+1", "-1", "neutro")
CAMPOS = ("NPS", "Lectura", "NPS_log2FC", "Lectura_log2FC", "Sensible_al_peso", "Cobertura", "n_activan",
          "n_inhiben", "n_pendiente")
CAMPOS_PAR = ("Gen", "Direccion", "Signo_par", "Estado_par", "Origen", "Motivos", "Log2FC", "Contribucion")


def test_pruebas_de_la_interfaz():
    r = subprocess.run([NODE, "--test", "pruebas/lectura.test.ts", "pruebas/acumulado.test.ts"], cwd=WEB,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr


def _pares(monkeypatch, f1, f2, log2fc) -> pd.DataFrame:
    """Los pares de la Fase 3 con todas sus columnas (calcular solo devuelve las de salida; tabla_rutas usa más)."""
    capturados = []
    original = nps.tabla_pares
    monkeypatch.setattr(nps, "tabla_pares", lambda *a, **k: capturados.append(original(*a, **k)) or capturados[-1])
    nps.calcular(f1, f2, log2fc)
    monkeypatch.setattr(nps, "tabla_pares", original)
    return capturados[0]


def _registros(df: pd.DataFrame):
    return json.loads(df.to_json(orient="records"))


def _casos_de_una_ruta(pares: pd.DataFrame, con_log2fc: bool, azar: random.Random):
    """(criterio, ruta automática, pares automáticos): cada gen a cada signo y cinco combinaciones de varios genes."""
    go = pares["GO_ID"].iloc[0]
    auto = _registros(tabla_rutas(pares, con_log2fc))[0]
    genes = sorted(pares["Gen"])
    criterios = [{g: s} for g, s in itertools.product(genes, SIGNOS)]
    criterios += [{g: azar.choice(SIGNOS) for g in azar.sample(genes, min(len(genes), azar.randint(2, 6)))}
                  for _ in range(5)]
    return [(go, c, auto) for c in criterios]


def _comparar(rutas_pares, con_log2fc: bool):
    azar = random.Random(41)
    casos, esperado = [], []
    for pares in rutas_pares:
        for go, criterio, auto in _casos_de_una_ruta(pares, con_log2fc, azar):
            fase3 = tabla_rutas(aplicar_criterio(pares, {(g, go): s for g, s in criterio.items()}), con_log2fc)
            esperado.append(_registros(fase3)[0])
            casos.append({"ruta": auto, "pares": _registros(pares[list(CAMPOS_PAR)]), "criterio": criterio})
    r = subprocess.run([NODE, "pruebas/recalcular.ts"], cwd=WEB, input=json.dumps(casos), capture_output=True,
                       text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    pantalla = json.loads(r.stdout)
    assert len(pantalla) == len(esperado)
    for caso, fase3, web in zip(casos, esperado, pantalla):
        for campo in CAMPOS:
            a, b = fase3.get(campo), web.get(campo)
            if not con_log2fc and campo in ("NPS_log2FC", "Lectura_log2FC", "Sensible_al_peso"):
                continue  # sin tabla de log2FC la Fase 3 ni siquiera tiene esas columnas
            if isinstance(a, float) or isinstance(b, float):
                assert a == pytest.approx(b, abs=1e-9), (caso["criterio"], campo, a, b)
            else:
                assert (a or "") == (b or ""), (caso["criterio"], campo, a, b)
    return len(casos)


def test_tu_criterio_en_pantalla_igual_que_la_fase3_ruta_sintetica(tmp_path, monkeypatch):
    """Una ruta con genes up y down, signos de GO y del LLM, neutros, sin signo, pendientes y log2FC."""
    from test_scoring import caso, entradas, par
    pares = [par("A", "GO:A"), par("B", "GO:A"), par("C", "GO:A", lista="Suprimida"),
             par("D", "GO:A", destino="aceptar_GO", signo_go="-1"), par("E", "GO:A", destino="sin_evidencia"),
             par("F", "GO:A"), par("G", "GO:A", lista="Suprimida"), par("H", "GO:A")]
    casos = [caso("A", "GO:A", "1", "+1"), caso("B", "GO:A", "2", "-1", conf=60),
             caso("C", "GO:A", "3", "+1"), caso("F", "GO:A", "4", "neutro"),
             caso("G", "GO:A", "5", "UNKNOWN", estado="no_concluyente", motivos="baja_confianza"),
             caso("H", "GO:A", "6", "UNKNOWN", estado="pendiente")]
    f1, f2 = entradas(tmp_path, pares, casos)
    fc = tmp_path / "fc.csv"
    pd.DataFrame({"Gen": list("ABCDEFGH"), "log2FC": [2.0, 0.5, -3.0, 1.0, 1.5, 0.8, -1.2, 4.0]}).to_csv(fc, index=False)
    for log2fc in (None, fc):
        assert _comparar([_pares(monkeypatch, f1, f2, log2fc)], log2fc is not None) == 8 * 3 + 5


RUTAS_REALES = sorted((config.DIR_CODIGO / "data" / "frontend").glob("GO_*"))


@pytest.mark.skipif(not RUTAS_REALES, reason="no hay rutas ejecutadas en codigo/data/frontend/")
def test_tu_criterio_en_pantalla_igual_que_la_fase3_rutas_reales(monkeypatch):
    """Las rutas ejecutadas desde la interfaz (sus Excels de las Fases 1 y 2), con la tabla de log2FC si está."""
    log2fc = config.FICHERO_LOG2FC if config.FICHERO_LOG2FC.exists() else None
    rutas = []
    for carpeta in RUTAS_REALES:
        f1, f2 = carpeta / "fase1_dataset_abstracts.xlsx", carpeta / "fase2_resultados.xlsx"
        try:
            p = _pares(monkeypatch, f1, f2, log2fc)
        except ValueError:  # falta un fichero, o es de una ejecución con un formato anterior
            continue
        rutas += [g for _, g in p.groupby("GO_ID")]
    assert rutas
    assert _comparar(rutas, log2fc is not None) > 100
