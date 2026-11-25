"""Puente HTTP local entre el frontend y las Fases 1 -> 2 -> 3, para una ruta cada vez.

Desde codigo/: python fase4_frontend/api_puente.py (escucha en http://127.0.0.1:8000).

  GET  /salud           -> {"ok": true}
  POST /ejecutar-ruta   -> {"GO_ID", "Descripcion", "Genes_up", "Genes_down"}: lanza las tres fases seguidas. Para la
                           versión 2 (#52; en la interfaz está congelado) admite además "Celula" (un CL de
                           estudio.CELULAS_DISPONIBLES) y "Log2FC" ({gen: log2FC}), que valen solo para esa ruta
  GET  /estudio         -> tipo celular y tejido del estudio (codigo/estudio.json), para los textos de la interfaz,
                           y las células que se pueden elegir
  GET  /estado          -> fase en curso y, al terminar, el resultado (Por_ruta, Por_par y el Excel de la Fase 3)
  POST /criterio        -> {"GO_ID", "criterio": {gen: signo}}: Fase 3 de esa ruta con los signos de «Tu criterio»
  GET  /claves          -> claves del LLM por proveedor (Gemini y Groq), enmascaradas: nunca se devuelve una entera
  POST /claves          -> {"proveedor", "accion": "anadir", "clave"} o {"proveedor", "accion": "quitar", "indice"}
  GET  / (y lo demás)   -> la interfaz ya construida (fase4_frontend/dist, de `npm run build`) si existe: así el
                           programa de escritorio (codigo/empaquetado/) no necesita Node ni Vite

Las claves (⚙ → token-api en la interfaz) se guardan en codigo/.env, varias por variable separadas por comas, y
valen desde la siguiente ejecución. /claves solo acepta peticiones sin Origin o desde localhost, para que otra web
abierta en el navegador no pueda cambiarlas.

Las rutas no se precargan: la persona sube en el frontend sus Excels y se envían los genes de la ruta elegida.
La ejecución va en un hilo y el frontend consulta /estado, porque en frío tarda unos minutos. Solo hay una a la
vez. Cada ruta escribe sus ficheros en codigo/data/frontend/<GO_ID>/, así que no pisa las salidas del Excel
completo; las cachés de la Fase 1 y el registro de respuestas del LLM (codigo/data/) son los de siempre, de modo
que una ruta ya consultada no vuelve a gastar llamadas.
"""
import base64
import functools
import gzip
import json
import os
import re
import sys
import threading
import math
import time
import traceback
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Tuple
from urllib.parse import unquote, urlparse

import pandas as pd

CODIGO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODIGO_DIR))
sys.path.insert(0, str(CODIGO_DIR / "fase1_ingesta"))  # la Fase 1 usa imports planos

# Las fases imprimen emojis: en la consola de Windows (cp1252) fallaría el print
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import cruce_gaf  # noqa: E402
import entrada_excel  # noqa: E402
import main as f1_main  # noqa: E402
import salida as f1_salida  # noqa: E402
from estudio import CELULAS_DISPONIBLES, Estudio, con_celula  # noqa: E402
from fase2_inferencia.__main__ import PRINCIPAL, SECUNDARIO  # noqa: E402
from fase2_inferencia.cliente import MODELOS, ClienteOpenAICompatible, claves, guardar_claves  # noqa: E402
from fase2_inferencia.esquema import ESTADO_PENDIENTE  # noqa: E402
from fase2_inferencia.limpieza import normalizar_pmid as limpiar  # noqa: E402
from fase2_inferencia.pipeline import ejecutar_fase2  # noqa: E402
from fase3_scoring import config as f3_config  # noqa: E402
from fase3_scoring.nps import (COLUMNAS_FASE2, calcular, casos_con_peso, escribir, leer_fuentes_go,  # noqa: E402
                               un_voto_por_articulo)

DIR_SALIDAS = CODIGO_DIR / "data" / "frontend"
DIR_WEB = Path(__file__).resolve().parent / "dist"  # npm run build
# Tipos fijos: en Windows, mimetypes lee el registro y puede dar text/plain a los .js, y el navegador no los ejecuta.
# El .js y el .css van sin «; charset=utf-8» (Vite ya los escribe en UTF-8): con él, en el equipo de pruebas
# (con Avast), Edge se quedaba siempre con el JavaScript cortado (ERR_CONNECTION_RESET) y la ventana en blanco;
# sin él carga a la primera.
TIPOS_WEB = {".html": "text/html; charset=utf-8", ".js": "text/javascript",
             ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
             ".json": "application/json", ".woff2": "font/woff2", ".woff": "font/woff", ".txt": "text/plain; charset=utf-8",
             ".webmanifest": "application/manifest+json"}
COMPRIMIBLES = (".html", ".js", ".css", ".svg", ".json", ".txt", ".webmanifest")  # con gzip, el JS pasa de 300 a 92 KB: menos que cortar
PATRON_GO = re.compile(r"^GO:\d{7}$")
COLUMNAS_CIMUS = ["ID", "Description", "geneID"]
SIGNOS_CRITERIO = ("+1", "-1", "neutro")
# Una clave de API: letras, cifras, «-», «_» y «.» (las de Gemini empiezan por AIza o AQ., las de Groq por gsk_)
PATRON_CLAVE = re.compile(r"^[A-Za-z0-9._-]{20,200}$")
PREFIJOS_AJENOS = {"gemini": (("gsk_",), "Groq"), "groq": (("AIza", "AQ."), "Gemini")}

_cerrojo = threading.Lock()
_estado = {"estado": "libre"}  # libre | ejecutando | terminado | error
# Mientras una ruta usa una célula elegida (#52), las Fases 1 y 3 la leen de sus módulos: otra ejecución o un
# «Tu criterio» esperan a que acabe para no mezclar estudios.
_cerrojo_estudio = threading.Lock()
MAX_GENES_LOG2FC = 100_000


def _actualizar(**cambios):
    with _cerrojo:
        _estado.update(cambios)


_cerrojo_claves = threading.Lock()


def _proveedores() -> dict:
    """Proveedor -> (configuración del modelo, papel): Gemini es el principal y Groq (gpt-oss) el respaldo."""
    return {MODELOS[n].proveedor: (MODELOS[n], papel) for n, papel in ((PRINCIPAL, "principal"),
                                                                       (SECUNDARIO, "respaldo"))}


def _mascara(c: str) -> str:
    return f"{c[:4]}…{c[-4:]}" if len(c) >= 12 else "…"


def estado_claves() -> list:
    """Las claves de cada proveedor, en el orden en que se usan, enmascaradas. de_entorno: la variable está en el
    entorno del sistema, que manda sobre .env, así que desde la interfaz no se puede cambiar."""
    return [{"id": prov, "modelo": cfg.modelo, "papel": papel, "variable": cfg.var_clave,
             "claves": [_mascara(c) for c in claves(cfg.var_clave)], "de_entorno": bool(os.environ.get(cfg.var_clave))}
            for prov, (cfg, papel) in _proveedores().items()]


def cambiar_claves(datos: dict) -> list:
    """Añade una clave al final de las de su proveedor o quita una por su posición. ValueError si no se puede; el
    mensaje nunca lleva la clave."""
    proveedor = str(datos.get("proveedor", "")).strip()
    if proveedor not in _proveedores():
        raise ValueError(f"Proveedor no válido: {proveedor!r}")
    var = _proveedores()[proveedor][0].var_clave
    if os.environ.get(var):
        raise ValueError(f"{var} está en las variables de entorno del sistema, que mandan sobre codigo/.env: "
                         "quítala de ahí para gestionar las claves desde aquí.")
    with _cerrojo_claves:
        actuales = claves(var)
        accion = datos.get("accion")
        if accion == "anadir":
            nueva = str(datos.get("clave") or "").strip()
            ajenos, otro = PREFIJOS_AJENOS[proveedor]
            if not PATRON_CLAVE.match(nueva):
                raise ValueError("No parece una clave de API: pega solo la clave, sin espacios ni comillas.")
            if nueva.startswith(ajenos):
                raise ValueError(f"Parece una clave de {otro}: añádela en su apartado.")
            if nueva in actuales:
                raise ValueError("Esa clave ya está en la lista.")
            actuales.append(nueva)
        elif accion == "quitar":
            indice = datos.get("indice")
            if not isinstance(indice, int) or not 0 <= indice < len(actuales):
                raise ValueError("No existe esa clave.")
            actuales.pop(indice)
        else:
            raise ValueError(f"Acción no válida: {accion!r}")
        guardar_claves(var, actuales)
    return estado_claves()


def _fase1(carpeta: Path, ruta: dict) -> Path:
    """Fase 1 con los dos Excels de CIMUS reducidos a la ruta. Se redirigen las rutas de entrada y salida
    igual que en las pruebas (tests/test_fase1_e2e.py), sin tocar fase1_ingesta/."""
    entradas = {}
    for lista, nombre in (("Genes_up", "entrada_activadas.xlsx"), ("Genes_down", "entrada_suprimidas.xlsx")):
        filas = [[ruta["GO_ID"], ruta["Descripcion"], ruta[lista]]] if ruta[lista] else []
        entradas[lista] = carpeta / nombre
        pd.DataFrame(filas, columns=COLUMNAS_CIMUS).to_excel(entradas[lista], index=False)
    salida_f1 = carpeta / "fase1_dataset_abstracts.xlsx"
    salida_f1.unlink(missing_ok=True)

    originales = (entrada_excel.EXCEL_ACTIVADAS, entrada_excel.EXCEL_SUPRIMIDAS, f1_salida.SALIDA)
    entrada_excel.EXCEL_ACTIVADAS, entrada_excel.EXCEL_SUPRIMIDAS = str(entradas["Genes_up"]), str(entradas["Genes_down"])
    f1_salida.SALIDA = str(salida_f1)
    try:
        f1_main.ejecutar_fase_1()
    finally:
        entrada_excel.EXCEL_ACTIVADAS, entrada_excel.EXCEL_SUPRIMIDAS, f1_salida.SALIDA = originales
    if not salida_f1.exists():
        raise RuntimeError("La Fase 1 no encontró ninguna evidencia para los genes de esta ruta.")
    return salida_f1


def _fase2(carpeta: Path, excel_f1: Path) -> Tuple[Path, dict]:
    """Fase 2 con los modelos del ADR-005: Gemini y gpt-oss solo como respaldo. Cada cliente lee aquí sus claves,
    así que un cambio en ⚙ → token-api vale desde la siguiente ejecución. agotados: modelo -> por qué se detuvo
    (cupo, clave, sin_clave o fallo), para el aviso de la interfaz."""
    salida_f2 = carpeta / "fase2_resultados.xlsx"
    salida_f2.unlink(missing_ok=True)
    clientes = [ClienteOpenAICompatible(MODELOS[n]) for n in (PRINCIPAL, SECUNDARIO)]
    preguntas, _, resumen, _ = ejecutar_fase2(str(excel_f1), clientes, salida=salida_f2)
    # Pendientes = preguntas sin ninguna respuesta. resumen.pendientes cuenta también las del principal que ya
    # respondió el respaldo, y el aviso de la interfaz diría que faltan cuando no falta nada.
    sin_respuesta = int((preguntas["Estado"] == ESTADO_PENDIENTE).sum()) if "Estado" in preguntas else 0
    if not salida_f2.exists():  # ningún par llegó al LLM: la Fase 3 necesita igualmente las hojas
        with pd.ExcelWriter(salida_f2) as w:
            for hoja, columnas in COLUMNAS_FASE2.items():
                pd.DataFrame(columns=list(columnas)).to_excel(w, sheet_name=hoja, index=False)
    tokens = sum(t["entrada"] + t["salida"] for t in resumen.tokens.values())
    return salida_f2, {"llamadas": resumen.llamadas, "reutilizadas": resumen.reutilizadas,
                       "pendientes": sin_respuesta, "tokens": tokens,
                       "agotados": {MODELOS[n].proveedor: m for n, m in resumen.motivos.items()}}


ESTUDIO_BASE = f3_config.ESTUDIO  # el de codigo/estudio.json


def _estudio_json(e: Estudio) -> dict:
    return {"celula": e.celula, "cl_celula": e.cl_celula, "clase_celula": e.clase_celula, "tejido": e.tejido,
            "tipos_celulares_validos": list(e.tipos_celulares_validos)}


def estudio() -> dict:
    """Lo que la interfaz necesita del estudio: cómo nombrar la célula y el tejido, qué tipos celulares del LLM
    pesan entero (el resto pesa la mitad, como en fase3_scoring/nps.py:peso) y qué células se pueden elegir."""
    return {**_estudio_json(ESTUDIO_BASE),
            "celulas_disponibles": [{"cl_celula": cl, "celula": c, "clase_celula": k}
                                    for cl, c, k in CELULAS_DISPONIBLES]}


@contextmanager
def _con_estudio(e: Estudio):
    """Aplica a las Fases 1 y 3 el estudio de una ruta y deja el de codigo/estudio.json al acabar."""
    with _cerrojo_estudio:
        antes = (cruce_gaf.ESTUDIO, f3_config.ESTUDIO, f3_config.TIPOS_CELULARES_VALIDOS)
        cruce_gaf.ESTUDIO, f3_config.ESTUDIO, f3_config.TIPOS_CELULARES_VALIDOS = e, e, e.tipos_celulares_validos
        try:
            yield
        finally:
            cruce_gaf.ESTUDIO, f3_config.ESTUDIO, f3_config.TIPOS_CELULARES_VALIDOS = antes


def preparar_estudio(carpeta: Path, celula: str = "", log2fc: dict = None) -> Estudio:
    """Guarda en la carpeta de la ruta la célula elegida (estudio_ruta.json) y la tabla de log2FC subida
    (log2fc.csv), para que «Tu criterio» las vuelva a usar; sin ellas, borra las de una ejecución anterior."""
    f_estudio, f_log2fc = carpeta / "estudio_ruta.json", carpeta / "log2fc.csv"
    if celula:
        f_estudio.write_text(json.dumps({"cl_celula": celula}), encoding="utf-8")
    else:
        f_estudio.unlink(missing_ok=True)
    if log2fc:
        pd.DataFrame(sorted(log2fc.items()), columns=["Gen", "log2FC"]).to_csv(f_log2fc, index=False, encoding="utf-8")
    else:
        f_log2fc.unlink(missing_ok=True)
    return estudio_de_carpeta(carpeta)


def estudio_de_carpeta(carpeta: Path) -> Estudio:
    f = carpeta / "estudio_ruta.json"
    if not f.exists():
        return ESTUDIO_BASE
    return con_celula(ESTUDIO_BASE, json.loads(f.read_text(encoding="utf-8"))["cl_celula"])


def _log2fc(carpeta: Path = None):
    """La tabla subida para esa ruta (log2fc.csv) o, si no hay, la del estudio."""
    if carpeta is not None and (carpeta / "log2fc.csv").exists():
        return carpeta / "log2fc.csv"
    return f3_config.FICHERO_LOG2FC if f3_config.FICHERO_LOG2FC and f3_config.FICHERO_LOG2FC.exists() else None


def validar_version2(datos: dict) -> tuple:
    """(célula, {gen: log2FC}) de una petición, o ValueError con lo que no vale. Un log2FC cuyo signo contradice
    la lista del gen en la ruta (negativo en un gen up) se rechaza aquí, antes de ejecutar nada."""
    celula = str(datos.get("Celula") or "").strip()
    if celula and celula not in {cl for cl, _, _ in CELULAS_DISPONIBLES}:
        raise ValueError(f"Célula no disponible: {celula!r}")
    bruto = datos.get("Log2FC") or {}
    if not isinstance(bruto, dict) or len(bruto) > MAX_GENES_LOG2FC:
        raise ValueError("La tabla de log2FC debe ser {gen: valor}, con hasta 100.000 genes.")
    fc = {}
    for gen, v in bruto.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError(f"log2FC no numérico para {gen!r}")
        fc[str(gen).strip().upper()] = float(v)
    for lista, signo in (("Genes_up", 1), ("Genes_down", -1)):
        for gen in str(datos.get(lista) or "").split("/"):
            v = fc.get(gen.strip().upper())
            if v is not None and v * signo < 0:
                raise ValueError(f"El log2FC de {gen.strip()} ({v}) contradice su lista "
                                 f"({'up' if signo > 0 else 'down'}).")
    return celula, fc


def _fase3(carpeta: Path, excel_f1: Path, excel_f2: Path):
    pares, rutas, res, abstracts = calcular(excel_f1, excel_f2, _log2fc(carpeta))
    return escribir(pares, rutas, res, abstracts, ruta=carpeta / "fase3_scoring.xlsx"), pares, rutas


def con_criterio(go_id: str, criterio: dict) -> dict:
    """Fase 3 de una ruta ya ejecutada con los signos de «Tu criterio» ({gen: "+1" | "-1" | "neutro"}). No vuelve a
    llamar al LLM: recalcula con las salidas de las Fases 1 y 2 de su carpeta. El Excel lleva el resultado con los
    cambios y, al lado, el automático (Lectura_automatica, NPS_automatico, Cambios_experto, Signo_automatico); se
    escribe en fase3_scoring_criterio.xlsx, sin pisar fase3_scoring.xlsx. Sin criterio, devuelve el automático."""
    carpeta = DIR_SALIDAS / go_id.replace(":", "_")
    excel_f1, excel_f2 = carpeta / "fase1_dataset_abstracts.xlsx", carpeta / "fase2_resultados.xlsx"
    if not (excel_f1.exists() and excel_f2.exists()):
        raise FileNotFoundError(f"No están las salidas de {go_id} en {carpeta}: vuelve a ejecutar la ruta.")
    with _con_estudio(estudio_de_carpeta(carpeta)):
        auto_p, auto_r, auto_res, auto_abs = calcular(excel_f1, excel_f2, _log2fc(carpeta))
        if criterio:
            pares, rutas, res, abstracts = calcular(excel_f1, excel_f2, _log2fc(carpeta),
                                                    criterio={(gen, go_id): s for gen, s in criterio.items()})
    if criterio:
        antes = dict(zip(auto_p["Gen"], auto_p["Signo_par"]))
        pares.insert(pares.columns.get_loc("Signo_par") + 1, "Signo_automatico", pares["Gen"].map(antes))
        auto = auto_r.set_index("GO_ID")
        i = rutas.columns.get_loc("Lectura") + 1
        rutas.insert(i, "Lectura_automatica", rutas["GO_ID"].map(auto["Lectura"]))
        rutas.insert(i + 1, "NPS_automatico", rutas["GO_ID"].map(auto["NPS"]))
        rutas.insert(i + 2, "Cambios_experto", "; ".join(
            f"{gen}: {antes.get(gen, '?')} → {s}" for gen, s in sorted(criterio.items()) if gen in antes))
        excel = escribir(pares, rutas, res, abstracts, ruta=carpeta / "fase3_scoring_criterio.xlsx")
        nombre = f"fase3_scoring_{carpeta.name}_criterio.xlsx"
    else:
        pares, rutas = auto_p, auto_r
        excel = escribir(auto_p, auto_r, auto_res, auto_abs, ruta=carpeta / "fase3_scoring.xlsx")
        nombre = f"fase3_scoring_{carpeta.name}.xlsx"
    return {"rutas": json.loads(rutas.to_json(orient="records")),
            "pares": json.loads(pares.to_json(orient="records")),
            "excel_b64": base64.b64encode(excel.read_bytes()).decode("ascii"),
            "nombre_excel": nombre}


def _texto(v) -> str:
    return "" if pd.isna(v) else str(v).strip()


def detalle(excel_f1: Path, excel_f2: Path, pares: pd.DataFrame, go_id: str):
    """Lo que la interfaz explica en lenguaje llano: un resumen de cada fase y, por gen, los artículos que leyó el
    LLM (título, signo, confianza y la frase citada) y las evidencias de GO cuando el signo sale de la anotación.
    Cada artículo lleva sus respuestas: una por subproceso de la ruta por el que se preguntó, con el peso que le da la
    Fase 3 (confianza / 100, por 0,5 si el estudio no es en humano y otro 0,5 si no es en células inmunes, y por
    FACTOR_FUENTE_GO si el artículo lo cita la anotación de GO). El artículo vota una sola vez (Cuenta marca la
    respuesta que vale), o ninguna si sus respuestas se contradicen (Se_contradice)."""
    f1 = pd.read_excel(excel_f1, sheet_name=["Con_abstract", "Triaje_polaridad"])
    con, triaje = f1["Con_abstract"], f1["Triaje_polaridad"]
    titulos = {limpiar(p): _texto(t) for p, t in zip(con["PMID"], con["Titulo"])}
    hojas = pd.read_excel(excel_f2, sheet_name=["Por_ruta", "Preguntas"])
    votos = casos_con_peso(hojas["Por_ruta"][hojas["Por_ruta"]["GO_ID"] == go_id], hojas["Preguntas"],
                           leer_fuentes_go(excel_f1))
    f2 = votos.sort_values("Confianza_final", ascending=False).drop_duplicates(["Gen", "PMID"])  # un PMID por gen
    # Un artículo vota una vez por gen (#41): la respuesta que cuenta y los artículos que se contradicen
    cuentan, se_contradicen = set(), set()
    for gen, g in votos.groupby("Gen"):
        elegidos, contradictorios = un_voto_por_articulo(g)
        cuentan |= set(elegidos.index)
        se_contradicen |= {(gen, p) for p in contradictorios}
    # Lo que respondió el modelo aunque el código lo dejara en UNKNOWN: efecto, confianza y tipo de evidencia
    preguntas = hojas["Preguntas"].copy()
    preguntas["PMID"] = preguntas["PMID"].map(limpiar)
    respuesta = {(r["Gen"], r["PMID"]): r for _, r in
                 preguntas.sort_values("Confianza_modelo", ascending=False).drop_duplicates(["Gen", "PMID"]).iterrows()}

    genes = {}
    for gen, filas in f2.groupby("Gen"):
        genes[gen] = {"articulos": [{
            "PMID": f["PMID"], "Titulo": titulos.get(f["PMID"], ""), "Signo": _texto(f["Signo_ruta"]),
            "Estado": _texto(f["Estado"]), "Motivos": _texto(f["Motivos"]),
            "Confianza": None if pd.isna(f["Confianza_final"]) else int(f["Confianza_final"]),
            "Cita": _texto(f["Cita"]),
            "Efecto_LLM": _texto(respuesta[(gen, f["PMID"])]["Efecto"]) if (gen, f["PMID"]) in respuesta else "",
            "Confianza_LLM": (None if (gen, f["PMID"]) not in respuesta
                              or pd.isna(respuesta[(gen, f["PMID"])]["Confianza_modelo"])
                              else int(respuesta[(gen, f["PMID"])]["Confianza_modelo"])),
            "Tipo_evidencia": _texto(respuesta[(gen, f["PMID"])]["Tipo_evidencia"]) if (gen, f["PMID"]) in respuesta else "",
            "Se_contradice": (gen, f["PMID"]) in se_contradicen,
            "Votos": [{"Proceso": _texto(v["Proceso"]), "Signo": _texto(v["Signo_ruta"]), "Cuenta": i in cuentan,
                       "Organismo": _texto(v["Organismo"]), "Tipo_celular": _texto(v["Tipo_celular"]),
                       "Confianza": None if pd.isna(v["Confianza_final"]) else int(v["Confianza_final"]),
                       "Peso": round(float(v["w"]), 2),
                       "Factor_GO": f3_config.FACTOR_FUENTE_GO if v["De_GO"] else None}
                      for i, v in votos[(votos["Gen"] == gen) & (votos["PMID"] == f["PMID"])].iterrows()],
        } for _, f in filas.iterrows()]}
    for _, f in triaje[triaje["GO_ID"] == go_id].iterrows():
        g = genes.setdefault(f["Gen"], {"articulos": []})
        pmids = [limpiar(p) for p in re.split(r"[;,|\s]+", _texto(f["PMIDs_signo"])) if p]
        g["GO"] = {"Evidencias": _texto(f["Evidencias_signo"]), "PMIDs": [p for p in pmids if p],
                   "Motivo": _texto(f["Motivo"])}

    origen = pares["Origen"]
    leidos = f2[~f2["Motivos"].fillna("").str.contains("no_menciona_gen")]
    resumen = {
        "fase1": {"genes": len(pares), "inmunoglobulinas": int((origen == "Ig").sum()),
                  "signo_GO": int((origen == "GO").sum()),
                  "genes_con_articulos": int(con.loc[con["GO_ID"] == go_id, "Gen"].nunique()),
                  "articulos": int(con.loc[con["GO_ID"] == go_id, "PMID"].nunique()),
                  "sin_articulos": int((pares["Motivos"].fillna("").str.contains("sin_evidencia")).sum())},
        "fase2": {"articulos_leidos": len(leidos),
                  "no_mencionan_gen": len(f2) - len(leidos),
                  "con_signo": int(leidos["Signo_ruta"].isin(["+1", "-1"]).sum()),
                  "sin_conclusion": int((~leidos["Signo_ruta"].isin(["+1", "-1", "neutro"])).sum())},
    }
    return genes, resumen


def ejecutar_ruta(ruta: dict):
    """Fases 1 -> 2 -> 3 para una ruta; el progreso y el resultado quedan en _estado."""
    carpeta = DIR_SALIDAS / ruta["GO_ID"].replace(":", "_")
    carpeta.mkdir(parents=True, exist_ok=True)
    tiempos = {}
    try:
        e = preparar_estudio(carpeta, ruta.get("Celula", ""), ruta.get("Log2FC"))
        with _con_estudio(e):
            t0 = time.time()
            _actualizar(fase=1)
            excel_f1 = _fase1(carpeta, ruta)
            tiempos["fase1"] = round(time.time() - t0)

            t0 = time.time()
            _actualizar(fase=2)
            excel_f2, llm = _fase2(carpeta, excel_f1)
            tiempos["fase2"] = round(time.time() - t0)

            t0 = time.time()
            _actualizar(fase=3)
            excel_f3, pares, rutas = _fase3(carpeta, excel_f1, excel_f2)
            tiempos["fase3"] = round(time.time() - t0)
            genes, resumen = detalle(excel_f1, excel_f2, pares, ruta["GO_ID"])

        resultado = {
            "rutas": json.loads(rutas.to_json(orient="records")),
            "pares": json.loads(pares.to_json(orient="records")),
            "genes": genes,
            "resumen": resumen,
            "llm": llm,
            "tiempos": tiempos,
            "carpeta": str(carpeta),
            "estudio": _estudio_json(e),
            "log2fc": "subida" if ruta.get("Log2FC") else ("del estudio" if _log2fc() else "ninguna"),
            "excel_b64": base64.b64encode(excel_f3.read_bytes()).decode("ascii"),
            "nombre_excel": f"fase3_scoring_{carpeta.name}.xlsx",
        }
        _actualizar(estado="terminado", fase=4, resultado=resultado)
    except Exception as exc:
        traceback.print_exc()
        _actualizar(estado="error", error=f"{type(exc).__name__}: {exc}")


@functools.lru_cache(maxsize=16)
def _comprimido(ruta: str, _modificado: float) -> bytes:
    """El fichero en gzip, una vez por versión (la fecha de modificación entra en la clave de la caché)."""
    return gzip.compress(Path(ruta).read_bytes(), 6)


class ManejadorPuente(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _responder_json(self, codigo: int, datos: dict):
        cuerpo = json.dumps(datos, default=str).encode("utf-8")
        self.send_response(codigo)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, formato, *args):
        if not self.path.startswith(("/estado", "/salud")):  # el frontend los consulta cada pocos segundos
            super().log_message(formato, *args)

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def _origen_local(self) -> bool:
        """Sin Origin (curl, el propio puente) o desde localhost: la interfaz de Vite. Otra web no puede tocar las
        claves aunque el puente responda con CORS abierto."""
        origen = self.headers.get("Origin")
        return not origen or urlparse(origen).hostname in ("localhost", "127.0.0.1", "::1")

    def _claves(self, post: bool):
        if not self._origen_local():
            if post:
                self._descartar_cuerpo()
            self._responder_json(403, {"ok": False, "error": "Las claves solo se gestionan desde la interfaz local."})
            return
        if not post:
            self._responder_json(200, {"ok": True, "proveedores": estado_claves()})
            return
        try:
            datos = self._leer_json()
        except (ValueError, UnicodeDecodeError):
            self._responder_json(400, {"ok": False, "error": "Petición mal formada."})
            return
        try:
            if not isinstance(datos, dict):
                raise ValueError("Petición mal formada.")
            proveedores = cambiar_claves(datos)
        except ValueError as exc:
            self._responder_json(400, {"ok": False, "error": str(exc)})
            return
        with _cerrojo:
            ejecutando = _estado.get("estado") == "ejecutando"
        self._responder_json(200, {"ok": True, "proveedores": proveedores, "ejecutando": ejecutando})

    def do_GET(self):
        if self.path == "/claves":
            self._claves(post=False)
            return
        if self.path == "/salud":
            self._responder_json(200, {"ok": True})
        elif self.path == "/estudio":
            self._responder_json(200, estudio())
        elif self.path == "/estado":
            with _cerrojo:
                self._responder_json(200, dict(_estado))
        elif not self._web():
            self.send_error(404)

    def _web(self) -> bool:
        """Un fichero de la interfaz construida (DIR_WEB); «/» es index.html. False si no hay interfaz construida o
        el fichero no existe o queda fuera de DIR_WEB (p. ej. con «..»)."""
        if not DIR_WEB.is_dir():
            return False
        raiz = DIR_WEB.resolve()
        relativa = unquote(urlparse(self.path).path).lstrip("/") or "index.html"
        fichero = (raiz / relativa).resolve()
        if not fichero.is_relative_to(raiz) or not fichero.is_file() or fichero.suffix.lower() not in TIPOS_WEB:
            return False
        comprimir = fichero.suffix.lower() in COMPRIMIBLES and "gzip" in self.headers.get("Accept-Encoding", "")
        cuerpo = _comprimido(str(fichero), fichero.stat().st_mtime) if comprimir else fichero.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", TIPOS_WEB[fichero.suffix.lower()])
        if comprimir:
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(cuerpo)))
        # Lo de assets/ lleva una huella en el nombre (Vite) y no cambia nunca; el resto (index.html, iconos, manifiesto)
        # se revalida cada vez, para que una versión nueva se vea sin borrar la caché del navegador
        inmutable = fichero.parent == raiz / "assets"
        self.send_header("Cache-Control", "max-age=31536000, immutable" if inmutable else "no-cache")
        self.end_headers()
        self.wfile.write(cuerpo)
        return True

    def _descartar_cuerpo(self):
        """Lee el cuerpo de una petición que se rechaza sin mirarlo: si queda sin leer, Windows corta la conexión
        (RST) y el cliente no llega a ver la respuesta (el 403 o el 404)."""
        self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def _leer_json(self) -> dict:
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8"))

    def _criterio(self):
        try:
            datos = self._leer_json()
            go_id = str(datos.get("GO_ID", "")).strip()
            criterio = {str(g).strip(): str(s).strip() for g, s in (datos.get("criterio") or {}).items()}
        except (ValueError, UnicodeDecodeError, AttributeError):
            self._responder_json(400, {"ok": False, "error": "Petición mal formada."})
            return
        if not PATRON_GO.match(go_id):
            self._responder_json(400, {"ok": False, "error": f"GO_ID no válido: {go_id!r}"})
            return
        malos = [g for g, s in criterio.items() if s not in SIGNOS_CRITERIO]
        if malos:
            self._responder_json(400, {"ok": False, "error": f"Signo no válido para {', '.join(malos)}."})
            return
        with _cerrojo:
            if _estado.get("estado") == "ejecutando" and _estado.get("GO_ID") == go_id:
                self._responder_json(409, {"ok": False, "error": f"Se está ejecutando {go_id}."})
                return
        try:
            self._responder_json(200, {"ok": True, **con_criterio(go_id, criterio)})
        except Exception as exc:
            traceback.print_exc()
            self._responder_json(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    def do_POST(self):
        if self.path == "/claves":
            self._claves(post=True)
            return
        if self.path == "/criterio":
            self._criterio()
            return
        if self.path != "/ejecutar-ruta":
            self._descartar_cuerpo()
            self.send_error(404)
            return
        try:
            datos = self._leer_json()
            ruta = {"GO_ID": str(datos.get("GO_ID", "")).strip(),
                    "Descripcion": str(datos.get("Descripcion", "")).strip(),
                    "Genes_up": str(datos.get("Genes_up") or "").strip(),
                    "Genes_down": str(datos.get("Genes_down") or "").strip()}
        except (ValueError, UnicodeDecodeError, AttributeError):
            self._responder_json(400, {"ok": False, "error": "Petición mal formada."})
            return
        try:
            ruta["Celula"], ruta["Log2FC"] = validar_version2(datos)
        except ValueError as exc:
            self._responder_json(400, {"ok": False, "error": str(exc)})
            return
        if not PATRON_GO.match(ruta["GO_ID"]):
            self._responder_json(400, {"ok": False, "error": f"GO_ID no válido: {ruta['GO_ID']!r}"})
            return
        if not (ruta["Genes_up"] or ruta["Genes_down"]):
            self._responder_json(400, {"ok": False, "error": "La ruta no tiene genes."})
            return
        with _cerrojo:
            if _estado["estado"] == "ejecutando":
                self._responder_json(409, {"ok": False, "error": f"Ya se está ejecutando {_estado['GO_ID']}."})
                return
            _estado.clear()
            _estado.update(estado="ejecutando", fase=1, GO_ID=ruta["GO_ID"], Descripcion=ruta["Descripcion"],
                           inicio=time.time())
        threading.Thread(target=ejecutar_ruta, args=(ruta,), daemon=True).start()
        self._responder_json(202, {"ok": True})


if __name__ == "__main__":
    servidor = ThreadingHTTPServer(("127.0.0.1", 8000), ManejadorPuente)
    print("Puente CU-01 activo en http://127.0.0.1:8000 (Ctrl+C para detener)")
    servidor.serve_forever()
