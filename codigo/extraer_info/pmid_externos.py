"""PMIDs de fuentes externas para los pares (Gen, Ruta) que el GAF deja sin PMID.

Para cada gen se reúnen las frases curadas de NCBI GeneRIF y de UniProt FUNCTION, cada una con su
PMID. Un PMID se asigna a un par si la frase, el título o el abstract mencionan la ruta o algún término
de su subárbol (relevancia.py). En los GeneRIF, además, el texto tiene que nombrar al gen: un mismo
GeneRIF puede venir de un artículo sobre otros genes. Las filas salen con el mismo esquema que las
evidencias del GAF, así que siguen el mismo camino hasta la hoja Con_abstract.
"""
import pandas as pd

from abstracts import descargar_abstracts
from config import MAX_PMIDS_EXTERNOS_POR_PAR
from fuentes.generif import datos_mygene
from fuentes.uniprot import entradas_uniprot, frases_funcion
from relevancia import coincidencia, menciona_gen, ngramas, patron_gen, vocabularios_rutas

COLUMNAS = ["Gen", "GO_ID", "PMID", "GO_ID_anotado", "Directo", "Profundidad", "Evidencia", "Via_gen",
            "Fuente", "Tipo_relacion", "Polaridad_GO", "Experimental", "Frase_fuente",
            "Termino_coincidente", "Coincide_en"]


def _candidatos(genes):
    """({gen: [(pmid, fuente, frase)]}, {gen: patrón del gen}) con las frases GeneRIF y UniProt."""
    mg = datos_mygene(genes)
    up = entradas_uniprot(genes)
    cand, patrones = {}, {}
    for g in genes:
        filas = [(r["PMID"], "GeneRIF", r["Texto"]) for r in mg[g]["GeneRIF"]]
        filas += [(p, "UniProt", frase) for pmids, frase in frases_funcion(up[g]["Funcion"]) for p in pmids]
        cand[g] = filas
        patrones[g] = patron_gen(g, mg[g]["Alias"], mg[g]["Nombre"])
    return cand, patrones


def buscar_pmids_externos(pares_sin, desc_map, sinonimos):
    """DataFrame con el esquema de df_ev (más Frase_fuente, Termino_coincidente y Coincide_en)."""
    if not pares_sin:
        return pd.DataFrame(columns=COLUMNAS)
    genes = sorted({g for g, _ in pares_sin})
    cand, patrones = _candidatos(genes)
    pmids = sorted({p for filas in cand.values() for p, _, _ in filas})
    print(f"🔎 Fuentes externas: {len(genes)} genes sin PMID en el GAF, {len(pmids)} PMIDs candidatos")
    df_abs = descargar_abstracts(pmids)
    textos = {p: f"{t} {a}" for p, t, a in zip(df_abs["PMID"], df_abs["Titulo"], df_abs["Abstract"])}
    vocab = vocabularios_rutas(desc_map, sinonimos, {r for _, r in pares_sin})

    gramas_abs = {}
    registros = []
    descartados = 0
    for g in genes:
        filas = []
        for p, f, frase in cand[g]:
            if f == "GeneRIF" and not menciona_gen(f"{frase} {textos.get(p, '')}", patrones[g]):
                descartados += 1
                continue
            filas.append((p, f, frase, ngramas(frase)))
        for gen, ruta in (par for par in pares_sin if par[0] == g):
            for pmid, fuente, frase, gramas in filas:
                termino, donde = coincidencia(gramas, vocab[ruta]), "frase"
                if not termino and pmid in textos:
                    if pmid not in gramas_abs:
                        gramas_abs[pmid] = ngramas(textos[pmid])
                    termino, donde = coincidencia(gramas_abs[pmid], vocab[ruta]), "abstract"
                if termino:
                    registros.append({"Gen": gen, "GO_ID": ruta, "PMID": pmid, "Fuente": fuente,
                                      "Frase_fuente": frase, "Termino_coincidente": termino, "Coincide_en": donde})
    print(f"   GeneRIF descartados porque el texto no nombra al gen: {descartados}")
    if not registros:
        return pd.DataFrame(columns=COLUMNAS)

    j = lambda x: "|".join(sorted(set(x)))
    df = (pd.DataFrame(registros).groupby(["Gen", "GO_ID", "PMID"], as_index=False)
          .agg(Fuente=("Fuente", j), Frase_fuente=("Frase_fuente", " | ".join),
               Termino_coincidente=("Termino_coincidente", j), Coincide_en=("Coincide_en", j)))
    # Primero los PMIDs cuya propia frase curada nombra la ruta; el abstract solo es respaldo
    # (y, a igualdad, los más recientes: PMID mayor)
    df["_orden"] = ~df["Coincide_en"].str.contains("frase")
    df["_pmid"] = df["PMID"].astype(int)
    df = (df.sort_values(["Gen", "GO_ID", "_orden", "_pmid"], ascending=[True, True, True, False])
          .groupby(["Gen", "GO_ID"]).head(MAX_PMIDS_EXTERNOS_POR_PAR).drop(columns=["_orden", "_pmid"]))
    df["GO_ID_anotado"], df["Directo"], df["Profundidad"] = "", False, None
    df["Evidencia"], df["Via_gen"] = df["Fuente"], "simbolo"
    df["Tipo_relacion"], df["Polaridad_GO"], df["Experimental"] = "", "", False
    return df[COLUMNAS].reset_index(drop=True)
