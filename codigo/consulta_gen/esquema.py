"""Tipos de datos y constantes compartidas por el paquete (sin lógica, sin dependencias externas)."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

SIGNO_POSITIVO = "+1"
SIGNO_NEGATIVO = "-1"
SIGNO_DESCONOCIDO = "UNKNOWN"
SIGNOS_VALIDOS = (SIGNO_POSITIVO, SIGNO_NEGATIVO, SIGNO_DESCONOCIDO)

# Versiones del prompt (se comparan en el benchmark sobre el mismo gold set)
V0_ORIGINAL = "v0_original"  # línea base congelada: pregunta por la ruta (solo para el benchmark)
V1_PROCESO = "v1_proceso"    # pregunta por el proceso núcleo; el código compone el signo hasta la ruta
VERSIONES = (V0_ORIGINAL, V1_PROCESO)

# Estado y motivos de la salida (ADR-003)
ESTADO_RESUELTO, ESTADO_REVISAR, ESTADO_NO_CONCLUYENTE = "resuelto", "revisar", "no_concluyente"
MIN_PALABRAS_CITA = 6  # una cita más corta no demuestra nada (CD7 aparece dentro de CD70)

HOJA_EVIDENCIAS = "Con_abstract"

# Columnas que escribe salida.escribir_excel en la hoja Con_abstract y que necesitamos sí o sí.
COLUMNAS_OBLIGATORIAS = ("Gen", "GO_ID", "Ruta_Nombre", "Estado_Original", "PMID", "Titulo", "Abstract")


@dataclass(frozen=True)
class Evidencia:
    """Una fila del Excel (un gen, una ruta, un PMID) ya normalizada."""
    gen: str
    go_id: str
    ruta_nombre: str
    estado_scrnaseq: str      # "Activada" / "Suprimida"
    pmid: str
    titulo: str
    abstract: str             # exactamente el texto que se enviará al LLM
    polaridad_go: str = ""    # "+1" / "-1" / "conflicto" / "" (pista derivada del grafo GO)
    evidencia_go: str = ""    # códigos de evidencia GAF (IDA, IMP, ...)
    directo: Optional[bool] = None


@dataclass(frozen=True)
class CasoProceso:
    """Unidad de pregunta de v1_proceso: (gen, PMID, proceso núcleo). Un mismo caso cubre todas las
    filas (gen, ruta) del Excel cuyo signo se deduce del efecto sobre ese proceso."""
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
    frase_fuente: str = ""           # frase donde la Fase 1 vio gen y proceso (solo la variante V2 la usa)

    @property
    def go_id(self) -> str:
        return self.nucleo_id

    @property
    def abstract(self) -> str:
        return " ".join(self.frases)


@dataclass(frozen=True)
class PromptLLM:
    """Prompt listo para entregar a cualquier LLM, independiente del proveedor.
    `evidencia` es una Evidencia (v0_original, una fila) o un CasoProceso (v1_proceso)."""
    evidencia: object
    system: str
    user: str
    version: str = V0_ORIGINAL
    esquema_json: Optional[Dict] = field(default=None, compare=False)  # salida estructurada (v1)

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


# Esquema de la respuesta de v1_proceso (salida estructurada estricta; en Ollama, el mismo objeto en `format`)
MOTIVOS_MODELO_V1 = ["none", "gene_not_discussed", "gene_is_the_target", "marker_or_correlation_only",
                     "effect_of_other_molecule", "no_effect_found", "speculation_only",
                     "conflicting_results", "process_not_addressed"]
ESQUEMA_V1 = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id_frase", "justificacion_literal", "tipo_evidencia", "organismo", "tipo_celular",
                 "razonamiento_corto", "efecto", "motivo_unknown"],
    "properties": {
        "id_frase": {"type": "string", "description": "T, S1, S2... or none"},
        "justificacion_literal": {"type": "string", "description": ">=6 words copied exactly from that sentence"},
        "tipo_evidencia": {"type": "string", "enum": ["loss_of_function", "gain_of_function", "direct_measurement",
                                                      "correlation_or_marker", "background_statement", "none"]},
        "organismo": {"type": "string", "enum": ["human", "mouse", "other", "not_stated"]},
        "tipo_celular": {"type": "string", "enum": ["NK", "T", "other_immune", "tumor", "other", "not_stated"]},
        "razonamiento_corto": {"type": "string", "description": "1-2 sentences; mention any sign inversion"},
        "efecto": {"type": "string", "enum": ["INCREASES", "DECREASES", "NO_CLEAR_EFFECT"]},
        "motivo_unknown": {"type": "string", "enum": MOTIVOS_MODELO_V1},
    },
}
EFECTO_A_SIGNO = {"INCREASES": 1, "DECREASES": -1, "NO_CLEAR_EFFECT": None}
# Motivos del modelo -> motivos del ADR-003 (los cuatro últimos son nuevos y hay que añadirlos al ADR)
MOTIVO_MODELO_A_ADR = {
    "gene_not_discussed": "no_menciona_gen", "effect_of_other_molecule": "efecto_indirecto",
    "conflicting_results": "contradictorio", "process_not_addressed": "contexto_ajeno",
    "gene_is_the_target": "direccion_inversa", "marker_or_correlation_only": "marcador_correlacion",
    "no_effect_found": "sin_efecto", "speculation_only": "especulativo",
}
