"""Spec de ingesta: formatos de entrada (.xlsx y .csv) y validación de columnas antes de la red."""
import pandas as pd
import pytest

import entrada_excel
import main

FILAS = [{"ID": "GO:0000001", "Description": "ruta vieja", "geneID": "CD7/gzmb/PRF1"},
         {"ID": "GO:0000003", "Description": "otra ruta", "geneID": "NKG7/KLRD1"}]
ALIAS = {"GO:0000001": "GO:0000002"}


@pytest.mark.parametrize("sep", [",", ";"])
def test_csv_da_los_mismos_pares_que_xlsx(tmp_path, sep):
    xlsx, csv = tmp_path / "rutas.xlsx", tmp_path / "rutas.csv"
    pd.DataFrame(FILAS).to_excel(xlsx, index=False)
    pd.DataFrame(FILAS).to_csv(csv, index=False, sep=sep)
    a = entrada_excel.leer_y_explotar_excel(str(xlsx), "Activada", ALIAS)
    b = entrada_excel.leer_y_explotar_excel(str(csv), "Activada", ALIAS)
    pd.testing.assert_frame_equal(a, b)
    assert list(zip(b.GO_ID, b.Gen))[:3] == [("GO:0000002", "CD7"), ("GO:0000002", "GZMB"), ("GO:0000002", "PRF1")]


@pytest.mark.parametrize("ext", [".xlsx", ".csv"])
@pytest.mark.parametrize("falta", entrada_excel.COLUMNAS_OBLIGATORIAS)
def test_columna_ausente_da_value_error_con_su_nombre(tmp_path, ext, falta):
    ruta = tmp_path / f"rutas{ext}"
    df = pd.DataFrame(FILAS).drop(columns=[falta])
    df.to_excel(ruta, index=False) if ext == ".xlsx" else df.to_csv(ruta, index=False)
    with pytest.raises(ValueError, match=falta):
        entrada_excel.leer_tabla(str(ruta))


def test_formato_no_admitido(tmp_path):
    ruta = tmp_path / "rutas.txt"
    ruta.write_text("ID\tDescription\tgeneID\n")
    with pytest.raises(ValueError, match="Formato no admitido"):
        entrada_excel.leer_tabla(str(ruta))


def test_la_entrada_se_valida_antes_de_descargar(tmp_path, monkeypatch):
    malo = tmp_path / "rutas.csv"
    pd.DataFrame(FILAS).drop(columns=["geneID"]).to_csv(malo, index=False)
    monkeypatch.setattr(entrada_excel, "EXCEL_ACTIVADAS", str(malo))
    descargas = []
    monkeypatch.setattr(main, "descargar_archivo", lambda *a: descargas.append(a))
    with pytest.raises(ValueError, match="geneID"):
        main.ejecutar_fase_1()
    assert descargas == []
