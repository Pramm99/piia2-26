"""Fase 4: el puente sirve la interfaz ya construida (fase4_frontend/dist), para el programa de escritorio. Sin red."""
import importlib
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest


@pytest.fixture
def servidor(tmp_path, monkeypatch):
    mod = importlib.import_module("fase4_frontend.api_puente")
    web = tmp_path / "dist"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<title>CU-01 PathScore Studio</title>", encoding="utf-8")
    (web / "assets" / "app-1a2b.js").write_text("console.log(1)", encoding="utf-8")
    (web / "assets" / "notas.md").write_text("no se sirve", encoding="utf-8")
    (tmp_path / "secreto.txt").write_text("fuera de dist", encoding="utf-8")
    monkeypatch.setattr(mod, "DIR_WEB", web)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), mod.ManejadorPuente)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield mod, web, f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _get(url):
    try:
        with urllib.request.urlopen(url) as r:
            return r.status, r.headers.get("Content-Type"), r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, None, ""


def test_sirve_la_interfaz_construida(servidor):
    _, _, base = servidor
    codigo, tipo, cuerpo = _get(base + "/")
    assert codigo == 200 and tipo.startswith("text/html") and "PathScore" in cuerpo
    codigo, tipo, _ = _get(base + "/assets/app-1a2b.js")
    assert codigo == 200 and tipo == "text/javascript"  # ni text/plain (registro de Windows) ni «; charset» (Avast)
    # Las rutas de la API siguen igual
    assert _get(base + "/salud")[:2] == (200, "application/json")


@pytest.mark.parametrize("ruta", ["/no-existe.js", "/assets/notas.md", "/../secreto.txt", "/%2e%2e/secreto.txt",
                                  "/assets/..%2f..%2fsecreto.txt"])
def test_no_sirve_nada_fuera_de_la_interfaz(servidor, ruta):
    _, _, base = servidor
    assert _get(base + ruta)[0] == 404


def test_sin_interfaz_construida_da_404(servidor, monkeypatch, tmp_path):
    mod, _, base = servidor
    monkeypatch.setattr(mod, "DIR_WEB", tmp_path / "no_hay_dist")
    assert _get(base + "/")[0] == 404


def test_comprime_si_el_navegador_lo_acepta(servidor):
    import gzip
    _, web, base = servidor
    req = urllib.request.Request(base + "/assets/app-1a2b.js", headers={"Accept-Encoding": "gzip, br"})
    with urllib.request.urlopen(req) as r:
        assert r.headers.get("Content-Encoding") == "gzip"
        assert gzip.decompress(r.read()) == (web / "assets" / "app-1a2b.js").read_bytes()
    with urllib.request.urlopen(base + "/assets/app-1a2b.js") as r:  # sin Accept-Encoding, tal cual
        assert r.headers.get("Content-Encoding") is None and r.read() == b"console.log(1)"


def test_solo_lo_de_assets_se_guarda_para_siempre(servidor):
    _, web, base = servidor
    (web / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")
    for ruta, cache in (("/assets/app-1a2b.js", "max-age=31536000, immutable"), ("/", "no-cache"),
                        ("/favicon.ico", "no-cache")):
        with urllib.request.urlopen(base + ruta) as r:
            assert r.headers.get("Cache-Control") == cache, ruta
