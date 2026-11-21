"""Triaje del signo GO por par (Gen, Ruta): qué pares acepta el grafo y cuáles tiene que leer el LLM.

Sigue el informe «Polaridad GO como signo directo» (2026-11-08). El signo GO solo se acepta, de
forma provisional y con revisión ligera, si el camino es corto (≤ PROFUNDIDAD_MAX_ACEPTAR) y lo
respalda una anotación experimental con PMID que no ocurre en otra célula ni es indirecta.

Los pares que se quedan sin ningún abstract no pueden ir al LLM: se cierran de forma determinista
como UNKNOWN (no_concluyente) con su causa. Su signo GO, si lo hay, queda solo como pista: viene de
anotaciones sin experimento (IEA/ISS/IBA/TAS) y no cuenta en el Net Pathway Score. Ver
entregas/cu-01-reinterpretacion-biologica/docs/limitacion-pares-sin-abstract.md.
"""
import pandas as pd

from config import (EVIDENCIAS_FILOGENETICAS, GENES_VIGILANCIA, PREFIJOS_VIGILANCIA,
                    PROFUNDIDAD_MAX_ACEPTAR)

ACEPTAR_GO = "aceptar_GO"          # signo provisional del grafo, sin LLM (revisión ligera)
LLM = "LLM"
LLM_Y_REVISION = "LLM_y_revision"  # además, revisión humana
SIN_EVIDENCIA = "sin_evidencia"    # ningún abstract: UNKNOWN determinista, sin LLM
DESTINOS_SIN_LLM = {ACEPTAR_GO, SIN_EVIDENCIA}

SIGNO_DESCONOCIDO = "UNKNOWN"
ESTADO_NO_CONCLUYENTE = "no_concluyente"
DETALLE_CAUSA = {
    "anotado_sin_PMID": "Solo hay anotación GO sin artículo ({evidencias})",
    "sin_anotacion_GAF": "No tiene anotación en el GAF actual (probablemente una anotación antigua de org.Hs.eg.db)",
    "PMID_sin_abstract": "Sus PMIDs no tienen abstract en PubMed",
}
NOMBRE_EVIDENCIA = {"IEA": "electrónica", "ISS": "por similitud de secuencia, a menudo de otra especie",
                    "ISO": "por ortología", "ISA": "por alineamiento", "ISM": "por modelo de secuencia",
                    "IBA": "filogenética", "TAS": "declaración de autor rastreable", "NAS": "declaración de autor"}

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
    if firmadas["Estados"].apply(lambda s: "P" in s and not ({"+", "-"} & s)).all():
        motivos.append("signo_por_pertenencia")  # el signo sale solo de estar anotado a la ruta de regulación

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


def _detalle(causa, evidencias):
    nombres = ", ".join(f"{e} ({NOMBRE_EVIDENCIA.get(e, e)})" for e in evidencias.split("|") if e)
    return DETALLE_CAUSA[causa].format(evidencias=nombres or "sin código") + ". No se envía al LLM."


def cerrar_sin_evidencia(sin_evidencia, triaje, df_anot):
    """Cierra los pares sin ningún abstract: Resultado UNKNOWN, Estado no_concluyente y Motivo
    sin_evidencia:<causa>, con la pista GO y las anotaciones de origen. Marca su Destino en el triaje
    y les quita la contribución al score. Los aceptar_GO se respetan: su signo no depende del abstract."""
    if sin_evidencia.empty:
        return sin_evidencia, triaje
    j = lambda x: "|".join(sorted({v for v in x if isinstance(v, str) and v}))
    anot = (df_anot.groupby(["Gen", "GO_ID"], as_index=False)
            .agg(Evidencias_GO=("Evidencia", j), Referencias_GO=("Referencia", j), With_From_GO=("With_From", j))
            if not df_anot.empty else pd.DataFrame(columns=["Gen", "GO_ID", "Evidencias_GO", "Referencias_GO", "With_From_GO"]))
    claves = ["Gen", "GO_ID", "Estado_Original"]
    df = (sin_evidencia.merge(triaje[claves + ["Signo_GO", "Destino"]], on=claves, how="left")
          .merge(anot, on=["Gen", "GO_ID"], how="left"))
    for c in ("Evidencias_GO", "Referencias_GO", "With_From_GO"):
        df[c] = df[c].fillna("")
    aceptado = df["Destino"] == ACEPTAR_GO
    df["Resultado"] = df["Signo_GO"].where(aceptado, SIGNO_DESCONOCIDO)
    df["Estado"] = ["resuelto_GO" if a else ESTADO_NO_CONCLUYENTE for a in aceptado]
    df["Motivo"] = ["aceptar_GO" if a else f"sin_evidencia:{c}" for a, c in zip(aceptado, df["Causa"])]
    df["Detalle"] = ["Signo GO aceptado (anotación experimental con PMID sin abstract)." if a
                     else _detalle(c, e) for a, c, e in zip(aceptado, df["Causa"], df["Evidencias_GO"])]
    df["Pista_GO"] = df["Signo_GO"].fillna("")  # informativa: no cuenta en el score
    df = df[claves[:2] + ["Ruta_Nombre", "Estado_Original", "Resultado", "Estado", "Motivo", "Detalle",
                          "Pista_GO", "Causa", "Evidencias_GO", "Referencias_GO", "With_From_GO"]]

    cerrar = set(zip(df.loc[~aceptado, "Gen"], df.loc[~aceptado, "GO_ID"]))
    triaje = triaje.copy()
    marca = [p in cerrar for p in zip(triaje["Gen"], triaje["GO_ID"])]
    triaje.loc[marca, "Destino"] = SIN_EVIDENCIA
    triaje.loc[marca, "Motivo"] = [f"{m}|sin_evidencia" if m else "sin_evidencia" for m in triaje.loc[marca, "Motivo"]]
    triaje.loc[marca, "Contribucion"] = None
    triaje.loc[marca, "Freno_retroalimentacion"] = False
    return df.reset_index(drop=True), triaje
