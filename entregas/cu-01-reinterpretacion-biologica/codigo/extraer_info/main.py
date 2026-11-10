"""Fase 1: ingesta. Ejecuta en orden los módulos del pipeline.

  1. red             -> descarga del OBO y del GAF
  2. grafo_go        -> grafo GO y propagación a descendientes (con profundidad)
  3. entrada_excel   -> pares (Gen, Ruta) de los Excels
  4. inmunoglobulinas-> las Ig salen aparte como neutras, con la función de la Ig completa
  5. cruce_gaf       -> anotaciones con/sin PMID para esos pares
  6. polaridad       -> triaje del signo GO: aceptar_GO (sin LLM) / LLM / LLM_y_revision;
                        al final, los pares sin ningún abstract se cierran como UNKNOWN (sin_evidencia)
  7. pmid_externos   -> PMIDs de GeneRIF y Europe PMC (fuentes/) para los pares sin abstract del GAF
  8. abstracts       -> títulos y abstracts de los PMIDs
  9. salida          -> embudo por consola y Excel final
"""
import pandas as pd

import salida
from abstracts import descargar_abstracts
from config import GAF_FILE, GAF_URL, OBO_FILE, OBO_URL
from cruce_gaf import cruzar_con_gaf
from entrada_excel import cargar_entrada
from grafo_go import cargar_go, cargar_sinonimos, construir_desc_map
from inmunoglobulinas import construir_hoja_ig, detectar_inmunoglobulinas
from pmid_externos import buscar_pmids_externos
from polaridad import cerrar_sin_evidencia, triaje_pares
from red import descargar_archivo


def ejecutar_fase_1():
    print("--- INICIANDO FASE 1 ---")
    descargar_archivo(OBO_URL, OBO_FILE)
    descargar_archivo(GAF_URL, GAF_FILE)
    hijos, alias = cargar_go(OBO_FILE)

    df_excel, pares = cargar_entrada(alias)
    igs = detectar_inmunoglobulinas(df_excel["Gen"])
    hoja_ig = construir_hoja_ig(df_excel, igs)
    df_excel = df_excel[~df_excel["Gen"].isin(igs)]
    pares = {(g, r) for g, r in pares if g not in igs}
    desc_map = construir_desc_map(pares, hijos)

    df_ev, df_sin, no_encontrados, df_anot = cruzar_con_gaf(pares, desc_map)
    if no_encontrados:
        print(f"⚠️ {len(no_encontrados)} genes del Excel no existen como símbolo en el GAF "
              f"(ej: {no_encontrados[:15]})")
    triaje = triaje_pares(df_excel, df_anot)

    # Las fuentes externas buscan todos los pares sin abstract utilizable del GAF: los que no tienen
    # PMID y los que solo tienen PMIDs sin abstract en PubMed (p. ej. revisiones antiguas indexadas sin él)
    pares_con_abstract = set()
    if not df_ev.empty:
        con_texto = descargar_abstracts(df_ev["PMID"].unique().tolist())["PMID"]
        ev_texto = df_ev[df_ev["PMID"].isin(con_texto)]
        pares_con_abstract = set(zip(ev_texto["Gen"], ev_texto["GO_ID"]))
    df_ext = buscar_pmids_externos(pares - pares_con_abstract, desc_map, cargar_sinonimos(OBO_FILE))
    if not df_ext.empty:
        df_ev = pd.concat([df_ev, df_ext], ignore_index=True) if not df_ev.empty else df_ext
    if df_ev.empty:
        print("❌ Cero evidencias encontradas.")
        return

    pmids = df_ev["PMID"].unique().tolist()
    df_abs = descargar_abstracts(pmids)

    base, con, sin = salida.combinar(df_excel, df_ev, df_abs)
    salida.imprimir_embudo(pares, base, con, pmids, df_abs)
    sin_evidencia = salida.construir_sin_evidencia(df_excel, con, df_anot, df_ev)
    sin_evidencia, triaje = cerrar_sin_evidencia(sin_evidencia, triaje, df_anot)

    sin_pmid = salida.construir_anotado_sin_pmid(df_excel, df_ev, df_sin)
    salida.imprimir_sin_pmid(sin_pmid)
    salida.imprimir_triaje(triaje, hoja_ig)

    con, sin, sin_pmid = (salida.anadir_destino(d, triaje) for d in (con, sin, sin_pmid))
    salida.escribir_excel(con, sin, sin_pmid, no_encontrados, triaje, hoja_ig, sin_evidencia)


if __name__ == "__main__":
    ejecutar_fase_1()
