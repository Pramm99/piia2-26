"""Nombres de la proteína de cada gen: UniProt Swiss-Prot humano (nombre recomendado, cortos y alternativos) y
«other_names» de MyGene.info.

Sirven para que el filtro de mención (relevancia.menciona_gen) reconozca al gen cuando el abstract usa el nombre de
la proteína («beta-catenin», «lymphotactin», «macrophage inflammatory protein 1-alpha»). Solo se usan en ese filtro:
no van al prompt (cambiarían las huellas de todas las preguntas) ni a las consultas de Europe PMC.
"""
from config import MYGENE_API, NOMBRES_CACHE, UNIPROT_API
from fuentes.cache import cargar_json, guardar_json
from red import configurar_sesion


def _uniprot(sesion, gen):
    """Nombres de la proteína en la entrada Swiss-Prot humana del gen ([] si no tiene)."""
    params = {"query": f"gene_exact:{gen} AND organism_id:9606 AND reviewed:true", "fields": "protein_name",
              "format": "json"}
    r = sesion.get(UNIPROT_API, params=params, timeout=60)
    r.raise_for_status()
    nombres = []
    for entrada in r.json().get("results", [])[:1]:
        d = entrada.get("proteinDescription", {})
        for bloque in [d.get("recommendedName", {})] + d.get("alternativeNames", []):
            nombres.append(bloque.get("fullName", {}).get("value", ""))
            nombres += [s.get("value", "") for s in bloque.get("shortNames", [])]
    return [n for n in nombres if n]


def nombres_proteina(genes, destino=NOMBRES_CACHE):
    """{gen: [nombres de la proteína]} para símbolos humanos, con caché en disco."""
    cache = cargar_json(destino)
    pendientes = sorted(set(genes) - set(cache))
    if pendientes:
        print(f"📥 Consultando nombres de proteína (MyGene.info y UniProt) para {len(pendientes)} genes ...")
        sesion = configurar_sesion()
        r = sesion.post(MYGENE_API, data={"q": ",".join(pendientes), "scopes": "symbol", "species": "human",
                                          "fields": "other_names"}, timeout=120)
        r.raise_for_status()
        otros = {}
        for h in r.json():
            if not h.get("notfound"):
                o = h.get("other_names", [])
                otros.setdefault(h["query"], set()).update(o if isinstance(o, list) else [o])
        for i, g in enumerate(pendientes, 1):
            cache[g] = sorted(otros.get(g, set()) | set(_uniprot(sesion, g)))
            if i % 50 == 0:
                guardar_json(cache, destino)
        guardar_json(cache, destino)
    return {g: cache[g] for g in genes}
