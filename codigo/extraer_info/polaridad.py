"""Triaje del signo GO por par (Gen, Ruta): qué pares acepta el grafo y cuáles tiene que leer el LLM.

Sigue el informe «Polaridad GO como signo directo» (2026-11-08). El signo GO solo se acepta, de
forma provisional y con revisión ligera, si el camino es corto (≤ PROFUNDIDAD_MAX_ACEPTAR) y lo
respalda una anotación experimental con PMID que no ocurre en otra célula ni es indirecta.
"""
import pandas as pd

from config import (EVIDENCIAS_FILOGENETICAS, GENES_VIGILANCIA, PREFIJOS_VIGILANCIA,
                    PROFUNDIDAD_MAX_ACEPTAR)

ACEPTAR_GO = "aceptar_GO"          # signo provisional del grafo, sin LLM (revisión ligera)
LLM = "LLM"
LLM_Y_REVISION = "LLM_y_revision"  # además, revisión humana
DESTINOS_SIN_LLM = {ACEPTAR_GO}

COLUMNAS = ["Gen", "GO_ID", "Ruta_Nombre", "Estado_Original", "Signo_GO", "Profundidad",
            "Evidencias_signo", "PMIDs_signo", "Destino", "Motivo", "Contribucion", "Freno_retroalimentacion"]


def en_vigilancia(gen):
    return gen in GENES_VIGILANCIA or gen.startswith(PREFIJOS_VIGILANCIA)


def _descartar_iba_contradictorias(anots):
    """Una IBA (herencia filogenética, ~31 % de error) que contradice a una experimental se descarta."""
    exp = {s for s, e in zip(anots["Signo"], anots["Experimental"]) if e and s in ("+1", "-1")}
    if not exp:
        return anots, False
    contradice = anots["Evidencia"].isin(EVIDENCIAS_FILOGENETICAS) & anots["Signo"].isin(["+1", "-1", "conflicto"]) \
        & ~anots["Signo"].isin(exp)
    return anots[~contradice], bool(contradice.any())


def _triaje_par(gen, anots):
    """Signo, profundidad, evidencias, destino y motivos de un par a partir de sus anotaciones."""
    motivos = []
    if anots is None or anots.empty:
        return "", None, "", "", LLM, "sin_anotacion_GAF"

    anots, iba_descartada = _descartar_iba_contradictorias(anots)
    if iba_descartada:
        motivos.append("iba_descartada")
    firmadas = anots[anots["Signo"] != ""]
    if firmadas.empty:
        return "", int(anots["Profundidad"].min()), "", "", LLM, "|".join(motivos + ["sin_signo"])

    signos = set()
    for s in firmadas["Signo"]:
        signos |= {"+1", "-1"} if s == "conflicto" else {s}
    signo = "conflicto" if len(signos) > 1 else signos.pop()
    prof = int(firmadas["Profundidad_signo"].min())
    evidencias = "|".join(sorted(set(firmadas["Evidencia"])))
    pmids = "|".join(sorted({p for ps in firmadas["PMIDs"] for p in ps}))

    contexto = firmadas["CL_no_NK"] != ""
    indirecta = firmadas["Calificador"].str.startswith("acts_upstream_of")
    fiables = firmadas[firmadas["Experimental"] & (firmadas["PMIDs"].str.len() > 0)
                       & (firmadas["Profundidad_signo"] <= PROFUNDIDAD_MAX_ACEPTAR)
                       & ~contexto & ~indirecta]

    if signo == "conflicto":
        motivos.append("conflicto")
    if en_vigilancia(gen):
        motivos.append("vigilancia")
    if prof > PROFUNDIDAD_MAX_ACEPTAR:
        motivos.append("lejano")
    if not (firmadas["Experimental"] & (firmadas["PMIDs"].str.len() > 0)).any():
        motivos.append("sin_experimental")
    if contexto.any():
        motivos.append("contexto_no_NK")
    if indirecta.any():
        motivos.append("indirecto")

    if signo == "conflicto":
        destino = LLM_Y_REVISION
    elif en_vigilancia(gen) or fiables.empty:
        destino = LLM
    else:
        destino = ACEPTAR_GO
    return signo, prof, evidencias, pmids, destino, "|".join(motivos)


def triaje_pares(df_excel, df_anot):
    """Una fila por par (Gen, Ruta) del Excel con el signo GO y a dónde va (aceptar_GO / LLM / ...)."""
    info = df_excel[["Gen", "GO_ID", "Ruta_Nombre", "Estado_Original"]].drop_duplicates()
    grupos = dict(tuple(df_anot.groupby(["Gen", "GO_ID"]))) if not df_anot.empty else {}
    filas = []
    for _, f in info.iterrows():
        signo, prof, evid, pmids, destino, motivo = _triaje_par(f["Gen"], grupos.get((f["Gen"], f["GO_ID"])))
        # c = s·d: un regulador negativo que sube en una ruta activada es un freno, no un error de signo
        d = 1 if f["Estado_Original"] == "Activada" else -1
        c = d * int(signo) if signo in ("+1", "-1") else None
        filas.append({**f.to_dict(), "Signo_GO": signo, "Profundidad": prof, "Evidencias_signo": evid,
                      "PMIDs_signo": pmids, "Destino": destino, "Motivo": motivo,
                      "Contribucion": c, "Freno_retroalimentacion": c == -1})
    return pd.DataFrame(filas, columns=COLUMNAS)
