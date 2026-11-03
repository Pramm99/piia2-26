"""
FASE 1 (v4) - Objetivo único: obtener el MÁXIMO de abstracts por par (Gen, Ruta GO) en humanos.

Cambios principales respecto a la v1:
  1. Propagación por el grafo GO (is_a + part_of): una anotación a un término HIJO
     cuenta como evidencia para la ruta PADRE (como hace clusterProfiler).
  2. Se excluyen las anotaciones con calificador NOT (afirman lo contrario).
  3. Coincidencia de gen por símbolo oficial y, si no, por sinónimo (sin ambigüedad).
  4. Se aceptan TODOS los códigos de evidencia que traigan PMID (se guarda la columna
     Evidencia y un flag Experimental para poder filtrar después).
  5. Descarga robusta: reintentos también en POST, lotes que fallan se parten,
     caché en disco por PMID, descargas atómicas (.tmp -> rename).
  6. Salida: hoja con abstract, hoja de pares sin abstract y hoja de genes no encontrados.

Cambios de la v4 respecto a la v2:
  7. La propagación incluye también regulates / positively_regulates / negatively_regulates
     (como hace GO.db, que usa clusterProfiler). Una anotación a "positive regulation of X"
     ahora cuenta para la ruta X.
  8. Se registra el TIPO de relación del camino término anotado -> ruta (Tipo_relacion) y,
     cuando hay regulación con signo, una polaridad determinista (Polaridad_GO = +1 / -1 /
     conflicto). Los signos se componen a lo largo del camino (neg. de neg. = pos.);
     is_a y part_of no cambian el signo.
  9. Las anotaciones GO que NO traen PMID (IBA, IEA, ISS con GO_REF...) ya no se descartan en
     silencio: los pares que solo tienen ese tipo de anotación van a la hoja Anotado_sin_PMID,
     con su polaridad GO (si la hay), evidencia, referencia y campo With/From.
 10. Segunda fuente opcional: NCBI gene2go (la base de org.Hs.eg.db, que usa clusterProfiler).
     Aporta anotaciones/PMIDs que el GAF de GOA no tiene. Se activa con USAR_GENE2GO.
     La columna Fuente indica de dónde viene cada fila (GOA, NCBI o GOA|NCBI).
 11. Rastreo de ortólogos (USAR_ORTOLOGOS): para los pares que siguen sin PMID, sigue el campo
     With/From hasta el gen de ratón/rata y recoge los PMIDs de su anotación. Marcado en Fuente.
  (limpiar_texto() NO se ha tocado: sigue pendiente el bug de títulos pegados.)
"""
import gzip
import html
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import defaultdict, deque

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- CONFIGURACIÓN ---
EXCEL_ACTIVADAS = "rutas_activadas.xlsx"
EXCEL_SUPRIMIDAS = "rutas_suprimidas.xlsx"
GAF_FILE = "data/goa_human.gaf.gz"
GAF_URL = "https://current.geneontology.org/annotations/goa_human.gaf.gz"
GENE2GO_FILE = "data/gene2go.gz"
GENE2GO_URL = "https://ftp.ncbi.nlm.nih.gov/gene/DATA/gene2go.gz"
GENEINFO_FILE = "data/Homo_sapiens.gene_info.gz"
GENEINFO_URL = "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz"
USAR_GENE2GO = False  # en las pruebas con datos reales NO aportó nada nuevo sobre GOA (36/45 genes en ambas)

# Rastreo de ortólogos: una anotación humana inferida (IBA/ISS/IEA) sin PMID suele apuntar, en el
# campo With/From, al gen de ratón/rata del que se infirió. Se busca la anotación de ESE gen a
# ese término (o a un hijo is_a/part_of) y se recogen sus PMIDs. Son artículos de ratón/rata,
# no de humano: quedan marcados en la columna Fuente (ORTOLOGO_raton / ORTOLOGO_rata).
USAR_ORTOLOGOS = False  # desactivado: no se consultan genes de ratón/rata
ORTOLOGO_GAFS = [  # (url, destino). Si una URL falla se avisa y se sigue con las demás.
    ("https://current.geneontology.org/annotations/mgi.gaf.gz", "data/mgi.gaf.gz"),
    ("https://current.geneontology.org/annotations/rgd.gaf.gz", "data/rgd.gaf.gz"),
    ("https://ftp.ebi.ac.uk/pub/databases/GO/goa/MOUSE/goa_mouse.gaf.gz", "data/goa_mouse.gaf.gz"),
    ("https://ftp.ebi.ac.uk/pub/databases/GO/goa/RAT/goa_rat.gaf.gz", "data/goa_rat.gaf.gz"),
]
ESPECIES = {"taxon:10090": "raton", "taxon:10116": "rata"}
OBO_FILE = "data/go-basic.obo"
OBO_URL = "https://purl.obolibrary.org/obo/go/go-basic.obo"
CACHE_FILE = "data/cache_abstracts.json"
SALIDA = "fase1_dataset_abstracts.xlsx"

EPMC_API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
NCBI_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
NCBI_EMAIL = "tu_email@ejemplo.com"          # <- pon el tuyo (buena práctica NCBI)
NCBI_API_KEY = os.environ.get("NCBI_API_KEY")  # opcional: sube el límite a 10 req/s

# Relaciones del grafo GO usadas para propagar y su "signo":
#   N = neutra (no cambia la polaridad), + = positiva, - = negativa, R = regula sin signo
ESTADO_RELACION = {
    "is_a": "N", "part_of": "N",
    "regulates": "R", "positively_regulates": "+", "negatively_regulates": "-",
}
# False = comportamiento de la v2 (solo is_a y part_of); útil para comparar resultados
PROPAGAR_REGULACION = True
RELACIONES_PROPAGACION = {r for r, e in ESTADO_RELACION.items()
                          if PROPAGAR_REGULACION or e == "N"}
NOMBRE_ESTADO = {"N": "is_a/part_of", "+": "positively_regulates",
                 "-": "negatively_regulates", "R": "regulates"}

# True = solo evidencia experimental; False = cualquier anotación con PMID (más abstracts)
SOLO_EXPERIMENTAL = False
EVIDENCIAS_EXPERIMENTALES = {"EXP", "IDA", "IPI", "IMP", "IGI", "IEP",
                             "HTP", "HDA", "HMP", "HGI", "HEP"}

ILEGALES_XLSX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


# ----------------------------------------------------------------------------
# Utilidades de red
# ----------------------------------------------------------------------------
def configurar_sesion():
    s = requests.Session()
    retries = Retry(
        total=5, backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST"]),  # la v1 no reintentaba POST
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s


def descargar_archivo(url, destino):
    """Descarga atómica: si se corta, no queda un archivo corrupto dando falsos positivos."""
    if os.path.exists(destino):
        return
    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
    print(f"📥 Descargando {url} ...")
    tmp = destino + ".tmp"
    with requests.get(url, stream=True, timeout=(15, 120)) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
    os.replace(tmp, destino)


# ----------------------------------------------------------------------------
# Grafo GO
# ----------------------------------------------------------------------------
def cargar_go(ruta_obo):
    """Devuelve (hijos, alias): hijos[padre] = {(hijo, relacion)} y alias[alt_id|replaced_by] = id vigente."""
    hijos = defaultdict(set)
    alias = {}
    en_termino = False
    actual = None
    obsoleto = False
    reemplazo = None
    alts = []

    def cerrar():
        if actual and obsoleto and reemplazo:
            alias[actual] = reemplazo

    with open(ruta_obo, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea.startswith("["):
                cerrar()
                en_termino = linea == "[Term]"
                actual, obsoleto, reemplazo, alts = None, False, None, []
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


# ----------------------------------------------------------------------------
# Excels
# ----------------------------------------------------------------------------
def leer_y_explotar_excel(ruta, etiqueta, alias):
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No existe {ruta}")
    df = pd.read_excel(ruta)
    filas = []
    for _, fila in df.iterrows():
        go_id = str(fila["ID"]).strip()
        go_id = alias.get(go_id, go_id)  # alt_id / término obsoleto -> vigente
        for gen in str(fila["geneID"]).split("/"):
            gen = gen.strip().upper()
            if gen:
                filas.append({"Gen": gen, "GO_ID": go_id,
                              "Ruta_Nombre": fila["Description"],
                              "Estado_Original": etiqueta})
    return pd.DataFrame(filas)


# ----------------------------------------------------------------------------
# Cruce con GAF (con propagación, sinónimos y todas las evidencias con PMID)
# ----------------------------------------------------------------------------
def leer_gene2go(desc_map):
    """Lee NCBI gene2go (+ gene_info para pasar GeneID -> símbolo/sinónimos), solo humano.
    Devuelve (cand_con_pmid, cand_sin_pmid, simbolos_oficiales, sinonimos) en el mismo formato que el GAF."""
    print("🔍 Leyendo NCBI gene2go...")
    simbolo_de, sinonimos_de = {}, {}
    with gzip.open(GENEINFO_FILE, "rt", encoding="utf-8") as f:
        for linea in f:
            if linea.startswith("#"):
                continue
            c = linea.rstrip("\n").split("\t")
            if len(c) < 5:
                continue
            simbolo_de[c[1]] = c[2].upper()
            sinonimos_de[c[1]] = [x.upper() for x in c[4].split("|") if x and x != "-"]
    cand, cand_sin = [], []
    with gzip.open(GENE2GO_FILE, "rt", encoding="utf-8") as f:
        for linea in f:
            if not linea.startswith("9606\t"):
                continue
            c = linea.rstrip("\n").split("\t")
            if len(c) < 8 or "NOT" in c[4] or c[2] not in desc_map:
                continue
            gid, go_id, evid = c[1], c[2], c[3]
            if gid not in simbolo_de:
                continue
            if SOLO_EXPERIMENTAL and evid not in EVIDENCIAS_EXPERIMENTALES:
                continue
            pmids = [x for x in c[6].split("|") if x and x != "-"]
            if pmids:
                cand.append((simbolo_de[gid], sinonimos_de[gid], go_id, pmids, evid, "NCBI"))
            else:
                cand_sin.append((simbolo_de[gid], sinonimos_de[gid], go_id, evid, "NCBI_gene2go", "", "NCBI"))
    oficiales = set(simbolo_de.values())
    sinon = {x for v in sinonimos_de.values() for x in v}
    return cand, cand_sin, oficiales, sinon


def cruzar_con_gaf(pares, desc_map):
    """
    pares:    set de (gen, go_id_ruta)
    desc_map: dict termino_GO -> {ruta del Excel: {estados de relación}} (ver construir_desc_map)
    """
    genes_query = {g for g, _ in pares}
    print("🔍 Leyendo GAF (una sola pasada)...")
    simbolos_oficiales = set()
    sinonimos_todos = set()
    candidatas = []      # (simbolo, sinonimos, go_id, pmids, evidencia, fuente)
    candidatas_sin = []  # (simbolo, sinonimos, go_id, evidencia, referencia, with_from, fuente)

    with gzip.open(GAF_FILE, "rt", encoding="utf-8") as f:
        for linea in f:
            if linea.startswith("!"):
                continue
            c = linea.rstrip("\n").split("\t")
            if len(c) < 15:
                continue
            simbolo = c[2].upper()
            simbolos_oficiales.add(simbolo)
            if c[10]:
                sinonimos_todos.update(c[10].upper().split("|"))
            if "NOT" in c[3] or not c[12].startswith("taxon:9606"):
                continue
            go_id = c[4]
            if go_id not in desc_map:
                continue
            evid = c[6]
            if SOLO_EXPERIMENTAL and evid not in EVIDENCIAS_EXPERIMENTALES:
                continue
            pmids = [r.split(":", 1)[1] for r in c[5].split("|") if r.startswith("PMID:")]
            sins = c[10].upper().split("|") if c[10] else []
            if not pmids:
                candidatas_sin.append((simbolo, sins, go_id, evid, c[5], c[7], "GOA"))
                continue
            candidatas.append((simbolo, sins, go_id, pmids, evid, "GOA"))

    if USAR_GENE2GO:
        c2, c2_sin, of2, sin2 = leer_gene2go(desc_map)
        g_goa = {x[0] for x in candidatas + candidatas_sin if x[0] in genes_query}
        g_ncbi = {x[0] for x in c2 + c2_sin if x[0] in genes_query}
        print(f"   Genes del Excel con alguna anotación bajo las rutas -> GOA: {len(g_goa)}/{len(genes_query)} | "
              f"NCBI: {len(g_ncbi)}/{len(genes_query)} | solo en NCBI: {len(g_ncbi - g_goa)}")
        print(f"   Anotaciones humanas bajo las rutas -> GOA: {len(candidatas) + len(candidatas_sin)} | "
              f"NCBI: {len(c2) + len(c2_sin)}")
        candidatas += c2
        candidatas_sin += c2_sin
        simbolos_oficiales |= of2
        sinonimos_todos |= sin2

    # Genes del Excel que no aparecen ni como símbolo ni como sinónimo
    no_encontrados = sorted(g for g in genes_query
                            if g not in simbolos_oficiales and g not in sinonimos_todos)

    def resolver_genes(simbolo, sinonimos):
        if simbolo in genes_query:
            return [(simbolo, "simbolo")]
        # sinónimo solo si NO es símbolo oficial de otro gen (evita ambigüedad)
        return [(s, "sinonimo") for s in sinonimos
                if s in genes_query and s not in simbolos_oficiales]

    # Anotaciones SIN PMID (conservadas para no perder la polaridad de GO)
    reg_sin = []
    for simbolo, sinonimos, go_anotado, evid, ref, with_from, fuente in candidatas_sin:
        for gen, via in resolver_genes(simbolo, sinonimos):
            for ruta, estados in desc_map[go_anotado].items():
                if (gen, ruta) in pares:
                    for estado in estados_efectivos(estados):
                        reg_sin.append({
                            "Gen": gen, "GO_ID": ruta, "GO_ID_anotado": go_anotado,
                            "Directo": go_anotado == ruta, "Evidencia": evid,
                            "Referencia": ref, "With_From": with_from,
                            "Via_gen": via, "Estado_rel": estado, "Fuente": fuente,
                        })
    df_sin = pd.DataFrame(reg_sin)
    if not df_sin.empty:
        j = lambda x: "|".join(sorted(set(x)))
        df_sin = (df_sin.groupby(["Gen", "GO_ID", "GO_ID_anotado"], as_index=False)
                  .agg(Directo=("Directo", "any"), Evidencia=("Evidencia", j),
                       Referencia=("Referencia", j), With_From=("With_From", j),
                       Via_gen=("Via_gen", j), Fuente=("Fuente", j),
                       Tipo_relacion=("Estado_rel", lambda x: "|".join(sorted({NOMBRE_ESTADO[e] for e in x}))),
                       Polaridad_GO=("Estado_rel", lambda x: polaridad_desde_estados(set(x)))))

    registros = []
    for simbolo, sinonimos, go_anotado, pmids, evid, fuente in candidatas:
        for gen, via in resolver_genes(simbolo, sinonimos):
            for ruta, estados in desc_map[go_anotado].items():
                if (gen, ruta) in pares:
                    for estado in estados_efectivos(estados):
                        for pmid in pmids:
                            registros.append({
                                "Gen": gen, "GO_ID": ruta, "GO_ID_anotado": go_anotado,
                                "Directo": go_anotado == ruta, "PMID": pmid,
                                "Evidencia": evid, "Via_gen": via, "Estado_rel": estado,
                                "Fuente": fuente,
                            })

    if not registros:
        return pd.DataFrame(), df_sin, no_encontrados

    df = pd.DataFrame(registros)
    df = (df.groupby(["Gen", "GO_ID", "PMID"], as_index=False)
            .agg(GO_ID_anotado=("GO_ID_anotado", lambda x: "|".join(sorted(set(x)))),
                 Directo=("Directo", "any"),
                 Evidencia=("Evidencia", lambda x: "|".join(sorted(set(x)))),
                 Via_gen=("Via_gen", lambda x: "|".join(sorted(set(x)))),
                 Fuente=("Fuente", lambda x: "|".join(sorted(set(x)))),
                 Tipo_relacion=("Estado_rel", lambda x: "|".join(sorted({NOMBRE_ESTADO[e] for e in x}))),
                 Polaridad_GO=("Estado_rel", lambda x: polaridad_desde_estados(set(x)))))
    df["Experimental"] = df["Evidencia"].apply(
        lambda e: any(x in EVIDENCIAS_EXPERIMENTALES for x in e.split("|")))
    return df, df_sin, no_encontrados


# ----------------------------------------------------------------------------
# Rastreo de ortólogos (ratón / rata) a través de With/From
# ----------------------------------------------------------------------------
def _claves_origen(with_from):
    """'PANTHER:PTN1|MGI:MGI:96447|UniProtKB:Q9Z0D9-2' -> {'MGI:MGI:96447', 'UniProtKB:Q9Z0D9-2', 'UniProtKB:Q9Z0D9', ...}"""
    claves = set()
    for tok in str(with_from).split("|"):
        tok = tok.strip()
        if ":" in tok:
            claves.add(tok)
            claves.add(re.sub(r"-\d+$", "", tok))  # isoforma -> proteína base
    return claves


def _combinar_polaridades(vals):
    v = {x for x in vals if x in ("+1", "-1")}
    return "conflicto" if len(v) == 2 else (v.pop() if v else "")


def rastrear_ortologos(df_sin, df_ev, hijos):
    """Devuelve un DataFrame con el mismo formato que df_ev para los pares que siguen sin PMID."""
    cols = ["Gen", "GO_ID", "PMID", "GO_ID_anotado", "Directo", "Evidencia", "Via_gen",
            "Fuente", "Tipo_relacion", "Polaridad_GO", "Experimental"]
    vacio = pd.DataFrame(columns=cols)
    if df_sin.empty:
        return vacio
    ya = set(zip(df_ev["Gen"], df_ev["GO_ID"])) if not df_ev.empty else set()
    obj = df_sin[[(g, r) not in ya for g, r in zip(df_sin["Gen"], df_sin["GO_ID"])]]
    if obj.empty:
        return vacio

    # 1) ficheros de ortólogos (si uno falla se avisa y se continúa)
    ficheros = []
    for url, destino in ORTOLOGO_GAFS:
        try:
            descargar_archivo(url, destino)
            ficheros.append(destino)
        except Exception as e:
            print(f"⚠️ No se pudo descargar {url}: {e}")
    if not ficheros:
        return vacio

    # 2) qué buscar: clave de origen -> [(gen, ruta, go_anotado, polaridad, tipo_rel)]
    peticiones = defaultdict(list)
    for _, r in obj.iterrows():
        for clave in _claves_origen(r["With_From"]):
            peticiones[clave].append(r)
    if not peticiones:
        return vacio

    # términos aceptables por cada go_anotado: él mismo y sus hijos por is_a/part_of (estado 'N')
    cache_desc = {}

    def aceptables(go):
        if go not in cache_desc:
            cache_desc[go] = {t for t, est in descendientes(go, hijos).items() if "N" in est}
        return cache_desc[go]

    # 3) una pasada por cada GAF de ortólogos
    print(f"🐭 Rastreando ortólogos: {len(obj)} anotaciones, {len(peticiones)} claves de origen...")
    registros = []
    for fich in ficheros:
        with gzip.open(fich, "rt", encoding="utf-8") as fh:
            for linea in fh:
                if linea.startswith("!"):
                    continue
                c = linea.rstrip("\n").split("\t")
                if len(c) < 13 or "NOT" in c[3]:
                    continue
                reqs = peticiones.get(f"{c[0]}:{c[1]}")
                if not reqs:
                    continue
                pmids = [x.split(":", 1)[1] for x in c[5].split("|") if x.startswith("PMID:")]
                if not pmids:
                    continue
                esp = ESPECIES.get(c[12].split("|")[0], c[12].split("|")[0])
                for r in reqs:
                    if c[4] in aceptables(r["GO_ID_anotado"]):
                        for pmid in pmids:
                            registros.append({
                                "Gen": r["Gen"], "GO_ID": r["GO_ID"], "PMID": pmid,
                                "GO_ID_anotado": r["GO_ID_anotado"],
                                "Directo": r["GO_ID_anotado"] == r["GO_ID"],
                                "Evidencia": c[6], "Via_gen": "ortologo",
                                "Fuente": f"ORTOLOGO_{esp}",
                                "Tipo_relacion": r["Tipo_relacion"], "Polaridad_GO": r["Polaridad_GO"],
                            })
    if not registros:
        print("   (ningún PMID encontrado por esta vía)")
        return vacio
    j = lambda x: "|".join(sorted(set(x)))
    df = (pd.DataFrame(registros)
          .groupby(["Gen", "GO_ID", "PMID"], as_index=False)
          .agg(GO_ID_anotado=("GO_ID_anotado", j), Directo=("Directo", "any"), Evidencia=("Evidencia", j),
               Via_gen=("Via_gen", j), Fuente=("Fuente", j), Tipo_relacion=("Tipo_relacion", j),
               Polaridad_GO=("Polaridad_GO", _combinar_polaridades)))
    df["Experimental"] = df["Evidencia"].apply(
        lambda e: any(x in EVIDENCIAS_EXPERIMENTALES for x in e.split("|")))
    print(f"   -> {df['PMID'].nunique()} PMIDs de ortólogos para {len(set(zip(df['Gen'], df['GO_ID'])))} pares")
    return df


# ----------------------------------------------------------------------------
# Abstracts (Europe PMC -> NCBI, con caché y lotes que se parten)
# ----------------------------------------------------------------------------
def limpiar_texto(t):
    return html.unescape(re.sub(r"<[^>]+>", "", t or "")).strip()


def cargar_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(tmp, CACHE_FILE)


def _epmc_lote(sesion, lote):
    query = "(" + " OR ".join(f"EXT_ID:{p}" for p in lote) + ") AND SRC:MED"
    params = {"query": query, "resultType": "core", "format": "json", "pageSize": 100}
    r = sesion.get(EPMC_API, params=params, timeout=30)
    r.raise_for_status()
    out = {}
    for art in r.json().get("resultList", {}).get("result", []):
        pmid = str(art.get("pmid", ""))
        ab = limpiar_texto(art.get("abstractText"))
        if pmid in lote and ab:
            out[pmid] = {"Titulo": limpiar_texto(art.get("title")), "Abstract": ab}
    return out


def _ncbi_lote(sesion, lote):
    """Devuelve {pmid: {Titulo, Abstract}} para todos los artículos que NCBI conoce
    (Abstract puede ser '' = confirmado sin abstract)."""
    data = {"db": "pubmed", "id": ",".join(lote), "retmode": "xml", "tool": "fase1_go_abstracts"}
    if NCBI_EMAIL:
        data["email"] = NCBI_EMAIL
    if NCBI_API_KEY:
        data["api_key"] = NCBI_API_KEY
    r = sesion.post(NCBI_URL, data=data, timeout=60)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = {}
    for nodo in list(root.findall("PubmedArticle")) + list(root.findall("PubmedBookArticle")):
        pmid = nodo.findtext("MedlineCitation/PMID") or nodo.findtext("BookDocument/PMID")
        if not pmid:
            continue
        t = nodo.find(".//ArticleTitle")
        if t is None:
            t = nodo.find(".//BookTitle")
        titulo = "".join(t.itertext()).strip() if t is not None else ""
        partes = nodo.findall(".//Abstract/AbstractText") or nodo.findall(".//OtherAbstract/AbstractText")
        textos = []
        for p in partes:
            txt = "".join(p.itertext()).strip()
            lab = p.get("Label")
            if txt:
                textos.append(f"{lab}: {txt}" if lab else txt)
        out[pmid] = {"Titulo": titulo, "Abstract": " ".join(textos)}
    return out


def descargar_abstracts(pmids):
    sesion = configurar_sesion()
    cache = cargar_cache()
    pendientes = [p for p in pmids if p not in cache]
    print(f"🌐 {len(pmids)} PMIDs únicos | {len(pmids) - len(pendientes)} en caché | {len(pendientes)} por descargar")

    # 1) Europe PMC
    for i in range(0, len(pendientes), 40):
        lote = pendientes[i:i + 40]
        try:
            cache.update(_epmc_lote(sesion, lote))
        except Exception as e:
            print(f"⚠️ Europe PMC (lote {i // 40}): {e}")
        time.sleep(0.2)
    guardar_cache(cache)

    # 2) NCBI para lo que falte; si un lote falla, se parte en PMIDs individuales
    pendientes = [p for p in pendientes if p not in cache]
    print(f"🔄 Pasando {len(pendientes)} PMIDs a NCBI...")
    pausa = 0.12 if NCBI_API_KEY else 0.35
    for i in range(0, len(pendientes), 100):
        lote = pendientes[i:i + 100]
        try:
            res = _ncbi_lote(sesion, lote)
        except Exception as e:
            print(f"⚠️ NCBI lote fallido ({e}); reintentando uno a uno")
            res = {}
            for p in lote:
                try:
                    res.update(_ncbi_lote(sesion, [p]))
                except Exception as e2:
                    print(f"   ❌ PMID {p}: {e2}")  # no se cachea: se reintentará en la próxima ejecución
                time.sleep(pausa)
        cache.update(res)  # incluye los confirmados sin abstract ("")
        time.sleep(pausa)
    guardar_cache(cache)

    filas = [{"PMID": p, "Titulo": cache[p]["Titulo"], "Abstract": cache[p]["Abstract"]}
             for p in pmids if p in cache and cache[p]["Abstract"].strip()]
    return pd.DataFrame(filas, columns=["PMID", "Titulo", "Abstract"])


# ----------------------------------------------------------------------------
# Salida
# ----------------------------------------------------------------------------
def limpiar_para_excel(df):
    df = df.copy()
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].apply(
            lambda v: ILEGALES_XLSX.sub("", v)[:32000] if isinstance(v, str) else v)
    return df


def ejecutar_fase_1():
    print("--- INICIANDO FASE 1 (v4) ---")
    descargar_archivo(OBO_URL, OBO_FILE)
    descargar_archivo(GAF_URL, GAF_FILE)
    if USAR_GENE2GO:
        descargar_archivo(GENEINFO_URL, GENEINFO_FILE)
        descargar_archivo(GENE2GO_URL, GENE2GO_FILE)
    hijos, alias = cargar_go(OBO_FILE)

    df_up = leer_y_explotar_excel(EXCEL_ACTIVADAS, "Activada", alias)
    df_down = leer_y_explotar_excel(EXCEL_SUPRIMIDAS, "Suprimida", alias)
    df_excel = pd.concat([df_up, df_down], ignore_index=True)
    pares = set(zip(df_excel["Gen"], df_excel["GO_ID"]))
    print(f"✅ Pares (Gen, Ruta) únicos de entrada: {len(pares)}")

    if df_excel["Gen"].str.fullmatch(r"\d+").mean() > 0.5:
        print("⚠️ La columna geneID parece ENTREZID, no SYMBOL: el cruce fallará. Convierte a símbolos.")

    desc_map = construir_desc_map(pares, hijos)

    df_ev, df_sin, no_encontrados = cruzar_con_gaf(pares, desc_map)
    if USAR_ORTOLOGOS:
        df_orto = rastrear_ortologos(df_sin, df_ev, hijos)
        if not df_orto.empty:
            df_ev = pd.concat([df_ev, df_orto], ignore_index=True)
    if no_encontrados:
        print(f"⚠️ {len(no_encontrados)} genes del Excel no existen como símbolo en el GAF "
              f"(ej: {no_encontrados[:15]})")
    if df_ev.empty:
        print("❌ Cero evidencias encontradas.")
        return

    pmids = df_ev["PMID"].unique().tolist()
    df_abs = descargar_abstracts(pmids)

    base = pd.merge(df_excel, df_ev, on=["Gen", "GO_ID"], how="inner")
    completo = pd.merge(base, df_abs, on="PMID", how="left")
    con = completo[completo["Abstract"].notna()]
    sin = completo[completo["Abstract"].isna()]

    pares_con_abs = len(set(zip(con["Gen"], con["GO_ID"])))
    pares_con_pmid = len(set(zip(base["Gen"], base["GO_ID"])))
    print("\n=== EMBUDO ===")
    print(f"Pares de entrada .............. {len(pares)}")
    print(f"Pares con >=1 PMID en GAF ..... {pares_con_pmid}")
    pares_via_reg = set(zip(base.loc[base["Tipo_relacion"].str.contains("regulates"), "Gen"],
                            base.loc[base["Tipo_relacion"].str.contains("regulates"), "GO_ID"]))
    pares_pol = set(zip(base.loc[base["Polaridad_GO"].isin(["+1", "-1"]), "Gen"],
                        base.loc[base["Polaridad_GO"].isin(["+1", "-1"]), "GO_ID"]))
    print(f"  de ellos, alcanzados por regulación ... {len(pares_via_reg)}")
    print(f"  de ellos, con polaridad GO (+1/-1) .... {len(pares_pol)}")
    print(f"Pares con >=1 abstract ........ {pares_con_abs}")
    def pares_solo(mask):
        a = set(zip(con.loc[mask, "Gen"], con.loc[mask, "GO_ID"]))
        b = set(zip(con.loc[~mask, "Gen"], con.loc[~mask, "GO_ID"]))
        return len(a - b)

    if USAR_GENE2GO:
        print(f"  pares con abstract SOLO gracias a NCBI gene2go ... {pares_solo(con['Fuente'] == 'NCBI')}")
    if USAR_ORTOLOGOS:
        print(f"  pares con abstract SOLO gracias a ortólogos ...... {pares_solo(con['Fuente'].str.startswith('ORTOLOGO'))}")
    print(f"PMIDs únicos .................. {len(pmids)}  (con abstract: {len(df_abs)})")
    print(f"Filas finales con abstract .... {len(con)}")

    # Pares con anotación pero SIN ningún PMID: hoja aparte (no hay abstract que recuperar en GO)
    pares_pmid = set(zip(df_ev["Gen"], df_ev["GO_ID"]))
    if df_sin.empty:
        sin_pmid = pd.DataFrame()
    else:
        sin_pmid = df_sin[[(g, r) not in pares_pmid for g, r in zip(df_sin["Gen"], df_sin["GO_ID"])]]
        info = df_excel[["Gen", "GO_ID", "Ruta_Nombre", "Estado_Original"]].drop_duplicates()
        sin_pmid = pd.merge(info, sin_pmid, on=["Gen", "GO_ID"], how="inner")
        nombres = cargar_nombres(OBO_FILE)
        sin_pmid.insert(sin_pmid.columns.get_loc("GO_ID_anotado") + 1, "Nombre_GO_anotado",
                        sin_pmid["GO_ID_anotado"].map(nombres))
    pares_sin_pmid = set(zip(sin_pmid["Gen"], sin_pmid["GO_ID"])) if not sin_pmid.empty else set()
    pares_sin_pmid_pol = (set(zip(sin_pmid.loc[sin_pmid["Polaridad_GO"].isin(["+1", "-1"]), "Gen"],
                                  sin_pmid.loc[sin_pmid["Polaridad_GO"].isin(["+1", "-1"]), "GO_ID"]))
                          if not sin_pmid.empty else set())
    print(f"Pares anotados SIN PMID ....... {len(pares_sin_pmid)}  (con polaridad GO +1/-1: {len(pares_sin_pmid_pol)})")

    genes_sin = pd.DataFrame({"Gen_no_encontrado_en_GAF": no_encontrados})
    with pd.ExcelWriter(SALIDA, engine="openpyxl") as w:
        limpiar_para_excel(con).to_excel(w, sheet_name="Con_abstract", index=False)
        limpiar_para_excel(sin.drop(columns=["Titulo", "Abstract"])).to_excel(
            w, sheet_name="PMID_sin_abstract", index=False)
        limpiar_para_excel(sin_pmid).to_excel(w, sheet_name="Anotado_sin_PMID", index=False)
        genes_sin.to_excel(w, sheet_name="Genes_no_encontrados", index=False)
    print(f"🚀 FASE 1 COMPLETADA -> {SALIDA}")


if __name__ == "__main__":
    ejecutar_fase_1()
