"""La ventana de la aplicación (Edge en modo aplicación) como un programa propio en la barra de tareas de Windows.

Sin esto, Windows la agrupa con Edge («Microsoft Edge: 1 ventana») y pinta como icono el favicon reescalado, borroso.
Aquí se le da a la ventana su propia identidad (AppUserModelID, el mismo que el lanzador), con nombre, icono y orden
para volver a abrirla si se ancla, y el icono .ico del programa a la medida exacta que pide Windows (que depende del
escalado de la pantalla). Edge puede volver a poner el suyo al cargar la página, así que el lanzador lo comprueba cada
segundo con poner_identidad().

Solo usa la API de Windows con ctypes (sin dependencias). Si algo falla, la ventana sigue funcionando igual.
"""
import ctypes
import uuid
from ctypes import wintypes
from pathlib import Path

AUMID = "USC.PIIA2.CU01PathScoreStudio"

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32")
user32.SendMessageW.restype = ctypes.c_void_p
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p]
user32.LoadImageW.restype = wintypes.HANDLE
user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                              wintypes.UINT]
WM_SETICON, WM_GETICON, ICON_SMALL, ICON_BIG = 0x80, 0x7F, 0, 1
SM_CXICON, SM_CXSMICON, IMAGE_ICON, LR_LOADFROMFILE = 11, 49, 1, 0x10
VT_LPWSTR = 31


class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort), ("Data3", ctypes.c_ushort),
                ("Data4", ctypes.c_ubyte * 8)]

    @classmethod
    def de(cls, texto):
        u = uuid.UUID(texto)
        return cls(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:]))


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", ctypes.c_ulong)]


class PROPVARIANT(ctypes.Structure):  # 24 bytes en 64 bits: tipo, 3 reservados y la unión (aquí, un puntero)
    _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort), ("r3", ctypes.c_ushort),
                ("valor", ctypes.c_void_p), ("relleno", ctypes.c_void_p)]


IID_IPROPERTYSTORE = GUID.de("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")
_APP = "9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"  # PKEY_AppUserModel_*
CLAVES = {"orden": 2, "icono": 3, "nombre": 4, "id": 5}  # RelaunchCommand, RelaunchIconResource, ...DisplayName, ID

_iconos = {}  # tamaño -> HICON, cargados una vez


def identidad_del_proceso():
    """El lanzador (pantalla de carga) y la ventana de la aplicación van al mismo botón de la barra de tareas."""
    try:
        shell32.SetCurrentProcessExplicitAppUserModelID(ctypes.c_wchar_p(AUMID))
    except (AttributeError, OSError):
        pass


def ventanas(pid: int, titulo: str):
    """Ventanas visibles del proceso pid con ese título (las de Edge son de su proceso principal)."""
    halladas = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def una(hwnd, _):
        dueno = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(dueno))
        if dueno.value == pid and user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if buf.value == titulo:
                halladas.append(hwnd)
        return True
    user32.EnumWindows(una, 0)
    return halladas


def _icono(ico: Path, metrica: int):
    tam = user32.GetSystemMetrics(metrica)
    if tam not in _iconos:
        _iconos[tam] = user32.LoadImageW(None, str(ico), IMAGE_ICON, tam, tam, LR_LOADFROMFILE)
    return _iconos[tam]


def _propiedades(hwnd, valores: dict):
    almacen = ctypes.c_void_p()
    if shell32.SHGetPropertyStoreForWindow(wintypes.HWND(hwnd), ctypes.byref(IID_IPROPERTYSTORE),
                                           ctypes.byref(almacen)) != 0 or not almacen:
        return
    tabla = ctypes.cast(almacen, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    poner = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(PROPERTYKEY),
                               ctypes.POINTER(PROPVARIANT))(tabla[6])  # IPropertyStore::SetValue
    soltar = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(tabla[2])  # IUnknown::Release
    try:
        for nombre in ("orden", "icono", "nombre", "id"):  # el ID, el último (así lo pide Windows)
            texto = ctypes.create_unicode_buffer(valores[nombre])
            var = PROPVARIANT(VT_LPWSTR, 0, 0, 0, ctypes.cast(texto, ctypes.c_void_p), None)
            poner(almacen, ctypes.byref(PROPERTYKEY(GUID.de(_APP), CLAVES[nombre])), ctypes.byref(var))
    finally:
        soltar(almacen)


def poner_identidad(hwnd, nombre: str, exe: Path, ico: Path, hechas: set):
    """Identidad propia (una vez por ventana) e icono nítido (cada vez que Edge lo haya cambiado)."""
    try:
        if hwnd not in hechas:
            _propiedades(hwnd, {"id": AUMID, "nombre": nombre, "orden": f'"{exe}"', "icono": f"{ico},0"})
            hechas.add(hwnd)
        grande, pequeno = _icono(ico, SM_CXICON), _icono(ico, SM_CXSMICON)
        if grande and user32.SendMessageW(hwnd, WM_GETICON, ICON_BIG, 0) != grande:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, grande)
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, pequeno)
    except OSError:
        pass
