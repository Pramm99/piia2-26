"""Puente hacia ../extraer_info (Fase 1). Es el ÚNICO sitio del paquete que conoce esa carpeta.

Los módulos de extraer_info se importan entre sí en plano (`from config import ...`), así que
hay que añadir esa carpeta a sys.path antes de importarlos. Los importamos con su nombre plano
(`abstracts`, `config`) para que Python los cargue una sola vez.
"""
import sys
from pathlib import Path

DIR_EXTRAER_INFO = Path(__file__).resolve().parent.parent / "extraer_info"

if not DIR_EXTRAER_INFO.is_dir():
    raise ImportError(f"No existe la carpeta de Fase 1: {DIR_EXTRAER_INFO}")
if str(DIR_EXTRAER_INFO) not in sys.path:
    sys.path.insert(0, str(DIR_EXTRAER_INFO))

from abstracts import limpiar_texto  # noqa: E402
from config import SALIDA  # noqa: E402
from polaridad import DESTINOS_SIN_LLM  # noqa: E402

__all__ = ["DIR_EXTRAER_INFO", "limpiar_texto", "SALIDA", "DESTINOS_SIN_LLM"]
