"""ADR-003: validación de la respuesta del LLM."""
import json

import pytest

from conftest import CITA, respuesta
from consulta_gen.esquema import UMBRAL_VEREDICTO
from consulta_gen.prompt import construir_prompt_lista
from consulta_gen.respuesta import extraer_json, repartir_lista, signo_en_ruta, validar_respuesta


# --- Veredicto, cita y confianza ---
def test_veredicto_con_confianza_suficiente(prompt):
    s = validar_respuesta(prompt, respuesta("INCREASES", UMBRAL_VEREDICTO))
    assert (s["signo"], s["estado"], s["motivos"]) == ("+1", "resuelto", [])
    assert s["rutas"][0]["signo_ruta"] == "+1"


def test_baja_confianza_da_unknown_y_guarda_el_veredicto(prompt):
    s = validar_respuesta(prompt, respuesta("DECREASES", UMBRAL_VEREDICTO - 1, limitacion="speculation_only"))
    assert (s["signo"], s["estado"]) == ("UNKNOWN", "no_concluyente")
    assert s["motivos"] == ["baja_confianza", "especulativo"]
    assert s["signo_llm"] == "-1" and s["rutas"][0]["signo_llm_ruta"] == "-1"


def test_cita_no_verificada(prompt):
    s = validar_respuesta(prompt, respuesta(cita="this sentence is not in the abstract at all"))
    assert s["signo"] == "UNKNOWN" and s["motivos"] == ["cita_no_verificada"] and s["signo_llm"] == "+1"


def test_cita_en_otra_frase_no_vale(prompt):
    s = validar_respuesta(prompt, respuesta(id_frase="S2"))
    assert s["motivos"] == ["cita_no_verificada"]


def test_basta_una_frase_verificada(prompt):
    crudo = json.loads(respuesta())
    crudo["frases"] = [{"id_frase": "S1", "cita": "invented words that are not there ok"}, {"id_frase": "S1", "cita": CITA}]
    s = validar_respuesta(prompt, json.dumps(crudo))
    assert s["signo"] == "+1" and s["cita_verificada"]


def test_limitacion_con_confianza_alta_es_incoherente(prompt):
    s = validar_respuesta(prompt, respuesta(confianza=95, limitacion="marker_or_correlation_only"))
    assert s["signo"] == "+1" and s["estado"] == "revisar"
    assert s["motivos"] == ["incoherencia_respuesta", "marcador_correlacion"]


def test_no_effect_es_neutro_en_todas_las_rutas(prompt):
    s = validar_respuesta(prompt, respuesta("NO_EFFECT", 90))
    assert s["signo"] == "neutro" and s["rutas"][0]["signo_ruta"] == "neutro"


@pytest.mark.parametrize("cambio", [{"confianza": 120}, {"confianza": 72.5}, {"confianza": True},
                                    {"confianza": None}, {"veredicto": "MAYBE"}, {"frases": []}])
def test_formato_invalido(prompt, cambio):
    crudo = {**json.loads(respuesta()), **cambio}
    s = validar_respuesta(prompt, json.dumps(crudo))
    assert s["signo"] == "UNKNOWN" and s["motivos"] == ["json_invalido"]


def test_respuesta_no_interpretable(prompt):
    s = validar_respuesta(prompt, "no hay JSON aquí")
    assert s["motivos"] == ["json_invalido"] and s["error"]


def test_extraer_json_tolera_vallas():
    assert extraer_json('Here:\n```json\n{"a": 1}\n```') == {"a": 1}


def test_gen_y_pmid_salen_de_la_evidencia_no_del_modelo(prompt):
    s = validar_respuesta(prompt, respuesta(gen="OTRO", pmid="999"))
    assert (s["gen"], s["pmid"]) == ("CD7", "1")


# --- Composición del signo hasta la ruta ---
@pytest.mark.parametrize("signo,factor,esperado", [("+1", 1, "+1"), ("+1", -1, "-1"), ("-1", -1, "+1"),
                                                   ("+1", None, "UNKNOWN"), ("neutro", -1, "neutro"),
                                                   ("UNKNOWN", 1, "UNKNOWN")])
def test_signo_en_ruta(signo, factor, esperado):
    assert signo_en_ruta(signo, factor) == esperado


# --- Respuesta en lista (una llamada por gen) ---
def test_repartir_lista(prompt):
    lista = construir_prompt_lista([prompt, prompt])
    texto = json.dumps({"respuestas": [{"q": "Q2. PMID 1", **json.loads(respuesta("DECREASES"))}]})
    q1, q2 = repartir_lista(lista, texto)
    assert q1 is None  # el modelo se la saltó: queda pendiente
    assert json.loads(q2)["veredicto"] == "DECREASES"


def test_repartir_lista_ilegible(prompt):
    assert repartir_lista(construir_prompt_lista([prompt]), "{roto") == [""]
