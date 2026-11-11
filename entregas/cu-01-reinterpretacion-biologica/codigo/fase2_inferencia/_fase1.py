"""Puente hacia ../fase1_ingesta (Fase 1). Es el ÚNICO sitio del paquete que conoce esa carpeta.

Los módulos de fase1_ingesta se importan entre sí en plano (`from config import ...`), así que
hay que añadir esa carpeta a sys.path antes de importarlos. Los importamos con su nombre plano
(`abstracts`, `config`) para que Python los cargue una sola vez.
"""
import sys
from pathlib import Path

DIR_FASE1 = Path(__file__).resolve().parent.parent / "fase1_ingesta"

if not DIR_FASE1.is_dir():
    raise ImportError(f"No existe la carpeta de Fase 1: {DIR_FASE1}")
if str(DIR_FASE1) not in sys.path:
    sys.path.insert(0, str(DIR_FASE1))

from abstracts import limpiar_texto  # noqa: E402
from config import OBO_FILE, SALIDA, SIN_DIRECCION_COMO_PROCESO  # noqa: E402
from fuentes.generif import datos_mygene  # noqa: E402
from grafo_go import (cargar_go, cargar_nombres, cargar_sinonimos, descendientes,  # noqa: E402
                      estados_efectivos)
from polaridad import DESTINOS_SIN_LLM  # noqa: E402
from relevancia import MIN_ALIAS, menciona_gen, patron_gen  # noqa: E402

__all__ = ["DIR_FASE1", "limpiar_texto", "SALIDA", "DESTINOS_SIN_LLM", "OBO_FILE", "SIN_DIRECCION_COMO_PROCESO",
           "datos_mygene",
           "cargar_go", "cargar_nombres", "cargar_sinonimos", "descendientes", "estados_efectivos",
           "MIN_ALIAS", "menciona_gen", "patron_gen"]
