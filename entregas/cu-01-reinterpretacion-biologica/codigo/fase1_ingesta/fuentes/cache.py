"""Caché JSON en disco con escritura atómica, común a todas las fuentes."""
import json
import os


def cargar_json(ruta, defecto=None):
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    return {} if defecto is None else defecto


def guardar_json(datos, ruta):
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
    os.replace(tmp, ruta)
