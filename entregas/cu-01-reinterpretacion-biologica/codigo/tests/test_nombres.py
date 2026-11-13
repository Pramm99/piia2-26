"""fuentes/nombres.py: nombres de la proteína de UniProt y MyGene, con caché y sin red."""
import json

from fuentes import nombres


class _Resp:
    def __init__(self, datos):
        self.datos = datos

    def raise_for_status(self):
        pass

    def json(self):
        return self.datos


class _Sesion:
    def __init__(self):
        self.llamadas = 0

    def post(self, url, data=None, timeout=None):
        self.llamadas += 1
        return _Resp([{"query": "CCL3", "other_names": ["macrophage inflammatory protein 1-alpha"]},
                       {"query": "NADA", "notfound": True}])

    def get(self, url, params=None, timeout=None):
        self.llamadas += 1
        if "CCL3" in params["query"]:
            return _Resp({"results": [{"proteinDescription": {
                "recommendedName": {"fullName": {"value": "C-C motif chemokine 3"}},
                "alternativeNames": [{"fullName": {"value": "Small-inducible cytokine A3"},
                                      "shortNames": [{"value": "MIP-1-alpha"}]}]}}]})
        return _Resp({"results": []})


def test_nombres_de_uniprot_y_mygene_con_cache(tmp_path, monkeypatch):
    sesion = _Sesion()
    monkeypatch.setattr(nombres, "configurar_sesion", lambda: sesion)
    destino = str(tmp_path / "nombres.json")
    n = nombres.nombres_proteina(["CCL3", "NADA"], destino=destino)
    assert n["CCL3"] == sorted({"macrophage inflammatory protein 1-alpha", "C-C motif chemokine 3",
                                "Small-inducible cytokine A3", "MIP-1-alpha"})
    assert n["NADA"] == [] and json.loads((tmp_path / "nombres.json").read_text(encoding="utf-8"))["CCL3"]
    antes = sesion.llamadas
    assert nombres.nombres_proteina(["CCL3"], destino=destino)["CCL3"] == n["CCL3"] and sesion.llamadas == antes
