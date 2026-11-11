"""Parámetros de la Fase 3 (spec de scoring). Son provisionales: los fija el equipo con CIMUS al revisar las
primeras rutas. Viven aquí para ajustarlos sin tocar la lógica."""
from pathlib import Path

DIR_CODIGO = Path(__file__).resolve().parent.parent
FICHERO_FASE1 = DIR_CODIGO / "fase1_ingesta" / "fase1_dataset_abstracts.xlsx"
FICHERO_FASE2 = DIR_CODIGO / "data" / "fase2_resultados.xlsx"
FICHERO_SCORING = DIR_CODIGO / "data" / "fase3_scoring.xlsx"

# Peso del voto: w = Confianza_final / 100 × f_contexto. Cada condición de contexto que no se cumple multiplica
# por FACTOR_CONTEXTO (ratón u otro organismo; tumor u otro tipo celular). Sin dato del modelo vale como cumplida.
ORGANISMOS_VALIDOS = ("human", "not_stated")
TIPOS_CELULARES_VALIDOS = ("NK", "T", "other_immune", "not_stated")
FACTOR_CONTEXTO = 0.5
CONFIANZA_POR_DEFECTO = 50  # fila resuelta sin Confianza_final (marca peso_por_defecto)

# Signo del par: la clase ganadora vale si la minoría pesa menos de este tanto del total; si no, revisar.
UMBRAL_MINORIA = 1 / 3
MIN_PESO_EVIDENCIA = 1.0  # por debajo, el par resuelto lleva evidencia_debil (p. ej. un único artículo en ratón)

# Lectura de la ruta
MIN_PARES_CON_SIGNO = 3
MIN_COBERTURA = 0.30
UMBRAL_NPS = 0.33
