"""Lectura y filtrado del Excel de salida de la Fase 1 (las filas se agrupan en casos en casos.py).
Cuentan las rutas de los dos Excels de CIMUS: activadas (genes upregulados) y suprimidas (downregulados),
distinguidas por la columna Estado_Original."""
from typing import Optional

import pandas as pd

from ._fase1 import DESTINOS_SIN_LLM
from .esquema import COLUMNAS_OBLIGATORIAS, HOJA_EVIDENCIAS


def cargar_hoja(ruta_excel: str, hoja: str = HOJA_EVIDENCIAS) -> pd.DataFrame:
    # Sin dtype, pandas convierte "+1"/"-1" en 1.0/-1.0 y la pista GO deja de reconocerse
    df = pd.read_excel(ruta_excel, sheet_name=hoja, dtype={"Polaridad_GO": str, "PMID": str})
    validar_columnas(df.columns)
    return df


def pendientes_de_llm(df: pd.DataFrame) -> pd.DataFrame:
    """Quita los pares cuyo signo ya acepta el grafo GO (columna Destino del triaje de la Fase 1)."""
    if "Destino" not in df.columns:
        return df
    return df[~df["Destino"].isin(DESTINOS_SIN_LLM)]


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
