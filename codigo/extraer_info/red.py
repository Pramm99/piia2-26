"""Utilidades de red: sesión con reintentos y descarga atómica de ficheros."""
import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def configurar_sesion():
    s = requests.Session()
    retries = Retry(
        total=5, backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST"]),  # la v1 no reintentaba POST
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s


def descargar_archivo(url, destino):
    """Descarga atómica: si se corta, no queda un archivo corrupto dando falsos positivos."""
    if os.path.exists(destino):
        return
    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
    print(f"📥 Descargando {url} ...")
    tmp = destino + ".tmp"
    with requests.get(url, stream=True, timeout=(15, 120)) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
    os.replace(tmp, destino)
