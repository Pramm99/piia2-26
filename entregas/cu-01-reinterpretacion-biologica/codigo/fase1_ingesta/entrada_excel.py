"""Lectura de los ficheros de rutas (activadas / suprimidas) y expansión a pares (Gen, Ruta).

Acepta .xlsx y .csv con las columnas ID, Description y geneID. main.py los lee y valida antes de cualquier
descarga, para que un fichero mal formado falle en el primer segundo y no tras bajar el OBO y el GAF.
"""
import os

import pandas as pd

from config import EXCEL_ACTIVADAS, EXCEL_SUPRIMIDAS

COLUMNAS_OBLIGATORIAS = ("ID", "Description", "geneID")


def leer_tabla(ruta):
    """DataFrame de un .xlsx o .csv de enrichGO, con las columnas obligatorias comprobadas (ValueError si falta alguna)."""
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No existe {ruta}")
    ext = os.path.splitext(ruta)[1].lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(ruta)
    elif ext == ".csv":
        # sep=None detecta «,» (write.csv de R) o «;» (Excel en español); todo como texto, igual que en el .xlsx
        df = pd.read_csv(ruta, sep=None, engine="python", dtype=str, encoding="utf-8-sig")
    else:
        raise ValueError(f"Formato no admitido ({ext or 'sin extensión'}) en {ruta}: usa .xlsx o .csv")
    faltan = [c for c in COLUMNAS_OBLIGATORIAS if c not in df.columns]
    if faltan:
        raise ValueError(f"A {ruta} le faltan las columnas obligatorias: {', '.join(faltan)}")
    return df


def explotar(df, etiqueta, alias):
    """Una fila por (gen, ruta) a partir de la tabla de rutas."""
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


def leer_y_explotar_excel(ruta, etiqueta, alias):
    return explotar(leer_tabla(ruta), etiqueta, alias)


def leer_entrada():
    """Lee y valida los dos ficheros de CIMUS sin tocar la red: {etiqueta: DataFrame}."""
    return {"Activada": leer_tabla(EXCEL_ACTIVADAS), "Suprimida": leer_tabla(EXCEL_SUPRIMIDAS)}


def cargar_entrada(alias, tablas=None):
    """Devuelve (df_excel, pares), con pares = {(gen, go_id)} únicos. tablas: lo que dio leer_entrada (si no, se leen)."""
    tablas = tablas or leer_entrada()
    df_excel = pd.concat([explotar(df, etiqueta, alias) for etiqueta, df in tablas.items()], ignore_index=True)
    pares = set(zip(df_excel["Gen"], df_excel["GO_ID"]))
    print(f"✅ Pares (Gen, Ruta) únicos de entrada: {len(pares)}")

    if df_excel["Gen"].str.fullmatch(r"\d+").mean() > 0.5:
        print("⚠️ La columna geneID parece ENTREZID, no SYMBOL: el cruce fallará. Convierte a símbolos.")
    return df_excel, pares
