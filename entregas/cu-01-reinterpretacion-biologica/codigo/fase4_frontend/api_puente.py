"""Puente HTTP local entre el frontend y las Fases 1 -> 2 -> 3, para una ruta cada vez.

Desde codigo/: python fase4_frontend/api_puente.py (escucha en http://127.0.0.1:8000).

  GET  /salud           -> {"ok": true}
  GET  /rutas           -> rutas de los dos Excels de CIMUS (tools_cimus/), juntadas por GO_ID
  POST /ejecutar-ruta   -> {"GO_ID", "Descripcion", "Genes_up", "Genes_down"}: lanza las tres fases seguidas
  GET  /estado          -> fase en curso y, al terminar, el resultado (Por_ruta, Por_par y el Excel de la Fase 3)

La ejecución va en un hilo y el frontend consulta /estado, porque en frío tarda unos minutos. Solo hay una a la
vez. Cada ruta escribe sus ficheros en codigo/data/frontend/<GO_ID>/, así que no pisa las salidas del Excel
completo; las cachés de la Fase 1 y el registro de respuestas del LLM (codigo/data/) son los de siempre, de modo
que una ruta ya consultada no vuelve a gastar llamadas.
"""
import base64
import json
import re
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Tuple

import pandas as pd

CODIGO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODIGO_DIR))
sys.path.insert(0, str(CODIGO_DIR / "fase1_ingesta"))  # la Fase 1 usa imports planos

# Las fases imprimen emojis: en la consola de Windows (cp1252) fallaría el print
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import config as f1_config  # noqa: E402
import entrada_excel  # noqa: E402
import main as f1_main  # noqa: E402
import salida as f1_salida  # noqa: E402
from fase2_inferencia.__main__ import PRINCIPAL, SECUNDARIO  # noqa: E402
from fase2_inferencia.cliente import MODELOS, ClienteOpenAICompatible  # noqa: E402
from fase2_inferencia.limpieza import normalizar_pmid as limpiar  # noqa: E402
from fase2_inferencia.pipeline import ejecutar_fase2  # noqa: E402
from fase3_scoring import config as f3_config  # noqa: E402
from fase3_scoring.nps import COLUMNAS_FASE2, calcular, escribir  # noqa: E402

DIR_SALIDAS = CODIGO_DIR / "data" / "frontend"
PATRON_GO = re.compile(r"^GO:\d{7}$")
COLUMNAS_CIMUS = ["ID", "Description", "geneID"]

_cerrojo = threading.Lock()
_estado = {"estado": "libre"}  # libre | ejecutando | terminado | error


def _actualizar(**cambios):
    with _cerrojo:
        _estado.update(cambios)


def rutas_cimus():
    """Rutas de los dos Excels de CIMUS juntadas por GO_ID (una ruta puede estar en las dos listas)."""
    rutas = {}
    for lista, fichero in (("Genes_up", f1_config.EXCEL_ACTIVADAS), ("Genes_down", f1_config.EXCEL_SUPRIMIDAS)):
        for _, fila in entrada_excel.leer_tabla(fichero).iterrows():
            go_id = str(fila["ID"]).strip()
            r = rutas.setdefault(go_id, {"GO_ID": go_id, "Descripcion": str(fila["Description"]).strip(),
                                         "Genes_up": "", "Genes_down": ""})
            r[lista] = str(fila["geneID"]).strip()
    return sorted(rutas.values(), key=lambda r: r["GO_ID"])


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
    """Fase 2 con los modelos del ADR-005: Gemini y gpt-oss solo como respaldo."""
    salida_f2 = carpeta / "fase2_resultados.xlsx"
    salida_f2.unlink(missing_ok=True)
    clientes = [ClienteOpenAICompatible(MODELOS[n]) for n in (PRINCIPAL, SECUNDARIO)]
    _, _, resumen, _ = ejecutar_fase2(str(excel_f1), clientes, salida=salida_f2)
    if not salida_f2.exists():  # ningún par llegó al LLM: la Fase 3 necesita igualmente las hojas
        with pd.ExcelWriter(salida_f2) as w:
            for hoja, columnas in COLUMNAS_FASE2.items():
                pd.DataFrame(columns=list(columnas)).to_excel(w, sheet_name=hoja, index=False)
    tokens = sum(t["entrada"] + t["salida"] for t in resumen.tokens.values())
    return salida_f2, {"llamadas": resumen.llamadas, "reutilizadas": resumen.reutilizadas,
                       "pendientes": resumen.pendientes, "tokens": tokens}


def _fase3(carpeta: Path, excel_f1: Path, excel_f2: Path):
    log2fc = f3_config.FICHERO_LOG2FC if f3_config.FICHERO_LOG2FC.exists() else None
    pares, rutas, res, abstracts = calcular(excel_f1, excel_f2, log2fc)
    return escribir(pares, rutas, res, abstracts, ruta=carpeta / "fase3_scoring.xlsx"), pares, rutas


def _texto(v) -> str:
    return "" if pd.isna(v) else str(v).strip()


def detalle(excel_f1: Path, excel_f2: Path, pares: pd.DataFrame, go_id: str):
    """Lo que la interfaz explica en lenguaje llano: un resumen de cada fase y, por gen, los artículos que leyó el
    LLM (título, signo, confianza y la frase citada) y las evidencias de GO cuando el signo sale de la anotación."""
    f1 = pd.read_excel(excel_f1, sheet_name=["Con_abstract", "Triaje_polaridad"])
    con, triaje = f1["Con_abstract"], f1["Triaje_polaridad"]
    titulos = {limpiar(p): _texto(t) for p, t in zip(con["PMID"], con["Titulo"])}
    f2 = pd.read_excel(excel_f2, sheet_name="Por_ruta")
    f2 = f2[f2["GO_ID"] == go_id].copy()
    f2["PMID"] = f2["PMID"].map(limpiar)
    f2 = f2.sort_values("Confianza_final", ascending=False).drop_duplicates(["Gen", "PMID"])  # un PMID por gen

    genes = {}
    for gen, filas in f2.groupby("Gen"):
        genes[gen] = {"articulos": [{
            "PMID": f["PMID"], "Titulo": titulos.get(f["PMID"], ""), "Signo": _texto(f["Signo_ruta"]),
            "Estado": _texto(f["Estado"]), "Motivos": _texto(f["Motivos"]),
            "Confianza": None if pd.isna(f["Confianza_final"]) else int(f["Confianza_final"]),
            "Cita": _texto(f["Cita"]),
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
            "excel_b64": base64.b64encode(excel_f3.read_bytes()).decode("ascii"),
            "nombre_excel": f"fase3_scoring_{carpeta.name}.xlsx",
        }
        _actualizar(estado="terminado", fase=4, resultado=resultado)
    except Exception as exc:
        traceback.print_exc()
        _actualizar(estado="error", error=f"{type(exc).__name__}: {exc}")


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

    def do_GET(self):
        if self.path == "/salud":
            self._responder_json(200, {"ok": True})
        elif self.path == "/rutas":
            try:
                self._responder_json(200, {"ok": True, "rutas": rutas_cimus()})
            except Exception as exc:
                self._responder_json(500, {"ok": False, "error": f"No se pudieron leer los Excels de CIMUS: {exc}"})
        elif self.path == "/estado":
            with _cerrojo:
                self._responder_json(200, dict(_estado))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/ejecutar-ruta":
            self.send_error(404)
            return
        try:
            datos = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8"))
            ruta = {"GO_ID": str(datos.get("GO_ID", "")).strip(),
                    "Descripcion": str(datos.get("Descripcion", "")).strip(),
                    "Genes_up": str(datos.get("Genes_up") or "").strip(),
                    "Genes_down": str(datos.get("Genes_down") or "").strip()}
        except (ValueError, UnicodeDecodeError):
            self._responder_json(400, {"ok": False, "error": "Petición mal formada."})
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
