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

Escucha en `http://127.0.0.1:8000`.

**Interfaz** (desde `codigo/fase4_frontend/`):

```bash
npm run dev
```

Se abre en `http://localhost:5173/`. Arriba aparece **● Motor Python conectado** cuando el puente responde. El botón
**Fondo blanco / Fondo oscuro** de la cabecera cambia el tema, y el navegador lo recuerda para la próxima vez.

## 3. Uso

1. Sube los Excels de rutas (columnas `ID`, `Description` y `geneID`). No hay nada precargado. Hay un hueco para el
   de **rutas sobreexpresadas (upregulated)** y otro para el de **rutas infraexpresadas (downregulated)**; vale con
   uno o con los dos. Solo hay un Excel por lista a la vez: **Cambiar** sube otro en su lugar (el anterior se olvida)
   y **Quitar** lo elimina. Los de CIMUS están en `codigo/tools_cimus/` (`NK_rutas_activadas_GO.xlsx` y
   `NK_rutas_suprimidas_GO.xlsx`).
2. Busca la ruta por GO_ID, nombre o gen y márcala. Se ve con sus genes sobreexpresados e infraexpresados: una ruta
   que está en los dos Excels se ejecuta con todos sus genes.
3. Pulsa **Ejecutar GO:…** y confirma. La barra muestra la fase en curso.
4. Al terminar aparece el resultado, explicado en lenguaje llano:
   * arriba, el veredicto: si la ruta está activada, inhibida, mixta o sin evidencia suficiente, la escala del NPS
     con sus tres zonas, cuántos genes la sostienen (con evidencia directa de Gene Ontology o por artículos, y cuántos
     débiles), cuántos tendrían que cambiar para perder la lectura y los genes repartidos en «empujan hacia activada»,
     «empujan hacia inhibida» y «no cuentan» (al pulsar uno se abre su detalle);
   * una tarjeta por fase: qué encontró la Fase 1 (genes, signos de Gene Ontology, artículos), qué dicen los
     artículos según el LLM en la Fase 2 y la lectura de la Fase 3 (activada, inhibida, mixta o insuficiente) con la
     cuenta del NPS y el NPS pesado por log2FC;
   * una fila por gen: si está sobreexpresado o infraexpresado en NK, qué hace en el proceso, hacia dónde empuja la ruta, de dónde sale el signo
     y por qué. Al pulsarla se ven sus artículos (título con enlace a PubMed, conclusión, confianza y la frase citada);
   * a la derecha de la tabla de genes, la columna **Tu criterio**: una persona experta puede decir que un gen activa,
     inhibe o no cambia el proceso. La lectura, el NPS, el veredicto y la tarjeta de la Fase 3 se recalculan al momento
     con las mismas reglas que `fase3_scoring/nps.py`, y un aviso compara el resultado automático con el que tiene los
     cambios (**Deshacer mis cambios** los quita). Los cambios no se guardan ni pasan al Excel: una nueva ejecución
     vuelve al resultado automático;
   * el botón **Descargar Excel de la Fase 3** (siempre el resultado automático).

## 4. Qué hace el puente

* **Fase 1** con los Excels subidos reducidos a la ruta elegida.
* **Fase 2** con Gemini como principal y gpt-oss solo como respaldo (ADR-005). Usa el registro de siempre
  (`codigo/data/respuestas_llm.jsonl`): lo que ya se preguntó no se vuelve a pedir. Si el cupo se agota, las preguntas
  quedan `pendiente` y la interfaz lo avisa; basta con volver a ejecutar la ruta más tarde.
* **Fase 3** con la tabla de log2FC de CIMUS si existe.

Tarda unos segundos con las cachés y unos 2–3 minutos en frío (`docs/kpis.md`). Solo se ejecuta una ruta a la vez.

## 5. Ficheros

Cada ruta escribe en `codigo/data/frontend/<GO_ID>/` (ignorado por git): los dos Excels de entrada reducidos,
`fase1_dataset_abstracts.xlsx`, `fase2_resultados.xlsx` y `fase3_scoring.xlsx`. No pisa las salidas del Excel completo.
Las cachés de la Fase 1 (`codigo/data/`) son compartidas.
