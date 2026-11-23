---
description: La interfaz web se reparte como programa de Windows de doble clic, con instalador propio: PyInstaller para el puente y las fases, Edge en modo aplicación como ventana y un asistente en Tk.
state: Aceptado (2026-11-23)
---

# ADR 006 - Programa de escritorio e instalador para la Fase 4

## Decisión
La Fase 4 se reparte también como **programa de Windows** para personas que no usan la terminal (código en `codigo/empaquetado/`; se construye con `python empaquetado/construir.py` desde `codigo/`):

| Pieza | Cómo |
|---|---|
| **Programa** (`CU-01 PathScore Studio.exe`) | `lanzador.py` empaquetado con **PyInstaller** (carpeta, sin consola). Arranca dentro de su proceso el mismo puente (`api_puente.py`), que además sirve la interfaz ya compilada (`npm run build`), en `127.0.0.1:47613`. El código de las fases va al lado, en `codigo/`, tal cual está en el repositorio. |
| **Ventana** | **Microsoft Edge en modo aplicación** (`--app`, con un perfil solo para el programa), que viene con Windows. Al cerrarla se apaga el programa. Tiene su propio botón en la barra de tareas, con su nombre y su icono (`barra_tareas.py`). Si no hay Edge ni Chrome, se abre el navegador por defecto y una ventanita para cerrar el programa. |
| **Instalador** (`Instalar CU-01 PathScore Studio.exe`) | Un único fichero con un **asistente propio en Tk** (`instalador.py`). Instala solo para el usuario en `%LOCALAPPDATA%\Programs`, sin pedir permisos de administrador, crea los accesos directos del escritorio y del menú Inicio y registra el programa en «Aplicaciones instaladas», desde donde se desinstala. Al actualizar conserva `codigo/data` y `codigo/.env`. |

Lleva las cachés de la Fase 1 y el registro de respuestas del LLM, para que las rutas ya analizadas salgan al momento y sin clave. **Nunca lleva `codigo/.env`**, y `construir.py` se para si encuentra algo con forma de clave en lo que va a empaquetar. Las claves se añaden en el programa, en ⚙ → token-api.

## Por qué
* **Coste cero y nada que instalar aparte:** PyInstaller y Tk son gratuitos y Edge ya está en Windows. La persona no necesita Python ni Node.
* **El mismo código que la línea de comandos:** el programa ejecuta las fases sin copiarlas ni reescribirlas, así que da el mismo resultado (GO:0072678, `activada` y NPS 0,333 dentro del ejecutable).
* **Sin permisos de administrador:** la instalación por usuario funciona en ordenadores gestionados, como los de un laboratorio.

## Alternativas descartadas
* **Electron o Tauri:** obligan a reescribir el arranque en Node o en Rust y a llevar un navegador completo dentro (Electron, más de 100 MB más).
* **pywebview:** en Windows necesita pythonnet, que no estaba claro que funcionara con Python 3.14. Edge en modo aplicación da una ventana equivalente sin dependencias.
* **Inno Setup, NSIS o MSIX:** son estándar, pero hay que instalar la herramienta para construir el instalador, y MSIX además exige firmar. El asistente en Tk se construye con lo que ya está en `requirements.txt` más PyInstaller y lleva el aspecto de la interfaz.
* **Seguir con dos terminales o un `.bat`:** pide Python y Node instalados y deja ventanas de consola abiertas.

## Consecuencias
* **Windows sin firmar:** al descargar el instalador de internet, SmartScreen avisa («Windows protegió su PC» → «Más información» → «Ejecutar de todas formas»). Firmarlo cuesta dinero, fuera del proyecto.
* **Tamaño:** el instalador ocupa unos 105 MB y el programa instalado unos 220 MB, casi todo cachés de datos (GO, abstracts) y la librería de Python.
* **Tabla de log2FC de CIMUS:** va dentro por defecto, porque sin ella no hay NPS pesado por log2FC. No es pública: un instalador para repartir fuera del equipo se construye con `--sin-datos-cimus`. Los ejecutables no se versionan (`codigo/empaquetado/salida/` está en el `.gitignore`).
* **Descargas que se cortan:** en el equipo de pruebas (con Avast), las descargas grandes del servidor local se cortaban a veces (`ERR_CONNECTION_RESET` tras unos 19 s), también con el servidor estándar de Python y con Chrome. Por eso la interfaz compilada carga su JavaScript y su CSS con un tiempo límite y reintentos (`vite.config.ts`), y el puente la sirve comprimida con gzip.
