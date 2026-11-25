"""El estudio que se analiza: tipo celular, tejido y ficheros de entrada (#51). Se describe en codigo/estudio.json (o
en el fichero al que apunte la variable de entorno ESTUDIO_JSON) y lo leen todas las fases y la interfaz, para que el
pipeline no dé por hecho que son células NK de laringe y faringe."""
import json
import os
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional, Tuple

DIR_CODIGO = Path(__file__).resolve().parent
FICHERO_ESTUDIO = DIR_CODIGO / "estudio.json"

# Tipo celular que da el LLM en la Fase 2 (fase2_inferencia/esquema.py) que cuenta como «el del estudio» en el peso
# del voto, según la clase de la célula estudiada. Para una célula inmune valen también las otras inmunes (el LLM solo
# distingue NK, T y otras inmunes); para una tumoral, los estudios en tumor; para otra, los de otro tipo celular.
# not_stated vale siempre: sin dato no se penaliza.
TIPOS_LLM_POR_CLASE = {
    "inmune": ("NK", "T", "other_immune", "not_stated"),
    "tumoral": ("tumor", "not_stated"),
    "otra": ("other", "not_stated"),
}
CL_ID = re.compile(r"^CL:\d{7}$")

# Células que se pueden elegir en la interfaz (#52, preparado para la versión 2: el selector está congelado). Términos
# de Cell Ontology comprobados en OLS4 el 2026-11-25. La clase decide qué tipo celular del LLM pesa entero.
CELULAS_DISPONIBLES = (
    ("CL:0000623", "células NK", "inmune"),
    ("CL:0000084", "células T", "inmune"),
    ("CL:0000624", "células T CD4+", "inmune"),
    ("CL:0000625", "células T CD8+", "inmune"),
    ("CL:0000815", "células T reguladoras", "inmune"),
    ("CL:0000236", "células B", "inmune"),
    ("CL:0000235", "macrófagos", "inmune"),
    ("CL:0000576", "monocitos", "inmune"),
    ("CL:0000451", "células dendríticas", "inmune"),
    ("CL:0000775", "neutrófilos", "inmune"),
    ("CL:0000097", "mastocitos", "inmune"),
    ("CL:0001064", "células tumorales", "tumoral"),
    ("CL:0000066", "células epiteliales", "otra"),
    ("CL:0000057", "fibroblastos", "otra"),
    ("CL:0000115", "células endoteliales", "otra"),
)


@dataclass(frozen=True)
class Estudio:
    celula: str            # en texto, para la interfaz y los Excels («células NK»)
    cl_celula: str         # término de Cell Ontology (CL:0000623 = natural killer cell)
    clase_celula: str      # inmune, tumoral u otra (TIPOS_LLM_POR_CLASE)
    tejido: str
    excel_activadas: Path
    excel_suprimidas: Path
    log2fc: Optional[Path]  # tabla de expresión diferencial; None si el estudio no la tiene

    @property
    def tipos_celulares_validos(self) -> Tuple[str, ...]:
        return TIPOS_LLM_POR_CLASE[self.clase_celula]


def con_celula(estudio: Estudio, cl: str) -> Estudio:
    """El mismo estudio (tejido y ficheros) con otra célula de CELULAS_DISPONIBLES; ValueError si no está."""
    for cl_celula, celula, clase in CELULAS_DISPONIBLES:
        if cl_celula == cl:
            return replace(estudio, cl_celula=cl_celula, celula=celula, clase_celula=clase)
    raise ValueError(f"{cl!r} no es una de las células que se pueden elegir")


def fichero_estudio() -> Path:
    return Path(os.environ.get("ESTUDIO_JSON") or FICHERO_ESTUDIO)


def leer_estudio(ruta=None) -> Estudio:
    """Lee y valida el estudio. Un error dice qué clave falta o qué valor no vale, antes de tocar la red."""
    ruta = Path(ruta or fichero_estudio())
    if not ruta.exists():
        raise ValueError(f"No existe el fichero del estudio: {ruta}")
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    obligatorias = ("celula", "cl_celula", "clase_celula", "tejido", "excel_activadas", "excel_suprimidas")
    faltan = [k for k in obligatorias if not str(datos.get(k) or "").strip()]
    if faltan:
        raise ValueError(f"{ruta.name}: faltan {', '.join(faltan)}")
    if not CL_ID.match(datos["cl_celula"].strip()):
        raise ValueError(f"{ruta.name}: cl_celula debe ser un término de Cell Ontology (CL:0000000), no "
                         f"{datos['cl_celula']!r}")
    if datos["clase_celula"] not in TIPOS_LLM_POR_CLASE:
        raise ValueError(f"{ruta.name}: clase_celula debe ser {', '.join(TIPOS_LLM_POR_CLASE)}, no "
                         f"{datos['clase_celula']!r}")
    relativa = lambda v: (DIR_CODIGO / v).resolve()
    log2fc = str(datos.get("log2fc") or "").strip()
    return Estudio(celula=datos["celula"].strip(), cl_celula=datos["cl_celula"].strip(),
                   clase_celula=datos["clase_celula"], tejido=datos["tejido"].strip(),
                   excel_activadas=relativa(datos["excel_activadas"]),
                   excel_suprimidas=relativa(datos["excel_suprimidas"]),
                   log2fc=relativa(log2fc) if log2fc else None)
