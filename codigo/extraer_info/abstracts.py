"""Descarga de abstracts (Europe PMC -> NCBI), con caché en disco y lotes que se parten si fallan.

La caché guarda el título y el abstract tal como llegan (marcados con "Crudo": True) y limpiar_texto se aplica
al leerlos: un cambio de la limpieza no obliga a volver a descargar. Las entradas sin esa marca son de la
caché antigua, que guardaba el texto ya limpio con un filtro que borraba texto entre «<» y «>»: se descargan
de nuevo la primera vez que se piden.
"""
import html
import json
import os
import re
import time
import xml.etree.ElementTree as ET

import pandas as pd

from config import CACHE_FILE, EPMC_API, NCBI_API_KEY, NCBI_EMAIL, NCBI_URL
from red import configurar_sesion

GUARDAR_CADA = 25  # lotes entre guardados de la caché (unos 1.000 PMIDs en Europe PMC, 2.500 en NCBI)


# Europe PMC mezcla etiquetas HTML (<h4>, <sup>, <i>...) con «<» y «>» del propio texto («(<20%)», «p < 0.001»):
# solo se quitan las etiquetas conocidas, para no borrar el texto que hay entre un «<» y el siguiente «>».
_FIN_TITULO = re.compile(r"</h[1-6]\s*>", re.I)  # «<h4>Conclusion</h4>DOT1L» -> «Conclusion: DOT1L»
_ETIQUETA_BLOQUE = re.compile(r"</?(?:h[1-6]|p|br|div|li|ul|ol|table|tr|td|th)\b[^<>]*/?>", re.I)  # -> espacio
_ETIQUETA_LINEA = re.compile(  # -> nada: «IL-1<sup>β</sup>» -> «IL-1β»
    r"</?(?:i|b|u|em|strong|sup|sub|span|a|sc|small|font|tt|big|inf|mml:[a-z]+)\b[^<>]*/?>", re.I)


def limpiar_texto(t):
    t = html.unescape(t or "")  # antes de quitar etiquetas: algunos títulos traen «CD8&lt;sup&gt;+&lt;/sup&gt;»
    t = _FIN_TITULO.sub(": ", t)
    t = _ETIQUETA_BLOQUE.sub(" ", t)
    t = _ETIQUETA_LINEA.sub("", t)
    return re.sub(r"\s+", " ", t).strip()


def cargar_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(tmp, CACHE_FILE)


def _epmc_lote(sesion, lote):
    query = "(" + " OR ".join(f"EXT_ID:{p}" for p in lote) + ") AND SRC:MED"
    params = {"query": query, "resultType": "core", "format": "json", "pageSize": 100}
    r = sesion.get(EPMC_API, params=params, timeout=30)
    r.raise_for_status()
    out = {}
    for art in r.json().get("resultList", {}).get("result", []):
        pmid = str(art.get("pmid", ""))
        ab = art.get("abstractText") or ""
        if pmid in lote and limpiar_texto(ab):
            out[pmid] = {"Titulo": art.get("title") or "", "Abstract": ab, "Crudo": True}
    return out


def _ncbi_lote(sesion, lote):
    """Devuelve {pmid: {Titulo, Abstract}} para todos los artículos que NCBI conoce
    (Abstract puede ser '' = confirmado sin abstract)."""
    data = {"db": "pubmed", "id": ",".join(lote), "retmode": "xml", "tool": "fase1_go_abstracts"}
    if NCBI_EMAIL:
        data["email"] = NCBI_EMAIL
    if NCBI_API_KEY:
        data["api_key"] = NCBI_API_KEY
    r = sesion.post(NCBI_URL, data=data, timeout=60)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = {}
    for nodo in list(root.findall("PubmedArticle")) + list(root.findall("PubmedBookArticle")):
        pmid = nodo.findtext("MedlineCitation/PMID") or nodo.findtext("BookDocument/PMID")
        if not pmid:
            continue
        t = nodo.find(".//ArticleTitle")
        if t is None:
            t = nodo.find(".//BookTitle")
        titulo = "".join(t.itertext()).strip() if t is not None else ""
        partes = nodo.findall(".//Abstract/AbstractText") or nodo.findall(".//OtherAbstract/AbstractText")
        textos = []
        for p in partes:
            txt = "".join(p.itertext()).strip()
            lab = p.get("Label")
            if txt:
                textos.append(f"{lab}: {txt}" if lab else txt)
        out[pmid] = {"Titulo": titulo, "Abstract": " ".join(textos), "Crudo": True}
    return out


def descargar_abstracts(pmids):
    """DataFrame (PMID, Titulo, Abstract) con el texto ya limpio de los PMIDs que tienen abstract."""
    sesion = configurar_sesion()
    cache = cargar_cache()
    pendientes = [p for p in pmids if not cache.get(p, {}).get("Crudo")]
    print(f"🌐 {len(pmids)} PMIDs únicos | {len(pmids) - len(pendientes)} en caché | {len(pendientes)} por descargar")

    # 1) Europe PMC
    for i in range(0, len(pendientes), 40):
        lote = pendientes[i:i + 40]
        try:
            cache.update(_epmc_lote(sesion, lote))
        except Exception as e:
            print(f"⚠️ Europe PMC (lote {i // 40}): {e}")
        if (i // 40 + 1) % GUARDAR_CADA == 0:  # si la ejecución se corta, no se repite lo ya descargado
            guardar_cache(cache)
        time.sleep(0.2)
    guardar_cache(cache)

    # 2) NCBI para lo que falte; si un lote falla, se parte en PMIDs individuales
    pendientes = [p for p in pendientes if not cache.get(p, {}).get("Crudo")]
    print(f"🔄 Pasando {len(pendientes)} PMIDs a NCBI...")
    pausa = 0.12 if NCBI_API_KEY else 0.35
    for i in range(0, len(pendientes), 100):
        lote = pendientes[i:i + 100]
        try:
            res = _ncbi_lote(sesion, lote)
        except Exception as e:
            print(f"⚠️ NCBI lote fallido ({e}); reintentando uno a uno")
            res = {}
            for p in lote:
                try:
                    res.update(_ncbi_lote(sesion, [p]))
                except Exception as e2:
                    print(f"   ❌ PMID {p}: {e2}")  # no se cachea: se reintentará en la próxima ejecución
                time.sleep(pausa)
        cache.update(res)  # incluye los confirmados sin abstract ("")
        if (i // 100 + 1) % GUARDAR_CADA == 0:
            guardar_cache(cache)
        time.sleep(pausa)
    guardar_cache(cache)

    filas, antiguas = [], 0
    for p in pmids:
        entrada = cache.get(p)
        if not entrada:
            continue
        antiguas += not entrada.get("Crudo")  # no se pudo volver a descargar: se usa el texto antiguo
        abstract = limpiar_texto(entrada["Abstract"])
        if abstract:
            filas.append({"PMID": p, "Titulo": limpiar_texto(entrada["Titulo"]), "Abstract": abstract})
    if antiguas:
        print(f"⚠️ {antiguas} PMIDs siguen con el texto de la caché antigua (puede faltar texto entre «<» y «>»); "
              f"se reintentarán en la próxima ejecución")
    return pd.DataFrame(filas, columns=["PMID", "Titulo", "Abstract"])
