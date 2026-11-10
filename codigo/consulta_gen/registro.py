"""Registro de respuestas del LLM (ADR-004): `codigo/data/respuestas_llm.jsonl`, solo de añadido.

Una línea JSON por llamada, escrita y volcada a disco en cuanto llega la respuesta: si la ejecución se
corta, como mucho se pierde la llamada en curso. La clave de un caso es
(versión del prompt, gen, PMID, go_id, modelo, huella del prompt): si ya existe, no se vuelve a llamar.
La huella (SHA-256 del texto enviado y del esquema) invalida el caso en cuanto cambia el prompt, sin
mezclar respuestas a prompts distintos. Este fichero NO es una caché: no se borra.

Una llamada lleva varias preguntas de un gen: la llamada (respuesta cruda completa, tokens,
tiempo) va a `llamadas_llm.jsonl`, y cada pregunta respondida a `respuestas_llm.jsonl` con su propia clave y
el `id_llamada`. La huella de cada pregunta es la de SU parte del prompt (prompt.construir_pregunta_gen), así
que si la Fase 1 añade un abstract a un gen solo se pregunta lo nuevo. Los dos ficheros son permanentes.
La `salida` de cada línea es la validación del momento: al reutilizarla se vuelve a validar la respuesta
cruda (ejecucion.py), así que un cambio del validador no obliga a volver a llamar.
"""
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from .esquema import PromptLista, PromptLLM

FICHERO = Path(__file__).resolve().parent.parent / "data" / "respuestas_llm.jsonl"
FICHERO_LLAMADAS = FICHERO.with_name("llamadas_llm.jsonl")


def huella(prompt) -> str:
    """PromptLLM o PromptLista: SHA-256 (16 primeros caracteres) del sistema, el usuario y el esquema."""
    texto = json.dumps([prompt.system, prompt.user, prompt.esquema_json], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def clave(prompt: PromptLLM, modelo: str) -> Tuple[str, ...]:
    ev = prompt.evidencia
    return (prompt.version, ev.gen, ev.pmid, ev.go_id, modelo, huella(prompt))


class Registro:
    def __init__(self, ruta: Path = FICHERO, ruta_llamadas: Optional[Path] = None):
        self.ruta = Path(ruta)
        self.ruta_llamadas = Path(ruta_llamadas) if ruta_llamadas else self.ruta.with_name(FICHERO_LLAMADAS.name)
        self._lineas: Dict[Tuple[str, ...], Dict] = {}
        for linea in self._leer():
            self._lineas[tuple(linea["clave"])] = linea  # si hay repetidas, manda la última

    def _leer(self) -> Iterator[Dict]:
        if not self.ruta.exists():
            return
        with open(self.ruta, encoding="utf-8") as f:
            for n, texto in enumerate(f, 1):
                if texto.strip():
                    try:
                        yield json.loads(texto)
                    except json.JSONDecodeError:
                        print(f"⚠️ {self.ruta.name}, línea {n} ilegible (¿corte a mitad de escritura?): se ignora")

    def __contains__(self, k) -> bool:
        return tuple(k) in self._lineas

    def __len__(self) -> int:
        return len(self._lineas)

    def get(self, k):
        return self._lineas.get(tuple(k))

    def anadir_lista(self, lista: PromptLista, modelo: str, texto_crudo: str, meta: Dict,
                     crudos: Sequence[Optional[str]], salidas: Sequence[Optional[Dict]]) -> List[Dict]:
        """Una llamada por gen: una línea en llamadas_llm.jsonl y una por pregunta respondida
        (crudo None = el modelo se la saltó: no se escribe y queda pendiente)."""
        fecha = datetime.now(timezone.utc).isoformat(timespec="seconds")
        id_llamada = uuid.uuid4().hex[:16]
        _escribir(self.ruta_llamadas, {
            "id_llamada": id_llamada, "version": lista.version, "modelo": modelo, "fecha": fecha, **meta,
            "huella_llamada": huella(lista), "preguntas": [list(clave(p, modelo)) for p in lista.preguntas],
            "respuesta_cruda": texto_crudo})
        lineas = []
        for i, (p, crudo, salida) in enumerate(zip(lista.preguntas, crudos, salidas), 1):
            if crudo is None:
                continue
            linea = {"clave": list(clave(p, modelo)), "version": p.version, "modelo": modelo, "fecha": fecha,
                     "id_llamada": id_llamada, "q": i, "huella_prompt": huella(p), "respuesta_cruda": crudo,
                     "salida": salida}
            _escribir(self.ruta, linea)
            self._lineas[tuple(linea["clave"])] = linea
            lineas.append(linea)
        return lineas


def _escribir(ruta: Path, linea: Dict) -> None:
    """Añade una línea y la vuelca a disco en ese momento."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(json.dumps(linea, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
