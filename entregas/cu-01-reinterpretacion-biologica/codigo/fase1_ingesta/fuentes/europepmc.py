"""Búsqueda dirigida en Europe PMC: artículos de PubMed cuyo título o abstract nombran el gen y la ruta."""
import time

from config import (EPMC_BUSQUEDAS_CACHE, EPMC_FRASES_POR_CONSULTA, EPMC_RESULTADOS_POR_CONSULTA,
                    EPMC_SEARCH_POST)
from fuentes.cache import cargar_json, guardar_json
from red import configurar_sesion


def _bloque(campo_valores):
    return "(" + " OR ".join(f'TITLE_ABS:"{v.replace(chr(34), "")}"' for v in campo_valores) + ")"


def construir_consultas(nombres_gen, frases_ruta):
    """Una consulta por bloque de frases: (gen OR alias...) AND (frase1 OR frase2...) AND SRC:MED."""
    gen = _bloque(sorted(nombres_gen))
    frases = sorted(frases_ruta)
    return [f"{gen} AND {_bloque(frases[i:i + EPMC_FRASES_POR_CONSULTA])} AND SRC:MED"
            for i in range(0, len(frases), EPMC_FRASES_POR_CONSULTA)]


def buscar(consultas, destino=EPMC_BUSQUEDAS_CACHE):
    """{consulta: [PMIDs más relevantes]}, con caché en disco (una petición por consulta nueva)."""
    cache = cargar_json(destino)
    pendientes = [q for q in dict.fromkeys(consultas) if q not in cache]
    if pendientes:
        print(f"📥 Europe PMC: {len(pendientes)} búsquedas dirigidas ...")
        sesion = configurar_sesion()
        for i, q in enumerate(pendientes, 1):
            try:
                r = sesion.post(EPMC_SEARCH_POST, data={"query": q, "format": "json", "resultType": "lite",
                                                        "pageSize": EPMC_RESULTADOS_POR_CONSULTA}, timeout=60)
                r.raise_for_status()
                cache[q] = [str(a["pmid"]) for a in r.json().get("resultList", {}).get("result", [])
                            if a.get("pmid")]
            except Exception as e:
                print(f"⚠️ Europe PMC: {e}")  # no se cachea: se reintentará en la próxima ejecución
            if i % 100 == 0:
                guardar_json(cache, destino)
            time.sleep(0.1)
        guardar_json(cache, destino)
    return {q: cache.get(q, []) for q in consultas}
