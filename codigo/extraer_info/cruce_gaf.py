"""Cruce de los pares (Gen, Ruta) con el GAF humano: propagación, sinónimos y todas las evidencias con PMID."""
import gzip

import pandas as pd

from config import EVIDENCIAS_EXPERIMENTALES, GAF_FILE, SOLO_EXPERIMENTAL
from grafo_go import NOMBRE_ESTADO, estados_efectivos, polaridad_desde_estados


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
