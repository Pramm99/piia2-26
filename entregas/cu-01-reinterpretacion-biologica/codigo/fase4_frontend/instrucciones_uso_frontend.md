# Instrucciones de uso · Fase 4 (frontend)

Interfaz web para ejecutar **una ruta** de principio a fin: se elige la ruta, se confirma y se ejecutan seguidas las
Fases 1, 2 y 3. Al terminar muestra la lectura de la ruta (NPS), la aportación de cada gen y el Excel de la Fase 3.
No se pueden lanzar las fases por separado: para eso está la línea de comandos (`AGENTS.md`).

## 1. Requisitos

1. **Python** con las dependencias de `codigo/requirements.txt` (el entorno `codigo/pia_venv/` sirve).
2. **Node.js y npm**, para la interfaz (React + Vite).
3. **Claves** en `codigo/.env` (copia de `codigo/.env.example`): `GEMINI_API_KEY`, `GROQ_API_KEY` y `NCBI_EMAIL`.
   El `.env` está en el `.gitignore` y nunca se sube a GitHub.

Dependencias de la interfaz, una sola vez, desde `codigo/fase4_frontend/`:

```bash
npm install
```

## 2. Arranque

Hacen falta dos terminales.

**Puente con las fases** (desde `codigo/`):

```bash
python fase4_frontend/api_puente.py
```

Escucha en `http://127.0.0.1:8000` y carga las 352 rutas de los Excels de CIMUS (`codigo/tools_cimus/`).

**Interfaz** (desde `codigo/fase4_frontend/`):

```bash
npm run dev
```

Se abre en `http://localhost:5173/`. Arriba aparece **● Motor Python conectado** cuando el puente responde.

## 3. Uso

1. Busca la ruta por GO_ID, nombre o gen y márcala. Se ve con sus genes *up* y *down*: una ruta que está en las dos
   listas de CIMUS se ejecuta con todos sus genes.
2. Pulsa **Ejecutar GO:…** y confirma. La barra muestra la fase en curso.
3. Al terminar aparecen la lectura (activada, inhibida, mixta o insuficiente), el NPS, el NPS con log2FC, la tabla gen a
   gen y el botón **Descargar Excel** (salida de la Fase 3).

También se puede **subir otro Excel** con las columnas `ID`, `Description` y `geneID`. La lista (genes *up* o *down*)
sale del nombre del fichero si contiene «suprimid» y, si no, del selector; **+ Añadir 2ª Lista** suma la otra lista.

## 4. Qué hace el puente

* **Fase 1** con los dos Excels de CIMUS reducidos a la ruta elegida.
* **Fase 2** con Gemini como principal y gpt-oss solo como respaldo (ADR-005). Usa el registro de siempre
  (`codigo/data/respuestas_llm.jsonl`): lo que ya se preguntó no se vuelve a pedir. Si el cupo se agota, las preguntas
  quedan `pendiente` y la interfaz lo avisa; basta con volver a ejecutar la ruta más tarde.
* **Fase 3** con la tabla de log2FC de CIMUS si existe.

Tarda unos segundos con las cachés y unos 2–3 minutos en frío (`docs/kpis.md`). Solo se ejecuta una ruta a la vez.

## 5. Ficheros

Cada ruta escribe en `codigo/data/frontend/<GO_ID>/` (ignorado por git): los dos Excels de entrada reducidos,
`fase1_dataset_abstracts.xlsx`, `fase2_resultados.xlsx` y `fase3_scoring.xlsx`. No pisa las salidas del Excel completo.
Las cachés de la Fase 1 (`codigo/data/`) son compartidas.
