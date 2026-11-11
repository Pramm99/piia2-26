"""ADR-005: conector común compatible con OpenAI, con HTTP simulado (sin red y sin leer las claves de codigo/.env)."""
import dataclasses

import pytest
import requests

from fase2_inferencia import cliente
from fase2_inferencia.cliente import MODELOS, ClienteOpenAICompatible, ErrorTransitorio


class _Resp:
    def __init__(self, status=200, json_=None, headers=None, text=""):
        self.status_code, self._json, self.headers, self.text = status, json_, headers or {}, text

    def json(self):
        if self._json is None:
            raise ValueError("sin JSON")
        return self._json


def ok(contenido='{"veredicto": "INCREASES"}'):
    return _Resp(json_={"model": "openai/gpt-oss-120b", "system_fingerprint": "fp_1", "usage": {"total_tokens": 9},
                        "choices": [{"message": {"content": contenido}, "finish_reason": "stop"}]})


class _Sesion:
    """Devuelve las respuestas en orden (o lanza la excepción) y guarda lo que se envió."""

    def __init__(self, *respuestas):
        self.respuestas, self.enviados = list(respuestas), []

    def post(self, url, json=None, headers=None, timeout=None):
        self.enviados.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture(autouse=True)
def sin_env(monkeypatch):
    """Ninguna prueba lee codigo/.env: la clave de prueba sale del entorno."""
    monkeypatch.setattr(cliente, "_leer_env", lambda *a: {})
    monkeypatch.setenv("GROQ_API_KEY", "clave-de-prueba")
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")


def conector(nombre, *respuestas, rpm=None):
    esperas = []
    cfg = dataclasses.replace(MODELOS[nombre], rpm=rpm) if rpm else MODELOS[nombre]
    cli = ClienteOpenAICompatible(cfg, sesion=_Sesion(*respuestas), dormir=esperas.append)
    return cli, esperas


def test_peticion_y_respuesta(prompt):
    cli, _ = conector("groq-gpt-oss-120b", ok())
    r = cli.completar(prompt)
    enviado = cli.sesion.enviados[0]
    assert enviado["url"] == MODELOS["groq-gpt-oss-120b"].url
    assert enviado["headers"]["Authorization"] == "Bearer clave-de-prueba"
    p = enviado["json"]
    assert p["model"] == "openai/gpt-oss-120b" and p["temperature"] == 0.0 and p["seed"] == 1234
    assert p["reasoning_effort"] == "low" and p["response_format"]["type"] == "json_schema"
    assert p["messages"] == prompt.como_mensajes()
    assert r.texto == '{"veredicto": "INCREASES"}'
    assert r.meta["fin"] == "stop" and r.meta["tokens"] == {"total_tokens": 9} and cli.llamadas == 1


def test_gemini_sin_seed_ni_temperatura(prompt):
    cli, _ = conector("gemini-3.5-flash-lite", ok())
    cli.completar(prompt)
    p = cli.sesion.enviados[0]["json"]
    assert "seed" not in p and "temperature" not in p and "reasoning_effort" not in p


def test_reintenta_429_con_retry_after_y_5xx_con_espera_exponencial(prompt):
    cli, esperas = conector("groq-gpt-oss-120b", _Resp(429, headers={"retry-after": "3"}), _Resp(503),
                            requests.ConnectionError("caída"), ok(), rpm=10 ** 6)  # sin pausas por ritmo
    assert cli.completar(prompt).texto
    # Retry-After de 3 s; después, espera exponencial 2·2^intento (intentos 1 y 2)
    assert [e for e in esperas if e >= 1] == [3.0, 4.0, 8.0]
    assert len(cli.sesion.enviados) == 4


def test_ritmo_segun_rpm(prompt):
    cli, esperas = conector("groq-gpt-oss-120b", ok(), ok())  # 30 RPM: 2 s entre llamadas
    cli.completar(prompt)
    cli.completar(prompt)
    assert len(esperas) == 1 and 1.9 < esperas[0] <= 2.0


def test_sin_respuesta_tras_los_reintentos_queda_pendiente(prompt):
    cli, _ = conector("groq-gpt-oss-120b", *[_Resp(429, text="rate limit")] * 6)
    with pytest.raises(ErrorTransitorio, match="sin respuesta tras 5 reintentos"):
        cli.completar(prompt)
    assert len(cli.sesion.enviados) == 6


def test_error_de_configuracion_no_se_reintenta(prompt):
    cli, _ = conector("groq-gpt-oss-120b", _Resp(401, json_={"error": {"code": "invalid_api_key"}}, text="no"))
    with pytest.raises(RuntimeError, match="HTTP 401"):
        cli.completar(prompt)
    assert len(cli.sesion.enviados) == 1


def test_json_rechazado_por_el_esquema_es_una_respuesta(prompt):
    fallo = _Resp(400, json_={"error": {"code": "json_validate_failed", "failed_generation": "{roto"}})
    cli, _ = conector("groq-gpt-oss-120b", fallo)
    r = cli.completar(prompt)
    assert r.texto == "{roto" and r.meta["fin"] == "json_validate_failed"
    # un 400 de otro tipo, o sin JSON, es un error de configuración
    for otro in (_Resp(400, json_={"error": {"code": "context_length_exceeded"}}), _Resp(400)):
        cli, _ = conector("groq-gpt-oss-120b", otro)
        with pytest.raises(RuntimeError):
            cli.completar(prompt)


def test_falta_la_clave(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY")
    with pytest.raises(RuntimeError, match="Falta GROQ_API_KEY"):
        ClienteOpenAICompatible(MODELOS["groq-gpt-oss-120b"], sesion=_Sesion())
    ClienteOpenAICompatible(MODELOS["ollama-qwen3-8b"], sesion=_Sesion())  # Ollama no necesita clave


def test_leer_env(tmp_path, monkeypatch):
    monkeypatch.undo()  # vuelve al _leer_env real, solo con un fichero temporal
    f = tmp_path / ".env"
    f.write_text("# comentario\nGROQ_API_KEY='abc'\n\nSIN_IGUAL\n", encoding="utf-8")
    assert cliente._leer_env(f) == {"GROQ_API_KEY": "abc"}
    assert cliente._leer_env(tmp_path / "no_existe") == {}
    assert cliente.clave(None) is None
