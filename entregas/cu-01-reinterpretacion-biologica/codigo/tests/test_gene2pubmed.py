"""fuentes/gene2pubmed.py y la etapa gene2pubmed + MeSH de pmid_externos.py (#31), sin red."""
import pmid_externos
from fuentes import gene2pubmed
from relevancia import patron_gen


class _Resp:
    def __init__(self, datos):
        self.datos = datos

    def raise_for_status(self):
        pass

    def json(self):
        return self.datos


class _Sesion:
    """MyGene da el Entrez ID; elink, los PMIDs ligados al gen con la consulta MeSH."""

    def __init__(self):
        self.consultas = []

    def post(self, url, data=None, timeout=None):
        return _Resp([{"query": "GATA3", "entrezgene": 2625}, {"query": "NADA", "notfound": True}])

    def get(self, url, params=None, timeout=None):
        self.consultas.append(params["term"])
        return _Resp({"linksets": [{"linksetdbs": [{"links": ["111", "333", "222"]}]}]})


def test_tabla_sin_comillas_y_sin_las_rutas_sin_mesh(tmp_path):
    f = tmp_path / "tabla.tsv"
    f.write_text("GO_ID\tRuta_Nombre\tConsulta_MeSH\tConfianza\tNota\tPares_sin_evidencia\n"
                 'GO:1\tT cell migration\t"T-Lymphocytes"[mh] AND "Cell Movement"[mh]\talta\t\t1\n'
                 "GO:2\tcell development\t\tsin_mesh\tdemasiado general\t1\n", encoding="utf-8")
    assert gene2pubmed.leer_tabla(str(f)) == {"GO:1": '"T-Lymphocytes"[mh] AND "Cell Movement"[mh]'}


def test_articulos_con_humans_ordenados_y_en_cache(tmp_path, monkeypatch):
    sesion = _Sesion()
    monkeypatch.setattr(gene2pubmed, "configurar_sesion", lambda: sesion)
    monkeypatch.setattr(gene2pubmed.time, "sleep", lambda s: None)
    destino = str(tmp_path / "g2p.json")
    q = '"Th2 Cells"[mh]'
    r = gene2pubmed.articulos({("GATA3", q), ("NADA", q)}, destino=destino)
    assert r[("GATA3", q)] == ["333", "222", "111"] and r[("NADA", q)] == []
    assert sesion.consultas == ['("Th2 Cells"[mh]) AND "Humans"[mh]']  # NADA no tiene Entrez ID: no se pregunta
    assert gene2pubmed.articulos({("GATA3", q)}, destino=destino)[("GATA3", q)] == ["333", "222", "111"]
    assert len(sesion.consultas) == 1  # la segunda vez sale de la caché


class _Textos:
    def __init__(self, texto):
        self.texto = texto

    def cargar(self, pmids):
        pass


def test_etapa_tres_mas_recientes_que_nombran_el_gen(monkeypatch):
    """De los artículos ligados, los 3 más recientes que nombran el gen; un par cuya ruta no está en la tabla, nada."""
    monkeypatch.setattr(gene2pubmed, "leer_tabla", lambda: {"GO:1": '"Th2 Cells"[mh]'})
    monkeypatch.setattr(gene2pubmed, "articulos", lambda c: {k: ["50", "40", "30", "20", "10"] for k in c})
    texto = {p: "GATA3 drives Th2 differentiation." for p in ("50", "30", "20", "10")}
    texto["40"] = "Th2 differentiation in allergy."  # no nombra el gen
    reg = pmid_externos._etapa_gene2pubmed({("GATA3", "GO:1"), ("GATA3", "GO:2")}, {"GATA3": patron_gen("GATA3")},
                                           _Textos(texto))
    assert [r["PMID"] for r in reg] == ["50", "30", "20"]
    assert {(r["GO_ID"], r["Fuente"], r["Coincide_en"]) for r in reg} == {("GO:1", "gene2pubmed", "mesh")}
