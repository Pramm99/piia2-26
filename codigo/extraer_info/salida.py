"""Construcción de las hojas de resultados, resumen por consola (embudo) y escritura del Excel final."""
import re

import pandas as pd

from config import OBO_FILE, SALIDA
from grafo_go import cargar_nombres

ILEGALES_XLSX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def limpiar_para_excel(df):
    df = df.copy()
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].apply(
            lambda v: ILEGALES_XLSX.sub("", v)[:32000] if isinstance(v, str) else v)
    return df


def _pares(df):
    return set(zip(df["Gen"], df["GO_ID"]))


def combinar(df_excel, df_ev, df_abs):
    """Une entrada + evidencias + abstracts. Devuelve (base, con_abstract, sin_abstract)."""
    base = pd.merge(df_excel, df_ev, on=["Gen", "GO_ID"], how="inner")
    completo = pd.merge(base, df_abs, on="PMID", how="left")
    con = completo[completo["Abstract"].notna()]
    sin = completo[completo["Abstract"].isna()]
    return base, con, sin


def imprimir_embudo(pares, base, con, pmids, df_abs):
    print("\n=== EMBUDO ===")
    print(f"Pares de entrada .............. {len(pares)}")
    gaf = base[base["Fuente"] == "GOA"]
    print(f"Pares con >=1 PMID en GAF ..... {len(_pares(gaf))}")
    print(f"Pares con PMID solo externo ... {len(_pares(base) - _pares(gaf))}  (GeneRIF / Europe PMC)")
    print(f"  de ellos, alcanzados por regulación ... {len(_pares(gaf[gaf['Tipo_relacion'].str.contains('regulates')]))}")
    print(f"  de ellos, con polaridad GO (+1/-1) .... {len(_pares(gaf[gaf['Polaridad_GO'].isin(['+1', '-1'])]))}")
    print(f"Pares con >=1 abstract ........ {len(_pares(con))}")
    print(f"PMIDs únicos .................. {len(pmids)}  (con abstract: {len(df_abs)})")
    print(f"Filas finales con abstract .... {len(con)}")


def construir_anotado_sin_pmid(df_excel, df_ev, df_sin):
    """Pares con anotación pero SIN ningún PMID: hoja aparte (no hay abstract que recuperar en GO)."""
    if df_sin.empty:
        return pd.DataFrame()
    pares_pmid = _pares(df_ev)
    sin_pmid = df_sin[[(g, r) not in pares_pmid for g, r in zip(df_sin["Gen"], df_sin["GO_ID"])]]
    info = df_excel[["Gen", "GO_ID", "Ruta_Nombre", "Estado_Original"]].drop_duplicates()
    sin_pmid = pd.merge(info, sin_pmid, on=["Gen", "GO_ID"], how="inner")
    nombres = cargar_nombres(OBO_FILE)
    sin_pmid.insert(sin_pmid.columns.get_loc("GO_ID_anotado") + 1, "Nombre_GO_anotado",
                    sin_pmid["GO_ID_anotado"].map(nombres))
    return sin_pmid


def anadir_destino(df, triaje):
    """Añade a cada fila el destino del triaje de su par (aceptar_GO / LLM / LLM_y_revision)."""
    if df.empty:
        return df
    return pd.merge(df, triaje[["Gen", "GO_ID", "Destino"]].drop_duplicates(), on=["Gen", "GO_ID"], how="left")


def imprimir_triaje(triaje, hoja_ig):
    print("\n=== TRIAJE DEL SIGNO GO ===")
    print(f"Pares de inmunoglobulinas (neutros, sin abstracts) ... {len(_pares(hoja_ig)) if not hoja_ig.empty else 0}")
    for destino, n in triaje.drop_duplicates(["Gen", "GO_ID"])["Destino"].value_counts().items():
        print(f"{destino:.<52} {n}")
    print(f"Pares con bandera freno/retroalimentación ........... {int(triaje['Freno_retroalimentacion'].sum())}")


def construir_sin_evidencia(df_excel, con, df_anot, df_ev):
    """Pares que se quedan sin ningún abstract (ni del GAF ni de las fuentes externas), con la causa."""
    info = df_excel[["Gen", "GO_ID", "Ruta_Nombre", "Estado_Original"]].drop_duplicates()
    falta = info[[p not in _pares(con) for p in zip(info["Gen"], info["GO_ID"])]].copy()
    anotados = _pares(df_anot) if not df_anot.empty else set()
    con_pmid = _pares(df_ev) if not df_ev.empty else set()
    falta["Causa"] = ["PMID_sin_abstract" if p in con_pmid else "anotado_sin_PMID" if p in anotados
                      else "sin_anotacion_GAF" for p in zip(falta["Gen"], falta["GO_ID"])]
    print(f"Pares sin ningún abstract ..... {len(falta)}  {falta['Causa'].value_counts().to_dict()}")
    return falta


def imprimir_sin_pmid(sin_pmid):
    if sin_pmid.empty:
        total, con_pol = 0, 0
    else:
        total = len(_pares(sin_pmid))
        con_pol = len(_pares(sin_pmid[sin_pmid["Polaridad_GO"].isin(["+1", "-1"])]))
    print(f"Pares anotados SIN PMID ....... {total}  (con polaridad GO +1/-1: {con_pol})")


def escribir_excel(con, sin, sin_pmid, no_encontrados, triaje, hoja_ig, sin_evidencia):
    genes_sin = pd.DataFrame({"Gen_no_encontrado_en_GAF": no_encontrados})
    with pd.ExcelWriter(SALIDA, engine="openpyxl") as w:
        limpiar_para_excel(con).to_excel(w, sheet_name="Con_abstract", index=False)
        limpiar_para_excel(sin.drop(columns=["Titulo", "Abstract"])).to_excel(
            w, sheet_name="PMID_sin_abstract", index=False)
        limpiar_para_excel(sin_pmid).to_excel(w, sheet_name="Anotado_sin_PMID", index=False)
        genes_sin.to_excel(w, sheet_name="Genes_no_encontrados", index=False)
        limpiar_para_excel(triaje).to_excel(w, sheet_name="Triaje_polaridad", index=False)
        limpiar_para_excel(hoja_ig).to_excel(w, sheet_name="Inmunoglobulinas", index=False)
        limpiar_para_excel(sin_evidencia).to_excel(w, sheet_name="Sin_evidencia", index=False)
    print(f"🚀 FASE 1 COMPLETADA -> {SALIDA}")
