"""Cell Ontology (OLS4): los tipos celulares compatibles con la célula del estudio, es decir, su término, sus
ancestros y sus subtipos (#51). Una anotación de GO con occurs_in de otro CL describe el efecto en otra célula y no
se acepta sin el LLM. Para NK se usa la lista fija de config.py, sin red."""
from urllib.parse import quote

from config import CELL_ONTOLOGY_CACHE, CL_COMPATIBLES_NK, CL_NK, OLS4_API
from fuentes.cache import cargar_json, guardar_json
from red import configurar_sesion


def _terminos(sesion, cl: str, relacion: str) -> set:
    """CL de los ancestros o descendientes jerárquicos (is_a y part_of) de un término, siguiendo la paginación."""
    iri = quote(quote(f"http://purl.obolibrary.org/obo/{cl.replace(':', '_')}", safe=""), safe="")
    url, ids = f"{OLS4_API}/{iri}/{relacion}?size=500", set()
    while url:
        r = sesion.get(url, timeout=60)
        r.raise_for_status()
        datos = r.json()
        ids |= {t["obo_id"] for t in datos.get("_embedded", {}).get("terms", [])
                if str(t.get("obo_id", "")).startswith("CL:")}
        url = datos.get("_links", {}).get("next", {}).get("href")
    return ids


def cl_compatibles(cl: str, destino=CELL_ONTOLOGY_CACHE) -> frozenset:
    """El término, sus ancestros y sus subtipos. Con caché en disco: solo consulta OLS4 la primera vez por término."""
    if cl == CL_NK:
        return frozenset(CL_COMPATIBLES_NK)
    cache = cargar_json(destino)
    if cl not in cache:
        print(f"📥 Consultando Cell Ontology (OLS4) para {cl} ...")
        sesion = configurar_sesion()
        try:
            ids = _terminos(sesion, cl, "hierarchicalAncestors") | _terminos(sesion, cl, "hierarchicalDescendants")
        except Exception as exc:  # sin la lista no se puede decidir qué anotaciones son de otra célula
            raise RuntimeError(f"No se pudo consultar Cell Ontology para {cl} en OLS4: {exc}") from exc
        cache[cl] = sorted(ids | {cl})
        guardar_json(cache, destino)
    return frozenset(cache[cl])
