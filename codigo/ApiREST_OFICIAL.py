import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def crear_sesion_segura(email_contacto="pablo.rey.marino@rai.usc.es"):
    """
    Crea una sesión HTTP persistente con User-Agent personalizado
    y política de reintentos automáticos ante errores 429 o 5xx.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": f"GeneOntologyClient/1.0 (Academic Research; mailto:{email_contacto})",
        "Accept": "application/json"
    })

    # Si el servidor está saturado (429 o 50x), reintenta hasta 5 veces
    # esperando 1.5s, 3s, 6s, 12s...
    retries = Retry(
        total=5,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def formatear_enlace_referencia(ref):
    """Convierte un identificador (PMID, GO_REF, Reactome) en su URL directa."""
    if ref.startswith("PMID:"):
        return f"https://pubmed.ncbi.nlm.nih.gov/{ref.split(':')[1]}/"
    elif ref.startswith("GO_REF:"):
        return f"https://geneontology.org/GO_REF/{ref.split(':')[1]}.html"
    elif ref.startswith("Reactome:"):
        return f"https://reactome.org/content/detail/{ref.split(':')[1]}"
    return f"https://amigo.geneontology.org/amigo/reference/{ref}"


def buscar_genes_amigo_batch(lista_genes, organismo="Homo sapiens", tamano_lote=25, pausa_segundos=0.5):
    """
    Busca una lista de genes en AmiGO 2 por lotes para minimizar peticiones,
    extrae el 'Gene/product name' y recopila todos los enlaces de referencia.
    """
    golr_url = "https://golr-aux.geneontology.io/solr/select"
    sesion = crear_sesion_segura()
    resultados_finales = {}

    # Dividir la lista de genes en lotes (por defecto de 25 en 25)
    for i in range(0, len(lista_genes), tamano_lote):
        lote = lista_genes[i:i + tamano_lote]
        query_genes = " OR ".join([f'"{gen}"' for gen in lote])

        # -----------------------------------------------------------------
        # PASO 1: Consulta agrupada de 'bioentity' (1 petición por lote)
        # -----------------------------------------------------------------
        params_bioentity = {
            "q": f"bioentity_label_searchable:({query_genes})",
            "fq": [
                'document_category:"bioentity"',
                f'taxon_subset_closure_label:"{organismo}"'
            ],
            "fl": "bioentity,bioentity_label,bioentity_name,taxon_label,source,panther_family_label",
            "wt": "json",
            "rows": len(lote) * 5  # Margen por si un símbolo tiene varias entradas
        }

        try:
            resp = sesion.get(golr_url, params=params_bioentity, timeout=15)
            resp.raise_for_status()
            docs_bioentity = resp.json().get("response", {}).get("docs", [])
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Fallo al consultar el lote {lote}: {e}")
            continue

        if not docs_bioentity:
            print(f"No se encontraron resultados para el lote: {lote}")
            continue

        # Mapear los IDs internos (ej. UniProtKB:P23771) encontrados en este lote
        mapa_bioentities = {}
        for doc in docs_bioentity:
            bio_id = doc.get("bioentity")
            symbol = doc.get("bioentity_label")
            full_name = doc.get("bioentity_name")

            amigo_link = f"https://amigo.geneontology.org/amigo/gene_product/{bio_id}"
            uniprot_link = (
                f"https://www.uniprot.org/uniprotkb/{bio_id.split(':')[1]}/entry"
                if bio_id and "UniProtKB:" in bio_id else None
            )

            mapa_bioentities[bio_id] = {
                "symbol": symbol,
                "bioentity_id": bio_id,
                "gene_product_name": full_name,
                "amigo_url": amigo_link,
                "uniprot_url": uniprot_link,
                "referencias": set()
            }

        # Pausa de cortesía entre el Paso 1 y el Paso 2
        time.sleep(pausa_segundos)

        # -----------------------------------------------------------------
        # PASO 2: Consulta agrupada de 'annotation' para obtener referencias
        # -----------------------------------------------------------------
        ids_encontrados = list(mapa_bioentities.keys())
        query_ids = " OR ".join([f'"{bid}"' for bid in ids_encontrados])

        params_annotations = {
            "q": "*:*",
            "fq": [
                'document_category:"annotation"',
                f"bioentity:({query_ids})"
            ],
            "fl": "bioentity,reference",
            "wt": "json",
            "rows": 10000  # Suficiente para traer todas las anotaciones del lote
        }

        try:
            resp_ann = sesion.get(golr_url, params=params_annotations, timeout=20)
            resp_ann.raise_for_status()
            docs_ann = resp_ann.json().get("response", {}).get("docs", [])

            for ann in docs_ann:
                b_id = ann.get("bioentity")
                if b_id in mapa_bioentities:
                    for ref in ann.get("reference", []):
                        mapa_bioentities[b_id]["referencias"].add(ref)

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Fallo al obtener referencias del lote {ids_encontrados}: {e}")

        # Formatear y guardar en el diccionario final
        for b_id, datos in mapa_bioentities.items():
            refs_ordenadas = sorted(datos["referencias"])
            datos["referencias"] = [
                {"id": r, "url": formatear_enlace_referencia(r)}
                for r in refs_ordenadas
            ]
            resultados_finales[b_id] = datos

        # Pausa de cortesía antes del siguiente lote
        time.sleep(pausa_segundos)

    return resultados_finales


# =====================================================================
# EJEMPLO DE USO
# =====================================================================
if __name__ == "__main__":
    # Puedes pasar 1 gen o una lista con cientos de ellos
    genes_a_buscar = ["CD7", "KLRC1", "KIR2DL4", "IGLC2", "IL2RB", "FES", "IGKC", "FCER1G", "IGHG3", "GATA3", "IGHG4", "IGHG1", "IRF7", "CRTAM", "IGLC3", "BST2", "CD96", "XCL1", "IL4R", "IGHA1", "LAT2", "LGALS9", "KLRC2", "HLA-DRA", "NFKBIZ", "ICAM1"]
    
    datos_genes = buscar_genes_amigo_batch(
        lista_genes=genes_a_buscar,
        organismo="Homo sapiens",
        tamano_lote=25,      # Procesa de 25 en 25 genes por petición
        pausa_segundos=0.5   # 0.5s entre peticiones (máximo 2 req/segundo)
    )

    for bio_id, info in datos_genes.items():
        print("=" * 75)
        print(f"Gen / Producto : {info['symbol']} ({info['bioentity_id']})")
        print(f"Nombre completo: {info['gene_product_name']}")
        print(f"Ficha AmiGO    : {info['amigo_url']}")
        if info["uniprot_url"]:
            print(f"Ficha UniProt  : {info['uniprot_url']}")
        
        print(f"\nDocumentos de referencia ({len(info['referencias'])}):")
        for ref in info["referencias"]:
            print(f"  - {ref['id']:<18} -> {ref['url']}")