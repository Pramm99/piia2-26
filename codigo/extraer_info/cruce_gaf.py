"""Cruce de los pares (Gen, Ruta) con el GAF humano: propagación, sinónimos y todas las evidencias con PMID."""
import gzip
import re

import pandas as pd

from config import CL_COMPATIBLES_NK, EVIDENCIAS_EXPERIMENTALES, GAF_FILE, SOLO_EXPERIMENTAL
from grafo_go import CON_SIGNO, NOMBRE_ESTADO, componer, estados_efectivos, polaridad_desde_estados

# Calificadores (col 4) que ya traen signo: se componen con el del camino hasta la ruta
SIGNO_CALIFICADOR = {
    "acts_upstream_of_positive_effect": "+", "acts_upstream_of_or_within_positive_effect": "+",
    "acts_upstream_of_negative_effect": "-", "acts_upstream_of_or_within_negative_effect": "-",
}
OCCURS_IN_CL = re.compile(r"occurs_in\((CL:\d+)\)")


def _estados_anotacion(estados, calificador):
    """{estado: profundidad} del camino, con el signo del calificador compuesto (si lo trae)."""
    signo = SIGNO_CALIFICADOR.get(calificador)
    if not signo:
        return estados_efectivos(estados)
    res = {}
    for e, prof in estados.items():
        nuevo = componer(e, signo)
        res[nuevo] = min(prof, res.get(nuevo, prof))
    return estados_efectivos(res)


def cruzar_con_gaf(pares, desc_map):
    """
    pares:    set de (gen, go_id_ruta)
    desc_map: dict termino_GO -> {ruta del Excel: {estado: profundidad}} (ver construir_desc_map)
    Devuelve (df_ev, df_sin, no_encontrados, df_anot): evidencias con PMID agrupadas por PMID,
    anotaciones sin PMID, genes que no están en el GAF y una fila por anotación (para el triaje).
    """
    genes_query = {g for g, _ in pares}
    print("🔍 Leyendo GAF (una sola pasada)...")
    simbolos_oficiales = set()
    sinonimos_todos = set()
    candidatas = []  # (simbolo, sinonimos, go_id, pmids, evidencia, referencia, with_from, calificador, extension)

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
            extension = c[15] if len(c) > 15 else ""
            candidatas.append((simbolo, sins, go_id, pmids, evid, c[5], c[7], c[3], extension))

    # Genes del Excel que no aparecen ni como símbolo ni como sinónimo
    no_encontrados = sorted(g for g in genes_query
                            if g not in simbolos_oficiales and g not in sinonimos_todos)

    def resolver_genes(simbolo, sinonimos):
        if simbolo in genes_query:
            return [(simbolo, "simbolo")]
        # sinónimo solo si NO es símbolo oficial de otro gen (evita ambigüedad)
        return [(s, "sinonimo") for s in sinonimos
                if s in genes_query and s not in simbolos_oficiales]

    anotaciones = []  # una fila por (gen, ruta, anotación del GAF)
    for simbolo, sinonimos, go_anotado, pmids, evid, ref, with_from, calif, extension in candidatas:
        cl_ajenos = sorted({cl for cl in OCCURS_IN_CL.findall(extension) if cl not in CL_COMPATIBLES_NK})
        for gen, via in resolver_genes(simbolo, sinonimos):
            for ruta, estados in desc_map[go_anotado].items():
                if (gen, ruta) not in pares:
                    continue
                efectivos = _estados_anotacion(estados, calif)
                anotaciones.append({
                    "Gen": gen, "GO_ID": ruta, "GO_ID_anotado": go_anotado,
                    "Directo": go_anotado == ruta, "PMIDs": pmids, "Evidencia": evid,
                    "Referencia": ref, "With_From": with_from, "Via_gen": via, "Fuente": "GOA",
                    "Calificador": calif, "CL_no_NK": "|".join(cl_ajenos),
                    "Estados": set(efectivos), "Profundidad": min(efectivos.values()),
                    "Profundidad_signo": min((p for e, p in efectivos.items() if e in CON_SIGNO), default=None),
                })
    df_anot = pd.DataFrame(anotaciones)
    if df_anot.empty:
        return pd.DataFrame(), pd.DataFrame(), no_encontrados, df_anot
    df_anot["Signo"] = df_anot["Estados"].apply(polaridad_desde_estados)
    df_anot["Experimental"] = df_anot["Evidencia"].isin(EVIDENCIAS_EXPERIMENTALES)

    j = lambda x: "|".join(sorted(set(x)))
    tipo = lambda x: "|".join(sorted({NOMBRE_ESTADO[e] for s in x for e in s}))
    polaridad = lambda x: polaridad_desde_estados(set().union(*x))

    # Anotaciones SIN PMID (conservadas para no perder la polaridad de GO)
    df_sin = df_anot[df_anot["PMIDs"].str.len() == 0]
    if not df_sin.empty:
        df_sin = (df_sin.groupby(["Gen", "GO_ID", "GO_ID_anotado"], as_index=False)
                  .agg(Directo=("Directo", "any"), Profundidad=("Profundidad", "min"),
                       Evidencia=("Evidencia", j), Referencia=("Referencia", j),
                       With_From=("With_From", j), Via_gen=("Via_gen", j), Fuente=("Fuente", j),
                       Tipo_relacion=("Estados", tipo), Polaridad_GO=("Estados", polaridad)))

    df = df_anot[df_anot["PMIDs"].str.len() > 0].explode("PMIDs").rename(columns={"PMIDs": "PMID"})
    if df.empty:
        return pd.DataFrame(), df_sin, no_encontrados, df_anot
    df = (df.groupby(["Gen", "GO_ID", "PMID"], as_index=False)
            .agg(GO_ID_anotado=("GO_ID_anotado", j), Directo=("Directo", "any"),
                 Profundidad=("Profundidad", "min"), Evidencia=("Evidencia", j),
                 Via_gen=("Via_gen", j), Fuente=("Fuente", j),
                 Tipo_relacion=("Estados", tipo), Polaridad_GO=("Estados", polaridad)))
    df["Experimental"] = df["Evidencia"].apply(
        lambda e: any(x in EVIDENCIAS_EXPERIMENTALES for x in e.split("|")))
    return df, df_sin, no_encontrados, df_anot
