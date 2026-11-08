"""Registro de respuestas del LLM (ADR-004): `codigo/data/respuestas_llm.jsonl`, solo de añadido.

Una línea JSON por llamada, escrita y volcada a disco en cuanto llega la respuesta: si la ejecución se
corta, como mucho se pierde la llamada en curso. La clave de un caso es
(versión del prompt, gen, PMID, go_id, modelo, huella del prompt): si ya existe, no se vuelve a llamar.
La huella (SHA-256 del texto enviado y del esquema) invalida el caso en cuanto cambia el prompt, sin
mezclar respuestas a prompts distintos. Este fichero NO es una caché: no se borra.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, Tuple

from .esquema import PromptLLM

FICHERO = Path(__file__).resolve().parent.parent / "data" / "respuestas_llm.jsonl"


def huella(prompt: PromptLLM) -> str:
    texto = json.dumps([prompt.system, prompt.user, prompt.esquema_json], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def clave(prompt: PromptLLM, modelo: str) -> Tuple[str, ...]:
    ev = prompt.evidencia
    return (prompt.version, ev.gen, ev.pmid, ev.go_id, modelo, huella(prompt))


class Registro:
    def __init__(self, ruta: Path = FICHERO):
        self.ruta = Path(ruta)
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

    def anadir(self, prompt: PromptLLM, modelo: str, texto_crudo: str, meta: Dict, salida: Dict) -> Dict:
        linea = {"clave": list(clave(prompt, modelo)), "version": prompt.version, "modelo": modelo,
                 "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), **meta,
                 "huella_prompt": huella(prompt), "respuesta_cruda": texto_crudo, "salida": salida}
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ruta, "a", encoding="utf-8") as f:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        self._lineas[tuple(linea["clave"])] = linea
        return linea
