"""ADR-003: contraste entre modelos y con Gene Ontology, y porcentaje final (confianza_final)."""
from conftest import caso, hoja_fase1, respuesta
from fase2_inferencia.confianza import confianza_final
from fase2_inferencia.ejecucion import ResultadoCaso
from fase2_inferencia.respuesta import validar_respuesta
from fase2_inferencia.resultados import contrastar, tablas


def _fila_ruta(prompt, polaridad, principal_txt, secundario_txt=None):
    salidas = {"principal": validar_respuesta(prompt, principal_txt)}
    if secundario_txt is not None:
        salidas["secundario"] = validar_respuesta(prompt, secundario_txt)
    _, por_ruta = tablas([ResultadoCaso(prompt, salidas)], "principal",
                         "secundario" if secundario_txt is not None else None, [], hoja_fase1(polaridad))
    return por_ruta.iloc[0]


# --- Contraste con Gene Ontology ---
def test_coincide_con_go_se_acepta_aunque_la_confianza_sea_baja(prompt):
    f = _fila_ruta(prompt, "+1", respuesta("INCREASES", 30))
    assert (f.Signo_ruta, f.Estado, f.Motivos) == ("+1", "resuelto", "coincide_polaridad_GO")
    # Antes salía vacía: ahora se calcula sobre el veredicto aceptado (30 × 1,0 × 0,9 × 0,9)
    assert f.Confianza_final == 24


def test_neutro_frente_a_go_queda_en_revision(prompt):
    f = _fila_ruta(prompt, "+1", respuesta("NO_EFFECT", 0, limitacion="process_not_addressed"))
    assert (f.Signo_ruta, f.Estado) == ("UNKNOWN", "revisar")
    assert f.Motivos == "baja_confianza|contexto_ajeno|discrepancia_polaridad_GO"


def test_discrepancia_con_go_conserva_el_signo_si_llega_al_umbral(prompt):
    f = _fila_ruta(prompt, "-1", respuesta("INCREASES", 90))
    assert (f.Signo_ruta, f.Estado, f.Motivos) == ("+1", "revisar", "discrepancia_polaridad_GO")


def test_sin_go_vale_el_umbral(prompt):
    assert _fila_ruta(prompt, "", respuesta("INCREASES", 90)).Estado == "resuelto"
    assert _fila_ruta(prompt, "", respuesta("INCREASES", 50)).Signo_ruta == "UNKNOWN"


# --- Contraste entre modelos ---
def test_discrepancia_entre_modelos(prompt):
    f = _fila_ruta(prompt, "", respuesta("INCREASES", 90), respuesta("DECREASES", 90))
    assert (f.Signo_ruta, f.Estado) == ("+1", "revisar")
    assert "discrepancia_entre_modelos" in f.Motivos
    assert (f.Signo_principal, f.Signo_secundario) == ("+1", "-1")


def test_json_invalido_del_secundario_no_es_discrepancia(prompt):
    f = _fila_ruta(prompt, "", respuesta("INCREASES", 90), "no es JSON")
    assert (f.Estado, f.Motivos) == ("resuelto", "")


def test_principal_sin_responder_queda_pendiente():
    c = contrastar(None, None)
    assert (c["signo"], c["estado"]) == ("UNKNOWN", "pendiente")


# --- Respaldo del secundario (ADR-005: Gemini principal, gpt-oss si falla) ---
def _fila_respaldo(prompt, principal, secundario_txt):
    salidas = {"principal": principal, "secundario": validar_respuesta(prompt, secundario_txt)}
    preguntas, por_ruta = tablas([ResultadoCaso(prompt, salidas)], "principal", "secundario", [], hoja_fase1(""))
    return preguntas.iloc[0], por_ruta.iloc[0]


def test_respaldo_si_el_principal_no_responde(prompt):
    q, f = _fila_respaldo(prompt, None, respuesta("DECREASES", 90))
    assert (f.Signo_ruta, f.Estado, f.Motivos) == ("-1", "resuelto", "respaldo_secundario")
    assert (f.Modelo_respuesta, f.Signo_principal, f.Signo_secundario) == ("secundario", None, "-1")
    assert q.Efecto == "DECREASES" and f.Confianza_final == 73  # 90 × 0,9 (frase S1) × 0,9 (sin_segundo)


def test_respaldo_si_el_json_del_principal_no_vale(prompt):
    q, f = _fila_respaldo(prompt, validar_respuesta(prompt, "no es JSON"), respuesta("INCREASES", 90))
    assert (f.Signo_ruta, f.Estado, f.Modelo_respuesta) == ("+1", "resuelto", "secundario")
    assert f.Signo_principal == "UNKNOWN" and "respaldo_secundario" in f.Motivos


def test_sin_respaldo_si_el_principal_responde(prompt):
    _, f = _fila_respaldo(prompt, validar_respuesta(prompt, respuesta("INCREASES", 90)), respuesta("INCREASES", 90))
    assert (f.Modelo_respuesta, f.Motivos) == ("principal", "")


def test_ambos_sin_responder_sigue_pendiente(prompt):
    salidas = {"principal": None, "secundario": None}
    _, por_ruta = tablas([ResultadoCaso(prompt, salidas)], "principal", "secundario", [], hoja_fase1(""))
    assert por_ruta.iloc[0].Estado == "pendiente"


def test_preguntas_cerradas_por_el_filtro_previo(prompt):
    preguntas, por_ruta = tablas([], "principal", None, [caso()], hoja_fase1())
    assert preguntas.iloc[0].Motivos == "no_menciona_gen" and por_ruta.iloc[0].Signo_ruta == "UNKNOWN"


# --- confianza_final ---
def test_confianza_final_factores():
    base = {"signo": "+1", "confianza_modelo": 100, "tipo_evidencia": "gain_of_function", "id_frase": "S5"}
    assert confianza_final(base, {"signo": "+1", "motivos": []}) == 100
    assert confianza_final({**base, "id_frase": "S1"}, {"signo": "+1", "motivos": []}) == 90
    assert confianza_final(base, {"signo": "-1", "motivos": []}) == 50
    assert confianza_final(base, {"signo": "UNKNOWN", "motivos": []}) == 80
    assert confianza_final(base, None) == 90
    assert confianza_final({**base, "tipo_evidencia": "correlation_or_marker"}, None) == 63
    assert confianza_final({**base, "signo": "UNKNOWN"}) is None
