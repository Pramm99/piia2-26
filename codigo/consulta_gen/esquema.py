"""Tipos de datos y constantes compartidas por el paquete (sin lógica, sin dependencias externas)."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

SIGNO_POSITIVO = "+1"
SIGNO_NEGATIVO = "-1"
SIGNO_DESCONOCIDO = "UNKNOWN"
SIGNO_NEUTRO = "neutro"  # el gen no aumenta ni disminuye el proceso (el mismo valor que las Ig de la Fase 1)

# Versiones del prompt (se comparan en el benchmark sobre el mismo gold set). Las dos preguntan por el proceso
# núcleo (el código compone el signo hasta la ruta) y se envían por gen, varias preguntas por llamada.
V1_GEN = "v1_proceso_gen"    # el modelo puede abstenerse (NO_CLEAR_EFFECT con motivo)
V2_VEREDICTO = "v2_veredicto"  # producción: veredicto obligado (+1/-1/neutro) con confianza; el UNKNOWN lo decide el código

# Estado y motivos de la salida (ADR-003)
ESTADO_RESUELTO, ESTADO_REVISAR, ESTADO_NO_CONCLUYENTE = "resuelto", "revisar", "no_concluyente"
MIN_PALABRAS_CITA = 6  # una cita más corta no demuestra nada (CD7 aparece dentro de CD70)
# Confianza declarada por el modelo en v1_proceso_gen (regla 13). Un signo por debajo del umbral se conserva, pero
# pasa a revisar con baja_confianza; por debajo de MIN_CONFIANZA_SIGNO_V1_GEN el prompt pide NO_CLEAR_EFFECT, así
# que un signo ahí es incoherencia_respuesta. El umbral es provisional: se ajustará con el gold set.
UMBRAL_CONFIANZA_V1_GEN = 70
MIN_CONFIANZA_SIGNO_V1_GEN = 50
# Mantienen el signo y piden revisión (los dos últimos los añade el contraste de resultados.py)
MOTIVOS_REVISAR = ("incoherencia_respuesta", "baja_confianza", "discrepancia_entre_modelos", "discrepancia_polaridad_GO")
ESTADO_PENDIENTE = "pendiente"  # el modelo principal aún no ha respondido (límite del plan gratuito): no es UNKNOWN
# v2_veredicto: el modelo siempre da un veredicto y una confianza; por debajo de este umbral el código lo convierte
# en UNKNOWN (baja_confianza), salvo que coincida con la Polaridad_GO de esa anotación (resultados.py).
# 80: decisión del 2026-11-10 tras la prueba de umbrales de Gemini sobre el gold v3 (con 40, precisión 54-57 %;
# con 80, 66-71 %, perdiendo 2-3 de 40 signos reales). El prompt no lo conoce.
UMBRAL_VEREDICTO = 80

HOJA_EVIDENCIAS = "Con_abstract"

# Columnas que escribe salida.escribir_excel en la hoja Con_abstract y que necesitamos sí o sí.
COLUMNAS_OBLIGATORIAS = ("Gen", "GO_ID", "Ruta_Nombre", "Estado_Original", "PMID", "Titulo", "Abstract")


@dataclass(frozen=True)
class CasoProceso:
    """Unidad de pregunta: (gen, PMID, proceso núcleo). Un mismo caso cubre todas las filas (gen, ruta) del
    Excel cuyo signo se deduce del efecto sobre ese proceso."""
    gen: str
    alias: Tuple[str, ...]
    pmid: str
    titulo: str
    frases: Tuple[str, ...]          # [S1..Sn] del abstract completo
    nucleo_id: str                   # GO ID del proceso por el que se pregunta
    nucleo_nombre: str
    rutas: Tuple[Tuple[str, str, Optional[int]], ...]  # (GO_ID ruta, nombre, factor e→signo; None = sin dirección)
    termino_origen: str = ""         # GO_ID_anotado o término coincidente del que sale el caso
    respaldo_ruta: bool = False      # True = la composición desde el término se rompía y se pregunta por la ruta

    @property
    def go_id(self) -> str:
        return self.nucleo_id

    @property
    def abstract(self) -> str:
        return " ".join(self.frases)


@dataclass(frozen=True)
class PromptLLM:
    """Una pregunta (un CasoProceso) lista para cualquier LLM, independiente del proveedor. Es la unidad del
    registro y del validador; lo que se envía es una PromptLista con las preguntas de un gen."""
    evidencia: CasoProceso
    system: str
    user: str
    version: str
    esquema_json: Optional[Dict] = field(default=None, compare=False)  # salida estructurada

    @property
    def pmid(self) -> str:
        return self.evidencia.pmid

    @property
    def gen(self) -> str:
        return self.evidencia.gen

    def como_mensajes(self) -> List[Dict[str, str]]:
        """Formato de chat estándar (role/content); lo entienden Groq, OpenAI, Ollama, etc."""
        return [{"role": "system", "content": self.system},
                {"role": "user", "content": self.user}]


@dataclass(frozen=True)
class PromptLista:
    """Lo que se envía: varias preguntas de un gen en una llamada.
    `preguntas` son los PromptLLM de cada pregunta (Q1..Qn, en orden): son la unidad del registro y del
    validador; la lista solo agrupa el envío."""
    system: str
    user: str
    preguntas: Tuple[PromptLLM, ...]
    esquema_json: Optional[Dict] = field(default=None, compare=False)
    max_salida: Optional[int] = None  # max_completion_tokens de la llamada (crece con el nº de preguntas)
    version: str = V1_GEN             # o V2_VEREDICTO

    @property
    def gen(self) -> str:
        return self.preguntas[0].gen

    def como_mensajes(self) -> List[Dict[str, str]]:
        return [{"role": "system", "content": self.system},
                {"role": "user", "content": self.user}]


# Campos de contexto de la respuesta, iguales en las dos versiones (salida estructurada estricta; en Ollama, el
# mismo objeto en `format`)
CAMPOS_CONTEXTO = {
    "tipo_evidencia": {"type": "string", "enum": ["loss_of_function", "gain_of_function", "direct_measurement",
                                                  "correlation_or_marker", "background_statement", "none"]},
    "organismo": {"type": "string", "enum": ["human", "mouse", "other", "not_stated"]},
    "tipo_celular": {"type": "string", "enum": ["NK", "T", "other_immune", "tumor", "other", "not_stated"]},
    "razonamiento_corto": {"type": "string", "description": "1-2 sentences; mention any sign inversion"},
}

# Esquema de la respuesta de v1_proceso_gen (una pregunta)
MOTIVOS_MODELO_V1_GEN = ["none", "gene_not_discussed", "gene_is_the_target", "marker_or_correlation_only",
                         "effect_of_other_molecule", "no_effect_found", "speculation_only",
                         "conflicting_results", "process_not_addressed"]
ESQUEMA_V1_GEN = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id_frase", "justificacion_literal", *CAMPOS_CONTEXTO, "confianza", "efecto", "motivo_unknown"],
    "properties": {
        "id_frase": {"type": "string", "description": "T, S1, S2... or none"},
        "justificacion_literal": {"type": "string", "description": ">=6 words copied exactly from that sentence"},
        **CAMPOS_CONTEXTO,
        # Después del razonamiento y antes del efecto: el modelo lo decide tras razonar (anclas en la regla 13)
        "confianza": {"type": "integer", "description": "integer 0-100, see rule 13"},
        "efecto": {"type": "string", "enum": ["INCREASES", "DECREASES", "NO_CLEAR_EFFECT"]},
        "motivo_unknown": {"type": "string", "enum": MOTIVOS_MODELO_V1_GEN},
    },
}
# Lo que se pide en la llamada: un objeto con la lista de respuestas; cada una dice a qué pregunta (Q1..Qn) responde
ESQUEMA_LISTA_V1_GEN = {
    "type": "object",
    "additionalProperties": False,
    "required": ["respuestas"],
    "properties": {"respuestas": {"type": "array", "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["q"] + ESQUEMA_V1_GEN["required"],
        "properties": {"q": {"type": "string", "description": "Q1, Q2..."}, **ESQUEMA_V1_GEN["properties"]},
    }}},
}
EFECTO_A_SIGNO = {"INCREASES": 1, "DECREASES": -1, "NO_CLEAR_EFFECT": None}

# Esquema de la respuesta de v2_veredicto: siempre un veredicto (sin abstención), su confianza y las frases que lo
# motivan, cada una con su cita literal. Las trampas de la v1 pasan a ser una «limitación» que explica una confianza baja.
LIMITACIONES_V2 = ["none", "gene_not_discussed", "gene_is_the_target", "marker_or_correlation_only",
                   "effect_of_other_molecule", "speculation_only", "conflicting_results", "process_not_addressed"]
ESQUEMA_V2 = {
    "type": "object",
    "additionalProperties": False,
    "required": ["frases", "tipo_evidencia", "organismo", "tipo_celular", "razonamiento_corto", "limitacion",
                 "confianza", "veredicto"],
    "properties": {
        "frases": {"type": "array", "description": "1-3 objects {\"id_frase\": T|S1|S2..., \"cita\": >=6 words copied exactly from that sentence}",
                   "items": {"type": "object", "additionalProperties": False, "required": ["id_frase", "cita"],
                             "properties": {"id_frase": {"type": "string"}, "cita": {"type": "string"}}}},
        **CAMPOS_CONTEXTO,
        "limitacion": {"type": "string", "enum": LIMITACIONES_V2},
        "confianza": {"type": "integer", "description": "integer 0-100, see rule 12"},
        "veredicto": {"type": "string", "enum": ["INCREASES", "DECREASES", "NO_EFFECT"]},
    },
}
ESQUEMA_LISTA_V2 = {
    "type": "object",
    "additionalProperties": False,
    "required": ["respuestas"],
    "properties": {"respuestas": {"type": "array", "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["q"] + ESQUEMA_V2["required"],
        "properties": {"q": {"type": "string", "description": "Q1, Q2..."}, **ESQUEMA_V2["properties"]},
    }}},
}
VEREDICTO_A_SIGNO = {"INCREASES": SIGNO_POSITIVO, "DECREASES": SIGNO_NEGATIVO, "NO_EFFECT": SIGNO_NEUTRO}
# Campos que pueden faltar en respuestas guardadas antes de existir (el benchmark vuelve a validar registros antiguos)
CAMPOS_NUEVOS_V1_GEN = ("confianza",)
# Motivos del modelo -> motivos del ADR-003 (los cuatro últimos son nuevos y hay que añadirlos al ADR)
MOTIVO_MODELO_A_ADR = {
    "gene_not_discussed": "no_menciona_gen", "effect_of_other_molecule": "efecto_indirecto",
    "conflicting_results": "contradictorio", "process_not_addressed": "contexto_ajeno",
    "gene_is_the_target": "direccion_inversa", "marker_or_correlation_only": "marcador_correlacion",
    "no_effect_found": "sin_efecto", "speculation_only": "especulativo",
}
