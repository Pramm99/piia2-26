"""Descarga de abstracts (Europe PMC -> NCBI), con caché en disco y lotes que se parten si fallan."""
import html
import json
import os
import re
import time
import xml.etree.ElementTree as ET

import pandas as pd

from config import CACHE_FILE, EPMC_API, NCBI_API_KEY, NCBI_EMAIL, NCBI_URL
from red import configurar_sesion


def limpiar_texto(t):
    return html.unescape(re.sub(r"<[^>]+>", "", t or "")).strip()


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
        ab = limpiar_texto(art.get("abstractText"))
        if pmid in lote and ab:
            out[pmid] = {"Titulo": limpiar_texto(art.get("title")), "Abstract": ab}
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
        out[pmid] = {"Titulo": titulo, "Abstract": " ".join(textos)}
    return out


def descargar_abstracts(pmids):
    sesion = configurar_sesion()
    cache = cargar_cache()
    pendientes = [p for p in pmids if p not in cache]
    print(f"🌐 {len(pmids)} PMIDs únicos | {len(pmids) - len(pendientes)} en caché | {len(pendientes)} por descargar")

    # 1) Europe PMC
    for i in range(0, len(pendientes), 40):
        lote = pendientes[i:i + 40]
        try:
            cache.update(_epmc_lote(sesion, lote))
        except Exception as e:
            print(f"⚠️ Europe PMC (lote {i // 40}): {e}")
        time.sleep(0.2)
    guardar_cache(cache)

    # 2) NCBI para lo que falte; si un lote falla, se parte en PMIDs individuales
    pendientes = [p for p in pendientes if p not in cache]
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
        time.sleep(pausa)
    guardar_cache(cache)

    filas = [{"PMID": p, "Titulo": cache[p]["Titulo"], "Abstract": cache[p]["Abstract"]}
             for p in pmids if p in cache and cache[p]["Abstract"].strip()]
    return pd.DataFrame(filas, columns=["PMID", "Titulo", "Abstract"])
