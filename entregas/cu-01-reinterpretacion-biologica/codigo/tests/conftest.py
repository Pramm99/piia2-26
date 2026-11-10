"""Datos comunes de las pruebas. Ninguna prueba usa la red ni las claves de codigo/.env."""
import json

import pandas as pd
import pytest

from consulta_gen.esquema import CasoProceso
from consulta_gen.prompt import CONFIG_V1_GEN, CONFIG_V2, construir_prompt

FRASE = "CD7 strongly increased T cell cytokine production in vitro."
CITA = "CD7 strongly increased T cell cytokine production"


def caso(gen="CD7", pmid="1", frases=(FRASE,), factor=1, rutas=None):
    """Una pregunta (gen, PMID, proceso núcleo) con una ruta del Excel por defecto."""
    return CasoProceso(gen=gen, alias=(), pmid=pmid, titulo="Title", frases=tuple(frases),
                       nucleo_id="GO:0002369", nucleo_nombre="T cell cytokine production",
                       rutas=rutas or (("GO:0002443", "leukocyte mediated immunity", factor),))


def respuesta_v2(veredicto="INCREASES", confianza=90, cita=CITA, id_frase="S1", limitacion="none",
                 evidencia="gain_of_function", **extra):
    """JSON de una respuesta v2_veredicto, como lo devolvería el modelo."""
    return json.dumps({"frases": [{"id_frase": id_frase, "cita": cita}], "tipo_evidencia": evidencia,
                       "organismo": "human", "tipo_celular": "T", "razonamiento_corto": "test",
                       "limitacion": limitacion, "confianza": confianza, "veredicto": veredicto, **extra})


def respuesta_v1(efecto="INCREASES", motivo="none", confianza=90, cita=CITA, id_frase="S1"):
    return json.dumps({"id_frase": id_frase, "justificacion_literal": cita, "tipo_evidencia": "gain_of_function",
                       "organismo": "human", "tipo_celular": "T", "razonamiento_corto": "test",
                       "confianza": confianza, "efecto": efecto, "motivo_unknown": motivo})


@pytest.fixture
def prompt_v2():
    return construir_prompt(caso(), CONFIG_V2)


@pytest.fixture
def prompt_v1():
    return construir_prompt(caso(), CONFIG_V1_GEN)


def hoja_fase1(polaridad="+1", gen="CD7", ruta="GO:0002443", pmid="1"):
    """Lo mínimo de Con_abstract que necesita resultados.tablas."""
    return pd.DataFrame([{"Gen": gen, "GO_ID": ruta, "PMID": pmid, "Polaridad_GO": polaridad, "Destino": "LLM"}])
