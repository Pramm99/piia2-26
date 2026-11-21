"""¿Habla un texto (frase GeneRIF/UniProt, título o abstract) de una ruta GO y del gen? Comparación determinista.

El vocabulario de una ruta son los nombres y sinónimos EXACT de TODO su subárbol (la anotación de un
gen suele ser un descendiente de la ruta del Excel) y, para «(positive/negative) regulation of X», también
X. Texto y vocabulario se normalizan igual: minúsculas, sin puntuación, NK = natural killer y sin plural.

El gen se busca por símbolo, alias o nombre completo, como palabra entera y sin guiones ni espacios
internos, con las griegas como letra (IL-4Rα = IL-4Ralpha = IL4RA; IκBζ = IKBZ; CD7 ≠ CD70). Un guion que une el
gen a una palabra corriente no lo esconde («CXCR3-mediated», «anti-CD7»). Un símbolo o alias escrito todo en
minúsculas no cuenta: muchos alias son palabras corrientes (ACP5 = TRAP, «trap»; TNFSF14 = LIGHT). También cuentan
los nombres de la proteína de UniProt y MyGene que identifican al gen («beta-catenin», «lymphotactin»), como frase.
"""
import re
import unicodedata
from collections import defaultdict

_NO_ALFANUM = re.compile(r"[^a-z0-9]+")
_REGULACION = re.compile(r"^(?:positive |negative )?regulation of ")
EQUIVALENCIAS = {"nk": ("natural", "killer")}
MAX_PALABRAS = 12  # los términos GO más largos que se buscan; más largos no aportan
MIN_LETRAS_SIGLA = 4  # un sinónimo de una sola palabra más corto es una sigla ambigua (HR = hazard ratio)
# Tampoco se usan los sinónimos de una sola palabra en mayúsculas: son siglas (ADCC = adenoid cystic carcinoma)


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


def vocabularios_rutas(desc_map, sinonimos, rutas, max_profundidad=None):
    """{ruta: {frase normalizada: frase original}} con el vocabulario del subárbol de cada ruta
    (entero, o solo hasta max_profundidad aristas desde la ruta)."""
    vocab = defaultdict(dict)
    for termino, por_ruta in desc_map.items():
        for ruta in por_ruta.keys() & rutas:
            if max_profundidad is not None and min(por_ruta[ruta].values()) > max_profundidad:
                continue
            for nombre in sinonimos.get(termino, ()):
                for frase in {nombre, _REGULACION.sub("", nombre)}:
                    clave = normalizar(frase)
                    sigla = len(clave) == 1 and (len(clave[0]) < MIN_LETRAS_SIGLA or frase.isupper())
                    # varias frases pueden normalizarse igual ("T-cell" / "T cell"): se guarda siempre la misma
                    if 0 < len(clave) <= MAX_PALABRAS and not sigla \
                            and (clave not in vocab[ruta] or frase < vocab[ruta][clave]):
                        vocab[ruta][clave] = frase
    return vocab


def ngramas(texto):
    """Todos los n-gramas (hasta MAX_PALABRAS) del texto: se calcula una vez y se cruza con cada ruta."""
    p = normalizar(texto)
    return {p[i:i + n] for n in range(1, MAX_PALABRAS + 1) for i in range(len(p) - n + 1)}


# Con la letra que usa HGNC en los símbolos (PRKCQ = PKCθ, NFKBIZ = IκBζ). «eta» no se incluye: es la sigla de un
# alias real (ETA = EDNRA) y aparece dentro de muchas palabras.
_GRIEGAS = [("alpha", "a"), ("α", "a"), ("beta", "b"), ("β", "b"), ("gamma", "g"), ("γ", "g"),
            ("delta", "d"), ("δ", "d"), ("epsilon", "e"), ("ε", "e"), ("zeta", "z"), ("ζ", "z"),
            ("theta", "q"), ("θ", "q"), ("kappa", "k"), ("κ", "k"), ("lambda", "l"), ("λ", "l")]
MIN_ALIAS = 3  # alias más cortos (p. ej. "P1") dan demasiados falsos positivos


_GRIEGA = re.compile("|".join(g for g, _ in _GRIEGAS), re.IGNORECASE)
_LETRA = dict(_GRIEGAS)


def _forma_gen(palabra):
    """'IL-4Rα' -> 'IL4Ra': griegas como letra y sin guiones, conservando mayúsculas."""
    # Sin distinguir mayúsculas, la búsqueda también casa variantes tipográficas (ϵ, ϑ, ϰ, ϐ) y mayúsculas griegas:
    # NFKC + casefold las lleva a la letra de la tabla.
    return _GRIEGA.sub(lambda m: _LETRA[unicodedata.normalize("NFKC", m.group()).casefold()], palabra).replace("-", "")


def _plano(texto):
    return " ".join(_NO_ALFANUM.sub(" ", texto.lower()).split())


# --- Nombres de la proteína (fuentes/nombres.py): se buscan como frase, sin distinguir mayúsculas y con las griegas
# escritas como palabra («MIP-1α» = «MIP-1 alpha» = «MIP-1alpha»). Solo cuentan los que identifican al gen.
_GRIEGA_PALABRA = {"α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon", "ζ": "zeta", "θ": "theta",
                   "κ": "kappa", "λ": "lambda"}
_DIGITO_GRIEGA = re.compile(r"(?<=\d)(?=(?:" + "|".join(_GRIEGA_PALABRA.values()) + r")\b)")
# Palabras que no distinguen una proteína de otra: un nombre hecho solo de ellas no identifica al gen
_GENERICAS = {"protein", "receptor", "factor", "chain", "subunit", "family", "member", "domain", "containing", "like",
              "putative", "uncharacterized", "coupled", "type", "isoform", "precursor", "antigen", "gene", "product",
              "kinase", "ligand", "homolog", "fragment", "molecule", "cell", "surface", "complex", "binding",
              "associated", "related", "regulatory", "small", "large", "and", "of", *_GRIEGA_PALABRA.values()}
MIN_LETRAS_NOMBRE = 5  # «furin» sí; más cortos son siglas ambiguas


def _plano_proteina(texto):
    texto = "".join(f" {_GRIEGA_PALABRA[c]} " if c in _GRIEGA_PALABRA else c
                    for c in unicodedata.normalize("NFKC", texto).casefold())
    return _DIGITO_GRIEGA.sub(" ", _plano(texto))


def _identifica(nombre):
    """El nombre distingue a la proteína: tiene alguna palabra propia (no genérica, con 3 letras o con número) y no es
    una sigla de una palabra (LIGHT de TNFSF14 sería «light»: las siglas ya se buscan como alias)."""
    palabras = _plano_proteina(nombre).split()
    if len("".join(palabras)) < MIN_LETRAS_NOMBRE:
        return False
    if len(palabras) == 1 and sum(c.isupper() for c in nombre) > 1:
        return False
    return any(p not in _GENERICAS and (len(p) >= 3 or any(c.isdigit() for c in p)) for p in palabras)


def nombres_utiles(nombres_por_gen):
    """{gen: frases normalizadas} con los nombres de la proteína que identifican al gen. Se quitan los genéricos
    («G protein-coupled receptor»), las siglas de una palabra y los que comparten varios genes del conjunto."""
    frases = {g: {_plano_proteina(n) for n in nombres if _identifica(n)} for g, nombres in nombres_por_gen.items()}
    veces = defaultdict(int)
    for f in frases.values():
        for p in f:
            veces[p] += 1
    return {g: tuple(sorted((p for p in f if veces[p] == 1), key=len, reverse=True)) for g, f in frases.items()}


def patron_gen(simbolo, alias=(), nombre="", proteinas=()):
    """(patrón de símbolo/alias, patrón del nombre completo, patrón de los nombres de la proteína) para menciona_gen.
    proteinas: frases ya filtradas con nombres_utiles."""
    formas = {_forma_gen(a) for a in (simbolo, *alias)}
    formas = sorted((f for f in formas if len(f) >= MIN_ALIAS and not f.isdigit()), key=len, reverse=True)
    simbolos = re.compile(r"(?<![a-z0-9])(?:" + "|".join(map(re.escape, formas)) + r")(?![a-z0-9])",
                          re.IGNORECASE) if formas else None
    completo = re.compile(r"\b" + re.escape(_plano(nombre)) + r"\b") if nombre else None
    proteina = re.compile(r"\b(?:" + "|".join(map(re.escape, proteinas)) + r")\b") if proteinas else None
    return simbolos, completo, proteina


_GUION_MINUSCULAS = re.compile(r"(?<=\b[a-z])-|-(?=[a-z])|(?<=[a-z]{2})-")  # «IL-4R-dependent», «anti-CD7»


def menciona_gen(texto, patron):
    """True si el texto nombra al gen como palabra entera (CD7 ≠ CD70), por símbolo, alias o nombre.
    Se mira el texto con los guiones quitados (IL-4R = IL4R), con los guiones como espacio («HVEM-Ig», «2,5-OAS1») y
    con espacio solo en los que tocan una palabra en minúsculas («IL-4R-dependent», «anti-CD7»): así el guion no
    pega el gen a la palabra de al lado. También cuenta un nombre de la proteína («beta-catenin»)."""
    simbolos, completo, proteina = (*patron, None)[:3]
    if simbolos:
        for variante in (texto, texto.replace("-", " "), _GUION_MINUSCULAS.sub(" ", texto)):
            if any(m.group() != m.group().lower()
                   for m in simbolos.finditer(" ".join(_forma_gen(p) for p in variante.split()))):
                return True
    if completo and completo.search(_plano(texto)):
        return True
    return bool(proteina and proteina.search(_plano_proteina(texto)))


_FIN_FRASE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(])")


def frases(texto):
    """Parte un título + abstract en frases (sin cortar en 'e.g.' o decimales: exige mayúscula detrás)."""
    return [f for f in _FIN_FRASE.split(texto) if f.strip()]


def coincidencia_en_frase(texto, patron, vocab_ruta):
    """(frase, término) de la primera frase que nombra a la vez al gen y a la ruta; ('', '') si ninguna."""
    for f in frases(texto):
        if menciona_gen(f, patron):
            termino = coincidencia(ngramas(f), vocab_ruta)
            if termino:
                return f, termino
    return "", ""


def coincidencia(gramas, vocab_ruta):
    """El término más largo de la ruta que aparece en el texto ('' si ninguno). Los empates se resuelven
    por orden alfabético: el orden de un set de str cambia entre ejecuciones y la salida debe ser fija."""
    comunes = gramas & vocab_ruta.keys()
    return vocab_ruta[max(comunes, key=lambda k: (len(k), k))] if comunes else ""
