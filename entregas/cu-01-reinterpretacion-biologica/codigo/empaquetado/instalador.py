"""Instalador y desinstalador de PathwayPulse, con un asistente de tres pantallas.

Instala solo para el usuario, en %LOCALAPPDATA%\\Programs, como VS Code o Discord: no pide permisos de administrador.
Crea los accesos directos del escritorio y del menú Inicio y registra el programa en «Aplicaciones instaladas» de
Windows, desde donde se desinstala. Al actualizar conserva codigo/data (cachés, registro del LLM, resultados) y
codigo/.env (las claves).

El mismo código hace de desinstalador (Desinstalar.exe en la carpeta del programa): sin el paquete app.zip dentro, o
con --desinstalar, desinstala. construir.py genera los dos ejecutables.
"""
import ctypes
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import winreg
import zipfile
from pathlib import Path

from comun import (ACENTO, ACENTO_CLARO, BORDE, CLAVE_REGISTRO, DIR_INSTALACION, EDITOR, ERROR, EXE_APP,
                   EXE_DESINSTALAR, FONDO, FUENTE, NOMBRE, PANEL, SUAVE, TENUE, TEXTO, VERSION, Barra, aviso_de_error,
                   boton, centrar, escala, imagen, nitidez, recurso, tk)

PAQUETE = recurso("app.zip")
SIN_VENTANA = subprocess.CREATE_NO_WINDOW
# Lo de la persona: se conserva al actualizar (y se borra al desinstalar)
SUYO = ("codigo/data/", "codigo/.env")


# --- Lo que hace (sin interfaz) ---

def carpeta_especial(csidl: int) -> Path:
    """Escritorio (0x10) o Programas del menú Inicio (0x02) del usuario, también si OneDrive los ha movido."""
    buf = ctypes.create_unicode_buffer(1024)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    return Path(buf.value)


def accesos_directos() -> dict:
    return {"escritorio": carpeta_especial(0x10) / f"{NOMBRE}.lnk",
            "inicio": carpeta_especial(0x02) / f"{NOMBRE}.lnk"}


def crear_acceso(lnk: Path, destino: Path):
    lnk.parent.mkdir(parents=True, exist_ok=True)
    # Las rutas van por variables de entorno: así ni espacios ni comillas rompen el comando
    script = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:CU01_LNK); $s.TargetPath = $env:CU01_EXE;"
              " $s.WorkingDirectory = $env:CU01_DIR; $s.IconLocation = $env:CU01_EXE + ',0';"
              " $s.Description = $env:CU01_DESC; $s.Save()")
    entorno = {**os.environ, "CU01_LNK": str(lnk), "CU01_EXE": str(destino), "CU01_DIR": str(destino.parent),
               "CU01_DESC": "Reinterpretación de rutas biológicas de células NK"}
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], env=entorno, check=True,
                   capture_output=True, creationflags=SIN_VENTANA)


def version_instalada():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE_REGISTRO) as k:
            return winreg.QueryValueEx(k, "DisplayVersion")[0]
    except OSError:
        return None


def registrar(carpeta: Path, kb: int):
    """La entrada de «Aplicaciones instaladas» (Configuración de Windows) y del Panel de control."""
    textos = {"DisplayName": NOMBRE, "DisplayVersion": VERSION, "Publisher": EDITOR,
              "DisplayIcon": str(carpeta / EXE_APP), "InstallLocation": str(carpeta),
              "UninstallString": f'"{carpeta / EXE_DESINSTALAR}"', "InstallDate": time.strftime("%Y%m%d")}
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CLAVE_REGISTRO) as k:
        for nombre, valor in textos.items():
            winreg.SetValueEx(k, nombre, 0, winreg.REG_SZ, valor)
        for nombre, valor in {"EstimatedSize": kb, "NoModify": 1, "NoRepair": 1}.items():
            winreg.SetValueEx(k, nombre, 0, winreg.REG_DWORD, valor)


def esta_abierto() -> bool:
    # En CSV: en la tabla normal, tasklist recorta a 25 caracteres los nombres largos de ejecutable
    r = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {EXE_APP}", "/FO", "CSV", "/NH"], capture_output=True,
                       text=True, creationflags=SIN_VENTANA)
    return f'"{EXE_APP.lower()}"' in r.stdout.lower()


def cerrar_programa():
    """Cierra el programa y su ventana (Edge, que cuelga de él)."""
    subprocess.run(["taskkill", "/IM", EXE_APP, "/T", "/F"], capture_output=True, creationflags=SIN_VENTANA)
    for _ in range(20):
        if not esta_abierto():
            return
        time.sleep(0.25)


def es_suyo(relativa: str) -> bool:
    return any(relativa == s or relativa.startswith(s) for s in SUYO)


def comprobar_carpeta(carpeta: Path):
    """Solo se vacía o se borra una carpeta que sea de este programa: nunca otra por error."""
    if carpeta.name != NOMBRE:
        raise RuntimeError(f"{carpeta} no es la carpeta de {NOMBRE}.")
    if carpeta.exists() and any(carpeta.iterdir()) and not (carpeta / EXE_APP).exists():
        raise RuntimeError(f"{carpeta} tiene otros ficheros y no es una instalación de {NOMBRE}: no se toca.")


def instalar(carpeta: Path, escritorio: bool, avisar):
    """avisar(fracción, texto) informa del avance."""
    comprobar_carpeta(carpeta)
    with zipfile.ZipFile(PAQUETE) as z:
        miembros = [m for m in z.infolist() if not m.is_dir()]
        total = sum(m.file_size for m in miembros) or 1
        avisar(0.02, "Preparando la carpeta…")
        if carpeta.exists():  # actualización: fuera lo del programa anterior, se queda lo de la persona
            for hijo in carpeta.iterdir():
                if hijo.name == "codigo":
                    for nieto in hijo.iterdir():
                        if nieto.name not in ("data", ".env"):
                            borrar(nieto)
                else:
                    borrar(hijo)
        hecho = 0
        for m in miembros:
            destino = carpeta / m.filename
            if not (es_suyo(m.filename) and destino.exists()):  # sus cachés y resultados no se pisan
                destino.parent.mkdir(parents=True, exist_ok=True)
                with z.open(m) as origen, open(destino, "wb") as salida:
                    shutil.copyfileobj(origen, salida, 1 << 20)
            hecho += m.file_size
            avisar(0.02 + 0.9 * hecho / total, "Copiando los archivos del programa…")
    avisar(0.94, "Creando los accesos directos…")
    exe = carpeta / EXE_APP
    lnk = accesos_directos()
    crear_acceso(lnk["inicio"], exe)
    if escritorio:
        crear_acceso(lnk["escritorio"], exe)
    elif lnk["escritorio"].exists():
        lnk["escritorio"].unlink()
    avisar(0.98, "Registrando el programa en Windows…")
    registrar(carpeta, total // 1024)
    avisar(1.0, "Listo")


def borrar(ruta: Path):
    for intento in range(10):  # Windows tarda un poco en soltar los ficheros de un programa recién cerrado
        try:
            if ruta.is_dir() and not ruta.is_symlink():
                shutil.rmtree(ruta)
            elif ruta.exists():
                ruta.unlink()
            return
        except PermissionError:
            if intento == 9:
                raise
            time.sleep(0.5)


def desinstalar(carpeta: Path, avisar):
    comprobar_carpeta(carpeta)
    avisar(0.1, "Quitando los accesos directos…")
    for lnk in accesos_directos().values():
        if lnk.exists():
            lnk.unlink()
    avisar(0.3, "Borrando los archivos…")
    borrar(carpeta)
    avisar(0.9, "Quitándolo de las aplicaciones instaladas…")
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, CLAVE_REGISTRO)
    except FileNotFoundError:
        pass
    avisar(1.0, "Listo")


# --- El asistente ---

class Asistente:
    def __init__(self, modo: str, carpeta: Path):
        nitidez()
        self.modo, self.carpeta = modo, carpeta
        self.raiz = tk.Tk()
        self.raiz.title(f"{'Instalar' if modo == 'instalar' else 'Desinstalar'} {NOMBRE}")
        self.raiz.configure(bg=PANEL)
        self.raiz.resizable(False, False)
        try:
            self.raiz.iconbitmap(default=str(recurso("icono.ico")))
        except tk.TclError:
            pass
        self.s = s = escala(self.raiz)
        self.ocupado = False
        self.raiz.protocol("WM_DELETE_WINDOW", self.salir)
        self.cola = queue.Queue()

        cabecera = tk.Frame(self.raiz, bg=FONDO, padx=int(28 * s), pady=int(20 * s))
        cabecera.pack(fill="x")
        self.logo = imagen(s)
        if self.logo:
            tk.Label(cabecera, image=self.logo, bg=FONDO).pack(side="left")
        textos = tk.Frame(cabecera, bg=FONDO, padx=int(16 * s))
        textos.pack(side="left", fill="x")
        tk.Label(textos, text=NOMBRE, bg=FONDO, fg=TEXTO, font=(FUENTE, 16, "bold")).pack(anchor="w")
        tk.Label(textos, text=f"Versión {VERSION} · {EDITOR}", bg=FONDO, fg=TENUE, font=(FUENTE, 9)).pack(anchor="w")
        tk.Frame(self.raiz, bg=BORDE, height=1).pack(fill="x")

        # El pie se coloca antes que el cuerpo: así los botones se ven siempre, aunque el texto ocupe más
        self.pie = tk.Frame(self.raiz, bg=FONDO, padx=int(20 * s), pady=int(14 * s))
        self.pie.pack(side="bottom", fill="x")
        tk.Frame(self.raiz, bg=BORDE, height=1).pack(side="bottom", fill="x")
        self.cuerpo = tk.Frame(self.raiz, bg=PANEL, padx=int(28 * s), pady=int(22 * s))
        self.cuerpo.pack(fill="both", expand=True)
        centrar(self.raiz, int(600 * s), int(540 * s))

    # piezas
    def _limpiar(self):
        for w in (*self.cuerpo.winfo_children(), *self.pie.winfo_children()):
            w.destroy()

    def _titulo(self, texto, color=TEXTO):
        tk.Label(self.cuerpo, text=texto, bg=PANEL, fg=color, font=(FUENTE, 14, "bold")).pack(anchor="w")

    def _parrafo(self, texto, color=SUAVE, arriba=6, tam=10):
        tk.Label(self.cuerpo, text=texto, bg=PANEL, fg=color, font=(FUENTE, tam), justify="left",
                 wraplength=int(540 * self.s)).pack(anchor="w", pady=(int(arriba * self.s), 0))

    def _caja(self, lineas):
        caja = tk.Frame(self.cuerpo, bg=FONDO, highlightthickness=1, highlightbackground=BORDE,
                        padx=int(14 * self.s), pady=int(10 * self.s))
        caja.pack(fill="x", pady=(int(16 * self.s), 0))
        for i, (texto, color, negrita) in enumerate(lineas):
            tk.Label(caja, text=texto, bg=FONDO, fg=color, font=(FUENTE, 9, "bold" if negrita else "normal"),
                     justify="left", wraplength=int(510 * self.s)).pack(anchor="w", pady=(int(4 * self.s) if i else 0, 0))

    def _casilla(self, texto, valor):
        tk.Checkbutton(self.cuerpo, text=" " + texto, variable=valor, bg=PANEL, fg=TEXTO, font=(FUENTE, 10),
                       activebackground=PANEL, activeforeground=TEXTO, selectcolor=FONDO, highlightthickness=0,
                       bd=0, cursor="hand2").pack(anchor="w", pady=(int(14 * self.s), 0))

    def _botones(self, *botones):
        """Intro pulsa el botón principal y Esc el otro (Cancelar), como en cualquier asistente de Windows."""
        for tecla in ("<Return>", "<Escape>"):
            self.raiz.unbind(tecla)
        for texto, comando, principal in reversed(botones):
            boton(self.pie, texto, comando, principal, self.s).pack(side="right", padx=(int(8 * self.s), 0))
            self.raiz.bind("<Return>" if principal else "<Escape>", lambda e, c=comando: c())
        self.raiz.focus_set()  # el widget que tenía el foco ya no existe: sin esto, Intro y Esc no llegan

    # pantallas
    def bienvenida(self):
        self._limpiar()
        previa = version_instalada() if (self.carpeta / EXE_APP).exists() else None
        if previa == VERSION:
            self._titulo(f"Reinstalar {NOMBRE}")
            self._parrafo(f"Ya tienes instalada esta versión ({VERSION}). Se volverá a instalar, por si algo falla, y "
                          "se conservarán tus claves y los resultados que tengas guardados.")
        elif previa:
            self._titulo(f"Actualizar {NOMBRE}")
            self._parrafo(f"Ya tienes instalada la versión {previa}. Se instalará la {VERSION} y se conservarán tus "
                          "claves y los resultados que tengas guardados.")
        else:
            self._titulo("Te damos la bienvenida")
            self._parrafo("Este programa analiza si cada ruta biológica de las células NK está activada o inhibida, "
                          "con la evidencia de Gene Ontology y de los artículos de PubMed.")
        with zipfile.ZipFile(PAQUETE) as z:
            mb = sum(m.file_size for m in z.infolist()) / 1e6
        self._caja([("Se instalará en", TENUE, False), (str(self.carpeta), TEXTO, True),
                    (f"Solo para tu usuario, sin permisos de administrador. Ocupa unos {mb:.0f} MB.", SUAVE, False)])
        self.escritorio = tk.BooleanVar(value=True)
        self._casilla("Crear un acceso directo en el escritorio", self.escritorio)
        accion = "Reinstalar" if previa == VERSION else "Actualizar" if previa else "Instalar"
        self._botones(("Cancelar", self.salir, False), (accion, self.empezar, True))

    def progreso(self, titulo):
        self._limpiar()
        for tecla in ("<Return>", "<Escape>"):
            self.raiz.unbind(tecla)
        self._titulo(titulo)
        self.paso = tk.Label(self.cuerpo, text="", bg=PANEL, fg=SUAVE, font=(FUENTE, 10))
        self.paso.pack(anchor="w", pady=(int(18 * self.s), int(10 * self.s)))
        self.barra = Barra(self.cuerpo, int(540 * self.s), max(6, int(10 * self.s)))
        self.barra.c.pack(anchor="w")
        self.pct = tk.Label(self.cuerpo, text="0 %", bg=PANEL, fg=ACENTO_CLARO, font=(FUENTE, 22, "bold"))
        self.pct.pack(anchor="w", pady=(int(12 * self.s), 0))

    def _avisar(self, fraccion, texto):
        self.cola.put(("avance", (fraccion, texto)))

    def _trabajar(self, tarea):
        self.ocupado = True

        def hilo():
            try:
                tarea()
                self.cola.put(("fin", None))
            except Exception as exc:  # se enseña en pantalla
                self.cola.put(("error", exc))
        threading.Thread(target=hilo, daemon=True).start()
        self._atender()

    def _atender(self):
        try:
            while True:
                tipo, dato = self.cola.get_nowait()
                if tipo == "avance":
                    self.barra.valor(dato[0])
                    self.pct.config(text=f"{int(dato[0] * 100)} %")
                    self.paso.config(text=dato[1])
                elif tipo == "fin":
                    self.ocupado = False
                    self.terminado() if self.modo == "instalar" else self.desinstalado()
                    return
                elif tipo == "error":
                    self.ocupado = False
                    self.fallo(dato)
                    return
        except queue.Empty:
            pass
        self.raiz.after(40, self._atender)

    def _si_esta_abierto(self, seguir):
        """Con el programa abierto no se pueden cambiar sus ficheros: se ofrece cerrarlo."""
        if not esta_abierto():
            seguir()
            return
        self._limpiar()
        self._titulo(f"{NOMBRE} está abierto")
        self._parrafo("Hay que cerrarlo para continuar. Si estás ejecutando una ruta, espera a que termine.")

        def cerrar_y_seguir():
            cerrar_programa()
            seguir()
        self._botones(("Cancelar", self.salir, False), ("Cerrarlo y continuar", cerrar_y_seguir, True))

    def empezar(self):
        escritorio = self.escritorio.get()

        def seguir():
            self.progreso(f"Instalando {NOMBRE}")
            self._trabajar(lambda: instalar(self.carpeta, escritorio, self._avisar))
        self._si_esta_abierto(seguir)

    def _marca(self, color, simbolo):
        c = tk.Canvas(self.cuerpo, width=int(52 * self.s), height=int(52 * self.s), bg=PANEL, highlightthickness=0)
        c.create_oval(2, 2, int(50 * self.s), int(50 * self.s), fill=color, outline="")
        c.create_text(int(26 * self.s), int(26 * self.s), text=simbolo, fill=FONDO, font=(FUENTE, 20, "bold"))
        c.pack(anchor="w", pady=(0, int(12 * self.s)))

    def terminado(self):
        self._limpiar()
        self._marca(ACENTO, "✓")
        self._titulo("Todo listo")
        self._parrafo(f"{NOMBRE} está instalado. Lo encontrarás en el menú Inicio"
                      + (" y en el escritorio." if self.escritorio.get() else "."))
        self._caja([("La primera vez", ACENTO_CLARO, True),
                    ("Para analizar rutas nuevas hace falta una clave gratuita de Gemini (o de Groq). Añádela en la "
                     "rueda ⚙ de arriba a la derecha → token-api. Las rutas que ya vienen analizadas funcionan sin "
                     "clave.", SUAVE, False)])
        self.abrir = tk.BooleanVar(value=True)
        self._casilla(f"Abrir {NOMBRE} ahora", self.abrir)
        self._botones(("Terminar", self.terminar, True))

    def terminar(self):
        if self.abrir.get():
            subprocess.Popen([str(self.carpeta / EXE_APP)], cwd=str(self.carpeta),
                             creationflags=subprocess.DETACHED_PROCESS)
        self.raiz.destroy()

    def fallo(self, exc):
        self._limpiar()
        self._marca(ERROR, "!")
        self._titulo("No se ha podido terminar", ERROR)
        self._parrafo(f"{type(exc).__name__}: {exc}", color=TEXTO)
        self._parrafo("Cierra el programa si está abierto y vuelve a intentarlo. Si sigue fallando, reinicia el "
                      "ordenador y prueba otra vez.")
        self._botones(("Cerrar", self.raiz.destroy, True))

    # desinstalar
    def confirmar(self):
        self._limpiar()
        self._titulo(f"Desinstalar {NOMBRE}")
        self._parrafo("Se borrará el programa del ordenador, junto con tus claves y los resultados guardados dentro "
                      "de él. Los Excel que descargaste no se tocan.")
        self._caja([("Carpeta que se borrará", TENUE, False), (str(self.carpeta), TEXTO, True)])
        self._botones(("Cancelar", self.salir, False), ("Desinstalar", self.quitar, True))

    def quitar(self):
        def seguir():
            self.progreso(f"Desinstalando {NOMBRE}")
            self._trabajar(lambda: desinstalar(self.carpeta, self._avisar))
        self._si_esta_abierto(seguir)

    def desinstalado(self):
        self._limpiar()
        self._marca(ACENTO, "✓")
        self._titulo("Desinstalado")
        self._parrafo(f"{NOMBRE} se ha quitado del ordenador.")
        self._botones(("Cerrar", self.raiz.destroy, True))

    def salir(self):
        if not self.ocupado:
            self.raiz.destroy()

    def ejecutar(self):
        self.bienvenida() if self.modo == "instalar" else self.confirmar()
        self.raiz.mainloop()


def carpeta_de_esta_instalacion() -> Path:
    """Desinstalar.exe vive en la carpeta del programa; sin empaquetar, la de siempre."""
    if getattr(sys, "frozen", False) and (Path(sys.executable).parent / EXE_APP).exists():
        return Path(sys.executable).parent
    return DIR_INSTALACION


def main():
    args = sys.argv[1:]
    if "--desde-copia" in args:  # 2.º paso del desinstalador: ya corre desde %TEMP% y puede borrar la carpeta
        carpeta = Path(args[args.index("--desde-copia") + 1])
        Asistente("desinstalar", carpeta).ejecutar()
        # La copia de %TEMP% se borra sola cuando termine este proceso
        subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 4 > nul & del /f /q "{sys.executable}"', shell=True,
                         creationflags=SIN_VENTANA | subprocess.DETACHED_PROCESS)
        return
    if "--desinstalar" in args or not PAQUETE.exists():
        carpeta = carpeta_de_esta_instalacion()
        if getattr(sys, "frozen", False):
            # Un .exe en marcha no se puede borrar: se copia a %TEMP% y sigue desde allí
            copia = Path(tempfile.gettempdir()) / f"desinstalar_cu01_{os.getpid()}.exe"
            shutil.copy2(sys.executable, copia)
            subprocess.Popen([str(copia), "--desde-copia", str(carpeta)], cwd=tempfile.gettempdir())
            return
        Asistente("desinstalar", carpeta).ejecutar()
        return
    Asistente("instalar", DIR_INSTALACION).ejecutar()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        aviso_de_error(NOMBRE, f"Algo ha fallado: {type(exc).__name__}: {exc}")
