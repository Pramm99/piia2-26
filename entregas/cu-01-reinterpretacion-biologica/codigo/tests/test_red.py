"""Spec de ingesta: reintentos con espera exponencial de la sesión HTTP común."""
from urllib3.util.retry import RequestHistory

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
