"""Construye el programa de escritorio y su instalador. Desde codigo/:

    python empaquetado/construir.py [--sin-datos-cimus]

Deja en empaquetado/salida/ (no se versiona):
  PathwayPulse/               el programa, en una carpeta que también funciona sin instalar
  Instalar PathwayPulse.exe   el instalador: un único fichero para repartir

Pasos: interfaz (npm run build) → lanzador con PyInstaller → código y datos al lado → desinstalador → app.zip →
instalador. Necesita Node.js y, en el mismo Python que tiene requirements.txt, `pip install pyinstaller`.

Lleva las cachés de la Fase 1 y el registro de respuestas del LLM de codigo/data, para que las rutas ya analizadas
salgan al momento y sin clave; nunca codigo/.env, y se para si encuentra algo con forma de clave en lo que va a
empaquetar. La tabla de log2FC de CIMUS (tools_cimus/NK_cells_DESeq2_results.xlsx) no es pública: con
--sin-datos-cimus no la lleva (y la interfaz no da el NPS pesado por log2FC).
"""
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from comun import EXE_APP, NOMBRE, VERSION

AQUI = Path(__file__).resolve().parent
CODIGO = AQUI.parent
SALIDA = AQUI / "salida"
TEMPORAL = SALIDA / "build"
APP = SALIDA / NOMBRE
INSTALADOR = f"Instalar {NOMBRE}"

# Lo que necesitan las fases para ejecutar una ruta (el resto de codigo/ son pruebas, evaluación o salidas)
CODIGO_FUENTE = ["fase1_ingesta", "fase2_inferencia", "fase3_scoring"]
DATOS = ["go-basic.obo", "goa_human.gaf.gz", "hgnc_inmunoglobulinas.json", "uniprot_inmunoglobulinas.json",
         "respuestas_llm.jsonl", "cache_abstracts.json", "cache_epmc_busquedas.json", "cache_gene2pubmed.json",
         "cache_mygene.json", "cache_nombres_proteina.json", "cache_uniprot.json"]
EXCELS_RUTAS = ["NK_rutas_activadas_GO.xlsx", "NK_rutas_suprimidas_GO.xlsx"]
LOG2FC = "NK_cells_DESeq2_results.xlsx"
# Claves de Gemini, Groq y Cerebras (AGENTS.md, regla 3)
PATRON_CLAVE = re.compile(rb"AIza[0-9A-Za-z_-]{35}|gsk_[0-9A-Za-z]{40,}|csk-[0-9A-Za-z]{20,}|AQ\.[0-9A-Za-z_-]{30,}")


def paso(texto):
    print(f"\n=== {texto}", flush=True)


def ejecutar(orden, **kw):
    print("  $", " ".join(str(o) for o in orden), flush=True)
    subprocess.run([str(o) for o in orden], check=True, **kw)


def pyinstaller(script, nombre, *opciones):
    ejecutar([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--log-level", "WARN",
              "--name", nombre, "--icon", AQUI / "icono.ico",
              *[a for png in sorted(AQUI.glob("icono_*.png")) for a in ("--add-data", f"{png};.")],
              "--add-data", f"{AQUI / 'icono.ico'};.",
              "--distpath", TEMPORAL / "dist", "--workpath", TEMPORAL / "work", "--specpath", TEMPORAL,
              "--exclude-module", "PIL", "--exclude-module", "pytest", "--exclude-module", "PyInstaller",
              *opciones, AQUI / script], cwd=AQUI)


def copiar_codigo(destino: Path, con_log2fc: bool):
    for carpeta in CODIGO_FUENTE:
        for f in (CODIGO / carpeta).rglob("*"):
            if f.is_file() and "__pycache__" not in f.parts and f.suffix not in (".xlsx", ".pyc"):
                (destino / f.relative_to(CODIGO)).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, destino / f.relative_to(CODIGO))
    puente = destino / "fase4_frontend"
    puente.mkdir(parents=True)
    shutil.copy2(CODIGO / "fase4_frontend" / "api_puente.py", puente)
    shutil.copytree(CODIGO / "fase4_frontend" / "dist", puente / "dist")
    (destino / "tools_cimus").mkdir()
    for nombre in EXCELS_RUTAS + ([LOG2FC] if con_log2fc else []):
        if (CODIGO / "tools_cimus" / nombre).exists():
            shutil.copy2(CODIGO / "tools_cimus" / nombre, destino / "tools_cimus")
        elif nombre != LOG2FC:
            sys.exit(f"Falta tools_cimus/{nombre}")
    (destino / "data").mkdir()
    for nombre in DATOS:
        if (CODIGO / "data" / nombre).exists():
            shutil.copy2(CODIGO / "data" / nombre, destino / "data")
        else:
            print(f"  (sin data/{nombre}: el programa lo descargará o lo creará cuando haga falta)")


def sin_claves(carpeta: Path):
    for f in carpeta.rglob("*"):
        if f.is_file() and f.name == ".env":
            sys.exit(f"PARADO: {f} no puede ir en el programa")
        if f.is_file() and f.suffix in (".py", ".json", ".jsonl", ".txt", ".js", ".html", ".tsv", ".md"):
            if PATRON_CLAVE.search(f.read_bytes()):
                sys.exit(f"PARADO: {f} tiene algo con forma de clave de API; no se empaqueta")


def main():
    con_log2fc = "--sin-datos-cimus" not in sys.argv[1:]
    web = CODIGO / "fase4_frontend"
    paso("1/6 Interfaz (npm run build)")
    if not (web / "node_modules").exists():
        ejecutar(["npm.cmd", "ci"], cwd=web)
    ejecutar(["npm.cmd", "run", "build"], cwd=web)

    paso("2/6 Programa (PyInstaller)")
    shutil.rmtree(SALIDA, ignore_errors=True)
    pyinstaller("lanzador.py", NOMBRE)
    shutil.move(TEMPORAL / "dist" / NOMBRE, APP)

    paso("3/6 Código de las fases, interfaz y datos")
    copiar_codigo(APP / "codigo", con_log2fc)
    ejemplos = APP / "Excels de ejemplo"
    ejemplos.mkdir()
    for nombre in EXCELS_RUTAS:
        shutil.copy2(CODIGO / "tools_cimus" / nombre, ejemplos)
    sin_claves(APP)

    paso("4/6 Desinstalador")
    pyinstaller("instalador.py", "Desinstalar", "--onefile")
    shutil.move(TEMPORAL / "dist" / "Desinstalar.exe", APP / "Desinstalar.exe")

    paso("5/6 Paquete (app.zip)")
    paquete = TEMPORAL / "app.zip"
    with zipfile.ZipFile(paquete, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(APP.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(APP).as_posix())
    print(f"  {paquete.stat().st_size / 1e6:.0f} MB comprimido")

    paso("6/6 Instalador")
    pyinstaller("instalador.py", INSTALADOR, "--onefile", "--add-data", f"{paquete};.")
    shutil.move(TEMPORAL / "dist" / f"{INSTALADOR}.exe", SALIDA / f"{INSTALADOR}.exe")
    shutil.rmtree(TEMPORAL, ignore_errors=True)

    tam = sum(f.stat().st_size for f in APP.rglob("*") if f.is_file()) / 1e6
    print(f"\nListo · versión {VERSION}" + ("" if con_log2fc else " · sin la tabla de log2FC de CIMUS"))
    print(f"  Programa:    {APP / EXE_APP}  ({tam:.0f} MB en total)")
    print(f"  Instalador:  {SALIDA / (INSTALADOR + '.exe')}  "
          f"({(SALIDA / (INSTALADOR + '.exe')).stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
