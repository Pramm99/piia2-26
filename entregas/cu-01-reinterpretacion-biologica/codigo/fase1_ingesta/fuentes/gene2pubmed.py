"""NCBI gene2pubmed + MeSH de la ruta: los artículos que NCBI liga al gen humano y que el indexador de MeSH marcó con el
tema de la ruta y con «Humans». NCBI liga el gen al artículo y MeSH juzga el tema, así que la ruta no tiene que aparecer
con las palabras de GO en el abstract (los autores escriben «Th2 differentiation», no «T-helper 2 cell
differentiation»).

La consulta MeSH de cada ruta sale de tabla_go_mesh.tsv, hecha a mano y versionada (#31). Es la última fuente externa:
solo actúa sobre los pares que siguen sin abstract tras GeneRIF y Europe PMC (pmid_externos.py).
"""
import csv
import time

from config import GENE2PUBMED_CACHE, MYGENE_API, NCBI_API_KEY, NCBI_ELINK, NCBI_EMAIL, TABLA_GO_MESH
from fuentes.cache import cargar_json, guardar_json
from red import configurar_sesion


def leer_tabla(ruta=TABLA_GO_MESH):
    """{GO_ID: consulta Entrez} de las rutas que tienen MeSH (las «sin_mesh» no se consultan)."""
    with open(ruta, encoding="utf-8") as f:
        # Sin entrecomillar: las consultas llevan comillas («"T-Lymphocytes"[mh]»)
        return {r["GO_ID"]: r["Consulta_MeSH"] for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
                if r["Consulta_MeSH"]}


def _entrez(sesion, genes):
    """{símbolo: Entrez Gene ID} de MyGene.info."""
    r = sesion.post(MYGENE_API, data={"q": ",".join(genes), "scopes": "symbol", "species": "human",
                                      "fields": "entrezgene"}, timeout=120)
    r.raise_for_status()
    return {h["query"]: str(h["entrezgene"]) for h in r.json() if not h.get("notfound") and h.get("entrezgene")}


def articulos(consultas, destino=GENE2PUBMED_CACHE):
    """{(gen, consulta): [PMIDs, del más reciente al más antiguo]} con caché en disco: una petición elink por par
    (gen, consulta) la primera vez."""
    cache = cargar_json(destino)
    clave = lambda g, c: f"{g}|{c}"
    pendientes = sorted({(g, c) for g, c in consultas if clave(g, c) not in cache})
    if pendientes:
        print(f"📥 gene2pubmed + MeSH: {len(pendientes)} consultas a NCBI ...")
        sesion = configurar_sesion()
        ids = _entrez(sesion, sorted({g for g, _ in pendientes}))
        pausa = 0.12 if NCBI_API_KEY else 0.35  # 10 o 3 peticiones por segundo
        for i, (g, c) in enumerate(pendientes, 1):
            pmids = set()
            if ids.get(g):
                params = {"dbfrom": "gene", "db": "pubmed", "linkname": "gene_pubmed", "id": ids[g],
                          "term": f'({c}) AND "Humans"[mh]', "retmode": "json", "tool": "piia2-cu01"}
                if NCBI_API_KEY:
                    params["api_key"] = NCBI_API_KEY
                if NCBI_EMAIL:
                    params["email"] = NCBI_EMAIL
                r = sesion.get(NCBI_ELINK, params=params, timeout=60)
                r.raise_for_status()
                for ls in r.json().get("linksets", []):
                    for db in ls.get("linksetdbs", []):
                        pmids.update(str(x) for x in db.get("links", []))
                time.sleep(pausa)
            cache[clave(g, c)] = sorted(pmids, key=int, reverse=True)
            if i % 50 == 0:
                guardar_json(cache, destino)
        guardar_json(cache, destino)
    return {(g, c): cache[clave(g, c)] for g, c in consultas}
