import pandas as pd


def obtener_titulos_y_abstracts(
    ruta_excel: str, hoja: str = "Con_abstract", gen: str = None
) -> list[dict]:
    """Carga el Excel y devuelve únicamente el Título y el Abstract de cada fila."""
    df = pd.read_excel(ruta_excel, sheet_name=hoja)

    # Filtrar por gen si se especifica
    if gen:
        df = df[df["Gen"].astype(str).str.upper() == gen.strip().upper()]

    # Asegurar que no haya nulos y limpiar valores vacíos
    sub_df = df[["Titulo", "Abstract"]].dropna(subset=["Abstract"])

    # Exportar como lista de diccionarios limpios
    return sub_df.rename(
        columns={"Titulo": "titulo", "Abstract": "abstract"}
    ).to_dict(orient="records")


# Ejemplo de uso:
if __name__ == "__main__":
    articulos = obtener_titulos_y_abstracts(
        "fase1_dataset_abstracts.xlsx", gen="CD7"
    )
    for art in articulos:
        print(f"Título: {art['titulo']}")
        print(f"Resumen: {art['abstract']}\n" + "-" * 40)