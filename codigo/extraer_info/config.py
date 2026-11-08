"""Configuración global: rutas, URLs y opciones. Es el único sitio que hay que editar para ajustar la ejecución."""
import os

# Rutas ancladas a esta carpeta (no al directorio desde el que se lanza el script)
DIR_FASE1 = os.path.dirname(os.path.abspath(__file__))           # codigo/extraer_info
DIR_DATA = os.path.join(os.path.dirname(DIR_FASE1), "data")      # codigo/data

# --- Entradas / salidas ---
EXCEL_ACTIVADAS = os.path.join(DIR_FASE1, "rutas_activadas.xlsx")
EXCEL_SUPRIMIDAS = os.path.join(DIR_FASE1, "rutas_suprimidas.xlsx")
SALIDA = os.path.join(DIR_FASE1, "fase1_dataset_abstracts.xlsx")

# --- Ficheros descargables (anotaciones GO) ---
GAF_FILE = os.path.join(DIR_DATA, "goa_human.gaf.gz")
GAF_URL = "https://current.geneontology.org/annotations/goa_human.gaf.gz"
OBO_FILE = os.path.join(DIR_DATA, "go-basic.obo")
OBO_URL = "https://purl.obolibrary.org/obo/go/go-basic.obo"
CACHE_FILE = os.path.join(DIR_DATA, "cache_abstracts.json")

# --- APIs de abstracts ---
EPMC_API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
NCBI_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
NCBI_EMAIL = "tu_email@ejemplo.com"          # <- pon el tuyo (buena práctica NCBI)
NCBI_API_KEY = os.environ.get("NCBI_API_KEY")  # opcional: sube el límite a 10 req/s

# --- Filtro de inmunoglobulinas (lista HGNC, se descarga una vez) ---
HGNC_IG_FILE = os.path.join(DIR_DATA, "hgnc_inmunoglobulinas.json")
HGNC_IG_URL = 'https://rest.genenames.org/search/locus_type/"immunoglobulin gene"'
# Forman parte de la Ig completa pero su símbolo no empieza por IG (cadena J y componente secretor)
EXCEPCIONES_IG = {"JCHAIN", "PIGR"}

# --- Función de la Ig completa (UniProt Swiss-Prot, se descarga una vez por gen) ---
UNIPROT_API = "https://rest.uniprot.org/uniprotkb/search"
UNIPROT_IG_FILE = os.path.join(DIR_DATA, "uniprot_inmunoglobulinas.json")
# Isotipos y piezas del complejo con función propia; el resto (segmentos V/D/J, cadenas κ/λ)
# usa el párrafo común de UniProt sobre la Ig completa
IG_FUNCION_PROPIA = {"IGHG1", "IGHG2", "IGHG3", "IGHG4", "IGHM", "IGHD", "IGHE",
                     "IGHA1", "IGHA2", "JCHAIN", "PIGR"}
IG_CON_SUBUNIDAD = {"IGHA1", "IGHA2"}  # la IgA secretora se describe en SUBUNIT
IG_GEN_PLANTILLA = "IGKC"              # de dónde sale el párrafo común si el gen no tiene entrada
IG_INICIO_PARRAFO = "Immunoglobulins, also known as antibodies"

# --- Triaje del signo GO (informe «Polaridad GO como signo directo», 2026-11-08) ---
# RO marca como deprecada la composición «regulates ∘ part_of»: una regulación por encima de
# un part_of no conserva el signo
CORTAR_REGULACION_TRAS_PART_OF = True
# Aristas is_a que generalizan demasiado: el signo que las cruza se pierde (hijo, padre)
ARISTAS_SIN_SIGNO = {
    ("GO:0050870", "GO:1903039"),  # positive regulation of T cell activation -> ... of leukocyte cell-cell adhesion
    ("GO:0050868", "GO:1903038"),  # negative regulation of T cell activation -> ... of leukocyte cell-cell adhesion
}
PROFUNDIDAD_MAX_ACEPTAR = 2  # a profundidad ≤2 con evidencia experimental no hubo errores en la auditoría
EVIDENCIAS_FILOGENETICAS = {"IBA", "IBD", "IKR", "IRD"}  # se descartan si contradicen a una experimental
# Tipos celulares de Cell Ontology compatibles con NK: CL:0000623, sus ancestros y sus subtipos
# (OLS4, consultado el 2026-11-08). Un occurs_in con otro CL describe el efecto en otra célula.
CL_COMPATIBLES_NK = {
    "CL:0000623",
    # ancestros
    "CL:0000000", "CL:0000219", "CL:0000226", "CL:0000255", "CL:0000542", "CL:0000738",
    "CL:0000842", "CL:0000988", "CL:0001065", "CL:0001067", "CL:0002242",
    # subtipos
    "CL:0000823", "CL:0000824", "CL:0000937", "CL:0000938", "CL:0000939", "CL:0002338",
    "CL:0002343", "CL:0002344", "CL:2000054", "CL:4033071", "CL:4047101", "CL:4052028",
    "CL:4052051", "CL:4052052", "CL:4052053",
}
# Genes con función dual documentada: van siempre al LLM, sea cual sea el signo GO
PREFIJOS_VIGILANCIA = ("KIR", "KLRC", "KLRD", "NCR")
GENES_VIGILANCIA = {"HAVCR2", "LGALS9", "TIGIT", "PVR", "BST2", "XCL1", "CCR7"}

# --- Opciones del cruce ---
# False = comportamiento de la v2 (solo is_a y part_of); útil para comparar resultados
PROPAGAR_REGULACION = True

# True = solo evidencia experimental; False = cualquier anotación con PMID (más abstracts)
SOLO_EXPERIMENTAL = False
EVIDENCIAS_EXPERIMENTALES = {"EXP", "IDA", "IPI", "IMP", "IGI", "IEP",
                             "HTP", "HDA", "HMP", "HGI", "HEP"}
