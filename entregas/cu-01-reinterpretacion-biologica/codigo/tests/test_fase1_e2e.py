"""Fase 1 de extremo a extremo, sin red, con los datos de tests/fixtures/ (y su paso por las Fases 2 y 3).

Los fixtures son una versión mínima de la entrada real: un OBO con 7 términos, un GAF con 11 anotaciones, las dos
listas de CIMUS en JSON (los Excels se escriben en tmp_path, porque no se versionan) y las respuestas grabadas de
HGNC, UniProt, MyGene.info, Europe PMC y NCBI. Cada gen cubre un camino del triaje:

  NKG7   anotación IDA a «positive regulation of …», profundidad 1 y con abstract -> aceptar_GO
  PRF1   anotación IMP a «negative regulation of …», su PMID no tiene abstract     -> aceptar_GO (se respeta)
  TIGIT  una anotación «+» y otra «−»                                                -> LLM_y_revision
  CXCR4  anotación sin signo (más una NOT y otra de ratón, que se descartan)         -> LLM
  CCL5   sin anotación; un GeneRIF nombra el gen y la ruta                           -> LLM (fuente GeneRIF)
  SELL   sin anotación; Europe PMC dirigida, gen y ruta en la misma frase            -> LLM (fuente EuropePMC)
  GZMB   su único PMID no tiene abstract                                             -> sin_evidencia (PMID_sin_abstract)
  IGFBP7 solo una IEA sin artículo; empieza por «IG» pero no es una Ig               -> sin_evidencia (anotado_sin_PMID)
  FAM89B sin anotación ni fuente externa                                             -> sin_evidencia (sin_anotacion_GAF)
  IGKC, IGHM  inmunoglobulinas                                                       -> hoja Inmunoglobulinas, neutro
"""
import gzip
import json
import re
import socket
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import pytest

import abstracts
import config
import cruce_gaf
import entrada_excel
import inmunoglobulinas
import main
import salida
from conftest import respuesta
from fuentes import europepmc, generif, nombres, uniprot

FIXTURES = Path(__file__).parent / "fixtures"
IGS = {"IGKC", "IGHM"}


class _Resp:
    def __init__(self, json_=None, content=b""):
        self._json, self.content = json_, content

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


class SesionGrabada:
    """Sustituye a red.configurar_sesion(): contesta con las respuestas de fixtures/ según la URL."""

    def __init__(self):
        self.datos = json.loads((FIXTURES / "respuestas_http.json").read_text(encoding="utf-8"))
        self.ncbi = ET.parse(FIXTURES / "ncbi_efetch.xml").getroot()
        self.peticiones = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.peticiones.append(url)
        if url == config.HGNC_IG_URL:
            return _Resp(self.datos["hgnc"])
        if url == config.UNIPROT_API:
            gen = re.search(r"gene_exact:(\S+)", params["query"]).group(1)
            entrada = self.datos["uniprot"].get(gen)
            return _Resp({"results": [entrada] if entrada else []})
        if url == config.EPMC_API:
            arts = self.datos["epmc_abstracts"]
            return _Resp({"resultList": {"result": [{"pmid": p, **arts[p]} for p in
                                                    re.findall(r"EXT_ID:(\d+)", params["query"]) if p in arts]}})
        raise AssertionError(f"GET no previsto: {url}")

    def post(self, url, data=None, timeout=None):
        self.peticiones.append(url)
        if url == config.NCBI_URL:
            ids = set(data["id"].split(","))
            raiz = ET.Element("PubmedArticleSet")
            raiz.extend(a for a in self.ncbi if a.findtext("MedlineCitation/PMID") in ids)
            return _Resp(content=ET.tostring(raiz))
        if url == config.MYGENE_API:
            mg = self.datos["mygene"]
            return _Resp([{"query": q, **mg[q]} if q in mg else {"query": q, "notfound": True}
                          for q in data["q"].split(",")])
        if url == config.EPMC_SEARCH_POST:
            return _Resp({"resultList": {"result": [r for gen, res in self.datos["epmc_busquedas"].items()
                                                    if f'TITLE_ABS:"{gen}"' in data["query"] for r in res]}})
        raise AssertionError(f"POST no previsto: {url}")


def _sin_red(*a, **k):
    raise AssertionError("la prueba no debe usar la red")


def preparar_fase1(tmp_path, mp):
    """Entrada, OBO, GAF y cachés en tmp_path; red simulada y sockets bloqueados. Devuelve la sesión."""
    mp.setattr(socket, "socket", _sin_red)
    mp.setattr(socket, "create_connection", _sin_red)
    mp.setattr(abstracts.time, "sleep", lambda s: None)

    rutas = json.loads((FIXTURES / "rutas_cimus.json").read_text(encoding="utf-8"))
    for etiqueta, var in (("Activada", "EXCEL_ACTIVADAS"), ("Suprimida", "EXCEL_SUPRIMIDAS")):
        ruta = tmp_path / f"{etiqueta}.xlsx"
        pd.DataFrame(rutas[etiqueta]).to_excel(ruta, index=False)
        mp.setattr(entrada_excel, var, str(ruta))

    obo, gaf = tmp_path / "go-basic.obo", tmp_path / "goa_human.gaf.gz"
    obo.write_text((FIXTURES / "go_mini.obo.txt").read_text(encoding="utf-8"), encoding="utf-8")
    with gzip.open(gaf, "wt", encoding="utf-8") as f:
        f.write((FIXTURES / "goa_mini.gaf").read_text(encoding="utf-8"))
    for modulo in (main, salida):
        mp.setattr(modulo, "OBO_FILE", str(obo))
    for modulo in (main, cruce_gaf):
        mp.setattr(modulo, "GAF_FILE", str(gaf))
    mp.setattr(salida, "SALIDA", str(tmp_path / "fase1_dataset_abstracts.xlsx"))

    # Las cachés: las globales de abstracts y los valores por defecto de las fuentes (se fijan al importar)
    mp.setattr(abstracts, "CACHE_FILE", str(tmp_path / "cache_abstracts.json"))
    for funcion, nombre in ((inmunoglobulinas.cargar_lista_ig, "hgnc.json"), (generif.datos_mygene, "mygene.json"),
                            (europepmc.buscar, "epmc.json"), (uniprot.entradas_uniprot, "uniprot.json"),
                            (nombres.nombres_proteina, "nombres.json")):
        mp.setattr(funcion, "__defaults__", (str(tmp_path / nombre),))

    sesion = SesionGrabada()
    for modulo in (abstracts, inmunoglobulinas, europepmc, generif, nombres, uniprot):
        mp.setattr(modulo, "configurar_sesion", lambda: sesion)
    return sesion


@pytest.fixture(scope="module")
def fase1(tmp_path_factory):
    """Ejecuta la Fase 1 una vez y devuelve (carpeta, hojas del Excel de salida, sesión)."""
    tmp_path = tmp_path_factory.mktemp("fase1")
    with pytest.MonkeyPatch.context() as mp:
        sesion = preparar_fase1(tmp_path, mp)
        main.ejecutar_fase_1()
    hojas = pd.read_excel(tmp_path / "fase1_dataset_abstracts.xlsx", sheet_name=None, dtype={"PMID": str})
    return tmp_path, hojas, sesion


def _pares(df):
    return set(zip(df["Gen"], df["GO_ID"]))


def _entrada():
    rutas = json.loads((FIXTURES / "rutas_cimus.json").read_text(encoding="utf-8"))
    alias = {"GO:9000099": "GO:9000020"}  # el término obsoleto de la entrada pasa a su sustituto
    return {(g, alias.get(r["ID"], r["ID"])): etiqueta for etiqueta, filas in rutas.items()
            for r in filas for g in r["geneID"].split("/")}


def test_salida_con_las_siete_hojas(fase1):
    _, hojas, sesion = fase1
    assert set(hojas) == {"Con_abstract", "PMID_sin_abstract", "Anotado_sin_PMID", "Genes_no_encontrados",
                          "Triaje_polaridad", "Inmunoglobulinas", "Sin_evidencia"}
    assert sesion.peticiones  # la red simulada sí se ha usado: lo que está bloqueado es la real


def test_inmunoglobulinas_neutras_y_fuera_de_con_abstract(fase1):
    _, hojas, _ = fase1
    ig = hojas["Inmunoglobulinas"]
    assert set(ig["Gen"]) == IGS and set(ig["Signo"]) == {"neutro"}
    assert set(ig["UniProt"]) == {"P01834", "P01871"}
    assert ig.set_index("Gen").loc["IGHM", "Regla_texto"] == "FUNCTION"
    assert not IGS & set(hojas["Con_abstract"]["Gen"]) and not IGS & set(hojas["Triaje_polaridad"]["Gen"])
    # IGFBP7 empieza por «IG» pero no es una inmunoglobulina: sigue en el triaje
    assert "IGFBP7" in set(hojas["Triaje_polaridad"]["Gen"])


def test_triaje_un_destino_por_par(fase1):
    _, hojas, _ = fase1
    triaje = hojas["Triaje_polaridad"]
    no_ig = {p for p in _entrada() if p[0] not in IGS}
    assert len(triaje) == len(no_ig) and _pares(triaje) == no_ig  # exactamente una fila por par
    destino = dict(zip(zip(triaje["Gen"], triaje["GO_ID"]), triaje["Destino"]))
    assert destino == {
        ("NKG7", "GO:9000001"): "aceptar_GO", ("PRF1", "GO:9000001"): "aceptar_GO",
        ("TIGIT", "GO:9000001"): "LLM_y_revision", ("CXCR4", "GO:9000010"): "LLM",
        ("CCL5", "GO:9000020"): "LLM", ("SELL", "GO:9000010"): "LLM",
        ("GZMB", "GO:9000001"): "sin_evidencia", ("IGFBP7", "GO:9000001"): "sin_evidencia",
        ("FAM89B", "GO:9000010"): "sin_evidencia",
    }
    signo = dict(zip(triaje["Gen"], triaje["Signo_GO"].fillna("")))
    assert signo["NKG7"] == "+1" and signo["PRF1"] == "-1" and signo["TIGIT"] == "conflicto"


def test_pares_sin_abstract_cerrados_con_su_causa(fase1):
    _, hojas, _ = fase1
    triaje, sin_ev = hojas["Triaje_polaridad"], hojas["Sin_evidencia"]
    sin_filas = {p for p in _pares(triaje) if p not in _pares(hojas["Con_abstract"])}
    causa = dict(zip(zip(sin_ev["Gen"], sin_ev["GO_ID"]), sin_ev["Causa"]))
    assert sin_filas == set(causa)  # cada par sin abstract tiene su fila en Sin_evidencia
    assert causa == {("GZMB", "GO:9000001"): "PMID_sin_abstract", ("IGFBP7", "GO:9000001"): "anotado_sin_PMID",
                     ("FAM89B", "GO:9000010"): "sin_anotacion_GAF", ("PRF1", "GO:9000001"): "PMID_sin_abstract"}
    cerrados = sin_ev[sin_ev["Estado"] == "no_concluyente"]
    assert set(cerrados["Resultado"]) == {"UNKNOWN"} and cerrados["Motivo"].str.startswith("sin_evidencia:").all()
    destino = dict(zip(zip(triaje["Gen"], triaje["GO_ID"]), triaje["Destino"]))
    assert all(destino[p] == "sin_evidencia" for p in _pares(cerrados))
    assert triaje.loc[triaje["Destino"] == "sin_evidencia", "Contribucion"].isna().all()


def test_aceptar_go_sin_abstract_conserva_el_signo_go(fase1):
    """Excepción de docs/limitacion-pares-sin-abstract.md: el signo de un aceptar_GO no depende del abstract."""
    _, hojas, _ = fase1
    assert hojas["Triaje_polaridad"].set_index("Gen").loc["PRF1", "Destino"] == "aceptar_GO"
    fila = hojas["Sin_evidencia"].set_index("Gen").loc["PRF1"]
    assert (fila["Resultado"], fila["Estado"], fila["Motivo"]) == ("-1", "resuelto_GO", "aceptar_GO")


def test_con_abstract_fuentes_y_limpieza(fase1):
    _, hojas, _ = fase1
    con = hojas["Con_abstract"]
    fuente = dict(zip(zip(con["Gen"], con["PMID"]), con["Fuente"]))
    assert fuente == {("NKG7", "100"): "GOA", ("TIGIT", "104"): "GOA", ("TIGIT", "105"): "GOA",
                      ("CXCR4", "103"): "GOA", ("CCL5", "200"): "GeneRIF", ("SELL", "300"): "EuropePMC"}
    # 301 nombra el gen y la ruta en frases distintas: no se acepta. La NOT (998) y la de ratón (997), tampoco.
    assert not {"301", "997", "998"} & set(con["PMID"])
    abstract = dict(zip(con["PMID"], con["Abstract"]))
    assert abstract["100"].startswith("Results: NKG7")              # etiqueta de título -> «: »
    assert "(p < 0.01)" in abstract["104"] and "IFN-γ" in abstract["105"]  # entidades desescapadas
    assert abstract["103"] == ("BACKGROUND: Chemokines guide leukocytes. RESULTS: CXCR4 blockade reduced "
                               "leukocyte chemotaxis of human NK cells.")  # respaldo de NCBI, con sus rótulos
    assert con["PMID"].str.fullmatch(r"\d+").all()
    assert set(hojas["Genes_no_encontrados"]["Gen_no_encontrado_en_GAF"]) == {"CCL5", "SELL", "FAM89B"}


def test_direccion_conservada_en_con_abstract(fase1):
    _, hojas, _ = fase1
    con = hojas["Con_abstract"]
    assert set(con["Estado_Original"]) == {"Activada", "Suprimida"}
    assert (con.groupby("Gen")["Estado_Original"].nunique() == 1).all()  # ningún gen con los dos valores
    entrada = _entrada()
    assert all(entrada[(g, r)] == e for g, r, e in zip(con["Gen"], con["GO_ID"], con["Estado_Original"]))


def test_segunda_ejecucion_sin_peticiones(tmp_path, monkeypatch):
    sesion = preparar_fase1(tmp_path, monkeypatch)
    main.ejecutar_fase_1()
    primera = pd.read_excel(tmp_path / "fase1_dataset_abstracts.xlsx", sheet_name=None)
    n = len(sesion.peticiones)
    main.ejecutar_fase_1()
    # Todo sale de las cachés salvo lo que nunca se pudo cachear: el PMID 201, que nadie conoce y se vuelve a
    # pedir una vez a Europe PMC y otra a NCBI. Ni HGNC, ni UniProt, ni MyGene, ni las búsquedas dirigidas.
    assert sesion.peticiones[n:] == [config.EPMC_API, config.NCBI_URL]
    segunda = pd.read_excel(tmp_path / "fase1_dataset_abstracts.xlsx", sheet_name=None)
    for hoja in primera:
        pd.testing.assert_frame_equal(primera[hoja], segunda[hoja])


def test_fases_2_y_3_sobre_la_salida_de_la_fase1(fase1, tmp_path, monkeypatch):
    """La dirección del gen viaja hasta el final: cada fila de Por_ruta se une con su Estado_Original."""
    from fase2_inferencia import proceso
    from fase2_inferencia.cliente import ClienteSimulado
    from fase2_inferencia.pipeline import ejecutar_fase2
    from fase2_inferencia.registro import Registro
    from fase3_scoring.nps import calcular

    carpeta, hojas, _ = fase1
    preparar_fase1(tmp_path, monkeypatch)  # red simulada y cachés para MyGene (alias de la Fase 2)
    monkeypatch.setattr(proceso, "OBO_FILE", str(carpeta / "go-basic.obo"))
    proceso._ontologia.cache_clear()

    def responder(lista):
        """+1 con la última frase de cada abstract como cita (verificable)."""
        items = []
        for i, p in enumerate(lista.preguntas, 1):
            n = len(p.evidencia.frases)
            items.append({"q": f"Q{i}", **json.loads(respuesta(cita=p.evidencia.frases[-1], id_frase=f"S{n}"))})
        return json.dumps({"respuestas": items})

    try:
        f1 = carpeta / "fase1_dataset_abstracts.xlsx"
        cli = ClienteSimulado("sim", responder)
        _, por_ruta, resumen, _ = ejecutar_fase2(str(f1), [cli], registro=Registro(tmp_path / "r.jsonl"),
                                                 salida=tmp_path / "fase2.xlsx")
        assert resumen.pendientes == 0 and cli.llamadas > 0
        assert set(por_ruta["Gen"]) == {"TIGIT", "CXCR4", "CCL5", "SELL"}  # aceptar_GO no va al LLM
        direccion = hojas["Con_abstract"][["Gen", "GO_ID", "Estado_Original"]].drop_duplicates()
        unido = por_ruta.merge(direccion, on=["Gen", "GO_ID"], how="left")
        assert len(unido) == len(por_ruta) and unido["Estado_Original"].notna().all()

        pares, rutas, *_ = calcular(f1, tmp_path / "fase2.xlsx")
        assert set(rutas["GO_ID"]) == {"GO:9000001", "GO:9000010", "GO:9000020"}
        assert set(pares.loc[pares["Gen"].isin(IGS), "Signo_par"]) == {"neutro"}
    finally:
        proceso._ontologia.cache_clear()
