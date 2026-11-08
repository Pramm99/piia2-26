"""Grafo de Gene Ontology: lectura del OBO, propagación a descendientes y polaridad de las relaciones."""
from collections import defaultdict, deque

from config import (ARISTAS_SIN_SIGNO, CORTAR_REGULACION_TRAS_PART_OF, PROPAGAR_REGULACION,
                    SIGNO_POR_PERTENENCIA_REGULACION, SIN_DIRECCION_COMO_PROCESO)

# Relaciones del grafo GO usadas para propagar y su "signo":
#   N = neutra (no cambia la polaridad), + = positiva, - = negativa, R = regula sin signo
#   P = pertenencia a una ruta de regulación con dirección: se comporta como + (ver descendientes)
ESTADO_RELACION = {
    "is_a": "N", "part_of": "N",
    "regulates": "R", "positively_regulates": "+", "negatively_regulates": "-",
}
RELACIONES_PROPAGACION = {r for r, e in ESTADO_RELACION.items()
                          if PROPAGAR_REGULACION or e == "N"}
NOMBRE_ESTADO = {"N": "is_a/part_of", "+": "positively_regulates",
                 "-": "negatively_regulates", "R": "regulates", "P": "pertenencia_regulacion"}
CON_SIGNO = ("+", "-", "P")


def cargar_go(ruta_obo):
    """Devuelve (hijos, alias): hijos[padre] = {(hijo, relacion)} y alias[alt_id|replaced_by] = id vigente."""
    hijos = defaultdict(set)
    alias = {}
    en_termino = False
    actual = None
    obsoleto = False
    reemplazo = None

    def cerrar():
        if actual and obsoleto and reemplazo:
            alias[actual] = reemplazo

    with open(ruta_obo, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea.startswith("["):
                cerrar()
                en_termino = linea == "[Term]"
                actual, obsoleto, reemplazo = None, False, None
                continue
            if not en_termino or ":" not in linea:
                continue
            if linea.startswith("id: GO:"):
                actual = linea[4:].strip()
            elif linea.startswith("alt_id: GO:") and actual:
                alias[linea[8:].strip()] = actual
            elif linea.startswith("is_a: GO:") and actual:
                hijos[linea.split()[1]].add((actual, "is_a"))
            elif linea.startswith("relationship: ") and actual:
                p = linea.split()
                if len(p) >= 3 and p[1] in RELACIONES_PROPAGACION:
                    hijos[p[2]].add((actual, p[1]))
            elif linea.startswith("is_obsolete: true"):
                obsoleto = True
            elif linea.startswith("replaced_by: GO:"):
                reemplazo = linea[13:].strip()
        cerrar()
    return hijos, alias


def componer(a, b):
    """Compone dos 'signos' de relación a lo largo de un camino (P cuenta como + salvo con N)."""
    if a == "N":
        return b
    if b == "N":
        return a
    a, b = ("+" if a == "P" else a), ("+" if b == "P" else b)
    if a == "R" or b == "R":
        return "R"
    return "+" if a == b else "-"  # (+,+)=+  (-,-)=+  (+,-)=-


def cargar_nombres(ruta_obo):
    """{GO_ID: nombre} leído del OBO (solo para informar; no afecta al grafo)."""
    nombres, actual = {}, None
    with open(ruta_obo, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea.startswith("["):
                actual = None
            elif linea.startswith("id: GO:"):
                actual = linea[4:].strip()
            elif linea.startswith("name:") and actual:
                nombres[actual] = linea[5:].strip()
    return nombres


def cargar_sinonimos(ruta_obo):
    """{GO_ID: [nombre, sinónimos EXACT...]} leído del OBO (vocabulario para buscar la ruta en textos)."""
    vocab, actual = defaultdict(list), None
    with open(ruta_obo, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea.startswith("["):
                actual = None
            elif linea.startswith("id: GO:"):
                actual = linea[4:].strip()
            elif actual and linea.startswith("name:"):
                vocab[actual].append(linea[5:].strip())
            elif actual and linea.startswith("synonym:") and " EXACT " in linea:
                vocab[actual].append(linea.split('"')[1])
    return vocab


def descendientes(go_id, hijos, estado_inicial="N"):
    """Devuelve {termino: {estado: profundidad}} con todos los descendientes de go_id (incluido él
    mismo, con estado_inicial a profundidad 0). El estado es la relación efectiva termino -> go_id (ver
    ESTADO_RELACION) y la profundidad, el camino más corto con ese estado (número de aristas).
    estado_inicial = 'P' para rutas de regulación con dirección: sus descendientes is_a también ejecutan
    esa regulación. Tres cortes del signo:
      - una regulación por encima de un part_of no conserva el signo (deprecado en RO);
      - las aristas de ARISTAS_SIN_SIGNO generalizan demasiado y dejan el camino sin signo;
      - una parte (part_of) de una regulación no hereda el signo de pertenencia (P -> N)."""
    res = defaultdict(dict)
    res[go_id][estado_inicial] = 0
    inicio = (go_id, estado_inicial, False)  # (termino, estado, ¿hay un part_of por encima?)
    vistos = {inicio}
    cola = deque([(inicio, 0)])
    while cola:  # BFS: la primera vez que se llega a (termino, estado) es por el camino más corto
        (t, est, tras_part_of), prof = cola.popleft()
        for h, rel in hijos.get(t, ()):
            signo = ESTADO_RELACION[rel]
            if signo != "N" and tras_part_of and CORTAR_REGULACION_TRAS_PART_OF:
                signo = "R"
            nuevo = "N" if est == "P" and rel == "part_of" else componer(est, signo)
            if (h, t) in ARISTAS_SIN_SIGNO and nuevo in CON_SIGNO:
                nuevo = "R"
            clave = (h, nuevo, tras_part_of or rel == "part_of")
            if clave not in vistos:
                vistos.add(clave)
                res[h].setdefault(nuevo, prof + 1)
                cola.append((clave, prof + 1))
    return res


def reguladores_dirigidos(hijos):
    """Términos con positively_regulates o negatively_regulates hacia otro: «positive/negative regulation of X»
    (se detecta por la estructura del OBO, no por el nombre)."""
    return {h for hs in hijos.values() for h, rel in hs
            if rel in ("positively_regulates", "negatively_regulates")}


def reguladores_sin_direccion(hijos):
    """{término: X} para los «regulation of X» sin dirección (solo relación regulates hacia X)."""
    dirigidos = reguladores_dirigidos(hijos)
    res = {}
    for objetivo, hs in sorted(hijos.items()):
        for h, rel in sorted(hs):
            if rel == "regulates" and h not in dirigidos:
                res.setdefault(h, objetivo)
    return res


def _descendientes_ruta(ruta, hijos, dirigidos, sin_direccion):
    """Descendientes de la ruta con el estado respecto a ella; en una «regulation of X» sin dirección,
    los términos de su subárbol llevan su estado respecto a X (la ruta se trata como X)."""
    desc = descendientes(ruta, hijos, "P" if ruta in dirigidos else "N")
    if ruta in sin_direccion:
        respecto_x = descendientes(sin_direccion[ruta], hijos)
        desc = {t: respecto_x.get(t, e) for t, e in desc.items()}
    return desc


def construir_desc_map(pares, hijos):
    """desc_map[termino_GO][ruta_del_Excel] = {estado de la relación termino -> ruta: profundidad}."""
    desc_map = defaultdict(dict)
    dirigidos = reguladores_dirigidos(hijos) if SIGNO_POR_PERTENENCIA_REGULACION else set()
    sin_direccion = reguladores_sin_direccion(hijos) if SIN_DIRECCION_COMO_PROCESO else {}
    for ruta in {r for _, r in pares}:
        for t, estados in _descendientes_ruta(ruta, hijos, dirigidos, sin_direccion).items():
            desc_map[t][ruta] = estados
    return desc_map


def estados_efectivos(estados):
    """Un término 'positive regulation of Y' llega también por el camino sin signo
    (su padre 'regulation of Y' -> regulates). Si ya hay camino con signo, el 'R' sobra.
    Acepta un set de estados o un dict {estado: profundidad} y devuelve lo mismo filtrado."""
    if any(e in estados for e in CON_SIGNO):
        return {e: v for e, v in estados.items() if e != "R"} if isinstance(estados, dict) else estados - {"R"}
    return estados.copy()


def polaridad_desde_estados(estados):
    """+1 / -1 si el camino de regulación tiene signo; 'conflicto' si hay ambos; '' si no hay."""
    pos, neg = "+" in estados or "P" in estados, "-" in estados
    if pos and neg:
        return "conflicto"
    return "+1" if pos else "-1" if neg else ""
