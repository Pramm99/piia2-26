"""ADR-003: validación de la respuesta del LLM (v2_veredicto en producción y v1_proceso_gen en el benchmark)."""
import json

import pytest

from conftest import CITA, respuesta_v1, respuesta_v2
from consulta_gen.esquema import UMBRAL_VEREDICTO
from consulta_gen.prompt import construir_prompt_lista
from consulta_gen.respuesta import extraer_json, repartir_lista, signo_en_ruta, validar_respuesta


# --- v2_veredicto ---
def test_v2_veredicto_con_confianza_suficiente(prompt_v2):
    s = validar_respuesta(prompt_v2, respuesta_v2("INCREASES", UMBRAL_VEREDICTO))
    assert (s["signo"], s["estado"], s["motivos"]) == ("+1", "resuelto", [])
    assert s["rutas"][0]["signo_ruta"] == "+1"


def test_v2_baja_confianza_da_unknown_y_guarda_el_veredicto(prompt_v2):
    s = validar_respuesta(prompt_v2, respuesta_v2("DECREASES", UMBRAL_VEREDICTO - 1, limitacion="speculation_only"))
    assert (s["signo"], s["estado"]) == ("UNKNOWN", "no_concluyente")
    assert s["motivos"] == ["baja_confianza", "especulativo"]
    assert s["signo_llm"] == "-1" and s["rutas"][0]["signo_llm_ruta"] == "-1"


def test_v2_cita_no_verificada(prompt_v2):
    s = validar_respuesta(prompt_v2, respuesta_v2(cita="this sentence is not in the abstract at all"))
    assert s["signo"] == "UNKNOWN" and s["motivos"] == ["cita_no_verificada"] and s["signo_llm"] == "+1"


def test_v2_cita_en_otra_frase_no_vale(prompt_v2):
    s = validar_respuesta(prompt_v2, respuesta_v2(id_frase="S2"))
    assert s["motivos"] == ["cita_no_verificada"]


def test_v2_basta_una_frase_verificada(prompt_v2):
    crudo = json.loads(respuesta_v2())
    crudo["frases"] = [{"id_frase": "S1", "cita": "invented words that are not there ok"}, {"id_frase": "S1", "cita": CITA}]
    s = validar_respuesta(prompt_v2, json.dumps(crudo))
    assert s["signo"] == "+1" and s["cita_verificada"]


def test_v2_limitacion_con_confianza_alta_es_incoherente(prompt_v2):
    s = validar_respuesta(prompt_v2, respuesta_v2(confianza=95, limitacion="marker_or_correlation_only"))
    assert s["signo"] == "+1" and s["estado"] == "revisar"
    assert s["motivos"] == ["incoherencia_respuesta", "marcador_correlacion"]


def test_v2_no_effect_es_neutro_en_todas_las_rutas(prompt_v2):
    s = validar_respuesta(prompt_v2, respuesta_v2("NO_EFFECT", 90))
    assert s["signo"] == "neutro" and s["rutas"][0]["signo_ruta"] == "neutro"


@pytest.mark.parametrize("cambio", [{"confianza": 120}, {"confianza": 72.5}, {"confianza": True},
                                    {"confianza": None}, {"veredicto": "MAYBE"}, {"frases": []}])
def test_v2_formato_invalido(prompt_v2, cambio):
    crudo = {**json.loads(respuesta_v2()), **cambio}
    s = validar_respuesta(prompt_v2, json.dumps(crudo))
    assert s["signo"] == "UNKNOWN" and s["motivos"] == ["json_invalido"]


def test_v2_respuesta_no_interpretable(prompt_v2):
    s = validar_respuesta(prompt_v2, "no hay JSON aquí")
    assert s["motivos"] == ["json_invalido"] and s["error"]


def test_extraer_json_tolera_vallas():
    assert extraer_json('Here:\n```json\n{"a": 1}\n```') == {"a": 1}


def test_gen_y_pmid_salen_de_la_evidencia_no_del_modelo(prompt_v2):
    s = validar_respuesta(prompt_v2, respuesta_v2(gen="OTRO", pmid="999"))
    assert (s["gen"], s["pmid"]) == ("CD7", "1")


# --- Composición del signo hasta la ruta ---
@pytest.mark.parametrize("signo,factor,esperado", [("+1", 1, "+1"), ("+1", -1, "-1"), ("-1", -1, "+1"),
                                                   ("+1", None, "UNKNOWN"), ("neutro", -1, "neutro"),
                                                   ("UNKNOWN", 1, "UNKNOWN")])
def test_signo_en_ruta(signo, factor, esperado):
    assert signo_en_ruta(signo, factor) == esperado


# --- v1_proceso_gen (benchmark) ---
def test_v1_signo_con_confianza_media_pasa_a_revisar(prompt_v1):
    s = validar_respuesta(prompt_v1, respuesta_v1("INCREASES", confianza=60))
    assert (s["signo"], s["estado"], s["motivos"]) == ("+1", "revisar", ["baja_confianza"])


def test_v1_abstencion_con_motivo(prompt_v1):
    s = validar_respuesta(prompt_v1, respuesta_v1("NO_CLEAR_EFFECT", "gene_is_the_target", confianza=20))
    assert (s["signo"], s["estado"], s["motivos"]) == ("UNKNOWN", "no_concluyente", ["direccion_inversa"])


def test_v1_signo_con_motivo_es_incoherente(prompt_v1):
    s = validar_respuesta(prompt_v1, respuesta_v1("INCREASES", "speculation_only"))
    assert "incoherencia_respuesta" in s["motivos"] and s["estado"] == "revisar"


# --- Respuesta en lista (una llamada por gen) ---
def test_repartir_lista(prompt_v2):
    lista = construir_prompt_lista([prompt_v2, prompt_v2])
    texto = json.dumps({"respuestas": [{"q": "Q2. PMID 1", **json.loads(respuesta_v2("DECREASES"))}]})
    q1, q2 = repartir_lista(lista, texto)
    assert q1 is None  # el modelo se la saltó: queda pendiente
    assert json.loads(q2)["veredicto"] == "DECREASES"


def test_repartir_lista_ilegible(prompt_v2):
    assert repartir_lista(construir_prompt_lista([prompt_v2]), "{roto") == [""]
