"""ADR-004: registro de respuestas y ejecución reanudable, con el cliente simulado (sin red)."""
import json

from conftest import caso, respuesta_v2
from consulta_gen.cliente import ClienteSimulado
from consulta_gen.ejecucion import ejecutar
from consulta_gen.prompt import CONFIG_V2, construir_prompt
from consulta_gen.registro import Registro, clave


def _preguntas():
    return [construir_prompt(caso(pmid=str(i)), CONFIG_V2) for i in (1, 2, 3)]


def _responder(lista):
    """Responde a todas las preguntas de la lista con un +1 verificable."""
    items = [{"q": f"Q{i}", **json.loads(respuesta_v2())} for i in range(1, len(lista.preguntas) + 1)]
    return json.dumps({"respuestas": items})


def test_reanudacion_sin_repetir_llamadas(tmp_path):
    registro = Registro(tmp_path / "respuestas_llm.jsonl")
    cli = ClienteSimulado("sim", _responder)
    resultados, resumen = ejecutar(_preguntas(), [cli], registro, cada=0)
    assert cli.llamadas == 1 and resumen.pendientes == 0  # las 3 preguntas del gen van en una llamada
    assert all(r.salidas["sim"]["signo"] == "+1" for r in resultados)

    lineas = (tmp_path / "respuestas_llm.jsonl").read_text(encoding="utf-8").splitlines()
    llamadas = (tmp_path / "llamadas_llm.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 3 and len(llamadas) == 1
    assert set(json.loads(lineas[0])) == {"clave", "version", "modelo", "fecha", "id_llamada", "q", "huella_prompt",
                                          "respuesta_cruda", "salida"}

    # Segunda ejecución con un registro nuevo sobre el mismo fichero: 0 llamadas
    cli2 = ClienteSimulado("sim", _responder)
    _, resumen2 = ejecutar(_preguntas(), [cli2], Registro(tmp_path / "respuestas_llm.jsonl"), cada=0)
    assert cli2.llamadas == 0 and resumen2.reutilizadas == 3


def test_limite_diario_deja_pendiente_no_unknown(tmp_path):
    cli = ClienteSimulado("sim", _responder, fallar=lambda lista: True)
    resultados, resumen = ejecutar(_preguntas(), [cli], Registro(tmp_path / "r.jsonl"), cada=0)
    assert resumen.pendientes == 3 and resumen.agotados == ["sim"]
    assert all(r.salidas["sim"] is None for r in resultados)


def test_pregunta_saltada_queda_pendiente(tmp_path):
    def solo_la_primera(lista):
        return json.dumps({"respuestas": [{"q": "Q1", **json.loads(respuesta_v2())}]})
    _, resumen = ejecutar(_preguntas(), [ClienteSimulado("sim", solo_la_primera)], Registro(tmp_path / "r.jsonl"),
                          cada=0)
    assert resumen.pendientes == 2


def test_la_huella_cambia_con_el_prompt():
    a, b = construir_prompt(caso(), CONFIG_V2), construir_prompt(caso(frases=("Other text here.",)), CONFIG_V2)
    assert clave(a, "m")[:5] == clave(b, "m")[:5] and clave(a, "m")[5] != clave(b, "m")[5]


def test_linea_cortada_del_registro_se_ignora(tmp_path):
    f = tmp_path / "r.jsonl"
    f.write_text('{"clave": ["v", "g", "p", "go", "m", "h"], "respuesta_cruda": ""}\n{"clave": [', encoding="utf-8")
    assert len(Registro(f)) == 1
