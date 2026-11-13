"""Puente HTTP local para ejecutar desde el frontend el pipeline completo o cada fase individual."""
import base64
import json
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import pandas as pd

CODIGO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODIGO_DIR))
sys.path.insert(0, str(CODIGO_DIR / "fase1_ingesta"))

from fase1_ingesta import main as f1_main
from fase2_inferencia import pipeline as f2_pipeline
from fase3_scoring import nps as f3_nps


def _archivo_a_b64(ruta: Path) -> str:
    return base64.b64encode(ruta.read_bytes()).decode("ascii")


class ManejadorPipeline(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _responder_json(self, codigo: int, datos: dict):
        self.send_response(codigo)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(datos, default=str).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/salud":
            self._responder_json(200, {"ok": True})
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))

        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)

                # --- EJECUCIÓN COMPLETA (FASES 1 -> 2 -> 3) ---
                if self.path == "/ejecutar-todo":
                    excel_act = tmp_path / "sel_activadas.xlsx"
                    excel_sup = tmp_path / "sel_suprimidas.xlsx"
                    pd.DataFrame(payload.get("activadas", []), columns=["ID", "Description", "geneID"]).to_excel(excel_act, index=False)
                    pd.DataFrame(payload.get("suprimidas", []), columns=["ID", "Description", "geneID"]).to_excel(excel_sup, index=False)

                    excel_f1 = Path(f1_main.ejecutar_fase_1(ruta_activadas=excel_act, ruta_suprimidas=excel_sup))
                    excel_f2 = Path(f2_pipeline.ejecutar_fase2(excel_fase1=excel_f1, solo_respaldo=True))
                    excel_f3 = Path(f3_nps.ejecutar_scoring(excel_fase1=excel_f1, excel_fase2=excel_f2))

                    df_rutas = pd.read_excel(excel_f3, sheet_name="Por_ruta").fillna("")
                    df_pares = pd.read_excel(excel_f3, sheet_name="Por_par").fillna("")

                    self._responder_json(200, {
                        "ok": True,
                        "rutas": df_rutas.to_dict(orient="records"),
                        "pares": df_pares.to_dict(orient="records"),
                        "excel_b64": _archivo_a_b64(excel_f3),
                        "nombre_excel": "fase3_scoring_completo.xlsx",
                    })
                    return

                # --- FASE 1 INDIVIDUAL ---
                if self.path == "/ejecutar-fase1":
                    excel_act = tmp_path / "f1_activadas.xlsx"
                    excel_sup = tmp_path / "f1_suprimidas.xlsx"
                    pd.DataFrame(payload.get("activadas", []), columns=["ID", "Description", "geneID"]).to_excel(excel_act, index=False)
                    pd.DataFrame(payload.get("suprimidas", []), columns=["ID", "Description", "geneID"]).to_excel(excel_sup, index=False)

                    excel_f1 = Path(f1_main.ejecutar_fase_1(ruta_activadas=excel_act, ruta_suprimidas=excel_sup))
                    df_triaje = pd.read_excel(excel_f1, sheet_name="Triaje_polaridad").fillna("")
                    df_abs = pd.read_excel(excel_f1, sheet_name="Con_abstract").fillna("")

                    self._responder_json(200, {
                        "ok": True,
                        "resumen": f"{len(df_triaje)} pares evaluados en triaje GO · {len(df_abs)} filas con abstract descargado.",
                        "preview": df_triaje.head(50).to_dict(orient="records"),
                        "excel_b64": _archivo_a_b64(excel_f1),
                        "nombre_excel": "fase1_dataset_abstracts.xlsx",
                    })
                    return

                # --- FASE 2 INDIVIDUAL ---
                if self.path == "/ejecutar-fase2":
                    excel_f1 = tmp_path / "entrada_f1.xlsx"
                    excel_f1.write_bytes(base64.b64decode(payload["excel_f1_b64"]))

                    excel_f2 = Path(f2_pipeline.ejecutar_fase2(excel_fase1=excel_f1, solo_respaldo=True))
                    df_preg = pd.read_excel(excel_f2, sheet_name="Preguntas").fillna("")

                    self._responder_json(200, {
                        "ok": True,
                        "resumen": f"{len(df_preg)} preguntas procesadas por LLM con validación de citas.",
                        "preview": df_preg.head(50).to_dict(orient="records"),
                        "excel_b64": _archivo_a_b64(excel_f2),
                        "nombre_excel": "fase2_resultados.xlsx",
                    })
                    return

                # --- FASE 3 INDIVIDUAL ---
                if self.path == "/ejecutar-fase3":
                    excel_f1 = tmp_path / "entrada_f1.xlsx"
                    excel_f2 = tmp_path / "entrada_f2.xlsx"
                    excel_f1.write_bytes(base64.b64decode(payload["excel_f1_b64"]))
                    excel_f2.write_bytes(base64.b64decode(payload["excel_f2_b64"]))

                    ruta_log2fc = None
                    if payload.get("excel_log2fc_b64"):
                        ruta_log2fc = tmp_path / "log2fc.xlsx"
                        ruta_log2fc.write_bytes(base64.b64decode(payload["excel_log2fc_b64"]))

                    excel_f3 = Path(f3_nps.ejecutar_scoring(
                        excel_fase1=excel_f1,
                        excel_fase2=excel_f2,
                        ruta_log2fc=ruta_log2fc,
                    ))
                    df_rutas = pd.read_excel(excel_f3, sheet_name="Por_ruta").fillna("")

                    self._responder_json(200, {
                        "ok": True,
                        "resumen": f"{len(df_rutas)} rutas puntuadas con Net Pathway Score.",
                        "preview": df_rutas.head(50).to_dict(orient="records"),
                        "excel_b64": _archivo_a_b64(excel_f3),
                        "nombre_excel": "fase3_scoring.xlsx",
                    })
                    return

                self.send_error(404)

        except Exception as exc:
            self._responder_json(500, {"ok": False, "error": str(exc)})


if __name__ == "__main__":
    servidor = HTTPServer(("127.0.0.1", 8000), ManejadorPipeline)
    print("Puente CU-01 activo en http://127.0.0.1:8000 (Ctrl+C para detener)")
    servidor.serve_forever()