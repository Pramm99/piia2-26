"""Spec de ingesta: reintentos con espera exponencial de la sesión HTTP común."""
from urllib3.util.retry import RequestHistory

import red
from red import configurar_sesion


def test_reintentos_con_espera_exponencial():
    r = configurar_sesion().get_adapter("https://www.ebi.ac.uk").max_retries
    assert r.total == 5 and r.backoff_factor == 1
    assert set(r.status_forcelist) == {429, 500, 502, 503, 504}
    assert {"GET", "POST"} <= set(r.allowed_methods)
    assert r.respect_retry_after_header

    fallo = RequestHistory("GET", "https://www.ebi.ac.uk", None, 503, None)
    esperas = [r.new(history=(fallo,) * n).get_backoff_time() for n in range(1, 6)]
    assert esperas == [0, 2, 4, 8, 16]


class _Descarga:
    def __init__(self, trozos):
        self.trozos = trozos

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield from self.trozos


def test_descarga_atomica_y_una_sola_vez(tmp_path, monkeypatch):
    urls = []
    monkeypatch.setattr(red.requests, "get", lambda url, **k: urls.append(url) or _Descarga([b"ab", b"cd"]))
    destino = tmp_path / "sub" / "go-basic.obo"
    red.descargar_archivo("https://ejemplo/go-basic.obo", str(destino))
    assert destino.read_bytes() == b"abcd" and not (tmp_path / "sub" / "go-basic.obo.tmp").exists()
    red.descargar_archivo("https://ejemplo/go-basic.obo", str(destino))  # ya existe: no se descarga otra vez
    assert urls == ["https://ejemplo/go-basic.obo"]


def test_descarga_cortada_no_deja_fichero(tmp_path, monkeypatch):
    class _Cortada(_Descarga):
        def iter_content(self, chunk_size):
            yield b"medio"
            raise ConnectionError("cortada")

    monkeypatch.setattr(red.requests, "get", lambda url, **k: _Cortada([]))
    destino = tmp_path / "goa_human.gaf.gz"
    try:
        red.descargar_archivo("https://ejemplo/goa", str(destino))
    except ConnectionError:
        pass
    assert not destino.exists()  # solo queda el .tmp, que la siguiente ejecución sobrescribe
