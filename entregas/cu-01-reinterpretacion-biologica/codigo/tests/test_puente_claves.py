"""Fase 4: claves del LLM desde la interfaz (⚙ → token-api). Sin red y con un .env temporal, nunca codigo/.env."""
import importlib
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from fase2_inferencia import cliente

GEMINI = "AIzaSyA" + "x" * 32
GEMINI_2 = "AIzaSyB" + "y" * 32
GROQ = "gsk_" + "z" * 40


@pytest.fixture
def puente(tmp_path, monkeypatch):
    """api_puente con FICHERO_ENV apuntando a un .env temporal y sin las variables de entorno de las claves."""
    env = tmp_path / ".env"
    env.write_text("# comentario\nNCBI_EMAIL=a@b.c\nGEMINI_API_KEY=\nGROQ_API_KEY=\n", encoding="utf-8")
    monkeypatch.setattr(cliente, "FICHERO_ENV", env)
    for var in ("GEMINI_API_KEY", "GROQ_API_KEY", "NCBI_API_KEY", "NCBI_EMAIL"):
        monkeypatch.delenv(var, raising=False)
    mod = importlib.import_module("fase4_frontend.api_puente")
    return mod, env


def _leer(ruta):
    pares = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if linea.strip() and not linea.startswith("#") and "=" in linea:
            k, v = linea.split("=", 1)
            pares[k.strip()] = v.strip()
    return pares


def test_guardar_claves_respeta_el_resto_del_env(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# c\nNCBI_EMAIL=a@b.c\nGEMINI_API_KEY=viejo\nGEMINI_API_KEY=repetida\n", encoding="utf-8")
    cliente.guardar_claves("GEMINI_API_KEY", ["k1", "k2"], env)
    assert env.read_text(encoding="utf-8") == "# c\nNCBI_EMAIL=a@b.c\nGEMINI_API_KEY=k1,k2\n"
    cliente.guardar_claves("GROQ_API_KEY", ["g1"], env)  # si no estaba, va al final
    assert env.read_text(encoding="utf-8").endswith("GEMINI_API_KEY=k1,k2\nGROQ_API_KEY=g1\n")
    nuevo = tmp_path / "no_existe" / ".env"
    nuevo.parent.mkdir()
    cliente.guardar_claves("GROQ_API_KEY", [], nuevo)
    assert nuevo.read_bytes() == b"GROQ_API_KEY=\n"
    # Los saltos de línea del fichero se respetan byte a byte (en Windows, write_text los pasaría a CRLF)
    env.write_bytes(b"# c\nGEMINI_API_KEY=k1\n")
    cliente.guardar_claves("GEMINI_API_KEY", ["k1"], env)
    assert env.read_bytes() == b"# c\nGEMINI_API_KEY=k1\n"
    env.write_bytes(b"# c\r\nGEMINI_API_KEY=k1\r\n")
    cliente.guardar_claves("GEMINI_API_KEY", ["k1", "k2"], env)
    assert env.read_bytes() == b"# c\r\nGEMINI_API_KEY=k1,k2\r\n"


def test_anadir_y_quitar_claves(puente):
    mod, env = puente
    mod.cambiar_claves({"proveedor": "gemini", "accion": "anadir", "clave": GEMINI})
    estado = mod.cambiar_claves({"proveedor": "gemini", "accion": "anadir", "clave": f"  {GEMINI_2} "})
    gemini = next(p for p in estado if p["id"] == "gemini")
    assert gemini["claves"] == ["AIza…xxxx", "AIza…yyyy"] and gemini["papel"] == "principal"
    assert _leer(env)["GEMINI_API_KEY"] == f"{GEMINI},{GEMINI_2}" and _leer(env)["NCBI_EMAIL"] == "a@b.c"
    assert cliente.claves("GEMINI_API_KEY") == [GEMINI, GEMINI_2]  # el orden es el de uso
    # Ninguna respuesta lleva una clave entera
    assert GEMINI not in json.dumps(estado) and GEMINI_2 not in json.dumps(estado)

    estado = mod.cambiar_claves({"proveedor": "gemini", "accion": "quitar", "indice": 0})
    assert next(p for p in estado if p["id"] == "gemini")["claves"] == ["AIza…yyyy"]
    mod.cambiar_claves({"proveedor": "groq", "accion": "anadir", "clave": GROQ})
    assert _leer(env)["GROQ_API_KEY"] == GROQ


@pytest.mark.parametrize("datos, error", [
    ({"proveedor": "openai", "accion": "anadir", "clave": GEMINI}, "Proveedor no válido"),
    ({"proveedor": "gemini", "accion": "anadir", "clave": "corta"}, "No parece una clave"),
    ({"proveedor": "gemini", "accion": "anadir", "clave": f"{GEMINI},{GEMINI_2}"}, "No parece una clave"),
    ({"proveedor": "gemini", "accion": "anadir", "clave": GROQ}, "Parece una clave de Groq"),
    ({"proveedor": "groq", "accion": "anadir", "clave": GEMINI}, "Parece una clave de Gemini"),
    ({"proveedor": "gemini", "accion": "quitar", "indice": 3}, "No existe esa clave"),
    ({"proveedor": "gemini", "accion": "borrar_todo"}, "Acción no válida"),
])
def test_peticiones_no_validas(puente, datos, error):
    mod, env = puente
    antes = env.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match=error) as e:
        mod.cambiar_claves(datos)
    assert GEMINI not in str(e.value) and GROQ not in str(e.value)
    assert env.read_text(encoding="utf-8") == antes


def test_clave_repetida_y_variable_de_entorno(puente, monkeypatch):
    mod, _ = puente
    mod.cambiar_claves({"proveedor": "gemini", "accion": "anadir", "clave": GEMINI})
    with pytest.raises(ValueError, match="ya está"):
        mod.cambiar_claves({"proveedor": "gemini", "accion": "anadir", "clave": GEMINI})
    monkeypatch.setenv("GROQ_API_KEY", GROQ)  # la del sistema manda sobre .env: no se puede tocar desde aquí
    with pytest.raises(ValueError, match="variables de entorno del sistema"):
        mod.cambiar_claves({"proveedor": "groq", "accion": "anadir", "clave": "gsk_" + "w" * 40})
    assert next(p for p in mod.estado_claves() if p["id"] == "groq")["de_entorno"] is True


NCBI = "0123456789abcdef0123456789abcdef0123"


def test_clave_y_correo_de_ncbi(puente, monkeypatch):
    """NCBI (Fase 1) tiene una sola clave y un correo: se guardan, se sustituyen y se quitan sin tocar el resto."""
    mod, env = puente
    assert mod.estado_ncbi() == {"clave": None, "email": "a@b.c", "clave_de_entorno": False, "email_de_entorno": False}
    mod.cambiar_claves({"proveedor": "ncbi", "accion": "guardar", "campo": "clave", "valor": f" {NCBI} "})
    mod.cambiar_ncbi({"accion": "guardar", "campo": "email", "valor": "yo@ejemplo.org"})
    estado = mod.estado_ncbi()
    assert estado["clave"] == "0123…0123" and estado["email"] == "yo@ejemplo.org" and NCBI not in json.dumps(estado)
    assert _leer(env)["NCBI_API_KEY"] == NCBI and _leer(env)["NCBI_EMAIL"] == "yo@ejemplo.org"
    assert _leer(env)["GEMINI_API_KEY"] == ""
    # La Fase 1 lo lee en el momento, sin reiniciar el puente
    import config as f1_config
    leer = f1_config._leer_env
    monkeypatch.setattr(f1_config, "_leer_env", lambda ruta=None: leer(str(env)))
    assert f1_config.ncbi() == ("yo@ejemplo.org", NCBI)
    mod.cambiar_ncbi({"accion": "quitar", "campo": "clave"})
    assert mod.estado_ncbi()["clave"] is None and _leer(env)["NCBI_API_KEY"] == ""


@pytest.mark.parametrize("datos, error", [
    ({"accion": "guardar", "campo": "clave", "valor": "AIzaSyA" + "x" * 32}, "No parece una clave de NCBI"),
    ({"accion": "guardar", "campo": "email", "valor": "sin-arroba"}, "No parece un correo"),
    ({"accion": "guardar", "campo": "otro", "valor": "x"}, "Campo no válido"),
    ({"accion": "borrar_todo", "campo": "clave"}, "Acción no válida"),
])
def test_ncbi_no_valido(puente, datos, error):
    mod, env = puente
    antes = env.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        mod.cambiar_ncbi(datos)
    assert env.read_text(encoding="utf-8") == antes


def test_otra_web_no_puede_tocar_las_claves(puente):
    """Por HTTP: desde localhost (la interfaz de Vite) sí; con el Origin de otra web, 403 y sin cambios."""
    mod, env = puente
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), mod.ManejadorPuente)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{servidor.server_address[1]}/claves"

    def pedir(origen, cuerpo=None):
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        req = urllib.request.Request(url, data=datos, headers={"Origin": origen, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    try:
        alta = {"proveedor": "gemini", "accion": "anadir", "clave": GEMINI}
        assert pedir("https://otra-web.example", alta)[0] == 403
        assert pedir("https://otra-web.example")[0] == 403
        assert "GEMINI_API_KEY=\n" in env.read_text(encoding="utf-8")
        codigo, d = pedir("http://localhost:5173", alta)
        assert codigo == 200 and d["ok"] and d["proveedores"][0]["claves"] == ["AIza…xxxx"]
        codigo, d = pedir("http://localhost:5173")
        assert codigo == 200 and GEMINI not in json.dumps(d)
        assert pedir("http://localhost:5173", {"proveedor": "gemini", "accion": "quitar", "indice": "0"})[0] == 400
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_aviso_de_la_fase2(puente, tmp_path, monkeypatch):
    """El puente cuenta como pendientes solo las preguntas sin ninguna respuesta (no las del principal que ya
    respondió el respaldo) y pasa por qué se detuvo cada proveedor. Sin llamar al LLM ni tocar el registro."""
    import pandas as pd
    from fase2_inferencia.ejecucion import Resumen
    mod, _ = puente
    resumen = Resumen(pendientes=3, motivos={"gemini-3.5-flash-lite": "cupo", "groq-gpt-oss-120b": "cupo"})
    preguntas = pd.DataFrame({"Estado": ["resuelto", "pendiente", "resuelto"]})
    monkeypatch.setattr(mod, "ejecutar_fase2", lambda *a, **k: (preguntas, pd.DataFrame(), resumen, {}))
    _, llm = mod._fase2(tmp_path, tmp_path / "fase1.xlsx")
    assert llm["pendientes"] == 1 and llm["agotados"] == {"gemini": "cupo", "groq": "cupo"}
