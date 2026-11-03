"""Configuración global: rutas, URLs y opciones. Es el único sitio que hay que editar para ajustar la ejecución."""
import os

# --- Entradas / salidas ---
EXCEL_ACTIVADAS = "rutas_activadas.xlsx"
EXCEL_SUPRIMIDAS = "rutas_suprimidas.xlsx"
SALIDA = "fase1_dataset_abstracts.xlsx"

# --- Ficheros descargables (anotaciones GO) ---
GAF_FILE = "data/goa_human.gaf.gz"
GAF_URL = "https://current.geneontology.org/annotations/goa_human.gaf.gz"
OBO_FILE = "data/go-basic.obo"
OBO_URL = "https://purl.obolibrary.org/obo/go/go-basic.obo"
CACHE_FILE = "data/cache_abstracts.json"

# --- APIs de abstracts ---
EPMC_API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
NCBI_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
NCBI_EMAIL = "tu_email@ejemplo.com"          # <- pon el tuyo (buena práctica NCBI)
NCBI_API_KEY = os.environ.get("NCBI_API_KEY")  # opcional: sube el límite a 10 req/s

# --- Opciones del cruce ---
# False = comportamiento de la v2 (solo is_a y part_of); útil para comparar resultados
PROPAGAR_REGULACION = True

# True = solo evidencia experimental; False = cualquier anotación con PMID (más abstracts)
SOLO_EXPERIMENTAL = False
EVIDENCIAS_EXPERIMENTALES = {"EXP", "IDA", "IPI", "IMP", "IGI", "IEP",
                             "HTP", "HDA", "HMP", "HGI", "HEP"}
