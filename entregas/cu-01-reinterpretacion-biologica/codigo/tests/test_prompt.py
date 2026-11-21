"""Spec de inferencia: contenido del prompt, orden del JSON, núcleo y polaridad, composición y troceo por gen."""
import re

import pytest

from conftest import FRASE, caso, respuesta
from fase2_inferencia import proceso
from fase2_inferencia.esquema import ESQUEMA_LISTA, UMBRAL_VEREDICTO
from fase2_inferencia.prompt import construir_prompt, construir_prompt_lista, tokens_estimados, trocear_por_gen
from fase2_inferencia.respuesta import validar_respuesta
from test_resultados import _fila_ruta

OBO = """format-version: 1.2

[Term]
id: GO:0000001
name: T cell proliferation

[Term]
id: GO:0000002
name: negative regulation of T cell proliferation
relationship: negatively_regulates GO:0000001

[Term]
id: GO:0000003
name: T cell activation

[Term]
id: GO:0000004
name: regulation of T cell activation
relationship: regulates GO:0000003

[Term]
id: GO:0000010
name: leukocyte mediated immunity

[Term]
id: GO:0000012
name: immune effector process

[Term]
id: GO:0000011
name: natural killer cell mediated cytotoxicity
is_a: GO:0000010
is_a: GO:0000012

[Term]
id: GO:0000013
name: regulation of immune effector process
relationship: regulates GO:0000012
"""


@pytest.fixture
def ontologia(tmp_path, monkeypatch):
    obo = tmp_path / "go-basic.obo"
    obo.write_text(OBO, encoding="utf-8")
    monkeypatch.setattr(proceso, "OBO_FILE", str(obo))
    proceso._ontologia.cache_clear()
    proceso._desc.cache_clear()
    yield
    proceso._ontologia.cache_clear()
    proceso._desc.cache_clear()


def test_contenido_del_prompt():
    """Ni la lista de CIMUS (dirección del gen), ni la polaridad de GO, ni el tumor, ni el umbral; el abstract
    entero en frases numeradas."""
    frases = (FRASE, "A second sentence closes the abstract.")
    lista = construir_prompt_lista([construir_prompt(caso(frases=frases))])
    texto = lista.system + "\n" + lista.user
    for prohibido in (r"\bActivada\b", r"\bSuprimida\b", r"\bUP\b", r"\bDOWN\b", r"Polaridad", r"\bHNSC\b",
                      rf"\b{UMBRAL_VEREDICTO}\b"):
        assert not re.search(prohibido, texto), prohibido
    assert f"[S1] {frases[0]}" in lista.user and f"[S2] {frases[1]}" in lista.user


def test_orden_del_json_y_campos_en_el_prompt():
    """Las frases (cita) y el razonamiento van antes que la confianza y el veredicto, y el prompt los enumera."""
    campos = list(ESQUEMA_LISTA["properties"]["respuestas"]["items"]["properties"])
    assert campos.index("frases") < campos.index("razonamiento_corto") < campos.index("confianza") \
        < campos.index("veredicto")
    system = construir_prompt(caso()).system
    assert all(f'"{c}"' in system for c in campos)


def test_nucleo_y_polaridad(ontologia):
    assert proceso.nucleo_y_polaridad("GO:0000002") == ("GO:0000001", -1)
    assert proceso.nucleo_y_polaridad("GO:0000004") == ("GO:0000003", 1)  # sin dirección: como el proceso


def test_composicion(ontologia):
    """Un DECREASES sobre la citotoxicidad NK da −1 en la ruta que la contiene y en «regulation of immune
    effector process», tratada como el proceso."""
    rutas = []
    for ruta in ("GO:0000010", "GO:0000013"):
        nucleo, pol = proceso.nucleo_y_polaridad(ruta)
        rutas.append((ruta, proceso.nombre(ruta), proceso.signo_camino("GO:0000011", nucleo) * pol))
    s = validar_respuesta(construir_prompt(caso(rutas=tuple(rutas))), respuesta("DECREASES", 90))
    assert [r["signo_ruta"] for r in s["rutas"]] == ["-1", "-1"]


def test_troceo_por_presupuesto():
    """Las preguntas de un gen van juntas mientras caben en el presupuesto; si no, en varias llamadas, en orden y
    sin perder ninguna. Cada gen va en sus propias llamadas."""
    preguntas = [construir_prompt(caso(pmid=str(i))) for i in range(1, 7)] + [construir_prompt(caso(gen="CD8A"))]
    juntas = trocear_por_gen(preguntas, 10 ** 6)
    assert [len(l.preguntas) for l in juntas] == [6, 1]
    una = tokens_estimados(construir_prompt_lista(preguntas[:1]))
    partidas = trocear_por_gen(preguntas, una + 800)
    assert len(partidas) > 2 and all(tokens_estimados(l) <= una + 800 for l in partidas)
    assert sorted(p.evidencia.pmid for l in partidas for p in l.preguntas if p.gen == "CD7") == \
        [str(i) for i in range(1, 7)]


def test_sin_cita_verificada_no_vale_coincidir_con_go(prompt):
    f = _fila_ruta(prompt, "+1", respuesta("INCREASES", 30, cita="this sentence is not in the abstract at all"))
    assert f.Signo_ruta == "UNKNOWN" and "coincide_polaridad_GO" not in f.Motivos
