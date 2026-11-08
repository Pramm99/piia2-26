"""¿Habla un texto (frase GeneRIF/UniProt, título o abstract) de una ruta GO y del gen? Comparación determinista.

El vocabulario de una ruta son los nombres y sinónimos EXACT de TODO su subárbol (la anotación de un
gen suele ser un descendiente de la ruta del Excel) y, para «(positive/negative) regulation of X», también
X. Texto y vocabulario se normalizan igual: minúsculas, sin puntuación, NK = natural killer y sin plural.

El gen se busca por símbolo, alias o nombre completo, como palabra entera y sin guiones ni espacios
internos, con las griegas como letra (IL-4Rα = IL-4Ralpha = IL4RA; CD7 ≠ CD70).
"""
import re
from collections import defaultdict

_NO_ALFANUM = re.compile(r"[^a-z0-9]+")
_REGULACION = re.compile(r"^(?:positive |negative )?regulation of ")
EQUIVALENCIAS = {"nk": ("natural", "killer")}
MAX_PALABRAS = 12  # los términos GO más largos que se buscan; más largos no aportan
MIN_LETRAS_SIGLA = 4  # un sinónimo de una sola palabra más corto es una sigla ambigua (HR = hazard ratio)


def normalizar(texto):
    """Tupla de palabras normalizadas."""
    palabras = []
    for p in _NO_ALFANUM.sub(" ", texto.lower()).split():
        if p in EQUIVALENCIAS:
            palabras.extend(EQUIVALENCIAS[p])
            continue
        if len(p) > 3 and p.endswith("s") and not p.endswith("ss"):
            p = p[:-1]
        palabras.append(p)
    return tuple(palabras)


def vocabularios_rutas(desc_map, sinonimos, rutas):
    """{ruta: {frase normalizada: frase original}} con el vocabulario de todo el subárbol de cada ruta."""
    vocab = defaultdict(dict)
    for termino, por_ruta in desc_map.items():
        for ruta in por_ruta.keys() & rutas:
            for nombre in sinonimos.get(termino, ()):
                for frase in {nombre, _REGULACION.sub("", nombre)}:
                    clave = normalizar(frase)
                    if 0 < len(clave) <= MAX_PALABRAS and (len(clave) > 1 or len(clave[0]) >= MIN_LETRAS_SIGLA):
                        vocab[ruta].setdefault(clave, frase)
    return vocab


def ngramas(texto):
    """Todos los n-gramas (hasta MAX_PALABRAS) del texto: se calcula una vez y se cruza con cada ruta."""
    p = normalizar(texto)
    return {p[i:i + n] for n in range(1, MAX_PALABRAS + 1) for i in range(len(p) - n + 1)}


_GRIEGAS = [("alpha", "a"), ("α", "a"), ("beta", "b"), ("β", "b"), ("gamma", "g"), ("γ", "g"),
            ("delta", "d"), ("δ", "d"), ("kappa", "k"), ("κ", "k")]
MIN_ALIAS = 3  # alias más cortos (p. ej. "P1") dan demasiados falsos positivos


def _forma_gen(palabra):
    """'IL-4Rα' -> 'il4ra': minúsculas, griegas como letra y sin guiones."""
    t = palabra.lower()
    for griega, letra in _GRIEGAS:
        t = t.replace(griega, letra)
    return t.replace("-", "")


def _plano(texto):
    return " ".join(_NO_ALFANUM.sub(" ", texto.lower()).split())


def patron_gen(simbolo, alias=(), nombre=""):
    """(patrón de símbolo/alias, patrón del nombre completo) para menciona_gen."""
    formas = {_forma_gen(a) for a in (simbolo, *alias)}
    formas = sorted((f for f in formas if len(f) >= MIN_ALIAS and not f.isdigit()), key=len, reverse=True)
    simbolos = re.compile(r"(?<![a-z0-9])(?:" + "|".join(map(re.escape, formas)) + r")(?![a-z0-9])") if formas else None
    completo = re.compile(r"\b" + re.escape(_plano(nombre)) + r"\b") if nombre else None
    return simbolos, completo


def menciona_gen(texto, patron):
    """True si el texto nombra al gen como palabra entera (CD7 ≠ CD70), por símbolo, alias o nombre."""
    simbolos, completo = patron
    if simbolos and simbolos.search(" ".join(_forma_gen(p) for p in texto.split())):
        return True
    return bool(completo and completo.search(_plano(texto)))


def coincidencia(gramas, vocab_ruta):
    """El término más largo de la ruta que aparece en el texto ('' si ninguno)."""
    comunes = gramas & vocab_ruta.keys()
    return vocab_ruta[max(comunes, key=len)] if comunes else ""
