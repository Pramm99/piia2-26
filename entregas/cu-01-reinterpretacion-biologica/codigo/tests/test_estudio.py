"""El estudio configurable (#51): codigo/estudio.json, los tipos celulares compatibles de la Fase 1 (Cell Ontology) y
los tipos celulares que pesan entero en la Fase 3. Sin red: OLS4 se simula."""
import gzip
import json

import pytest

import cruce_gaf
import estudio
from fase3_scoring import config as f3_config
from fase3_scoring.nps import peso
from fuentes import cell_ontology

BASE = {"celula": "células T", "cl_celula": "CL:0000084", "clase_celula": "inmune", "tejido": "pulmón",
        "excel_activadas": "a.xlsx", "excel_suprimidas": "b.xlsx", "log2fc": ""}


def escribir(tmp_path, **cambios):
    f = tmp_path / "estudio.json"
    f.write_text(json.dumps({**BASE, **cambios}), encoding="utf-8")
    return f


def test_el_estudio_del_repositorio_es_el_de_cimus():
    e = estudio.leer_estudio(estudio.FICHERO_ESTUDIO)
    assert (e.celula, e.cl_celula, e.clase_celula) == ("células NK", "CL:0000623", "inmune")
    assert e.excel_activadas.name == "NK_rutas_activadas_GO.xlsx" and e.log2fc.name == "NK_cells_DESeq2_results.xlsx"
    assert e.tipos_celulares_validos == ("NK", "T", "other_immune", "not_stated")  # los de antes de #51


def test_leer_estudio_rutas_relativas_a_codigo_y_log2fc_opcional(tmp_path, monkeypatch):
    monkeypatch.setenv("ESTUDIO_JSON", str(escribir(tmp_path)))
    e = estudio.leer_estudio()
    assert e.excel_activadas == (estudio.DIR_CODIGO / "a.xlsx").resolve()
    assert e.log2fc is None and e.celula == "células T"


@pytest.mark.parametrize("cambio, error", [
    ({"tejido": ""}, "faltan tejido"),
    ({"cl_celula": "natural killer"}, "cl_celula"),
    ({"clase_celula": "linfocito"}, "clase_celula"),
])
def test_leer_estudio_valida(tmp_path, cambio, error):
    with pytest.raises(ValueError, match=error):
        estudio.leer_estudio(escribir(tmp_path, **cambio))


@pytest.mark.parametrize("clase, validos", list(estudio.TIPOS_LLM_POR_CLASE.items()))
def test_tipos_celulares_validos_por_clase(tmp_path, clase, validos):
    assert estudio.leer_estudio(escribir(tmp_path, clase_celula=clase)).tipos_celulares_validos == validos


# --- Fase 1: tipos celulares compatibles (Cell Ontology) ---
class SesionOLS:
    """OLS4 simulado: ancestros y descendientes de CL:0000084, el segundo en dos páginas."""
    def __init__(self):
        self.urls = []

    def get(self, url, timeout=None):
        self.urls.append(url)
        if "hierarchicalAncestors" in url:
            datos = {"_embedded": {"terms": [{"obo_id": "CL:0000738"}, {"obo_id": "BFO:0000002"}]}}
        elif "page=2" in url:
            datos = {"_embedded": {"terms": [{"obo_id": "CL:0000625"}]}}
        else:
            datos = {"_embedded": {"terms": [{"obo_id": "CL:0000624"}]}, "_links": {"next": {"href": url + "&page=2"}}}
        return type("R", (), {"json": lambda s: datos, "raise_for_status": lambda s: None})()


def test_cl_compatibles_de_ols4_con_cache(tmp_path, monkeypatch):
    sesion = SesionOLS()
    monkeypatch.setattr(cell_ontology, "configurar_sesion", lambda: sesion)
    cache = str(tmp_path / "cache.json")
    t = cell_ontology.cl_compatibles("CL:0000084", destino=cache)
    assert t == {"CL:0000084", "CL:0000738", "CL:0000624", "CL:0000625"}  # sin términos de otras ontologías
    n = len(sesion.urls)
    assert cell_ontology.cl_compatibles("CL:0000084", destino=cache) == t and len(sesion.urls) == n  # de la caché


def test_cl_compatibles_de_nk_sin_red(tmp_path, monkeypatch):
    monkeypatch.setattr(cell_ontology, "configurar_sesion", lambda: pytest.fail("NK no consulta OLS4"))
    nk = cell_ontology.cl_compatibles("CL:0000623", destino=str(tmp_path / "c.json"))
    assert "CL:0000623" in nk and "CL:0000084" not in nk


def test_anotacion_en_otra_celula_segun_el_estudio(tmp_path, monkeypatch):
    """Una anotación con occurs_in(CL:0000084) (célula T) es de otra célula si se estudian NK, y no si se estudian T."""
    gaf = tmp_path / "mini.gaf.gz"
    fila = ["UniProtKB", "P1", "CD7", "involved_in", "GO:0000001", "PMID:1", "IDA", "", "P", "", "", "protein",
            "taxon:9606", "20200101", "GO", "occurs_in(CL:0000084)"]
    with gzip.open(gaf, "wt", encoding="utf-8") as f:
        f.write("\t".join(fila) + "\n")
    monkeypatch.setattr(cruce_gaf, "GAF_FILE", str(gaf))
    pares, desc_map = {("CD7", "GO:0000001")}, {"GO:0000001": {"GO:0000001": {"N": 0}}}
    for cl, ajeno in (("CL:0000623", "CL:0000084"), ("CL:0000084", "")):
        monkeypatch.setattr(cruce_gaf, "ESTUDIO", estudio.leer_estudio(escribir(tmp_path, cl_celula=cl)))
        monkeypatch.setattr(cruce_gaf, "cl_compatibles", lambda c: {c} | ({"CL:0000623"} if c == "CL:0000623" else set()))
        anot = cruce_gaf.cruzar_con_gaf(pares, desc_map)[3]
        assert list(anot["CL_otra_celula"]) == [ajeno]


# --- Fase 3: el tipo celular que pesa entero depende de la clase del estudio ---
def test_peso_segun_la_clase_del_estudio(monkeypatch):
    assert peso(80, "human", "tumor") == (pytest.approx(0.4), False)  # estudio de NK: tumor pesa la mitad
    monkeypatch.setattr(f3_config, "TIPOS_CELULARES_VALIDOS", estudio.TIPOS_LLM_POR_CLASE["tumoral"])
    assert peso(80, "human", "tumor") == (pytest.approx(0.8), False)
    assert peso(80, "human", "NK") == (pytest.approx(0.4), False)


def test_con_celula_del_catalogo(tmp_path):
    e = estudio.leer_estudio(escribir(tmp_path))
    t = estudio.con_celula(e, "CL:0001064")
    assert (t.celula, t.clase_celula, t.tejido, t.excel_activadas) == ("células tumorales", "tumoral", e.tejido,
                                                                       e.excel_activadas)
    with pytest.raises(ValueError, match="no es una de las células"):
        estudio.con_celula(e, "CL:0000999")
    assert len({cl for cl, _, _ in estudio.CELULAS_DISPONIBLES}) == len(estudio.CELULAS_DISPONIBLES)
    assert all(estudio.CL_ID.match(cl) and k in estudio.TIPOS_LLM_POR_CLASE for cl, _, k in estudio.CELULAS_DISPONIBLES)
