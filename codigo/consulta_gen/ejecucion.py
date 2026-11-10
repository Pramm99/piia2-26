"""Ejecución de los prompts con uno o varios modelos, reanudable (ADR-004).

Para cada prompt y cada modelo: si la clave ya está en el registro, se vuelve a validar su respuesta cruda
(0 llamadas: un cambio del validador o de la composición del signo no obliga a llamar otra vez); si no, se
llama, se valida (respuesta.py) y se añade al registro en ese momento. Si un modelo no responde tras los
reintentos (ErrorTransitorio), el caso queda PENDIENTE y ese modelo deja de llamarse en esta ejecución: casi
siempre es el límite diario del plan gratuito, y seguir solo gastaría reintentos. La siguiente ejecución
retoma justo lo pendiente.

v1_proceso_gen: las preguntas que le faltan a algún modelo se agrupan por gen y se trocean con el presupuesto
por llamada más pequeño de los modelos (prompt.trocear_por_gen), para que todos reciban la misma agrupación.
A cada modelo se le envían solo las preguntas del grupo que le faltan; cada una se registra y se valida sola.
Una pregunta que el modelo se salta queda pendiente; si la salida se corta por max_completion_tokens, la lista
se parte en dos y se repite.

El resumen cuenta los tokens de cada modelo, incluidos los servidos de la caché del proveedor y los de
razonamiento, cuando el proveedor los da (`usage.prompt_tokens_details.cached_tokens`,
`usage.completion_tokens_details.reasoning_tokens`).
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .cliente import ErrorTransitorio
from .esquema import V1_GEN, PromptLista, PromptLLM
from .prompt import construir_prompt_lista, trocear_por_gen
from .registro import Registro, clave
from .respuesta import repartir_lista, validar_respuesta


@dataclass
class ResultadoCaso:
    prompt: PromptLLM
    salidas: Dict[str, Optional[Dict]] = field(default_factory=dict)  # modelo -> salida validada (None = pendiente)


@dataclass
class Resumen:
    llamadas: int = 0
    reutilizadas: int = 0
    pendientes: int = 0
    agotados: List[str] = field(default_factory=list)
    cortadas: int = 0                 # llamadas con la salida cortada (finish_reason "length")
    tokens: Dict[str, Dict[str, int]] = field(default_factory=dict)  # modelo -> entrada/salida/cache/razonamiento


def _sumar_tokens(resumen: Resumen, modelo: str, meta: Dict) -> None:
    u = meta.get("tokens") or {}
    t = resumen.tokens.setdefault(modelo, {"entrada": 0, "salida": 0, "cache": 0, "razonamiento": 0})
    t["entrada"] += u.get("prompt_tokens") or 0
    t["salida"] += u.get("completion_tokens") or 0
    t["cache"] += (u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
    t["razonamiento"] += (u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
    if meta.get("fin") == "length":
        resumen.cortadas += 1


def ejecutar(prompts: Sequence[PromptLLM], clientes: Sequence, registro: Optional[Registro] = None,
             cada: int = 25) -> (List[ResultadoCaso], Resumen):
    """clientes: objetos con `.cfg` (nombre, presupuesto_llamada) y `.completar(prompt)` (ClienteOpenAICompatible
    o ClienteSimulado). Con prompts de v1_proceso_gen (preguntas sueltas) envía por gen."""
    registro = registro if registro is not None else Registro()
    versiones = {p.version for p in prompts}
    if V1_GEN in versiones:
        if len(versiones) > 1:
            raise ValueError("No se pueden mezclar preguntas de v1_proceso_gen con otras versiones")
        return _ejecutar_por_gen(prompts, clientes, registro, cada)

    resumen, resultados, agotados = Resumen(), [], set()
    for i, prompt in enumerate(prompts, 1):
        res = ResultadoCaso(prompt)
        for cli in clientes:
            nombre = cli.cfg.nombre
            k = clave(prompt, nombre)
            if k in registro:
                res.salidas[nombre] = validar_respuesta(prompt, registro.get(k)["respuesta_cruda"])
                resumen.reutilizadas += 1
                continue
            if nombre in agotados:
                res.salidas[nombre] = None
                resumen.pendientes += 1
                continue
            try:
                r = cli.completar(prompt)
            except ErrorTransitorio as e:
                print(f"⏸️ {e}. Los casos que faltan de {nombre} quedan pendientes para la próxima ejecución.")
                agotados.add(nombre)
                res.salidas[nombre] = None
                resumen.pendientes += 1
                continue
            resumen.llamadas += 1
            _sumar_tokens(resumen, nombre, r.meta)
            salida = validar_respuesta(prompt, r.texto)
            registro.anadir(prompt, nombre, r.texto, r.meta, salida)
            res.salidas[nombre] = salida
        resultados.append(res)
        if cada and i % cada == 0:
            print(f"   {i}/{len(prompts)} casos | llamadas {resumen.llamadas} | reutilizadas {resumen.reutilizadas} "
                  f"| pendientes {resumen.pendientes}")
    resumen.agotados = sorted(agotados)
    return resultados, resumen


def _llamar_lista(cli, lista: PromptLista, registro: Registro, resumen: Resumen) -> None:
    """Una llamada de v1_proceso_gen. Si la salida se corta y hay más de una pregunta, la llamada queda en el
    registro de llamadas (para auditoría, sin respuestas) y la lista se parte en dos."""
    nombre, n = cli.cfg.nombre, len(lista.preguntas)
    r = cli.completar(lista)  # ErrorTransitorio sube hasta _ejecutar_por_gen
    resumen.llamadas += 1
    _sumar_tokens(resumen, nombre, r.meta)
    if r.meta.get("fin") == "length" and n > 1:
        registro.anadir_lista(lista, nombre, r.texto, r.meta, [None] * n, [None] * n)
        for parte in (lista.preguntas[:n // 2], lista.preguntas[n // 2:]):
            _llamar_lista(cli, construir_prompt_lista(parte), registro, resumen)
        return
    crudos = repartir_lista(lista, r.texto)
    salidas = [None if c is None else validar_respuesta(p, c) for p, c in zip(lista.preguntas, crudos)]
    registro.anadir_lista(lista, nombre, r.texto, r.meta, crudos, salidas)


def _ejecutar_por_gen(preguntas: Sequence[PromptLLM], clientes: Sequence, registro: Registro,
                      cada: int) -> (List[ResultadoCaso], Resumen):
    resumen, agotados = Resumen(), set()
    resumen.reutilizadas = sum(clave(p, c.cfg.nombre) in registro for p in preguntas for c in clientes)
    faltan_a_alguno = [p for p in preguntas if any(clave(p, c.cfg.nombre) not in registro for c in clientes)]
    presupuesto = min(c.cfg.presupuesto_llamada for c in clientes)
    grupos = trocear_por_gen(faltan_a_alguno, presupuesto) if faltan_a_alguno else []
    for i, grupo in enumerate(grupos, 1):
        for cli in clientes:
            nombre = cli.cfg.nombre
            faltan = [p for p in grupo.preguntas if clave(p, nombre) not in registro]
            if not faltan or nombre in agotados:
                continue
            lista = grupo if len(faltan) == len(grupo.preguntas) else construir_prompt_lista(faltan)
            try:
                _llamar_lista(cli, lista, registro, resumen)
            except ErrorTransitorio as e:
                print(f"⏸️ {e}. Las preguntas que faltan de {nombre} quedan pendientes para la próxima ejecución.")
                agotados.add(nombre)
        if cada and i % cada == 0:
            print(f"   {i}/{len(grupos)} grupos | llamadas {resumen.llamadas} | reutilizadas {resumen.reutilizadas}")

    resultados = []
    for p in preguntas:
        res = ResultadoCaso(p)
        for cli in clientes:
            linea = registro.get(clave(p, cli.cfg.nombre))
            res.salidas[cli.cfg.nombre] = validar_respuesta(p, linea["respuesta_cruda"]) if linea else None
            resumen.pendientes += linea is None
        resultados.append(res)
    resumen.agotados = sorted(agotados)
    return resultados, resumen
