"""Lectura del Excel de salida de la Fase 1 y conversión de UNA fila a Evidencia."""
from typing import Iterator, Mapping, Optional

import pandas as pd

from .esquema import COLUMNAS_OBLIGATORIAS, HOJA_EVIDENCIAS, Evidencia
from .limpieza import limpiar_abstract, normalizar_pmid, recortar, valor_texto


def cargar_hoja(ruta_excel: str, hoja: str = HOJA_EVIDENCIAS) -> pd.DataFrame:
    df = pd.read_excel(ruta_excel, sheet_name=hoja)
    validar_columnas(df.columns)
    return df


def validar_columnas(columnas) -> None:
    faltan = [c for c in COLUMNAS_OBLIGATORIAS if c not in set(columnas)]
    if faltan:
        raise ValueError(f"Faltan columnas en la hoja de evidencias: {faltan}")


def filtrar(df: pd.DataFrame, gen: Optional[str] = None, go_id: Optional[str] = None) -> pd.DataFrame:
    """Filtra por gen y/o ruta (insensible a mayúsculas)."""
    if gen:
        df = df[df["Gen"].astype(str).str.strip().str.upper() == gen.strip().upper()]
    if go_id:
        df = df[df["GO_ID"].astype(str).str.strip().str.upper() == go_id.strip().upper()]
    return df


def fila_a_evidencia(fila: Mapping, max_chars_abstract: Optional[int] = None) -> Optional[Evidencia]:
    """Convierte una fila (Series o dict) en Evidencia. Devuelve None si no hay abstract utilizable."""
    abstract = recortar(limpiar_abstract(fila.get("Abstract")), max_chars_abstract)
    if not abstract:
        return None
    directo = fila.get("Directo")
    return Evidencia(
        gen=valor_texto(fila.get("Gen")).upper(),
        go_id=valor_texto(fila.get("GO_ID")),
        ruta_nombre=valor_texto(fila.get("Ruta_Nombre")),
        estado_scrnaseq=valor_texto(fila.get("Estado_Original")),
        pmid=normalizar_pmid(fila.get("PMID")),
        titulo=limpiar_abstract(fila.get("Titulo")),
        abstract=abstract,
        polaridad_go=valor_texto(fila.get("Polaridad_GO")),
        evidencia_go=valor_texto(fila.get("Evidencia")),
        directo=None if directo is None or pd.isna(directo) else bool(directo),
    )


def iterar_filas(df: pd.DataFrame) -> Iterator[Mapping]:
    for _, fila in df.iterrows():
        yield fila
