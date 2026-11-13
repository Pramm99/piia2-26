# Instrucciones de Uso · CU-01 Reinterpretación de Rutas Biológicas (scRNA-seq HNSC)

Guía rápida para arrancar el entorno, configurar el motor local y probar tanto la interfaz gráfica interactiva (con el flujo completo de extremo a extremo o por fases) como la ejecución directa mediante comandos de terminal.

---

## 1. Requisitos Previos y Entorno

1. **Python 3.14** (probado y compatible).
2. **Node.js y npm** (para levantar la interfaz web de React + Vite).
3. **Claves de API gratuitas:** Copia el fichero de ejemplo `codigo/.env.example` como `codigo/.env` y añade tus credenciales (`GEMINI_API_KEY`, `GROQ_API_KEY`, `NCBI_EMAIL`). El archivo `.env` está protegido por el `.gitignore` y nunca se sube a GitHub.

---

## 2. Instalación de Dependencias

### Backend (Python)
Desde la carpeta `codigo/`:
```bash
pip install -r requirements.txt

```

### Frontend (Node.js)

Desde la carpeta `codigo/frontend/`:

```bash
npm install
npm install lucide-react

```

---

## 3. Cómo Probar el Frontend Interactivo (Paso a Paso)

El frontend incluye dos modos de trabajo:

* **Ejecución Completa (Fases 1 → 3)** *(Modo por defecto)*: Te permite subir un Excel crudo de CIMUS (`ID`, `Description`, `geneID`), marcar interactivamente las filas de interés (evitando cuellos de botella masivos de descargas de abstracts), pulsar un botón para encadenar automáticamente las tres fases y visualizar de inmediato el **Net Pathway Score (NPS)** de cada ruta junto con la **aportación individual de cada gen** ($c = s \times d$).
* **Control por Fases Separadas**: Permite probar de forma aislada la Fase 1 (Ingesta), la Fase 2 (Inferencia LLM) o la Fase 3 (Scoring), con guías detalladas de qué ficheros subir y la descarga directa de los resultados en `.xlsx`.

### Paso A: Arrancar el Puente HTTP local de Python

Para que la interfaz web pueda comunicarse con el pipeline en Python de manera local (sin bases de datos y guardando los resultados en ficheros locales dentro de `codigo/data/`, cumpliendo el ADR-001 y el ADR-004), abre una terminal en la carpeta `codigo/` y ejecuta:

```bash
python frontend/api_puente.py

```

*(El servidor HTTP local se activará en `http://127.0.0.1:8000`, recordar que esto todavia no funciona realmente, es solo un "simulacro")*.

### Paso B: Arrancar el Servidor Web (Frontend)

Abre una **segunda terminal** situada en la carpeta `codigo/frontend/` y ejecuta:

```bash
npm run dev

```

### Paso C: Abrir la Aplicación en el Navegador

Abre tu navegador (Edge, Chrome, etc.) y entra en:
**`http://localhost:5173/`**

En la esquina superior izquierda verás un indicador en verde con el texto **`● Motor Python conectado`**, confirmando que el frontend puede invocar las funciones del proyecto en tiempo real.

---

## 4. Ejecución Alternativa por Terminal (CLI)

Si prefieres probar el pipeline directamente desde la línea de comandos (desde la carpeta `codigo/`):

1. **Fase 1 (Ingesta y Triaje GO):**
```bash
python fase1_ingesta/main.py

```


2. **Fase 2 (Inferencia LLM reanudable):**
```bash
python -m fase2_inferencia ejecutar --solo-respaldo

```


3. **Fase 3 (Net Pathway Score determinista):**
```bash
python -m fase3_scoring

```



---

## 5. Ficheros Generados y Cachés

Todas las salidas y cachés se almacenan de forma local en `codigo/data/` (ignoradas por git):

* `fase1_dataset_abstracts.xlsx`: Resultado de la Ingesta y Triaje GO (Fase 1).
* `fase2_resultados.xlsx` y `respuestas_llm.jsonl`: Registro de inferencias y validación de citas de los LLM (Fase 2).
* `fase3_scoring.xlsx`: Fichero final con las hojas `Por_ruta` (NPS y lecturas de ruta) y `Por_par` (aportaciones gen a gen y frenos de retroalimentación).

```

```