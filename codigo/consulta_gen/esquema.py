"""Tipos de datos y constantes compartidas por el paquete (sin lógica, sin dependencias externas)."""
from dataclasses import dataclass
from typing import Dict, List, Optional

SIGNO_POSITIVO = "+1"
SIGNO_NEGATIVO = "-1"
SIGNO_DESCONOCIDO = "UNKNOWN"
SIGNOS_VALIDOS = (SIGNO_POSITIVO, SIGNO_NEGATIVO, SIGNO_DESCONOCIDO)

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
class PromptLLM:
    """Prompt listo para entregar a cualquier LLM, independiente del proveedor."""
    evidencia: Evidencia
    system: str
    user: str

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
