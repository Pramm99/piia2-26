"""NCBI GeneRIF (frases curadas sobre la función del gen, cada una con su PMID), a través de MyGene.info.

También guarda el nombre completo y los alias del gen: un GeneRIF puede venir de un artículo con
varios genes, y pmid_externos.py comprueba que el texto nombra de verdad al gen.
"""
from config import MYGENE_API, MYGENE_CACHE
from fuentes.cache import cargar_json, guardar_json
from red import configurar_sesion

LOTE = 1000  # máximo de MyGene.info por petición
VACIO = {"Nombre": "", "Alias": [], "GeneRIF": []}


def datos_mygene(genes, destino=MYGENE_CACHE):
    """{gen: {Nombre, Alias, GeneRIF: [{PMID, Texto}]}} para símbolos humanos, con caché en disco."""
    cache = cargar_json(destino)
    pendientes = sorted(set(genes) - set(cache))
    if pendientes:
        print(f"📥 Consultando GeneRIF (MyGene.info) para {len(pendientes)} genes ...")
        sesion = configurar_sesion()
        for i in range(0, len(pendientes), LOTE):
            lote = pendientes[i:i + LOTE]
            r = sesion.post(MYGENE_API, data={"q": ",".join(lote), "scopes": "symbol", "species": "human",
                                              "fields": "name,alias,generif"}, timeout=120)
            r.raise_for_status()
            for g in lote:
                cache.setdefault(g, VACIO)
            for h in r.json():
                if h.get("notfound"):
                    continue
                rifs = h.get("generif", [])
                rifs = rifs if isinstance(rifs, list) else [rifs]
                alias = h.get("alias", [])
                cache[h["query"]] = {
                    "Nombre": h.get("name", ""),
                    "Alias": alias if isinstance(alias, list) else [alias],
                    "GeneRIF": [{"PMID": str(x["pubmed"]), "Texto": x.get("text", "")}
                                for x in rifs if x.get("pubmed")],
                }
        guardar_json(cache, destino)
    return {g: cache.get(g, VACIO) for g in genes}
