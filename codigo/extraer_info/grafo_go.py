"""Grafo de Gene Ontology: lectura del OBO, propagación a descendientes y polaridad de las relaciones."""
from collections import defaultdict, deque

from config import PROPAGAR_REGULACION

# Relaciones del grafo GO usadas para propagar y su "signo":
#   N = neutra (no cambia la polaridad), + = positiva, - = negativa, R = regula sin signo
ESTADO_RELACION = {
    "is_a": "N", "part_of": "N",
    "regulates": "R", "positively_regulates": "+", "negatively_regulates": "-",
}
RELACIONES_PROPAGACION = {r for r, e in ESTADO_RELACION.items()
                          if PROPAGAR_REGULACION or e == "N"}
NOMBRE_ESTADO = {"N": "is_a/part_of", "+": "positively_regulates",
                 "-": "negatively_regulates", "R": "regulates"}


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


def _componer(a, b):
    """Compone dos 'signos' de relación a lo largo de un camino."""
    if a == "N":
        return b
    if b == "N":
        return a
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


def descendientes(go_id, hijos):
    """Devuelve {termino: {estados}} con todos los descendientes de go_id (incluido él mismo, 'N').
    El estado indica la relación efectiva termino -> go_id (ver ESTADO_RELACION)."""
    res = defaultdict(set)
    res[go_id].add("N")
    inicio = (go_id, "N")
    vistos = {inicio}
    cola = deque([inicio])
    while cola:
        t, est = cola.popleft()
        for h, rel in hijos.get(t, ()):
            nuevo = _componer(est, ESTADO_RELACION[rel])
            if (h, nuevo) not in vistos:
                vistos.add((h, nuevo))
                res[h].add(nuevo)
                cola.append((h, nuevo))
    return res


def construir_desc_map(pares, hijos):
    """desc_map[termino_GO][ruta_del_Excel] = {estados de la relación termino -> ruta}."""
    desc_map = defaultdict(dict)
    for ruta in {r for _, r in pares}:
        for t, estados in descendientes(ruta, hijos).items():
            desc_map[t][ruta] = estados
    return desc_map


def estados_efectivos(estados):
    """Un término 'positive regulation of Y' llega también por el camino sin signo
    (su padre 'regulation of Y' -> regulates). Si ya hay camino con signo, el 'R' sobra."""
    if "+" in estados or "-" in estados:
        return estados - {"R"}
    return set(estados)


def polaridad_desde_estados(estados):
    """+1 / -1 si el camino de regulación tiene signo; 'conflicto' si hay ambos; '' si no hay."""
    pos, neg = "+" in estados, "-" in estados
    if pos and neg:
        return "conflicto"
    return "+1" if pos else "-1" if neg else ""
