"""Fase 4: el puente por HTTP (POST /ejecutar-ruta, GET /estado, POST /criterio), con las fases simuladas: sin red,
sin LLM y sin tocar codigo/data. La Fase 3 de /criterio es la real, sobre Excels sintéticos."""
import base64
import importlib
import io
import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pandas as pd
import pytest

GO = "GO:0000001"
RUTA = {"GO_ID": GO, "Descripcion": "ruta de prueba", "Genes_up": "A/B", "Genes_down": "C"}


@pytest.fixture
def puente(tmp_path, monkeypatch):
    """El puente en un puerto libre, con las salidas en una carpeta temporal y el estado limpio."""
    mod = importlib.import_module("fase4_frontend.api_puente")
    monkeypatch.setattr(mod, "DIR_SALIDAS", tmp_path / "frontend")
    monkeypatch.setattr(mod, "_estado", {"estado": "libre"})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), mod.ManejadorPuente)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield mod, f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def pedir(url, cuerpo=None, crudo=None):
    datos = crudo if crudo is not None else (json.dumps(cuerpo).encode() if cuerpo is not None else None)
    req = urllib.request.Request(url, data=datos, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def esperar(base, hasta=("terminado", "error"), limite=10):
    fin = time.time() + limite
    while time.time() < fin:
        _, d = pedir(base + "/estado")
        if d["estado"] in hasta:
            return d
        time.sleep(0.05)
    raise AssertionError(f"el puente sigue en {d}")


def simular_fases(mod, monkeypatch, tmp_path, sujetar=None, fallo=None):
    """Fases 1-3 de mentira con la misma forma de salida. sujetar: Event que retiene la Fase 2 (para ver la ejecución
    en marcha); fallo: fase que lanza un error."""
    llamadas = {}

    def fase1(carpeta, ruta):
        llamadas["fase1"] = ruta
        if fallo == 1:
            raise RuntimeError("La Fase 1 no encontró ninguna evidencia para los genes de esta ruta.")
        (carpeta / "f1.xlsx").write_bytes(b"f1")
        return carpeta / "f1.xlsx"

    def fase2(carpeta, excel_f1):
        if sujetar is not None:
            sujetar.wait(5)
        return carpeta / "f2.xlsx", {"llamadas": 3, "reutilizadas": 9, "pendientes": 0, "tokens": 120, "agotados": {}}

    def fase3(carpeta, f1, f2):
        excel = carpeta / "fase3_scoring.xlsx"
        excel.write_bytes(b"excel de la fase 3")
        pares = pd.DataFrame({"Gen": ["A", "B", "C"], "GO_ID": [GO] * 3, "Signo_par": ["+1", "+1", "-1"]})
        rutas = pd.DataFrame({"GO_ID": [GO], "Lectura": ["activada"], "NPS": [1.0]})
        return excel, pares, rutas

    monkeypatch.setattr(mod, "_fase1", fase1)
    monkeypatch.setattr(mod, "_fase2", fase2)
    monkeypatch.setattr(mod, "_fase3", fase3)
    monkeypatch.setattr(mod, "detalle", lambda f1, f2, pares, go: ({"A": {"articulos": []}}, {"fase1": {}, "fase2": {}}))
    return llamadas


def test_ejecutar_una_ruta_de_principio_a_fin(puente, monkeypatch, tmp_path):
    mod, base = puente
    llamadas = simular_fases(mod, monkeypatch, tmp_path)
    assert pedir(base + "/estado") == (200, {"estado": "libre"})
    codigo, d = pedir(base + "/ejecutar-ruta", {**RUTA, "GO_ID": f"  {GO} ", "Otro": "se ignora"})
    assert (codigo, d) == (202, {"ok": True})
    d = esperar(base)
    assert (d["estado"], d["fase"], d["GO_ID"], d["Descripcion"]) == ("terminado", 4, GO, "ruta de prueba")
    r = d["resultado"]
    assert r["rutas"] == [{"GO_ID": GO, "Lectura": "activada", "NPS": 1.0}] and len(r["pares"]) == 3
    assert r["llm"]["reutilizadas"] == 9 and set(r["tiempos"]) == {"fase1", "fase2", "fase3"}
    assert base64.b64decode(r["excel_b64"]) == b"excel de la fase 3"
    assert r["nombre_excel"] == "fase3_scoring_GO_0000001.xlsx"
    assert r["carpeta"].endswith("GO_0000001")  # cada ruta en su carpeta, sin los dos puntos
    assert llamadas["fase1"] == {**RUTA, "Celula": "", "Log2FC": {}}  # los genes llegan tal cual a la Fase 1
    assert r["estudio"]["cl_celula"] == mod.ESTUDIO_BASE.cl_celula  # sin célula elegida, la del estudio


def test_una_ruta_a_la_vez(puente, monkeypatch, tmp_path):
    mod, base = puente
    sujetar = threading.Event()
    simular_fases(mod, monkeypatch, tmp_path, sujetar=sujetar)
    assert pedir(base + "/ejecutar-ruta", RUTA)[0] == 202
    d = esperar(base, hasta=("ejecutando",))
    assert d["fase"] in (1, 2)
    codigo, d = pedir(base + "/ejecutar-ruta", {**RUTA, "GO_ID": "GO:0000002"})
    assert codigo == 409 and GO in d["error"]
    # Mientras se ejecuta, tampoco se puede recalcular «Tu criterio» de esa ruta
    assert pedir(base + "/criterio", {"GO_ID": GO, "criterio": {"A": "-1"}})[0] == 409
    sujetar.set()
    assert esperar(base)["estado"] == "terminado"
    assert pedir(base + "/ejecutar-ruta", RUTA)[0] == 202  # terminada, se puede lanzar otra
    esperar(base)


def test_un_error_en_una_fase_queda_en_el_estado(puente, monkeypatch, tmp_path):
    mod, base = puente
    simular_fases(mod, monkeypatch, tmp_path, fallo=1)
    assert pedir(base + "/ejecutar-ruta", RUTA)[0] == 202
    d = esperar(base)
    assert (d["estado"], d["fase"]) == ("error", 1)
    assert d["error"] == "RuntimeError: La Fase 1 no encontró ninguna evidencia para los genes de esta ruta."


@pytest.mark.parametrize("cuerpo, crudo, error", [
    ({**RUTA, "GO_ID": "GO:123"}, None, "GO_ID no válido"),
    ({**RUTA, "GO_ID": "0000001"}, None, "GO_ID no válido"),
    ({**RUTA, "Genes_up": "", "Genes_down": None}, None, "La ruta no tiene genes"),
    (None, b"{no es json", "Petición mal formada"),
])
def test_peticiones_no_validas(puente, monkeypatch, tmp_path, cuerpo, crudo, error):
    mod, base = puente
    llamadas = simular_fases(mod, monkeypatch, tmp_path)
    codigo, d = pedir(base + "/ejecutar-ruta", cuerpo, crudo)
    assert codigo == 400 and error in d["error"]
    assert pedir(base + "/estado")[1] == {"estado": "libre"} and not llamadas  # no se lanza nada


@pytest.mark.parametrize("datos", [None, b"{}"])  # GET y POST
def test_rutas_que_no_existen(puente, datos):
    _, base = puente
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(urllib.request.Request(base + "/no-existe", data=datos))
    assert e.value.code == 404


def _salidas_de_una_ruta(mod, tmp_path):
    """Los Excels de las Fases 1 y 2 de GO (tres genes que activan, como en test_scoring) en la carpeta de la ruta."""
    from test_scoring import caso, entradas, par
    pares = [par("A", GO), par("B", GO), par("C", GO, lista="Suprimida")]
    casos = [caso("A", GO, "1", "+1"), caso("B", GO, "2", "+1"), caso("C", GO, "3", "-1")]
    f1, f2 = entradas(tmp_path, pares, casos)
    carpeta = mod.DIR_SALIDAS / GO.replace(":", "_")
    carpeta.mkdir(parents=True)
    f1.rename(carpeta / "fase1_dataset_abstracts.xlsx")
    f2.rename(carpeta / "fase2_resultados.xlsx")
    return carpeta


def test_tu_criterio_recalcula_la_fase_3(puente, monkeypatch, tmp_path):
    mod, base = puente
    monkeypatch.setattr(mod, "_log2fc", lambda carpeta=None: None)
    carpeta = _salidas_de_una_ruta(mod, tmp_path)
    codigo, d = pedir(base + "/criterio", {"GO_ID": GO, "criterio": {"A": "-1", "B": "-1"}})
    assert codigo == 200 and d["ok"]
    ruta = d["rutas"][0]
    # A y B (up) pasan a inhibir: (−1 − 1 + 1) / 3; C (down) sigue frenando la inhibición, +1
    assert (ruta["Lectura"], ruta["NPS"], ruta["Lectura_automatica"], ruta["NPS_automatico"]) == \
        ("inhibida", -0.333, "activada", 1.0)
    assert ruta["Cambios_experto"] == "A: +1 → -1; B: +1 → -1"
    a = next(p for p in d["pares"] if p["Gen"] == "A")
    assert (a["Signo_par"], a["Signo_automatico"], a["Origen"]) == ("-1", "+1", "Experto")
    assert d["nombre_excel"] == "fase3_scoring_GO_0000001_criterio.xlsx"
    excel = pd.read_excel(io.BytesIO(base64.b64decode(d["excel_b64"])), sheet_name=None)
    assert "Lectura_automatica" in excel["Por_ruta"].columns
    assert (carpeta / "fase3_scoring_criterio.xlsx").exists()
    # Sin cambios, el automático (y en su Excel de siempre)
    codigo, d = pedir(base + "/criterio", {"GO_ID": GO, "criterio": {}})
    assert codigo == 200 and d["rutas"][0]["Lectura"] == "activada" and d["nombre_excel"] == "fase3_scoring_GO_0000001.xlsx"


@pytest.mark.parametrize("cuerpo, codigo_esperado, error", [
    ({"GO_ID": "GO:1", "criterio": {}}, 400, "GO_ID no válido"),
    ({"GO_ID": GO, "criterio": {"A": "activa"}}, 400, "Signo no válido para A"),
    ({"GO_ID": GO, "criterio": ["A"]}, 400, "Petición mal formada"),
    ({"GO_ID": "GO:0000009", "criterio": {"A": "+1"}}, 500, "vuelve a ejecutar la ruta"),  # sin sus salidas
])
def test_tu_criterio_peticiones_no_validas(puente, cuerpo, codigo_esperado, error):
    _, base = puente
    codigo, d = pedir(base + "/criterio", cuerpo)
    assert codigo == codigo_esperado and error in d["error"]


# --- Versión 2 (#52): célula elegida y tabla de log2FC por ruta (en la interfaz está congelado) ---
TUMORAL = "CL:0001064"


def test_estudio_con_las_celulas_que_se_pueden_elegir(puente):
    mod, base = puente
    codigo, d = pedir(base + "/estudio")
    assert codigo == 200 and d["cl_celula"] == mod.ESTUDIO_BASE.cl_celula
    assert d["celulas_disponibles"][0] == {"cl_celula": "CL:0000623", "celula": "células NK", "clase_celula": "inmune"}
    assert {c["clase_celula"] for c in d["celulas_disponibles"]} == {"inmune", "tumoral", "otra"}


def test_version2_celula_y_log2fc_solo_para_esa_ruta(puente, monkeypatch, tmp_path):
    mod, base = puente
    llamadas = simular_fases(mod, monkeypatch, tmp_path)
    vistos = {}
    fase1 = mod._fase1

    def fase1_mira(carpeta, ruta):  # qué estudio ven las Fases 1 y 3 durante la ejecución
        vistos["f1"], vistos["f3"] = mod.cruce_gaf.ESTUDIO.cl_celula, mod.f3_config.TIPOS_CELULARES_VALIDOS
        return fase1(carpeta, ruta)

    monkeypatch.setattr(mod, "_fase1", fase1_mira)
    cuerpo = {**RUTA, "Celula": TUMORAL, "Log2FC": {"a": 2.5, "B": 1, "C": -1.2, "OTRO": 0.3}}
    assert pedir(base + "/ejecutar-ruta", cuerpo)[0] == 202
    r = esperar(base)["resultado"]
    assert vistos == {"f1": TUMORAL, "f3": ("tumor", "not_stated")}
    assert (r["estudio"]["celula"], r["log2fc"]) == ("células tumorales", "subida")
    assert llamadas["fase1"]["Log2FC"] == {"A": 2.5, "B": 1.0, "C": -1.2, "OTRO": 0.3}
    carpeta = mod.DIR_SALIDAS / "GO_0000001"
    assert json.loads((carpeta / "estudio_ruta.json").read_text(encoding="utf-8")) == {"cl_celula": TUMORAL}
    assert pd.read_csv(carpeta / "log2fc.csv").set_index("Gen")["log2FC"].to_dict()["A"] == 2.5
    # Al acabar vuelve el estudio de codigo/estudio.json
    assert mod.cruce_gaf.ESTUDIO == mod.ESTUDIO_BASE and mod.f3_config.ESTUDIO == mod.ESTUDIO_BASE
    assert mod.f3_config.TIPOS_CELULARES_VALIDOS == mod.ESTUDIO_BASE.tipos_celulares_validos
    # Otra ejecución sin elegir nada borra lo de la anterior
    assert pedir(base + "/ejecutar-ruta", RUTA)[0] == 202
    r = esperar(base)["resultado"]
    assert r["estudio"]["cl_celula"] == mod.ESTUDIO_BASE.cl_celula
    assert not (carpeta / "estudio_ruta.json").exists() and not (carpeta / "log2fc.csv").exists()


@pytest.mark.parametrize("extra, error", [
    ({"Celula": "CL:9999999"}, "Célula no disponible"),
    ({"Log2FC": [1, 2]}, "La tabla de log2FC"),
    ({"Log2FC": {"A": "mucho"}}, "no numérico"),
    ({"Log2FC": {"A": -1.0}}, "contradice su lista (up)"),  # A es un gen up
    ({"Log2FC": {"C": 0.5}}, "contradice su lista (down)"),
])
def test_version2_peticiones_no_validas(puente, monkeypatch, tmp_path, extra, error):
    mod, base = puente
    llamadas = simular_fases(mod, monkeypatch, tmp_path)
    codigo, d = pedir(base + "/ejecutar-ruta", {**RUTA, **extra})
    assert codigo == 400 and error in d["error"] and not llamadas


def test_tu_criterio_usa_la_celula_y_el_log2fc_de_la_ruta(puente):
    """Con la célula tumoral guardada para la ruta, los artículos en NK pesan la mitad; con su log2FC, sale la
    sensibilidad. Sin ellos, como siempre."""
    mod, base = puente
    carpeta = _salidas_de_una_ruta(mod, mod.DIR_SALIDAS.parent)
    mod.preparar_estudio(carpeta, TUMORAL, {"A": 3.0, "B": 1.0, "C": -1.0})
    codigo, d = pedir(base + "/criterio", {"GO_ID": GO, "criterio": {}})
    assert codigo == 200
    a = next(p for p in d["pares"] if p["Gen"] == "A")
    assert (a["W_pos"], a["Log2FC"]) == (0.5, 3.0)  # caso en NK (test_scoring.caso) con un estudio tumoral
    assert d["rutas"][0]["Lectura_log2FC"] != ""
    excel = pd.read_excel(io.BytesIO(base64.b64decode(d["excel_b64"])), sheet_name="Resumen")
    assert "células tumorales" in excel["Valor"].astype(str).tolist()
    mod.preparar_estudio(carpeta)
    d = pedir(base + "/criterio", {"GO_ID": GO, "criterio": {}})[1]
    assert next(p for p in d["pares"] if p["Gen"] == "A")["W_pos"] == 1.0
