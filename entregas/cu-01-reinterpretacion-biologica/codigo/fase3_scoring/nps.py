"""Fase 3 (spec de scoring): votos de cada artículo -> signo del par (gen, ruta) -> Net Pathway Score de la ruta.

Solo lee ficheros locales (salidas de las Fases 1 y 2 y, si lo hay, el log2FC de CIMUS) y es determinista:
no llama a ningún modelo ni a la red, así que se puede repetir sin gastar cupo. No reescribe nada de las
fases anteriores.

  1. Voto: cada fila resuelta de Por_ruta (Fase 2) vota su Signo_ruta con peso
     w = Confianza_final / 100 × f_contexto (especie y tipo celular de la pregunta).
  2. Par: reglas 1-9 de la spec, en orden (Ig, GO, sin_evidencia, mayoría, conflicto, revisar, contradictorio,
     pendiente, UNKNOWN). Un conflicto no se promedia a 0: va a revisar con los recuentos visibles.
  3. Ruta (término GO, juntando las dos listas de CIMUS): c = s × d y NPS = media de c sobre los pares
     resueltos con signo ±1; todos los genes pesan igual. Los neutros no entran (se informan como Fraccion_neutros).
     Con el log2FC de CIMUS se calcula además NPS_log2FC = Σ c·|log2FC| / Σ |log2FC| como sensibilidad: las rutas
     cuya lectura cambia llevan Sensible_al_peso.
  4. Para leer a mano lo que quedó sin signo: la hoja Abstracts_sin_signo da cada artículo de los pares UNKNOWN que sí
     tienen evidencia (enlace a PubMed, título, abstract y lo que respondió el modelo).
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from fase2_inferencia.esquema import (ESTADO_NO_CONCLUYENTE, ESTADO_PENDIENTE, ESTADO_RESUELTO, ESTADO_REVISAR,
                                  SIGNO_DESCONOCIDO, SIGNO_NEGATIVO, SIGNO_NEUTRO, SIGNO_POSITIVO)
from fase2_inferencia.limpieza import normalizar_pmid, valor_texto

from . import config

CLASES = (SIGNO_POSITIVO, SIGNO_NEGATIVO, SIGNO_NEUTRO)
VALOR = {SIGNO_POSITIVO: 1, SIGNO_NEGATIVO: -1, SIGNO_NEUTRO: 0}
DIRECCION = {"Activada": 1, "Suprimida": -1}  # nombre de la lista de CIMUS -> gen up / down

# Hojas y columnas que se leen (si falta alguna, ValueError con su nombre)
COLUMNAS_FASE2 = {"Por_ruta": ("Gen", "GO_ID", "PMID", "Proceso_ID", "Signo_ruta", "Estado", "Motivos",
                               "Confianza_final"),
                  "Preguntas": ("Gen", "PMID", "Proceso_ID", "Organismo", "Tipo_celular")}
COLUMNAS_FASE1 = {"Triaje_polaridad": ("Gen", "GO_ID", "Ruta_Nombre", "Estado_Original", "Signo_GO", "Destino"),
                  "Inmunoglobulinas": ("Gen", "GO_ID", "Ruta_Nombre", "Estado_Original")}
URL_PUBMED = "https://pubmed.ncbi.nlm.nih.gov/{}/"


def leer_hojas(ruta, columnas: Dict[str, Tuple[str, ...]]) -> Dict[str, pd.DataFrame]:
    """Lee las hojas pedidas y comprueba que traen las columnas que usa el scoring."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise ValueError(f"No existe el fichero de entrada: {ruta}")
    hojas = pd.read_excel(ruta, sheet_name=None)
    faltan = [h for h in columnas if h not in hojas]
    if faltan:
        raise ValueError(f"{ruta.name}: faltan las hojas {', '.join(faltan)}")
    for hoja, cols in columnas.items():
        faltan = [c for c in cols if c not in hojas[hoja].columns]
        if faltan:
            raise ValueError(f"{ruta.name}, hoja {hoja}: faltan las columnas {', '.join(faltan)}")
    return {h: hojas[h] for h in columnas}


def leer_log2fc(ruta, direcciones: Dict[str, int]) -> Dict[str, float]:
    """Fichero de CIMUS (.xlsx o .csv) con Gen y log2FC, o su tabla de expresión diferencial tal cual (el gen en
    la primera columna, sin nombre, y log2FoldChange). Un log2FC cuyo signo contradice la lista del gen
    (negativo en la de genes up, positivo en la de down) es un error de entrada, no un dato."""
    ruta = Path(ruta)
    if ruta.suffix.lower() == ".csv":
        df = pd.read_csv(ruta, sep=None, engine="python", encoding="utf-8-sig")
    else:
        df = pd.read_excel(ruta)
    if "Gen" not in df.columns and str(df.columns[0]).startswith("Unnamed"):
        df = df.rename(columns={df.columns[0]: "Gen"})
    df = df.rename(columns={"log2FoldChange": "log2FC"})
    faltan = [c for c in ("Gen", "log2FC") if c not in df.columns]
    if faltan:
        raise ValueError(f"{ruta.name}: faltan las columnas {', '.join(faltan)}")
    valores = {}
    for gen, fc in zip(df["Gen"].map(valor_texto).str.upper(), pd.to_numeric(df["log2FC"], errors="coerce")):
        if not gen or pd.isna(fc):
            continue
        d = direcciones.get(gen)
        if d is not None and fc * d < 0:
            raise ValueError(f"log2FC de {gen} ({fc}) contradice su lista ({'up' if d > 0 else 'down'})")
        valores[gen] = float(fc)
    return valores


def leer_abstracts(ruta) -> pd.DataFrame:
    """Título y abstract de cada PMID (hoja Con_abstract de la Fase 1). Es opcional: sin la hoja, tabla vacía."""
    vacio = pd.DataFrame(columns=["PMID", "Titulo", "Abstract"])
    if "Con_abstract" not in pd.ExcelFile(ruta).sheet_names:
        return vacio
    df = pd.read_excel(ruta, sheet_name="Con_abstract")
    if not {"PMID", "Titulo", "Abstract"} <= set(df.columns):
        return vacio
    df = df[["PMID", "Titulo", "Abstract"]].copy()
    df["PMID"] = df["PMID"].map(normalizar_pmid)
    return df.drop_duplicates("PMID")


def normalizar_signo(v) -> str:
    """Excel convierte en número una columna que solo trae «+1»/«-1»: 1, 1.0 o '1' -> '+1'."""
    s = valor_texto(v)
    try:
        return {1: SIGNO_POSITIVO, -1: SIGNO_NEGATIVO}.get(int(float(s)), s)
    except ValueError:
        return s


def peso(confianza, organismo, tipo_celular) -> Tuple[float, bool]:
    """w = Confianza_final / 100 × f_contexto. Devuelve también si se usó la confianza por defecto."""
    por_defecto = confianza is None or pd.isna(confianza)
    f = 1.0
    if valor_texto(organismo) not in ("",) + config.ORGANISMOS_VALIDOS:
        f *= config.FACTOR_CONTEXTO
    if valor_texto(tipo_celular) not in ("",) + config.TIPOS_CELULARES_VALIDOS:
        f *= config.FACTOR_CONTEXTO
    c = config.CONFIANZA_POR_DEFECTO if por_defecto else float(confianza)
    return c / 100 * f, por_defecto


def casos_con_peso(por_ruta: pd.DataFrame, preguntas: pd.DataFrame) -> pd.DataFrame:
    """Por_ruta con el contexto de su pregunta (unido por Gen, PMID y Proceso_ID) y el peso de cada fila."""
    clave = ["Gen", "PMID", "Proceso_ID"]
    p = preguntas[clave + ["Organismo", "Tipo_celular"]].copy()
    r = por_ruta.copy()
    for df in (p, r):
        df["PMID"] = df["PMID"].map(normalizar_pmid)
        df["Proceso_ID"] = df["Proceso_ID"].map(valor_texto)
    r = r.merge(p.drop_duplicates(clave), on=clave, how="left")
    pesos = [peso(c, o, t) for c, o, t in zip(r["Confianza_final"], r["Organismo"], r["Tipo_celular"])]
    r["w"] = [w for w, _ in pesos]
    r["peso_por_defecto"] = [d for _, d in pesos]
    r["Motivos"] = r["Motivos"].map(valor_texto)
    r["Signo_ruta"] = r["Signo_ruta"].map(normalizar_signo)
    return r


def _motivos(textos) -> List[str]:
    return sorted({m for t in textos for m in valor_texto(t).split("|") if m})


def _ganadora(w: Dict[str, float]) -> Optional[str]:
    """Clase de mayor peso; None si no hay peso o hay empate en cabeza."""
    maximo = max(w.values())
    cabeza = [k for k in CLASES if w[k] == maximo]
    return cabeza[0] if maximo > 0 and len(cabeza) == 1 else None


def signo_par(destino: str, casos: pd.DataFrame) -> Dict:
    """Reglas 4-9 de la spec para un par que pasó por el LLM (las 1-3 no miran los casos)."""
    votos = casos[(casos["Estado"] == ESTADO_RESUELTO) & casos["Signo_ruta"].isin(CLASES)]
    w = {k: float(votos.loc[votos["Signo_ruta"] == k, "w"].sum()) for k in CLASES}
    n = {k: votos.loc[votos["Signo_ruta"] == k, "PMID"].nunique() for k in CLASES}
    fila = {"W_pos": w[SIGNO_POSITIVO], "W_neg": w[SIGNO_NEGATIVO], "W_neutro": w[SIGNO_NEUTRO],
            "n_PMIDs": votos["PMID"].nunique(), "n_PMIDs_pos": n[SIGNO_POSITIVO],
            "n_PMIDs_neg": n[SIGNO_NEGATIVO], "n_PMIDs_neutro": n[SIGNO_NEUTRO],
            "Votos": "; ".join(f"{s}:{p}({x:.2f})" for s, p, x in
                               sorted(zip(votos["Signo_ruta"], votos["PMID"], votos["w"]))),
            "Signo_revisar": None}
    marcas = ["peso_por_defecto"] if votos["peso_por_defecto"].any() else []
    total = sum(w.values())

    def salida(signo, estado, motivos, revisar=None):
        fila.update(Signo_par=signo, Estado_par=estado, Motivos="|".join(motivos + marcas), Signo_revisar=revisar)
        return fila

    if total > 0:
        gana = _ganadora(w)
        minoria = (total - max(w.values())) / total
        if gana is not None and minoria < config.UMBRAL_MINORIA:
            motivos = (["minoria_discrepante"] if minoria > 0 else []) + \
                      (["evidencia_debil"] if total < config.MIN_PESO_EVIDENCIA else [])
            if destino == "LLM_y_revision":
                return salida(gana, ESTADO_REVISAR, ["LLM_y_revision"] + motivos, gana)
            return salida(gana, ESTADO_RESUELTO, motivos)
        return salida(SIGNO_DESCONOCIDO, ESTADO_REVISAR, ["conflicto_entre_abstracts"], gana)
    if len(votos):  # votos que no pesan nada (confianza 0): como si no hubiera
        marcas.append("votos_sin_peso")
    revisar = casos[casos["Estado"] == ESTADO_REVISAR]
    if len(revisar):
        w_rev = {k: float(revisar.loc[revisar["Signo_ruta"] == k, "w"].sum()) for k in CLASES}
        return salida(SIGNO_DESCONOCIDO, ESTADO_REVISAR, _motivos(revisar["Motivos"]), _ganadora(w_rev))
    if casos["Motivos"].str.split("|").map(lambda m: "contradictorio" in m).any():
        return salida(SIGNO_DESCONOCIDO, ESTADO_REVISAR, ["contradictorio"])
    if (casos["Estado"] == ESTADO_PENDIENTE).any():
        return salida(SIGNO_DESCONOCIDO, ESTADO_PENDIENTE, ["pendiente_fase2"])
    if casos.empty:  # la Fase 2 aún no ha preguntado por este par (p. ej. se ejecutó solo para un gen)
        return salida(SIGNO_DESCONOCIDO, ESTADO_PENDIENTE, ["sin_fase2"])
    return salida(SIGNO_DESCONOCIDO, ESTADO_NO_CONCLUYENTE, _motivos(casos["Motivos"]))


def tabla_pares(triaje: pd.DataFrame, igs: pd.DataFrame, casos: pd.DataFrame,
                log2fc: Optional[Dict[str, float]] = None) -> pd.DataFrame:
    """Una fila por par (gen, ruta) de la Fase 1, Ig incluidas, con su signo, estado y contribución."""
    por_par = {k: g for k, g in casos.groupby(["Gen", "GO_ID"])}
    vacio = casos.iloc[0:0]
    filas = []
    base = [(r, "Ig") for r in igs.to_dict("records")] + [(r, None) for r in triaje.to_dict("records")]
    for r, origen in base:
        gen, go = valor_texto(r["Gen"]), valor_texto(r["GO_ID"])
        destino = valor_texto(r.get("Destino"))
        fila = {"Gen": gen, "GO_ID": go, "Ruta_Nombre": valor_texto(r["Ruta_Nombre"]),
                "Estado_Original": valor_texto(r["Estado_Original"])}
        if origen == "Ig":  # regla 1
            fila.update(Signo_par=SIGNO_NEUTRO, Estado_par=ESTADO_RESUELTO, Motivos="inmunoglobulina")
        elif destino == "aceptar_GO":  # regla 2
            fila.update(Signo_par=normalizar_signo(r["Signo_GO"]), Estado_par=ESTADO_RESUELTO,
                        Motivos="aceptado_por_GO")
            origen = "GO"
        elif destino == "sin_evidencia":  # regla 3
            fila.update(Signo_par=SIGNO_DESCONOCIDO, Estado_par=ESTADO_NO_CONCLUYENTE, Motivos="sin_evidencia")
        else:  # reglas 4-9
            fila.update(signo_par(destino, por_par.get((gen, go), vacio)))
        fila["Origen"] = origen or ("LLM" if fila["Signo_par"] in CLASES and "W_pos" in fila else "ninguno")
        filas.append(fila)
    df = pd.DataFrame(filas)
    for c in ("W_pos", "W_neg", "W_neutro", "n_PMIDs", "n_PMIDs_pos", "n_PMIDs_neg", "n_PMIDs_neutro",
              "Votos", "Signo_revisar"):
        if c not in df.columns:  # ningún par pasó por el LLM
            df[c] = None
    for c in ("W_pos", "W_neg", "W_neutro"):
        df[c] = df[c].astype(float).fillna(0.0).round(3)
    for c in ("n_PMIDs", "n_PMIDs_pos", "n_PMIDs_neg", "n_PMIDs_neutro"):
        df[c] = df[c].astype(float).fillna(0).astype(int)
    df["Votos"] = df["Votos"].fillna("")
    # Todos los artículos que la Fase 2 leyó para el par, también los que no votaron (UNKNOWN, revisar, pendiente)
    consultados = casos.groupby(["Gen", "GO_ID"])["PMID"].agg(lambda s: "; ".join(sorted(set(map(str, s)))))
    df["PMIDs_consultados"] = [consultados.get((g, go), "") for g, go in zip(df["Gen"], df["GO_ID"])]
    df["Direccion"] = df["Estado_Original"].map({"Activada": "up", "Suprimida": "down"})
    d = df["Estado_Original"].map(DIRECCION)
    if log2fc is not None:
        df["Log2FC"] = df["Gen"].str.upper().map(log2fc)
        sin = df["Log2FC"].isna()
        df.loc[sin, "Motivos"] = df.loc[sin, "Motivos"].map(lambda m: "|".join(filter(None, [m, "sin_log2FC"])))
    else:
        df["Log2FC"] = float("nan")
    # Peso del gen solo en la sensibilidad (NPS_log2FC): |log2FC|, o 1 si el gen no lo tiene.
    df["m_log2FC"] = df["Log2FC"].abs().fillna(1.0)
    s = df["Signo_par"].map(VALOR).fillna(0)
    resuelto = df["Estado_par"] == ESTADO_RESUELTO
    df["Contribucion"] = (s * d).where(resuelto, 0.0).astype(float) + 0.0  # sin -0.0
    df["Freno_retroalimentacion"] = df["Contribucion"] < 0
    # Lo que aportaría el par si se confirmara su clase de mayor peso (NPS_con_revisar)
    df["c_revisar"] = (df["Signo_revisar"].map(VALOR).fillna(0) * d).where(df["Estado_par"] == ESTADO_REVISAR, 0.0)
    df = df.sort_values(["GO_ID", "Gen"], kind="mergesort").reset_index(drop=True)
    return df


def _lectura(nps, n_con_signo, cobertura) -> str:
    if n_con_signo < config.MIN_PARES_CON_SIGNO or cobertura < config.MIN_COBERTURA:
        return "insuficiente"
    if nps >= config.UMBRAL_NPS:
        return "activada"
    return "inhibida" if nps <= -config.UMBRAL_NPS else "mixta"


def _genes(g: pd.DataFrame) -> str:
    return "; ".join(sorted(g["Gen"]))


def tabla_rutas(pares: pd.DataFrame, con_log2fc: bool) -> pd.DataFrame:
    """Una fila por término GO, juntando los pares de las dos listas de CIMUS."""
    filas = []
    for go, g in pares.groupby("GO_ID", sort=True):
        resuelto = g["Estado_par"] == ESTADO_RESUELTO
        con_signo = g[resuelto & g["Signo_par"].isin((SIGNO_POSITIVO, SIGNO_NEGATIVO))]
        neutros = g[resuelto & (g["Signo_par"] == SIGNO_NEUTRO)]
        revisar = g[g["Estado_par"] == ESTADO_REVISAR]
        sin_ev = g["Motivos"].str.split("|").map(lambda m: "sin_evidencia" in m)
        nps = con_signo["Contribucion"].mean() if len(con_signo) else float("nan")
        rev = revisar[revisar["c_revisar"] != 0]
        den = len(con_signo) + len(rev)
        nps_rev = (con_signo["Contribucion"].sum() + rev["c_revisar"].sum()) / den if den else float("nan")
        m = con_signo["m_log2FC"]
        nps_fc = (con_signo["Contribucion"] * m).sum() / m.sum() if con_log2fc and len(con_signo) else float("nan")
        cobertura = (len(con_signo) + len(neutros)) / len(g)
        lectura = _lectura(nps, len(con_signo), cobertura)
        lectura_fc = _lectura(nps_fc, len(con_signo), cobertura) if con_log2fc else ""
        listas = set(g["Estado_Original"])
        filas.append({
            "GO_ID": go, "Ruta_Nombre": g["Ruta_Nombre"].iloc[0],
            "Listas": "ambas" if len(listas) > 1 else {"Activada": "activadas", "Suprimida": "suprimidas"}
            .get(next(iter(listas)), ""),
            "NPS": round(nps, 3), "NPS_con_revisar": round(nps_rev, 3), "Lectura": lectura,
            "NPS_log2FC": round(nps_fc, 3), "Lectura_log2FC": lectura_fc,
            "Sensible_al_peso": ("sí" if lectura_fc != lectura else "no") if con_log2fc else "",
            "n_total": len(g), "n_activan": int((g["Contribucion"] > 0).sum()),
            "n_inhiben": int((g["Contribucion"] < 0).sum()), "n_neutros": len(neutros), "n_revisar": len(revisar),
            "n_no_concluyente": int(((g["Estado_par"] == ESTADO_NO_CONCLUYENTE) & ~sin_ev).sum()),
            "n_sin_evidencia": int(sin_ev.sum()), "n_pendiente": int((g["Estado_par"] == ESTADO_PENDIENTE).sum()),
            "Cobertura": round(cobertura, 3),
            "Fraccion_neutros": round(len(neutros) / (len(con_signo) + len(neutros)), 3)
            if len(con_signo) + len(neutros) else float("nan"),
            "Genes_activan": _genes(g[g["Contribucion"] > 0]), "Genes_inhiben": _genes(g[g["Contribucion"] < 0]),
            "Genes_revisar": _genes(revisar)})
    df = pd.DataFrame(filas)
    orden = df["NPS"].abs().fillna(-1)
    return df.assign(_o=orden).sort_values(["_o", "GO_ID"], ascending=[False, True], kind="mergesort") \
        .drop(columns="_o").reset_index(drop=True)


COLUMNAS_ABSTRACTS = ["Gen", "GO_ID", "Ruta_Nombre", "Direccion", "Estado_par", "PMID", "Enlace", "Proceso",
                      "Veredicto_LLM", "Confianza_modelo", "Estado", "Motivos", "Cita", "Titulo", "Abstract"]


def tabla_abstracts_sin_signo(pares: pd.DataFrame, casos: pd.DataFrame, abstracts: pd.DataFrame) -> pd.DataFrame:
    """Una fila por artículo de cada par UNKNOWN que sí tiene casos en la Fase 2 (no concluyente, en revisión o
    pendiente), con su enlace a PubMed y lo que respondió el modelo: para leerlos a mano. Los pares sin_evidencia no
    tienen ningún artículo y no salen."""
    sin = pares.loc[pares["Signo_par"] == SIGNO_DESCONOCIDO, ["Gen", "GO_ID", "Ruta_Nombre", "Direccion", "Estado_par"]]
    cols = ["Gen", "GO_ID", "PMID", "Proceso", "Veredicto_LLM", "Confianza_modelo", "Estado", "Motivos", "Cita"]
    df = sin.merge(casos.reindex(columns=cols), on=["Gen", "GO_ID"], how="inner")
    df = df.merge(abstracts, on="PMID", how="left")
    df["Enlace"] = df["PMID"].map(URL_PUBMED.format)
    return df.reindex(columns=COLUMNAS_ABSTRACTS).sort_values(["GO_ID", "Gen", "PMID"], kind="mergesort") \
        .reset_index(drop=True)


def _fecha(ruta) -> str:
    return datetime.fromtimestamp(Path(ruta).stat().st_mtime).isoformat(timespec="seconds")


def resumen(pares: pd.DataFrame, rutas: pd.DataFrame, entradas: Dict[str, Optional[Path]],
            abstracts: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    filas = [("Estado_par", f"{e} {s}", int(n)) for (e, s), n in
             pares.groupby(["Estado_par", "Signo_par"]).size().items()]
    if abstracts is not None:
        filas.append(("Abstracts_sin_signo", "artículos (pares)",
                      f"{len(abstracts)} ({abstracts[['Gen', 'GO_ID']].drop_duplicates().shape[0]})"))
    filas += [("Lectura", k, int(n)) for k, n in rutas["Lectura"].value_counts().sort_index().items()]
    if (rutas["Lectura_log2FC"] != "").any():
        filas += [("Lectura_log2FC", k, int(n)) for k, n in rutas["Lectura_log2FC"].value_counts().sort_index().items()]
        filas.append(("Sensibilidad", "rutas Sensible_al_peso", int((rutas["Sensible_al_peso"] == "sí").sum())))
    filas += [("Entrada", k, f"{v} ({_fecha(v)})" if v else "no") for k, v in entradas.items()]
    filas += [("Parametro", k, str(getattr(config, k))) for k in
              ("ORGANISMOS_VALIDOS", "TIPOS_CELULARES_VALIDOS", "FACTOR_CONTEXTO", "CONFIANZA_POR_DEFECTO",
               "UMBRAL_MINORIA", "MIN_PESO_EVIDENCIA", "MIN_PARES_CON_SIGNO", "MIN_COBERTURA", "UMBRAL_NPS")]
    return pd.DataFrame(filas, columns=["Apartado", "Clave", "Valor"])


COLUMNAS_PAR = ["Gen", "GO_ID", "Ruta_Nombre", "Direccion", "Log2FC", "Signo_par", "Estado_par", "Motivos",
                "Origen", "W_pos", "W_neg", "W_neutro", "n_PMIDs", "n_PMIDs_pos", "n_PMIDs_neg", "n_PMIDs_neutro",
                "Votos", "PMIDs_consultados", "Signo_revisar", "Contribucion", "Freno_retroalimentacion"]


def calcular(fase1=config.FICHERO_FASE1, fase2=config.FICHERO_FASE2, log2fc=None):
    """Entradas -> (Por_par, Por_ruta, Resumen, Abstracts_sin_signo)."""
    f2 = leer_hojas(fase2, COLUMNAS_FASE2)
    f1 = leer_hojas(fase1, COLUMNAS_FASE1)
    triaje, igs = f1["Triaje_polaridad"], f1["Inmunoglobulinas"]
    casos = casos_con_peso(f2["Por_ruta"], f2["Preguntas"])
    direcciones = {valor_texto(g).upper(): DIRECCION.get(valor_texto(e)) for g, e in
                   pd.concat([triaje, igs])[["Gen", "Estado_Original"]].itertuples(index=False)}
    fc = leer_log2fc(log2fc, direcciones) if log2fc else None
    pares = tabla_pares(triaje, igs, casos, fc)
    rutas = tabla_rutas(pares, fc is not None)
    abstracts = tabla_abstracts_sin_signo(pares, casos, leer_abstracts(fase1))
    res = resumen(pares, rutas, {"Fase 1": Path(fase1), "Fase 2": Path(fase2),
                                 "log2FC": Path(log2fc) if log2fc else None}, abstracts)
    return pares[COLUMNAS_PAR], rutas, res, abstracts


def escribir(pares: pd.DataFrame, rutas: pd.DataFrame, res: pd.DataFrame, abstracts: Optional[pd.DataFrame] = None,
             ruta=config.FICHERO_SCORING) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(ruta) as w:
        rutas.to_excel(w, sheet_name="Por_ruta", index=False)
        pares.to_excel(w, sheet_name="Por_par", index=False)
        res.to_excel(w, sheet_name="Resumen", index=False)
        if abstracts is not None:
            abstracts.to_excel(w, sheet_name="Abstracts_sin_signo", index=False)
            hoja, col = w.sheets["Abstracts_sin_signo"], COLUMNAS_ABSTRACTS.index("PMID") + 1
            for fila, url in enumerate(abstracts["Enlace"], start=2):  # el PMID se abre en PubMed con un clic
                celda = hoja.cell(row=fila, column=col)
                celda.hyperlink, celda.style = url, "Hyperlink"
    return ruta
