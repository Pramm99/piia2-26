"""UniProt Swiss-Prot (humano): secciones FUNCTION y SUBUNIT, y las frases de FUNCTION con sus PMIDs."""
import re

from config import UNIPROT_API, UNIPROT_CACHE
from fuentes.cache import cargar_json, guardar_json
from red import configurar_sesion

# UniProt cita al final de cada frase o grupo de frases: "(PubMed:123, PubMed:456)"
CITA = re.compile(r"\((?:PubMed:\d+(?:,\s*)?)+\)")
PMID = re.compile(r"PubMed:(\d+)")


def _entrada(sesion, gen):
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


def entradas_uniprot(genes, destino=UNIPROT_CACHE):
    """{gen: {Accesion, Funcion, Subunidad}}, con caché en disco (una consulta por gen la primera vez)."""
    cache = cargar_json(destino)
    pendientes = sorted(set(genes) - set(cache))
    if pendientes:
        print(f"📥 Consultando UniProt para {len(pendientes)} genes ...")
        sesion = configurar_sesion()
        for i, g in enumerate(pendientes, 1):
            cache[g] = _entrada(sesion, g)
            if i % 50 == 0:
                guardar_json(cache, destino)
        guardar_json(cache, destino)
    return {g: cache[g] for g in genes}


def frases_funcion(funcion):
    """[(pmids, frase)]: cada tramo de FUNCTION con los PMIDs que lo respaldan (sin tramos sin cita)."""
    frases, inicio = [], 0
    for m in CITA.finditer(funcion):
        frase = funcion[inicio:m.start()].strip(" .")
        if frase:
            frases.append((PMID.findall(m.group()), frase))
        inicio = m.end()
    return frases
