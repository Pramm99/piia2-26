"""Lo que comparten el lanzador y el instalador: nombre, versión, rutas de instalación y los colores de la interfaz."""
import ctypes
import math
import os
import sys
import time
import tkinter as tk
from pathlib import Path

NOMBRE = "PathwayPulse"
VERSION = "1.1.1"
EDITOR = "Equipo CU-01 · PIIA2 (USC)"
EXE_APP = f"{NOMBRE}.exe"
EXE_DESINSTALAR = "Desinstalar.exe"
CLAVE_REGISTRO = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\PathwayPulse"
# Instalación por usuario, como VS Code o Discord: no pide permisos de administrador y la carpeta se puede escribir
DIR_INSTALACION = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Programs" / NOMBRE

# Los mismos colores que la web (fase4_frontend/src/index.css, tema oscuro)
FONDO = "#020617"
PANEL = "#0f172a"
BORDE = "#1e293b"
TEXTO = "#f8fafc"
SUAVE = "#94a3b8"
TENUE = "#64748b"
ACENTO = "#14b8a6"
ACENTO_CLARO = "#2dd4bf"
ACENTO_HOVER = "#0d9488"
OK = "#34d399"
ERROR = "#f87171"
FUENTE = "Segoe UI"


def recurso(nombre: str) -> Path:
    """Un fichero que va dentro del ejecutable (PyInstaller lo deja en sys._MEIPASS) o, sin empaquetar, aquí al lado."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / nombre


def nitidez():
    """Sin esto, Windows con el escalado al 125-150 % estira las ventanas de Tk y se ven borrosas."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def escala(raiz) -> float:
    return raiz.winfo_fpixels("1i") / 96


def imagen(s: float):
    """El logo dibujado al tamaño más cercano a 64 px con el escalado de Windows (iconos.py los genera; reducir uno
    grande lo emborrona), o None si no se puede abrir: sin logo, la ventana sale igual."""
    tam = min((64, 80, 96, 128), key=lambda t: abs(t - 64 * s))
    try:
        return tk.PhotoImage(file=str(recurso(f"icono_{tam}.png")))
    except tk.TclError:
        return None


def aviso_de_error(titulo: str, texto: str):
    """Un fallo inesperado, en una ventana de aviso y en palabras de la persona (sin el volcado de Python)."""
    from tkinter import messagebox
    raiz = tk.Tk()
    raiz.withdraw()
    messagebox.showerror(titulo, texto, parent=raiz)
    raiz.destroy()


def centrar(ventana, ancho: int, alto: int):
    ventana.update_idletasks()
    x = (ventana.winfo_screenwidth() - ancho) // 2
    y = (ventana.winfo_screenheight() - alto) // 3
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")


# --- Piezas de interfaz (Tk) con el aspecto de la web ---

def boton(padre, texto: str, comando, principal: bool = True, s: float = 1.0):
    """Un botón plano con los colores de la web (Label: tk.Button en Windows ignora parte de los colores)."""
    fondo, hover, color = (ACENTO, ACENTO_HOVER, FONDO) if principal else (BORDE, "#334155", TEXTO)
    b = tk.Label(padre, text=texto, bg=fondo, fg=color, font=(FUENTE, 10, "bold" if principal else "normal"),
                 padx=int(18 * s), pady=int(7 * s), cursor="hand2")
    b.bind("<Enter>", lambda e: b.config(bg=hover))
    b.bind("<Leave>", lambda e: b.config(bg=fondo))
    b.bind("<Button-1>", lambda e: comando())
    return b


class Barra:
    """Barra de progreso redondeada en un Canvas: con valor (0-1) o, con indeterminada(), un tramo que va y viene."""

    def __init__(self, padre, ancho: int, alto: int, fondo: str = PANEL):
        self.ancho, self.alto = ancho, alto
        self.c = tk.Canvas(padre, width=ancho, height=alto, bg=fondo, highlightthickness=0, bd=0)
        r = alto / 2
        self.c.create_line(r, r, ancho - r, r, width=alto, capstyle="round", fill=BORDE)
        self.tramo = self.c.create_line(r, r, r, r, width=alto, capstyle="round", fill=ACENTO_CLARO)
        self._t0 = None

    def valor(self, fraccion: float):
        self._t0 = None
        r = self.alto / 2
        fin = r + max(0.0, min(1.0, fraccion)) * (self.ancho - 2 * r)
        self.c.coords(self.tramo, r, r, fin, r)

    def indeterminada(self):
        self._t0 = time.time()
        self._animar()

    def _animar(self):
        if self._t0 is None:
            return
        r, largo = self.alto / 2, self.ancho * 0.3
        f = (math.sin((time.time() - self._t0) * 2.2) + 1) / 2  # 0 -> 1 -> 0, suave en los extremos
        x = r + f * (self.ancho - 2 * r - largo)
        self.c.coords(self.tramo, x, r, x + largo, r)
        self.c.after(16, self._animar)
