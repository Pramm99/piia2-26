"""CU-01 PathScore Studio: el programa de doble clic (la Fase 4 sin terminales, ni Python ni Node instalados).

Arranca el puente (fase4_frontend/api_puente.py) dentro de este mismo proceso, que además sirve la interfaz ya
construida, y la abre en una ventana propia: Microsoft Edge, que viene con Windows, en modo aplicación (sin pestañas
ni barra de direcciones) y con un perfil solo para el programa. Al cerrar esa ventana se apaga todo. Si no hay Edge ni
Chrome, la abre en el navegador por defecto y deja una ventanita para cerrar el programa.

Empaquetado (construir.py), el código de las fases va al lado del ejecutable, en codigo/, tal cual está en el
repositorio: así codigo/data (cachés y registro del LLM) y codigo/.env (claves) funcionan igual que siempre. Sin
empaquetar, `python empaquetado/lanzador.py` desde codigo/ usa este mismo repositorio.
"""
import importlib
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path
from tkinter import messagebox

import barra_tareas
from comun import (BORDE, FUENTE, NOMBRE, PANEL, SUAVE, TENUE, TEXTO, VERSION, Barra, aviso_de_error, boton, centrar,
                   escala, imagen, nitidez, recurso, tk)

# Un puerto alto y fijo (fijo para saber si el programa ya está abierto), no el 8000 del puente de desarrollo: así no
# chocan, y en el equipo de pruebas (con Avast) las descargas grandes en el 8000 se cortaban a veces y en este no. La
# web compilada llama al puente con rutas relativas, así que vale cualquier puerto.
PUERTO = 47613
URL = f"http://127.0.0.1:{PUERTO}/"
# La web pide /salud cada 5 s. Minimizada, el navegador puede espaciarlo hasta una vez por minuto: sin ventana de Edge
# que vigilar, el programa se apaga tras SIN_LATIDO segundos sin ninguna.
SIN_LATIDO = 180
ARRANQUE_MINIMO = 8  # s: si Edge termina antes, es que pasó la ventana a otro Edge abierto y se vigila el latido


def dir_codigo() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "codigo"
    return Path(__file__).resolve().parents[1]


def dir_app() -> Path:
    """Registro y perfil del navegador del programa: dentro de codigo/data, que no se versiona."""
    carpeta = dir_codigo() / "data" / "app"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _dependencias_de_las_fases():  # pragma: no cover
    """No se llama nunca: está para que PyInstaller meta en el ejecutable lo que importan las fases, que van como
    código fuente en codigo/ y no las analiza."""
    import base64, collections, csv, dataclasses, datetime, functools, gzip, hashlib, html, json, math  # noqa
    import re, typing, unicodedata, uuid, urllib.error, urllib.parse, xml.etree.ElementTree  # noqa
    import numpy, openpyxl, pandas, requests, urllib3  # noqa


def navegador_app():
    """Edge (o Chrome) para abrir la interfaz como una aplicación; None si no hay ninguno."""
    candidatos = []
    for var in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(var)
        if base:
            candidatos += [Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                           Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"]
    return next((c for c in candidatos if c.is_file()), None)


def abrir_ventana():
    """Abre la interfaz; devuelve el proceso del navegador, o None si se abrió en el navegador por defecto."""
    exe = navegador_app()
    if exe is None:
        webbrowser.open(URL)
        return None
    return subprocess.Popen([str(exe), f"--app={URL}", f"--user-data-dir={dir_app() / 'navegador'}",
                             "--no-first-run", "--no-default-browser-check", "--disable-sync", "--start-maximized"])


def puerto_ocupado() -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", PUERTO)) == 0


def es_nuestro() -> bool:
    """¿Lo que escucha en el puerto es este programa (con la interfaz)? Si es así, basta con abrir otra ventana."""
    try:
        with urllib.request.urlopen(URL, timeout=3) as r:
            return "PathScore" in r.read(4096).decode("utf-8", "replace")
    except OSError:
        return False


class Lanzador:
    def __init__(self):
        nitidez()
        self.raiz = tk.Tk()
        self.raiz.withdraw()
        self.raiz.title(NOMBRE)
        try:
            self.raiz.iconbitmap(default=str(recurso("icono.ico")))
        except tk.TclError:
            pass
        self.s = escala(self.raiz)
        self.cola = queue.Queue()
        self.servidor = None
        self.proceso = None
        self.abierto_en = 0.0
        self.latido = 0.0
        self.cerrando = False
        self.marcadas = set()  # ventanas de Edge que ya tienen la identidad del programa en la barra de tareas
        self._pantalla_de_carga()

    # --- Pantalla de carga ---
    def _pantalla_de_carga(self):
        s = self.s
        ancho, alto = int(440 * s), int(300 * s)
        v = self.carga = tk.Toplevel(self.raiz, bg=BORDE)
        v.overrideredirect(True)  # sin marco de ventana: una tarjeta, como la web
        v.attributes("-topmost", True)
        caja = tk.Frame(v, bg=PANEL)
        caja.place(x=1, y=1, width=ancho - 2, height=alto - 2)
        self.logo = imagen(s)
        if self.logo:
            tk.Label(caja, image=self.logo, bg=PANEL).pack(pady=(int(30 * s), int(12 * s)))
        else:
            tk.Frame(caja, bg=PANEL, height=int(60 * s)).pack()
        tk.Label(caja, text=NOMBRE, bg=PANEL, fg=TEXTO, font=(FUENTE, 17, "bold")).pack()
        tk.Label(caja, text="Reinterpretación de rutas biológicas · células NK", bg=PANEL, fg=SUAVE,
                 font=(FUENTE, 10)).pack(pady=(int(2 * s), int(20 * s)))
        self.barra = Barra(caja, int(300 * s), max(4, int(6 * s)))
        self.barra.c.pack()
        self.barra.indeterminada()
        self.aviso = tk.Label(caja, text="Abriendo…", bg=PANEL, fg=TENUE, font=(FUENTE, 9))
        self.aviso.pack(pady=(int(10 * s), 0))
        tk.Label(caja, text=f"versión {VERSION}", bg=PANEL, fg="#334155", font=(FUENTE, 8)).place(
            relx=1, rely=1, x=-int(10 * s), y=-int(6 * s), anchor="se")
        centrar(v, ancho, alto)

    # --- Arranque (en un hilo: la pantalla sigue animándose) ---
    def _arrancar(self):
        try:
            if puerto_ocupado():
                if es_nuestro():
                    self.cola.put(("ya_abierto", None))
                else:
                    self.cola.put(("error", f"Otro programa está usando el puerto {PUERTO}, que necesita {NOMBRE}.\n\n"
                                            "Ciérralo (o reinicia el ordenador) y vuelve a abrir el programa."))
                return
            self.cola.put(("aviso", "Preparando el motor de análisis…"))
            codigo = dir_codigo()
            if not (codigo / "fase4_frontend" / "api_puente.py").is_file():
                raise FileNotFoundError(f"No está el código del programa en {codigo}. Vuelve a instalarlo.")
            sys.path.insert(0, str(codigo))
            api = importlib.import_module("fase4_frontend.api_puente")
            lanzador = self

            class Manejador(api.ManejadorPuente):
                def do_GET(self):
                    if self.path == "/salud":
                        lanzador.latido = time.time()
                    super().do_GET()

            self.servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
            threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
            self.cola.put(("aviso", "Abriendo la ventana…"))
            self.cola.put(("listo", None))
        except Exception as exc:
            traceback.print_exc()
            self.cola.put(("error", f"No se pudo arrancar {NOMBRE}.\n\n{exc}\n\n"
                                    f"Detalles en {dir_app() / 'registro.log'}"))

    def _atender(self):
        try:
            while True:
                tipo, dato = self.cola.get_nowait()
                if tipo == "aviso":
                    self.aviso.config(text=dato)
                elif tipo == "listo":
                    self.proceso = abrir_ventana()
                    self.abierto_en = self.latido = time.time()
                    if self.proceso is None:
                        self._ventana_sin_edge()
                    self.raiz.after(1500, self.carga.destroy)  # lo justo para que aparezca la ventana
                    self.raiz.after(2000, self._vigilar)
                elif tipo == "ya_abierto":
                    abrir_ventana()
                    self.raiz.after(1500, self.raiz.destroy)
                elif tipo == "error":
                    self.carga.destroy()
                    messagebox.showerror(NOMBRE, dato)
                    self.cerrar()
        except queue.Empty:
            pass
        if not self.cerrando:
            self.raiz.after(50, self._atender)

    # --- Mientras está abierto ---
    def _barra_de_tareas(self):
        """Botón propio en la barra de tareas, con el nombre y el icono nítido del programa (barra_tareas.py)."""
        exe = Path(sys.executable) if getattr(sys, "frozen", False) else Path(__file__)
        for hwnd in barra_tareas.ventanas(self.proceso.pid, NOMBRE):
            barra_tareas.poner_identidad(hwnd, NOMBRE, exe, recurso("icono.ico"), self.marcadas)

    def _vigilar(self):
        if self.cerrando:
            return
        ahora = time.time()
        if self.proceso is not None and self.proceso.poll() is None:
            self._barra_de_tareas()
        if self.proceso is not None and self.proceso.poll() is not None:
            if ahora - self.abierto_en > ARRANQUE_MINIMO:
                self.cerrar()  # se cerró la ventana
                return
            self.proceso = None  # la ventana la lleva otro Edge: se vigila el latido
        if self.proceso is None and ahora - self.latido > SIN_LATIDO:
            self.cerrar()
            return
        self.raiz.after(1000, self._vigilar)

    def _ventana_sin_edge(self):
        """Sin Edge ni Chrome: la interfaz va en el navegador por defecto y esta ventanita apaga el programa."""
        s = self.s
        v = tk.Toplevel(self.raiz, bg=PANEL, padx=int(24 * s), pady=int(20 * s))
        v.title(NOMBRE)
        v.resizable(False, False)
        v.protocol("WM_DELETE_WINDOW", self.cerrar)
        tk.Label(v, text=f"{NOMBRE} está abierto en tu navegador", bg=PANEL, fg=TEXTO,
                 font=(FUENTE, 12, "bold")).pack(anchor="w")
        tk.Label(v, text="Deja esta ventana abierta mientras lo uses. Al cerrarla, el programa se apaga.",
                 bg=PANEL, fg=SUAVE, font=(FUENTE, 9), wraplength=int(380 * s), justify="left").pack(
            anchor="w", pady=(int(4 * s), int(16 * s)))
        fila = tk.Frame(v, bg=PANEL)
        fila.pack(anchor="e")
        boton(fila, "Abrir otra vez", lambda: webbrowser.open(URL), principal=False, s=s).pack(side="left")
        boton(fila, "Cerrar el programa", self.cerrar, s=s).pack(side="left", padx=(int(8 * s), 0))
        centrar(v, int(460 * s), int(160 * s))

    def cerrar(self):
        if self.cerrando:
            return
        self.cerrando = True
        if self.servidor is not None:
            self.servidor.shutdown()
            self.servidor.server_close()
        self.raiz.destroy()

    def ejecutar(self):
        threading.Thread(target=self._arrancar, daemon=True).start()
        self.raiz.after(50, self._atender)
        self.raiz.mainloop()


def main():
    # Sin consola (el .exe), los print de las fases van al registro; el puente reconfigura stdout y necesita uno
    if getattr(sys, "frozen", False) or sys.stdout is None:
        registro = open(dir_app() / "registro.log", "w", encoding="utf-8", errors="replace", buffering=1)
        sys.stdout = sys.stderr = registro
    print(f"{NOMBRE} {VERSION} · {time.strftime('%Y-%m-%d %H:%M:%S')} · código en {dir_codigo()}")
    barra_tareas.identidad_del_proceso()
    try:
        Lanzador().ejecutar()
    except Exception as exc:
        traceback.print_exc()
        aviso_de_error(NOMBRE, f"No se pudo abrir {NOMBRE}.\n\n{exc}\n\nVuelve a intentarlo; si sigue fallando, "
                               f"reinstálalo. Detalles en {dir_app() / 'registro.log'}")
    os._exit(0)  # por si queda algún hilo de una ruta a medias: el programa se cierra igualmente


if __name__ == "__main__":
    main()
