"""Utilidades de red: sesión con reintentos, descarga atómica de ficheros y aviso de progreso."""
import os
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def configurar_sesion():
    s = requests.Session()
    retries = Retry(
        total=5, backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST"]),  # también POST: las peticiones a NCBI lo son
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


def _mmss(segundos):
    m, s = divmod(int(segundos), 60)
    return f"{m} min {s:02d} s"


class Progreso:
    """Avisa del avance de una descarga larga (porcentaje, tiempo transcurrido y lo que falta), para que no
    parezca colgada. Avisa al cruzar cada `paso` % y como mucho una vez cada `cada_s` segundos: una descarga
    corta no escribe nada."""

    def __init__(self, etiqueta, total, paso=5, cada_s=10):
        self.etiqueta, self.total, self.paso, self.cada_s = etiqueta, total, paso, cada_s
        self.inicio = self._ultimo = time.monotonic()
        self._siguiente, self._avisado = paso, False

    def avanzar(self, hechos):
        ahora = time.monotonic()
        pct = 100 * hechos / self.total if self.total else 100
        fin = hechos >= self.total
        if fin and not self._avisado:
            return
        if not fin and (pct < self._siguiente or ahora - self._ultimo < self.cada_s):
            return
        while self._siguiente <= pct:
            self._siguiente += self.paso
        self._ultimo, self._avisado = ahora, True
        t = ahora - self.inicio
        resto = "" if fin else f" · quedan ~{_mmss(t * (self.total - hechos) / hechos)}"
        print(f"   ⏳ {self.etiqueta}: {hechos}/{self.total} ({pct:.0f} %) · {_mmss(t)}{resto}")
