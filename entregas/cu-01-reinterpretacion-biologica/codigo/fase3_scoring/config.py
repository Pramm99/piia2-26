"""Parámetros de la Fase 3 (spec de scoring). MIN_PESO_EVIDENCIA y los umbrales de lectura se fijaron con datos en
#35; los pesos de contexto, el factor de GO y la minoría son provisionales. Viven aquí para ajustarlos sin tocar la
lógica."""
from pathlib import Path

DIR_CODIGO = Path(__file__).resolve().parent.parent
FICHERO_FASE1 = DIR_CODIGO / "fase1_ingesta" / "fase1_dataset_abstracts.xlsx"
FICHERO_FASE2 = DIR_CODIGO / "data" / "fase2_resultados.xlsx"
FICHERO_SCORING = DIR_CODIGO / "data" / "fase3_scoring.xlsx"
# Tabla de expresión diferencial de CIMUS (log2FC por gen). Si existe, el CLI la usa sola para NPS_log2FC.
FICHERO_LOG2FC = DIR_CODIGO / "tools_cimus" / "NK_cells_DESeq2_results.xlsx"

# Peso del voto: w = Confianza_final / 100 × f_contexto. Cada condición de contexto que no se cumple multiplica
# por FACTOR_CONTEXTO (ratón u otro organismo; tumor u otro tipo celular). Sin dato del modelo vale como cumplida.
ORGANISMOS_VALIDOS = ("human", "not_stated")
TIPOS_CELULARES_VALIDOS = ("NK", "T", "other_immune", "not_stated")
FACTOR_CONTEXTO = 0.5
CONFIANZA_POR_DEFECTO = 50  # fila resuelta sin Confianza_final (marca peso_por_defecto)
# El artículo que cita la anotación de GO del gen (Fuente GOA en la Fase 1) multiplica su peso: un curador ya lo
# leyó y lo ligó al proceso. Con 1,5, un artículo humano de GO con confianza 47 o más no es débil; uno en ratón o
# en tumor lo sigue siendo (como mucho 0,9 × 1,5 × 0,5 = 0,675 < MIN_PESO_EVIDENCIA). No cambia el NPS: un par tiene solo artículos GOA o ninguno, así que el factor no altera qué signo gana.
FACTOR_FUENTE_GO = 1.5

# Signo del par: la clase ganadora vale si la minoría pesa menos de este tanto del total; si no, revisar.
UMBRAL_MINORIA = 1 / 3
# Por debajo, el par resuelto lleva evidencia_debil. Solo marca: el signo cuenta igual en el NPS (#35). Con 0,7, un
# único artículo es débil si es en ratón u otro organismo, en tumor u otro tipo celular, o con confianza < 70 (< 47
# si lo cita la anotación de GO); uno humano en células inmunes con confianza 70 o más no lo es.
MIN_PESO_EVIDENCIA = 0.7

# Lectura de la ruta. Medidos en #35: ninguna combinación cercana gira una ruta de activada a inhibida ni al revés.
MIN_PARES_CON_SIGNO = 3
MIN_COBERTURA = 0.30
UMBRAL_NPS = 0.33
