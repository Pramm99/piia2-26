"""Spec de ingesta: entrada, grafo GO, inmunoglobulinas, descarga de abstracts (HTTP simulado) y claves de .env."""
import pandas as pd
import pytest

import abstracts
import config
import entrada_excel
import inmunoglobulinas
from grafo_go import cargar_go, componer, descendientes, polaridad_desde_estados


# --- Entrada ---
def test_entrada_extrae_pares_y_traduce_ids_obsoletos(tmp_path):
    ruta = tmp_path / "rutas.xlsx"
    pd.DataFrame([{"ID": "GO:0000001", "Description": "ruta vieja", "geneID": "CD7/gzmb/PRF1/NKG7/KLRD1"}]).to_excel(
        ruta, index=False)
    df = entrada_excel.leer_y_explotar_excel(str(ruta), "Activada", {"GO:0000001": "GO:0000002"})
    assert list(df.Gen) == ["CD7", "GZMB", "PRF1", "NKG7", "KLRD1"]
    assert set(df.GO_ID) == {"GO:0000002"} and set(df.Estado_Original) == {"Activada"}


def test_entrada_lee_los_excels_de_cimus():
    assert config.EXCEL_ACTIVADAS.endswith("tools_cimus\\NK_rutas_activadas_GO.xlsx") or \
        config.EXCEL_ACTIVADAS.endswith("tools_cimus/NK_rutas_activadas_GO.xlsx")
    df, pares = entrada_excel.cargar_entrada({})
    assert len(pares) == 3172 and df.Gen.nunique() == 224
    # un gen está en una sola de las dos listas
    por_gen = df.groupby("Gen").Estado_Original.nunique()
    assert (por_gen == 1).all()


# --- Grafo GO ---
OBO = """format-version: 1.2

[Term]
id: GO:0000001
name: proceso

[Term]
id: GO:0000002
name: negative regulation of proceso
relationship: negatively_regulates GO:0000001

[Term]
id: GO:0000003
name: negative regulation of negative regulation
relationship: negatively_regulates GO:0000002

[Term]
id: GO:0000004
name: positive regulation of proceso
relationship: positively_regulates GO:0000001

[Term]
id: GO:0000005
name: ambos caminos
is_a: GO:0000002
is_a: GO:0000004

[Term]
id: GO:0000009
name: obsoleto
is_obsolete: true
replaced_by: GO:0000001
"""


@pytest.fixture
def grafo(tmp_path):
    f = tmp_path / "mini.obo"
    f.write_text(OBO, encoding="utf-8")
    return cargar_go(str(f))


def test_polaridad_compuesta_por_el_grafo(grafo):
    hijos, alias = grafo
    desc = descendientes("GO:0000001", hijos)
    assert polaridad_desde_estados(desc["GO:0000002"]) == "-1"
    assert polaridad_desde_estados(desc["GO:0000003"]) == "+1"  # (-)·(-) = +
    assert polaridad_desde_estados(desc["GO:0000004"]) == "+1"
    assert polaridad_desde_estados(desc["GO:0000005"]) == "conflicto"
    assert desc["GO:0000003"]["+"] == 2  # profundidad
    assert alias["GO:0000009"] == "GO:0000001"


def test_componer():
    assert componer("N", "-") == "-" and componer("-", "-") == "+" and componer("+", "R") == "R"


# --- Inmunoglobulinas ---
def test_inmunoglobulinas_por_lista_hgnc_no_por_prefijo(monkeypatch):
    monkeypatch.setattr(inmunoglobulinas, "cargar_lista_ig", lambda: {"IGKC", "IGHM", "IGLC2"})
    genes = ["IGKC", "ighm", "IGFBP7", "IGSF6", "JCHAIN", "PIGR", "CD7"]
    assert inmunoglobulinas.detectar_inmunoglobulinas(genes) == {"IGKC", "IGHM", "JCHAIN", "PIGR"}


# --- Descarga de abstracts con HTTP simulado ---
class _Resp:
    def __init__(self, json_=None, content=b""):
        self._json, self.content = json_, content

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


class _Sesion:
    """Europe PMC devuelve el 1 y el 2; NCBI conoce el 3 pero sin abstract."""

    def __init__(self):
        self.get_llamadas, self.post_llamadas = 0, 0

    def get(self, url, params=None, timeout=None):
        self.get_llamadas += 1
        res = [{"pmid": "1", "title": "T1", "abstractText": "<p>Uno</p>"},
               {"pmid": "2", "title": "T2", "abstractText": "Dos &amp; tres"}]
        return _Resp({"resultList": {"result": res}})

    def post(self, url, data=None, timeout=None):
        self.post_llamadas += 1
        xml = b"<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>3</PMID><Article><ArticleTitle>T3" \
              b"</ArticleTitle></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"
        return _Resp(content=xml)


def test_descarga_por_lotes_con_respaldo_y_cache(tmp_path, monkeypatch):
    sesion = _Sesion()
    monkeypatch.setattr(abstracts, "configurar_sesion", lambda: sesion)
    monkeypatch.setattr(abstracts, "CACHE_FILE", str(tmp_path / "cache_abstracts.json"))
    monkeypatch.setattr(abstracts.time, "sleep", lambda s: None)

    df = abstracts.descargar_abstracts(["1", "2", "3"])
    assert sesion.get_llamadas == 1 and sesion.post_llamadas == 1  # un lote de Europe PMC y uno de NCBI
    assert list(df.PMID) == ["1", "2"]  # el 3 no tiene abstract: no sale, sin interrumpir el lote
    assert df.Abstract.tolist() == ["Uno", "Dos & tres"]

    df2 = abstracts.descargar_abstracts(["1", "2", "3"])  # segunda vez, todo desde la caché
    assert sesion.get_llamadas == 1 and sesion.post_llamadas == 1
    assert df2.equals(df)


# --- Claves desde codigo/.env ---
def test_leer_env(tmp_path):
    f = tmp_path / ".env"
    f.write_text("# comentario\nNCBI_EMAIL=\"yo@example.org\"\nVACIA=\n\nSIN_IGUAL\n", encoding="utf-8")
    assert config._leer_env(str(f)) == {"NCBI_EMAIL": "yo@example.org", "VACIA": ""}
    assert config._leer_env(str(tmp_path / "no_existe")) == {}


def test_la_variable_de_entorno_manda(monkeypatch):
    monkeypatch.setenv("PRUEBA_VARIABLE_PIIA2", "del_entorno")
    assert config._env("PRUEBA_VARIABLE_PIIA2") == "del_entorno"
    monkeypatch.delenv("PRUEBA_VARIABLE_PIIA2")
    assert config._env("PRUEBA_VARIABLE_PIIA2") is None
