"""Casos: filas (gen, ruta, PMID) de Con_abstract -> preguntas (gen, PMID, proceso núcleo).

Opción B con respaldo A (informe «Prompt y modelos gratuitos Fase 2»):
  - el término estrecho de cada fila es su GO_ID_anotado (filas del GAF; uno por término si hay varios)
    o su Termino_coincidente (filas de GeneRIF / Europe PMC), resuelto a GO ID;
  - se pregunta por el núcleo del término y la fila guarda el factor que convierte el efecto en signo de
    su ruta: signo_camino(núcleo término -> núcleo ruta) × polaridad(ruta);
  - si ningún término compone con la ruta, la fila pregunta directamente por el núcleo de la ruta
    (respaldo A).
Varias filas que comparten (gen, PMID, núcleo) son UN caso: el mismo abstract se lee una sola vez.
"""
from collections import OrderedDict
from typing import Dict, List, Tuple

import pandas as pd

from ._extraer_info import MIN_ALIAS, datos_mygene, menciona_gen, patron_gen
from .esquema import CasoProceso
from .limpieza import limpiar_abstract, normalizar_pmid, segmentar_frases, valor_texto
from .proceso import nombre, nucleo_y_polaridad, resolver_termino, signo_camino

MAX_ALIAS = 8  # los más largos primero: los cortos son los más ambiguos


def _alias(gen: str, datos: Dict) -> Tuple[str, ...]:
    alias = [a for a in datos.get("Alias", []) if len(a) >= MIN_ALIAS and a.upper() != gen and a != a.lower()]
    return tuple(sorted(set(alias), key=lambda a: (-len(a), a))[:MAX_ALIAS])


def _terminos(fila) -> List[str]:
    if valor_texto(fila.get("Fuente")) == "GOA":
        return [t for t in valor_texto(fila.get("GO_ID_anotado")).split("|") if t]
    return [g for f in valor_texto(fila.get("Termino_coincidente")).split("|") if f for g in resolver_termino(f)]


def construir_casos(df: pd.DataFrame) -> Tuple[List[CasoProceso], Dict[str, int]]:
    """(casos, recuento). Los casos cuyo texto no nombra al gen se cuentan aparte (motivo no_menciona_gen,
    sin llamar al LLM) y no entran en la lista."""
    casos, _, cuenta = construir_casos_y_cerrados(df)
    return casos, cuenta


def construir_casos_y_cerrados(df: pd.DataFrame) -> Tuple[List[CasoProceso], List[CasoProceso], Dict[str, int]]:
    """(casos para el LLM, casos cerrados con no_menciona_gen, recuento). Los cerrados se devuelven para que
    la salida final de la Fase 2 los incluya como UNKNOWN."""
    genes = sorted({valor_texto(g).upper() for g in df["Gen"]})
    mg = datos_mygene(genes)
    patrones = {g: patron_gen(g, mg[g]["Alias"], mg[g]["Nombre"]) for g in genes}

    casos: "OrderedDict[tuple, dict]" = OrderedDict()
    cuenta = {"filas": 0, "filas_respaldo_ruta": 0, "filas_ruta_sin_direccion": 0}
    for _, fila in df.iterrows():
        abstract = limpiar_abstract(fila.get("Abstract"))
        if not abstract:
            continue
        cuenta["filas"] += 1
        gen, pmid, ruta = valor_texto(fila["Gen"]).upper(), normalizar_pmid(fila.get("PMID")), valor_texto(fila["GO_ID"])
        nucleo_r, pol_r = nucleo_y_polaridad(ruta)
        validos = [(nucleo_y_polaridad(t)[0], t) for t in _terminos(fila)]
        validos = [(n, t, signo_camino(n, nucleo_r)) for n, t in validos]
        validos = [(n, t, s) for n, t, s in validos if s is not None]
        respaldo = not validos
        if respaldo:
            validos = [(nucleo_r, ruta, 1)]
            cuenta["filas_respaldo_ruta"] += 1
        if pol_r is None:
            cuenta["filas_ruta_sin_direccion"] += 1
        for nucleo, termino, s in dict.fromkeys(validos):
            c = casos.setdefault((gen, pmid, nucleo), {
                "gen": gen, "pmid": pmid, "nucleo": nucleo, "titulo": limpiar_abstract(fila.get("Titulo")),
                "frases": tuple(segmentar_frases(abstract)), "termino": termino, "respaldo": respaldo,
                "rutas": OrderedDict(), "texto": f"{fila.get('Titulo', '')} {abstract}"})
            c["rutas"].setdefault(ruta, (ruta, valor_texto(fila.get("Ruta_Nombre")),
                                         None if pol_r is None else s * pol_r))

    lista, cerrados = [], []
    for c in casos.values():
        caso = CasoProceso(
            gen=c["gen"], alias=_alias(c["gen"], mg[c["gen"]]), pmid=c["pmid"], titulo=c["titulo"],
            frases=c["frases"], nucleo_id=c["nucleo"], nucleo_nombre=nombre(c["nucleo"]),
            rutas=tuple(c["rutas"].values()), termino_origen=c["termino"], respaldo_ruta=c["respaldo"])
        # no_menciona_gen: se cierra sin llamar al LLM
        (lista if menciona_gen(c["texto"], patrones[c["gen"]]) else cerrados).append(caso)
    cuenta.update({"casos": len(lista), "casos_no_menciona_gen": len(cerrados),
                   "casos_respaldo_ruta": sum(c.respaldo_ruta for c in lista),
                   "casos_solo_rutas_sin_direccion": sum(all(f is None for *_, f in c.rutas) for c in lista)})
    return lista, cerrados, cuenta
