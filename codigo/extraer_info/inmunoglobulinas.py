"""Filtro de inmunoglobulinas: se evalúa la Ig completa, no cada subunidad (cadena pesada, κ, λ...).

Se interseca el conjunto de genes con la lista HGNC (locus_type "immunoglobulin gene") más las
excepciones. Es más rápido que filtrar antes por el prefijo IG: la intersección recorre el conjunto
pequeño (~230 símbolos) y no depende de cuántos genes haya (medido el 2026-11-08).

Las Ig no activan ni inhiben la ruta: sus pares no buscan abstracts, salen como «neutro» y llevan
la función de la Ig completa tomada de UniProt Swiss-Prot (FUNCTION y, para la IgA, SUBUNIT).
"""
import json
import os

import pandas as pd

from config import (EXCEPCIONES_IG, HGNC_IG_FILE, HGNC_IG_URL, IG_CON_SUBUNIDAD, IG_FUNCION_PROPIA,
                    IG_GEN_PLANTILLA, IG_INICIO_PARRAFO, UNIPROT_API, UNIPROT_IG_FILE)
from red import configurar_sesion

SIGNO_NEUTRO = "neutro"


def cargar_lista_ig(destino=HGNC_IG_FILE):
    """Símbolos HGNC de inmunoglobulinas. Se descargan una vez y se guardan en caché (escritura atómica)."""
    if not os.path.exists(destino):
        print("📥 Descargando la lista de inmunoglobulinas de HGNC ...")
        r = configurar_sesion().get(HGNC_IG_URL, headers={"Accept": "application/json"}, timeout=60)
        r.raise_for_status()
        simbolos = sorted(d["symbol"].upper() for d in r.json()["response"]["docs"])
        if not simbolos:
            raise RuntimeError("HGNC no ha devuelto ninguna inmunoglobulina: revisa HGNC_IG_URL")
        _guardar_json(simbolos, destino)
    with open(destino, encoding="utf-8") as f:
        return set(json.load(f))


def detectar_inmunoglobulinas(genes):
    """Devuelve los genes que son inmunoglobulinas (lista HGNC + excepciones)."""
    return {g.strip().upper() for g in genes} & (cargar_lista_ig() | EXCEPCIONES_IG)


def _guardar_json(datos, destino):
    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
    tmp = destino + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
    os.replace(tmp, destino)


def _entrada_uniprot(sesion, gen):
    """{Accesion, Funcion, Subunidad} de la entrada Swiss-Prot humana del gen ('' si no tiene)."""
    params = {"query": f"gene_exact:{gen} AND organism_id:9606 AND reviewed:true",
              "fields": "accession,cc_function,cc_subunit", "format": "json"}
    r = sesion.get(UNIPROT_API, params=params, timeout=60)
    r.raise_for_status()
    res = r.json().get("results", [])
    if not res:
        return {"Accesion": "", "Funcion": "", "Subunidad": ""}
    textos = {"FUNCTION": [], "SUBUNIT": []}
    for c in res[0].get("comments", []):
        if c.get("commentType") in textos:
            textos[c["commentType"]] += [t["value"] for t in c.get("texts", [])]
    return {"Accesion": res[0]["primaryAccession"], "Funcion": " ".join(textos["FUNCTION"]),
            "Subunidad": " ".join(textos["SUBUNIT"])}


def cargar_uniprot_ig(genes, destino=UNIPROT_IG_FILE):
    """Entradas UniProt de los genes (y del gen plantilla), con caché en disco."""
    cache = {}
    if os.path.exists(destino):
        with open(destino, encoding="utf-8") as f:
            cache = json.load(f)
    pendientes = sorted((set(genes) | {IG_GEN_PLANTILLA}) - set(cache))
    if pendientes:
        print(f"📥 Consultando UniProt para {len(pendientes)} inmunoglobulinas ...")
        sesion = configurar_sesion()
        for g in pendientes:
            cache[g] = _entrada_uniprot(sesion, g)
        _guardar_json(cache, destino)
    return cache


def _parrafo_comun(funcion):
    i = funcion.find(IG_INICIO_PARRAFO)
    return funcion[i:] if i >= 0 else ""


def funcion_ig_completa(gen, entradas):
    """(texto, accesión, regla): la función de la Ig completa de la que forma parte el gen.
    Isotipos, J y PIGR usan su propio FUNCTION (más SUBUNIT en la IgA); el resto, el párrafo común."""
    e = entradas.get(gen, {})
    if gen in IG_FUNCION_PROPIA and e.get("Funcion"):
        texto = e["Funcion"]
        if gen in IG_CON_SUBUNIDAD and e.get("Subunidad"):
            return f"{texto} {e['Subunidad']}", e["Accesion"], "FUNCTION+SUBUNIT"
        return texto, e["Accesion"], "FUNCTION"
    comun = _parrafo_comun(e.get("Funcion", ""))
    if comun:
        return comun, e["Accesion"], "parrafo_comun"
    plantilla = entradas[IG_GEN_PLANTILLA]
    return _parrafo_comun(plantilla["Funcion"]), plantilla["Accesion"], f"parrafo_comun_de_{IG_GEN_PLANTILLA}"


def construir_hoja_ig(df_excel, igs):
    """Una fila por par (Ig, Ruta): signo neutro y la función de la Ig completa."""
    columnas = ["Gen", "GO_ID", "Ruta_Nombre", "Estado_Original", "Signo", "Motivo",
                "Funcion_Ig_completa", "UniProt", "Regla_texto"]
    df = df_excel[df_excel["Gen"].isin(igs)][columnas[:4]].drop_duplicates()
    if df.empty:
        return pd.DataFrame(columns=columnas)
    entradas = cargar_uniprot_ig(igs)
    textos = {g: funcion_ig_completa(g, entradas) for g in igs}
    df["Signo"] = SIGNO_NEUTRO
    df["Motivo"] = "inmunoglobulina"
    df["Funcion_Ig_completa"] = df["Gen"].map(lambda g: textos[g][0])
    df["UniProt"] = df["Gen"].map(lambda g: textos[g][1])
    df["Regla_texto"] = df["Gen"].map(lambda g: textos[g][2])
    return df.reset_index(drop=True)
