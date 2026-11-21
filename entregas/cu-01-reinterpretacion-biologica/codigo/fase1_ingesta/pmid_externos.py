"""PMIDs de fuentes externas para los pares (Gen, Ruta) sin abstract utilizable del GAF. Tres etapas:

  1. NCBI GeneRIF: frases curadas sobre el gen, cada una con su PMID.
  2. Europe PMC dirigida, solo para los pares que siguen vacíos: artículos que nombran el gen y la
     ruta en la MISMA frase del título o del abstract (no está curada: la coincidencia en frases
     distintas daba muchos artículos que solo mencionan el gen de pasada).
  3. NCBI gene2pubmed + MeSH de la ruta + «Humans», para los que siguen vacíos (#31): NCBI liga el gen al
     artículo y MeSH juzga el tema, así que no se exige la ruta en el texto. Acierta en ~53 % de los pares (muestra
     del 2026-11-13): el LLM hace de filtro y solo entran los 3 más recientes por par.

Un PMID se asigna a un par si la frase GeneRIF, el título o el abstract mencionan la ruta o algún
término de su subárbol (relevancia.py) y, además, nombran al gen: un GeneRIF puede venir de un artículo
sobre otros genes y la búsqueda de Europe PMC no distingue CD7 de CD-7 ni de alias ambiguos. Las filas
salen con el mismo esquema que las evidencias del GAF y siguen el mismo camino hasta Con_abstract.
"""
from collections import defaultdict

import pandas as pd

from abstracts import descargar_abstracts
from config import EPMC_PROFUNDIDAD_CONSULTA, MAX_PMIDS_EXTERNOS_POR_PAR, MAX_PMIDS_GENE2PUBMED_POR_PAR
from fuentes import europepmc, gene2pubmed
from fuentes.generif import datos_mygene
from fuentes.nombres import nombres_proteina
from relevancia import (MIN_ALIAS, coincidencia, coincidencia_en_frase, menciona_gen, ngramas, nombres_utiles,
                        patron_gen, vocabularios_rutas)

COLUMNAS = ["Gen", "GO_ID", "PMID", "GO_ID_anotado", "Directo", "Profundidad", "Evidencia", "Via_gen",
            "Fuente", "Tipo_relacion", "Polaridad_GO", "Experimental", "Frase_fuente",
            "Termino_coincidente", "Coincide_en"]


class _Textos:
    """Título + abstract por PMID (descargados con abstracts.py) y sus n-gramas, calculados una vez."""

    def __init__(self):
        self.texto, self._gramas = {}, {}

    def cargar(self, pmids):
        nuevos = sorted(set(pmids) - set(self.texto))
        if nuevos:
            df = descargar_abstracts(nuevos)
            self.texto.update({p: f"{t} {a}" for p, t, a in zip(df["PMID"], df["Titulo"], df["Abstract"])})

    def gramas(self, pmid):
        if pmid not in self._gramas:
            self._gramas[pmid] = ngramas(self.texto.get(pmid, ""))
        return self._gramas[pmid]


def _etapa_generif(pares, mg, patrones, vocab, textos):
    """Registros GeneRIF: la frase curada o el abstract nombran la ruta, y el texto nombra al gen."""
    textos.cargar(r["PMID"] for g in {g for g, _ in pares} for r in mg[g]["GeneRIF"])
    por_gen, registros, descartados = defaultdict(list), [], 0
    for g in {g for g, _ in pares}:
        for r in mg[g]["GeneRIF"]:
            p, frase = r["PMID"], r["Texto"]
            if not menciona_gen(f"{frase} {textos.texto.get(p, '')}", patrones[g]):
                descartados += 1
                continue
            por_gen[g].append((p, frase, ngramas(frase)))
    for gen, ruta in pares:
        for pmid, frase, gramas in por_gen[gen]:
            termino, donde = coincidencia(gramas, vocab[ruta]), "frase"
            if not termino and pmid in textos.texto:
                termino, donde = coincidencia(textos.gramas(pmid), vocab[ruta]), "abstract"
            if termino:
                registros.append({"Gen": gen, "GO_ID": ruta, "PMID": pmid, "Fuente": "GeneRIF",
                                  "Frase_fuente": frase, "Termino_coincidente": termino, "Coincide_en": donde})
    print(f"   GeneRIF: {len(registros)} asignaciones; {descartados} descartados porque el texto no nombra al gen")
    return registros


def _etapa_europepmc(pares, mg, patrones, vocab, vocab_consulta, textos):
    """Registros Europe PMC: búsqueda por gen + frases cercanas de la ruta, verificada en local frase a frase."""
    consultas = {}
    for gen, ruta in pares:
        nombres = {gen} | {a for a in mg[gen]["Alias"] if len(a) >= MIN_ALIAS and not a.isdigit()}
        consultas[(gen, ruta)] = europepmc.construir_consultas(nombres, vocab_consulta[ruta].values())
    resultados = europepmc.buscar([q for qs in consultas.values() for q in qs])
    candidatos = {par: list(dict.fromkeys(p for q in qs for p in resultados[q])) for par, qs in consultas.items()}
    textos.cargar(p for ps in candidatos.values() for p in ps)
    registros = []
    for (gen, ruta), pmids in candidatos.items():
        for pmid in pmids:
            if pmid not in textos.texto:
                continue
            frase, termino = coincidencia_en_frase(textos.texto[pmid], patrones[gen], vocab[ruta])
            if termino:
                registros.append({"Gen": gen, "GO_ID": ruta, "PMID": pmid, "Fuente": "EuropePMC",
                                  "Frase_fuente": frase, "Termino_coincidente": termino, "Coincide_en": "frase_abstract"})
    print(f"   Europe PMC: {len(registros)} asignaciones en {len({(r['Gen'], r['GO_ID']) for r in registros})} pares")
    return registros


def _etapa_gene2pubmed(pares, patrones, textos):
    """Registros gene2pubmed + MeSH: de los artículos más recientes que NCBI liga al gen con el MeSH de la ruta y
    «Humans», los que nombran al gen; como mucho MAX_PMIDS_GENE2PUBMED_POR_PAR por par."""
    tabla = gene2pubmed.leer_tabla()
    consultas = {(g, r): tabla[r] for g, r in pares if r in tabla}
    if not consultas:
        return []
    arts = gene2pubmed.articulos({(g, c) for (g, _), c in consultas.items()})
    candidatos = {par: arts[(par[0], c)][:MAX_PMIDS_EXTERNOS_POR_PAR] for par, c in consultas.items()}
    textos.cargar(p for ps in candidatos.values() for p in ps)
    registros = []
    for (gen, ruta), pmids in candidatos.items():
        validos = [p for p in pmids if p in textos.texto and menciona_gen(textos.texto[p], patrones[gen])]
        registros += [{"Gen": gen, "GO_ID": ruta, "PMID": p, "Fuente": "gene2pubmed", "Frase_fuente": "",
                       "Termino_coincidente": "", "Coincide_en": "mesh"}
                      for p in validos[:MAX_PMIDS_GENE2PUBMED_POR_PAR]]
    print(f"   gene2pubmed + MeSH: {len(registros)} asignaciones en {len({(r['Gen'], r['GO_ID']) for r in registros})} pares")
    return registros


def buscar_pmids_externos(pares_sin, desc_map, sinonimos):
    """DataFrame con el esquema de df_ev (más Frase_fuente, Termino_coincidente y Coincide_en)."""
    if not pares_sin:
        return pd.DataFrame(columns=COLUMNAS)
    genes = sorted({g for g, _ in pares_sin})
    rutas = {r for _, r in pares_sin}
    print(f"🔎 Fuentes externas para {len(pares_sin)} pares sin abstract del GAF ({len(genes)} genes)")
    mg = datos_mygene(genes)
    proteinas = nombres_utiles(nombres_proteina(genes))
    patrones = {g: patron_gen(g, mg[g]["Alias"], mg[g]["Nombre"], proteinas[g]) for g in genes}
    vocab = vocabularios_rutas(desc_map, sinonimos, rutas)
    textos = _Textos()

    registros = _etapa_generif(pares_sin, mg, patrones, vocab, textos)
    vacios = pares_sin - {(r["Gen"], r["GO_ID"]) for r in registros}
    if vacios:
        cerca = vocabularios_rutas(desc_map, sinonimos, {r for _, r in vacios}, EPMC_PROFUNDIDAD_CONSULTA)
        registros += _etapa_europepmc(vacios, mg, patrones, vocab, cerca, textos)
    vacios = pares_sin - {(r["Gen"], r["GO_ID"]) for r in registros}
    if vacios:
        registros += _etapa_gene2pubmed(vacios, patrones, textos)
    if not registros:
        return pd.DataFrame(columns=COLUMNAS)

    j = lambda x: "|".join(sorted(set(x)))
    df = (pd.DataFrame(registros).groupby(["Gen", "GO_ID", "PMID"], as_index=False)
          .agg(Fuente=("Fuente", j), Frase_fuente=("Frase_fuente", lambda x: " | ".join(f for f in x if f)),
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
