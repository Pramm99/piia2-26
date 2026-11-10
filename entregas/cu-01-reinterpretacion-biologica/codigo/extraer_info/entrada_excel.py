"""Lectura de los Excels de rutas (activadas / suprimidas) y expansión a pares (Gen, Ruta)."""
import os

import pandas as pd

from config import EXCEL_ACTIVADAS, EXCEL_SUPRIMIDAS


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


def cargar_entrada(alias):
    """Lee ambos Excels y devuelve (df_excel, pares), con pares = {(gen, go_id)} únicos."""
    df_up = leer_y_explotar_excel(EXCEL_ACTIVADAS, "Activada", alias)
    df_down = leer_y_explotar_excel(EXCEL_SUPRIMIDAS, "Suprimida", alias)
    df_excel = pd.concat([df_up, df_down], ignore_index=True)
    pares = set(zip(df_excel["Gen"], df_excel["GO_ID"]))
    print(f"✅ Pares (Gen, Ruta) únicos de entrada: {len(pares)}")

    if df_excel["Gen"].str.fullmatch(r"\d+").mean() > 0.5:
        print("⚠️ La columna geneID parece ENTREZID, no SYMBOL: el cruce fallará. Convierte a símbolos.")
    return df_excel, pares
