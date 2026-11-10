"""Spec de limpieza: sanitización conservadora, forma de comparación, verificación de la cita y mención del gen."""
import pytest

from abstracts import limpiar_texto
from consulta_gen.limpieza import forma_comparacion, limpiar_abstract, normalizar_pmid, segmentar_frases
from consulta_gen.respuesta import verificar_cita
from relevancia import menciona_gen, patron_gen

ABSTRACT = ("Human K12-Fc stimulated the up-regulation of CD25, CD54, and CD69 on human NK cells. "
            "NF-κB activation required IL-4Rα and CD70 binding.")


# --- Sanitización conservadora (limpiar_texto) ---
def test_etiquetas_de_bloque_dejan_un_espacio():
    assert limpiar_texto("<p>foo</p><p>bar</p>") == "foo bar"


def test_fin_de_titulo_no_pega_el_rotulo():
    assert limpiar_texto("<h4>Conclusion</h4>DOT1L") == "Conclusion: DOT1L"


def test_etiquetas_de_linea_no_parten_el_nombre():
    assert limpiar_texto("IL-1<sup>β</sup> and <i>CD8</i>") == "IL-1β and CD8"


def test_entidades_y_etiquetas_escapadas():
    assert limpiar_texto("A &amp; B") == "A & B"
    assert limpiar_texto("CD8&lt;sup&gt;+&lt;/sup&gt; cells") == "CD8+ cells"


def test_no_borra_el_texto_entre_menor_y_mayor():
    t = limpiar_texto("p < 0.05 in tumours (<20%) and > 3 fold")
    assert "p < 0.05" in t and "(<20%)" in t and "> 3 fold" in t


@pytest.mark.parametrize("nombre", ["NF-κB", "TGF-β", "CD8+", "HLA-A", "IL-2R", "miR-155", "STAT3", "p53"])
def test_nomenclatura_intacta(nombre):
    assert limpiar_texto(f"<p>{nombre}</p>") == nombre


def test_limpiar_texto_es_idempotente():
    t = limpiar_texto("<h4>Results</h4><p>IL-1<sup>β</sup> &amp; NF-κB</p>")
    assert limpiar_texto(t) == t


def test_valores_vacios_del_excel():
    assert limpiar_abstract(None) == ""
    assert limpiar_abstract(float("nan")) == ""
    assert normalizar_pmid(12345678.0) == "12345678"


# --- Forma de comparación ---
def test_forma_comparacion():
    assert forma_comparacion("NF-κB – IL-4Rα, µM") == "nf kappab il 4ralpha mum"


# --- Verificación de la cita ---
@pytest.mark.parametrize("cita", [
    "human k12-fc stimulated the up-regulation of CD25",       # mayúsculas
    "Human K12 Fc stimulated the up-regulation of CD25",       # guion por espacio
    "Human K12–Fc stimulated the up-regulation of CD25",       # otro tipo de guion
    "NF-kappaB activation required IL-4Ralpha and CD70 binding",  # griegas escritas
    "up-regulation of CD25 CD54 and CD69 on human",            # coma omitida
])
def test_cita_tolerante(cita):
    assert verificar_cita(cita, ABSTRACT)


@pytest.mark.parametrize("cita", [
    "K12-Fc increased CD25 and CD69 on NK cells",  # paráfrasis
    "CD7",                                         # menos de 6 palabras
    "Human K12Fc stimulated the up-regulation of CD25",  # guion suprimido sin espacio
])
def test_cita_rechazada(cita):
    assert not verificar_cita(cita, ABSTRACT)


# --- Frases numeradas ---
def test_segmentar_frases_respeta_abreviaturas_y_decimales():
    frases = segmentar_frases("NK cells rose 2.5 fold. Then CD7 fell, e.g. in mice. End.")
    assert frases == ["NK cells rose 2.5 fold.", "Then CD7 fell, e.g. in mice.", "End."]


def test_segmentar_frases_no_corta_tras_et_al():
    assert segmentar_frases("As shown by Smith et al. NK cells rose. End.") == ["As shown by Smith et al. NK cells rose.",
                                                                                 "End."]


# --- Mención del gen ---
def test_mencion_por_palabra_completa():
    p = patron_gen("CD7")
    assert not menciona_gen("binding of CD70 to cells", p)
    assert menciona_gen("expression of CD-7 on T cells", p)
    assert not menciona_gen("expression of cd7 on T cells", p)  # todo en minúsculas no cuenta


def test_mencion_por_alias_y_nombre_completo():
    p = patron_gen("TNFRSF10A", alias=("DR4",), nombre="TNF receptor superfamily member 10a")
    assert menciona_gen("DR4 triggers apoptosis", p)
    assert menciona_gen("the TNF receptor superfamily member 10a was cleaved", p)
