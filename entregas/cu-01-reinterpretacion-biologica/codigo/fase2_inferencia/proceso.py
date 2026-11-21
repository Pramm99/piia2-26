"""Proceso núcleo de un término GO y signo del camino entre dos procesos (para las preguntas de la Fase 2).

El LLM no recibe «(positive/negative) regulation of X»: se le pregunta por X (el núcleo) y el código
traslada el efecto a la ruta del Excel:

    signo_ruta = efecto_sobre_nucleo_T × signo_camino(nucleo_T -> nucleo_R) × polaridad(R)

  - polaridad(R): +1 si la ruta es un proceso o «positive regulation of X»; -1 si es «negative
    regulation of X». Una ruta «regulation of X» sin dirección se trata como X (+1 = el gen promueve
    X; decisión del usuario del 2026-11-08). La opción SIN_DIRECCION_COMO_PROCESO está en el config.py
    de la Fase 1, que la aplica igual a Polaridad_GO; con False daría None y la ruta quedaría en UNKNOWN
    (ruta_sin_direccion).
  - signo_camino: is_a y part_of conservan el signo (un subtipo o una parte de X), las regulaciones
    con signo multiplican, y regulates sin signo, una regulación por encima de un part_of (deprecado
    en RO) o caminos con signos opuestos lo rompen. Reutiliza grafo_go.descendientes de la Fase 1.
"""
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from ._fase1 import (OBO_FILE, SIN_DIRECCION_COMO_PROCESO, cargar_go, cargar_nombres, cargar_sinonimos,
                            descendientes, estados_efectivos)

SIGNO_REGULA = {"positively_regulates": 1, "negatively_regulates": -1,
                "regulates": 1 if SIN_DIRECCION_COMO_PROCESO else None}
SIGNO_ESTADO = {"N": 1, "+": 1, "P": 1, "-": -1}


@lru_cache(maxsize=1)
def _ontologia():
    """(hijos, nombres, regula, por_nombre) del OBO de la Fase 1; se carga una vez."""
    hijos, _ = cargar_go(OBO_FILE)
    nombres = cargar_nombres(OBO_FILE)
    regula: Dict[str, Tuple[str, Optional[int]]] = {}
    for objetivo, hs in sorted(hijos.items()):
        for termino, rel in sorted(hs):
            if rel in SIGNO_REGULA:
                regula.setdefault(termino, (objetivo, SIGNO_REGULA[rel]))
    por_nombre: Dict[str, List[str]] = {}
    for go_id, frases in cargar_sinonimos(OBO_FILE).items():
        for f in frases:
            por_nombre.setdefault(f.casefold(), []).append(go_id)
    return hijos, nombres, regula, por_nombre


def nombre(go_id: str) -> str:
    return _ontologia()[1].get(go_id, go_id)


def nucleo_y_polaridad(go_id: str) -> Tuple[str, Optional[int]]:
    """'negative regulation of T cell proliferation' -> (GO de 'T cell proliferation', -1).
    Sigue las regulaciones encadenadas multiplicando su signo; una regulación sin signo cuenta como +1
    (SIN_DIRECCION_COMO_PROCESO) o da None."""
    regula = _ontologia()[2]
    t, polaridad, vistos = go_id, 1, set()
    while t in regula and t not in vistos:
        vistos.add(t)
        t, s = regula[t]
        polaridad = None if polaridad is None or s is None else polaridad * s
    return t, polaridad


@lru_cache(maxsize=4096)
def _desc(nucleo_r: str):
    return descendientes(nucleo_r, _ontologia()[0])


def signo_camino(nucleo_t: str, nucleo_r: str) -> Optional[int]:
    """Signo de «aumentar nucleo_t» respecto a nucleo_r (+1 / -1), o None si el camino no existe,
    no tiene signo o tiene signos opuestos."""
    if nucleo_t == nucleo_r:
        return 1
    estados = _desc(nucleo_r).get(nucleo_t)
    if not estados:
        return None
    signos = {SIGNO_ESTADO[e] for e in estados_efectivos(estados) if e in SIGNO_ESTADO}
    return signos.pop() if len(signos) == 1 and "R" not in estados_efectivos(estados) else None


def resolver_termino(frase: str) -> List[str]:
    """GO IDs cuyo nombre o sinónimo EXACT es la frase (Termino_coincidente de la Fase 1)."""
    return sorted(_ontologia()[3].get(frase.strip().casefold(), []))
