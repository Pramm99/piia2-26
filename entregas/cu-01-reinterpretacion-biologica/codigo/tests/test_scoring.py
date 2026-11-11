"""Spec de scoring (Fase 3): votos ponderados, signo del par, contribución y Net Pathway Score. Tablas sintéticas."""
import socket

import pandas as pd
import pytest

from scoring import config
from scoring.nps import calcular, escribir, peso

HUMANO, RATON = ("human", "NK"), ("mouse", "NK")


def caso(gen, go, pmid, signo, estado="resuelto", conf=100, contexto=HUMANO, motivos="", proceso="GO:1"):
    return {"Gen": gen, "GO_ID": go, "PMID": pmid, "Proceso_ID": proceso, "Signo_ruta": signo, "Estado": estado,
            "Motivos": motivos, "Confianza_final": conf, "Organismo": contexto[0], "Tipo_celular": contexto[1]}


def par(gen, go, destino="LLM", lista="Activada", signo_go=None, ruta="ruta"):
    return {"Gen": gen, "GO_ID": go, "Ruta_Nombre": ruta, "Estado_Original": lista, "Signo_GO": signo_go,
            "Destino": destino}


def entradas(tmp_path, pares, casos, igs=()):
    """Escribe los Excels de las Fases 1 y 2 con lo mínimo que lee el scoring."""
    f1, f2 = tmp_path / "fase1.xlsx", tmp_path / "fase2.xlsx"
    cols_ig = ["Gen", "GO_ID", "Ruta_Nombre", "Estado_Original", "Signo"]
    with pd.ExcelWriter(f1) as w:
        pd.DataFrame(pares, columns=list(par("x", "y"))).to_excel(w, sheet_name="Triaje_polaridad", index=False)
        pd.DataFrame(list(igs), columns=cols_ig).to_excel(w, sheet_name="Inmunoglobulinas", index=False)
    df = pd.DataFrame(casos, columns=list(caso("x", "y", "1", "+1")))
    with pd.ExcelWriter(f2) as w:
        df.drop(columns=["Organismo", "Tipo_celular"]).to_excel(w, sheet_name="Por_ruta", index=False)
        df[["Gen", "PMID", "Proceso_ID", "Organismo", "Tipo_celular"]].to_excel(w, sheet_name="Preguntas",
                                                                               index=False)
    return f1, f2


def puntuar(tmp_path, pares, casos, igs=(), log2fc=None):
    f1, f2 = entradas(tmp_path, pares, casos, igs)
    return calcular(f1, f2, log2fc)


def fila(df, gen, go="GO:A"):
    return df[(df.Gen == gen) & (df.GO_ID == go)].iloc[0]


@pytest.mark.parametrize("ultimo, signo, estado, motivo", [
    (HUMANO, "UNKNOWN", "revisar", "conflicto_entre_abstracts"),  # minoría 1,0 / 2,5 = 40 %
    (RATON, "+1", "resuelto", "minoria_discrepante"),              # minoría 0,5 / 2,5 = 20 %
])
def test_mayoria_y_conflicto(tmp_path, ultimo, signo, estado, motivo):
    casos = [caso("G", "GO:A", "1", "+1"), caso("G", "GO:A", "2", "+1", contexto=RATON),
             caso("G", "GO:A", "3", "-1", contexto=ultimo)]
    p, _, _ = puntuar(tmp_path, [par("G", "GO:A")], casos)
    f = fila(p, "G")
    assert (f.Signo_par, f.Estado_par) == (signo, estado)
    assert motivo in f.Motivos.split("|")
    assert f.W_pos == 1.5 and f.W_neg == ultimo_peso(ultimo)
    assert (f.n_PMIDs_pos, f.n_PMIDs_neg) == (2, 1)


def ultimo_peso(contexto):
    return 1.0 if contexto == HUMANO else 0.5


def test_pesos():
    assert peso(80, "mouse", "tumor") == (pytest.approx(0.2), False)
    assert peso(80, "human", "T") == (pytest.approx(0.8), False)
    assert peso(None, "human", "NK") == (pytest.approx(0.5), True)


def test_evidencia_debil(tmp_path):
    p, _, _ = puntuar(tmp_path, [par("G", "GO:A")], [caso("G", "GO:A", "1", "-1", conf=40)])
    f = fila(p, "G")
    assert (f.Signo_par, f.Estado_par, f.Motivos) == ("-1", "resuelto", "evidencia_debil")
    assert f.Votos == "-1:1(0.40)"


def test_solo_unknown_no_entra_en_el_nps(tmp_path):
    pares = [par("G", "GO:A"), par("H", "GO:A")]
    casos = [caso("G", "GO:A", "1", "UNKNOWN", estado="no_concluyente", motivos="baja_confianza"),
             caso("H", "GO:A", "2", "+1")]
    p, r, _ = puntuar(tmp_path, pares, casos)
    f = fila(p, "G")
    assert (f.Estado_par, f.Contribucion, f.Motivos) == ("no_concluyente", 0, "baja_confianza")
    assert r.iloc[0].NPS == 1.0 and r.iloc[0].n_no_concluyente == 1


def test_contradiccion_va_a_revisar(tmp_path):
    p, _, _ = puntuar(tmp_path, [par("G", "GO:A")],
                      [caso("G", "GO:A", "1", "UNKNOWN", estado="no_concluyente", motivos="contradictorio")])
    assert (fila(p, "G").Estado_par, fila(p, "G").Motivos) == ("revisar", "contradictorio")


def test_pendiente(tmp_path):
    p, r, _ = puntuar(tmp_path, [par("G", "GO:A"), par("H", "GO:A")],
                      [caso("G", "GO:A", "1", "UNKNOWN", estado="pendiente")])
    assert (fila(p, "G").Estado_par, fila(p, "G").Motivos) == ("pendiente", "pendiente_fase2")
    assert (fila(p, "H").Estado_par, fila(p, "H").Motivos) == ("pendiente", "sin_fase2")  # sin casos en la Fase 2
    assert r.iloc[0].n_pendiente == 2


def test_go_y_direccion(tmp_path):
    p, _, _ = puntuar(tmp_path, [par("G", "GO:A", "aceptar_GO", "Suprimida", "-1")], [])
    f = fila(p, "G")
    assert (f.Signo_par, f.Origen, f.Direccion, f.Contribucion) == ("-1", "GO", "down", 1.0)
    assert not f.Freno_retroalimentacion


def test_freno(tmp_path):
    p, _, _ = puntuar(tmp_path, [par("G", "GO:A")], [caso("G", "GO:A", "1", "-1")])
    f = fila(p, "G")
    assert f.Contribucion == -1.0 and f.Freno_retroalimentacion


RUTA = [par("A", "GO:A"), par("B", "GO:A"), par("C", "GO:A"), par("N", "GO:A"), par("S", "GO:A", "sin_evidencia")]
VOTOS = [caso("A", "GO:A", "1", "+1"), caso("B", "GO:A", "2", "+1"), caso("C", "GO:A", "3", "-1"),
         caso("N", "GO:A", "4", "neutro")]


def test_nps_y_lectura(tmp_path):
    _, r, _ = puntuar(tmp_path, RUTA, VOTOS)
    f = r.iloc[0]
    assert (f.NPS, f.Fraccion_neutros, f.Cobertura, f.Lectura) == (0.333, 0.25, 0.8, "activada")
    assert (f.n_activan, f.n_inhiben, f.n_neutros, f.n_sin_evidencia, f.n_total) == (2, 1, 1, 1, 5)
    assert (f.Genes_activan, f.Genes_inhiben) == ("A; B", "C")
    _, r, _ = puntuar(tmp_path, RUTA[1:], VOTOS[1:])
    assert r.iloc[0].Lectura == "insuficiente"


def test_inmunoglobulinas_no_cambian_el_nps(tmp_path):
    ig = [{"Gen": "IGKC", "GO_ID": "GO:A", "Ruta_Nombre": "ruta", "Estado_Original": "Activada", "Signo": "neutro"}]
    p, r, _ = puntuar(tmp_path, RUTA, VOTOS, igs=ig)
    f = fila(p, "IGKC")
    assert (f.Signo_par, f.Estado_par, f.Origen, f.Motivos) == ("neutro", "resuelto", "Ig", "inmunoglobulina")
    assert (r.iloc[0].NPS, r.iloc[0].n_neutros, r.iloc[0].n_total) == (0.333, 2, 6)


def test_revisar_cuenta_solo_en_nps_con_revisar(tmp_path):
    pares = RUTA + [par("R", "GO:A", "LLM_y_revision")]
    p, r, _ = puntuar(tmp_path, pares, VOTOS + [caso("R", "GO:A", "5", "-1")])
    f = fila(p, "R")
    assert (f.Signo_par, f.Estado_par, f.Signo_revisar, f.Contribucion) == ("-1", "revisar", "-1", 0)
    assert (r.iloc[0].NPS, r.iloc[0].NPS_con_revisar, r.iloc[0].Genes_revisar) == (0.333, 0.0, "R")


def test_ruta_en_las_dos_listas_es_una_fila(tmp_path):
    pares = [par("U", "GO:A"), par("D", "GO:A", lista="Suprimida")]
    _, r, _ = puntuar(tmp_path, pares, [caso("U", "GO:A", "1", "+1"), caso("D", "GO:A", "2", "+1")])
    assert len(r) == 1 and r.iloc[0].Listas == "ambas" and r.iloc[0].NPS == 0.0


def test_log2fc(tmp_path):
    fc = tmp_path / "fc.csv"
    pd.DataFrame({"Gen": ["D"], "log2FC": [-2.0]}).to_csv(fc, index=False)
    p, r, _ = puntuar(tmp_path, [par("D", "GO:A", lista="Suprimida"), par("E", "GO:A")],
                      [caso("D", "GO:A", "1", "+1"), caso("E", "GO:A", "2", "+1")], log2fc=fc)
    assert fila(p, "D").Contribucion == -2.0 and fila(p, "D").Log2FC == -2.0
    assert "sin_log2FC" in fila(p, "E").Motivos and r.iloc[0].Con_log2FC == "sí"
    assert r.iloc[0].NPS == pytest.approx(round((-2 + 1) / 3, 3))
    pd.DataFrame({"Gen": ["D"], "log2FC": [1.5]}).to_csv(fc, index=False)
    with pytest.raises(ValueError, match="D"):
        puntuar(tmp_path, [par("D", "GO:A", lista="Suprimida")], [], log2fc=fc)


@pytest.mark.parametrize("hoja, columna", [("Por_ruta", None), ("Por_ruta", "Confianza_final")])
def test_entrada_incompleta(tmp_path, hoja, columna):
    f1, f2 = entradas(tmp_path, RUTA, VOTOS)
    hojas = pd.read_excel(f2, sheet_name=None)
    if columna:
        hojas[hoja] = hojas[hoja].drop(columns=[columna])
    else:
        del hojas[hoja]
    with pd.ExcelWriter(f2) as w:
        for k, v in hojas.items():
            v.to_excel(w, sheet_name=k, index=False)
    with pytest.raises(ValueError, match=columna or hoja):
        calcular(f1, f2)
    with pytest.raises(ValueError, match="No existe"):
        calcular(f1, tmp_path / "no_esta.xlsx")


def test_determinista_y_sin_red(tmp_path, monkeypatch):
    def sin_red(*a, **k):
        raise AssertionError("el scoring no debe usar la red")
    monkeypatch.setattr(socket, "socket", sin_red)
    monkeypatch.setattr(socket, "create_connection", sin_red)
    f1, f2 = entradas(tmp_path, RUTA, VOTOS)
    a, b = escribir(*calcular(f1, f2), tmp_path / "a.xlsx"), escribir(*calcular(f1, f2), tmp_path / "b.xlsx")
    for hoja in ("Por_ruta", "Por_par", "Resumen"):
        pd.testing.assert_frame_equal(pd.read_excel(a, sheet_name=hoja), pd.read_excel(b, sheet_name=hoja))


@pytest.mark.skipif(not (config.FICHERO_FASE1.exists() and config.FICHERO_FASE2.exists()),
                    reason="hacen falta las salidas reales de las Fases 1 y 2")
def test_recuento_completo_con_las_salidas_reales():
    p, r, _ = calcular()
    triaje = pd.read_excel(config.FICHERO_FASE1, sheet_name=["Triaje_polaridad", "Inmunoglobulinas"])
    total = pd.concat(triaje.values())
    assert len(p) == len(total) and len(r) == total["GO_ID"].nunique()
