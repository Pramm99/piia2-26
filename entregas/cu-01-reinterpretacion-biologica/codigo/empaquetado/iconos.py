"""Genera los iconos del programa y de la web a partir de icono.svg (desde codigo/: python empaquetado/iconos.py).

Cada tamaño se dibuja aparte, con Edge sin ventana, en lugar de reducir uno grande: así los de 16-48 px (barra de
tareas, escritorio) salen nítidos. Deja icono.ico (todos los tamaños), icono_<N>.png para las ventanas del programa y
del instalador (se elige el más cercano al escalado de Windows) y, en fase4_frontend/public, favicon.ico e iconos/ con
un PNG por tamaño para la pestaña del navegador. En la barra de tareas, el lanzador le pone a la ventana icono.ico
(barra_tareas.py): con solo el favicon, Edge lo reescalaba y salía borroso.
Hace falta Pillow (solo aquí: pip install pillow). Los ficheros generados se versionan.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
SVG = AQUI / "icono.svg"
TAMANOS_ICO = [16, 20, 24, 32, 40, 48, 64, 128, 256]
TAMANOS_PNG = [64, 80, 96, 128]  # logo de las ventanas a 100, 125, 150 y 200 % de escalado
TAMANOS_WEB = [16, 24, 32, 48, 64, 96, 192, 256]  # los <link rel="icon"> de fase4_frontend/index.html


def edge() -> Path:
    for base in (r"C:\Program Files (x86)", r"C:\Program Files"):
        exe = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        if exe.exists():
            return exe
    sys.exit("Hace falta Microsoft Edge para dibujar el SVG")


def dibujar(tam: int, carpeta: Path) -> Image.Image:
    pagina = carpeta / f"p{tam}.html"
    pagina.write_text(f"<html><body style='margin:0;background:transparent'><img src='{SVG.as_uri()}' width={tam} "
                      f"height={tam} style='display:block'></body></html>", encoding="utf-8")
    png = carpeta / f"i{tam}.png"
    for intento in range(3):  # Edge sin ventana se cuelga muy de vez en cuando: se corta y se repite
        try:
            subprocess.run([str(edge()), "--headless", "--disable-gpu", "--hide-scrollbars",
                            "--force-device-scale-factor=1", "--default-background-color=00000000",
                            f"--window-size={tam},{tam}", f"--user-data-dir={carpeta / f'perfil{tam}_{intento}'}",
                            f"--screenshot={png}", pagina.as_uri()], capture_output=True, check=True, timeout=60)
            return Image.open(png).convert("RGBA")
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            if intento == 2:
                raise


def main():
    with tempfile.TemporaryDirectory() as tmp:
        imagenes = {t: dibujar(t, Path(tmp)) for t in sorted(set(TAMANOS_ICO + TAMANOS_PNG + TAMANOS_WEB))}
    grande = imagenes[256]
    grande.save(AQUI / "icono.ico", sizes=[(t, t) for t in TAMANOS_ICO],
                append_images=[imagenes[t] for t in TAMANOS_ICO if t != 256])
    for t in TAMANOS_PNG:
        imagenes[t].save(AQUI / f"icono_{t}.png")
    publico = AQUI.parent / "fase4_frontend" / "public"
    shutil.copy2(AQUI / "icono.ico", publico / "favicon.ico")
    (publico / "favicon.svg").unlink(missing_ok=True)
    shutil.rmtree(publico / "iconos", ignore_errors=True)
    (publico / "iconos").mkdir()
    for t in TAMANOS_WEB:
        imagenes[t].save(publico / "iconos" / f"icono-{t}.png")
    print("icono.ico, " + ", ".join(f"icono_{t}.png" for t in TAMANOS_PNG) + ", favicon.ico e iconos/ de la web")


if __name__ == "__main__":
    main()
