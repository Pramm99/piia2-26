"""Filtro de inmunoglobulinas: se evalúa la Ig completa, no cada subunidad (cadena pesada, κ, λ...).

Se interseca el conjunto de genes con la lista HGNC (locus_type "immunoglobulin gene") más las
excepciones. Es más rápido que filtrar antes por el prefijo IG: la intersección recorre el conjunto
pequeño (~230 símbolos) y no depende de cuántos genes haya (medido el 2026-11-08).

Las Ig no activan ni inhiben la ruta: sus pares no buscan abstracts, salen como «neutro» y llevan
la función de la Ig completa tomada de UniProt Swiss-Prot (FUNCTION y, para la IgA, SUBUNIT).
"""
import os

import pandas as pd

from config import (EXCEPCIONES_IG, HGNC_IG_FILE, HGNC_IG_URL, IG_CON_SUBUNIDAD, IG_FUNCION_PROPIA,
                    IG_GEN_PLANTILLA, IG_INICIO_PARRAFO)
from fuentes.cache import cargar_json, guardar_json
from fuentes.uniprot import entradas_uniprot
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
        guardar_json(simbolos, destino)
    return set(cargar_json(destino))


def detectar_inmunoglobulinas(genes):
    """Devuelve los genes que son inmunoglobulinas (lista HGNC + excepciones)."""
    return {g.strip().upper() for g in genes} & (cargar_lista_ig() | EXCEPCIONES_IG)


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
    entradas = entradas_uniprot(set(igs) | {IG_GEN_PLANTILLA})
    textos = {g: funcion_ig_completa(g, entradas) for g in igs}
    df["Signo"] = SIGNO_NEUTRO
    df["Motivo"] = "inmunoglobulina"
    df["Funcion_Ig_completa"] = df["Gen"].map(lambda g: textos[g][0])
    df["UniProt"] = df["Gen"].map(lambda g: textos[g][1])
    df["Regla_texto"] = df["Gen"].map(lambda g: textos[g][2])
    return df.reset_index(drop=True)
