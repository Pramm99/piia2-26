"""Ejecución de los prompts con uno o varios modelos, reanudable (ADR-004).

Para cada prompt y cada modelo: si la clave ya está en el registro se reutiliza su salida (0 llamadas);
si no, se llama, se valida (respuesta.py) y se añade al registro en ese momento. Si un modelo no
responde tras los reintentos (ErrorTransitorio), el caso queda PENDIENTE y ese modelo deja de llamarse
en esta ejecución: casi siempre es el límite diario del plan gratuito, y seguir solo gastaría reintentos.
La siguiente ejecución retoma justo lo pendiente.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .cliente import ErrorTransitorio
from .esquema import PromptLLM
from .registro import Registro, clave
from .respuesta import validar_respuesta


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


def ejecutar(prompts: Sequence[PromptLLM], clientes: Sequence, registro: Optional[Registro] = None,
             cada: int = 25) -> (List[ResultadoCaso], Resumen):
    """clientes: objetos con `.cfg.nombre` y `.completar(prompt)` (ClienteOpenAICompatible o ClienteSimulado)."""
    registro = registro if registro is not None else Registro()
    resumen, resultados, agotados = Resumen(), [], set()
    for i, prompt in enumerate(prompts, 1):
        res = ResultadoCaso(prompt)
        for cli in clientes:
            nombre = cli.cfg.nombre
            k = clave(prompt, nombre)
            if k in registro:
                res.salidas[nombre] = registro.get(k)["salida"]
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
            salida = validar_respuesta(prompt, r.texto)
            registro.anadir(prompt, nombre, r.texto, r.meta, salida)
            res.salidas[nombre] = salida
        resultados.append(res)
        if cada and i % cada == 0:
            print(f"   {i}/{len(prompts)} casos | llamadas {resumen.llamadas} | reutilizadas {resumen.reutilizadas} "
                  f"| pendientes {resumen.pendientes}")
    resumen.agotados = sorted(agotados)
    return resultados, resumen
