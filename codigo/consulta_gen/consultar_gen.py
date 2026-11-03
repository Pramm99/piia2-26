"""src/consultar_gen.py

Módulo para consultar evidencias de genes en conflicto y ejecutar inferencia semántica
mediante LLM determinista (Llama-3 vía Groq) en el contexto de HNSC (laringe y faringe).
"""

import json
import os
from typing import Any, Dict, List, Optional
import pandas as pd

from abstracts import (
    _epmc_lote,
    _ncbi_lote,
    cargar_cache,
    guardar_cache,
    limpiar_texto,
)
from config import SALIDA
from red import configurar_sesion

try:
    from groq import Groq

    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


def extraer_evidencias_gen(
    ruta_excel: str, gen: str, go_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Carga las evidencias literarias de un gen desde el Excel de Fase 1.

    Aplica fallback a caché/red si faltase el abstract de algún PMID.
    """
    if not os.path.exists(ruta_excel):
        raise FileNotFoundError(
            f"No existe el archivo de evidencias: {ruta_excel}"
        )

    df = pd.read_excel(ruta_excel, sheet_name="Con_abstract")
    gen_norm = gen.strip().upper()

    sub = df[df["Gen"].astype(str).str.upper() == gen_norm]
    if go_id:
        sub = sub[
            sub["GO_ID"].astype(str).str.upper() == go_id.strip().upper()
        ]

    if sub.empty:
        return []

    cache = cargar_cache()
    sesion = configurar_sesion()
    cache_actualizada = False
    evidencias = []

    for _, fila in sub.iterrows():
        abstract = str(fila.get("Abstract", "")).strip()
        titulo = str(fila.get("Titulo", "")).strip()
        pmid = str(fila.get("PMID", "")).split(".")[0].strip()

        # Contingencia si el abstract estuviera ausente en el Excel
        if not abstract or abstract.lower() == "nan":
            if not pmid or pmid.lower() == "nan":
                continue
            if pmid not in cache or not cache[pmid].get("Abstract"):
                try:
                    res_epmc = _epmc_lote(sesion, [pmid])
                    cache.update(res_epmc)
                    cache_actualizada = True
                except Exception:
                    pass

                if pmid not in cache or not cache[pmid].get("Abstract"):
                    try:
                        res_ncbi = _ncbi_lote(sesion, [pmid])
                        cache.update(res_ncbi)
                        cache_actualizada = True
                    except Exception:
                        pass

            if pmid in cache and cache[pmid].get("Abstract"):
                titulo = cache[pmid].get("Titulo", "")
                abstract = cache[pmid].get("Abstract", "")

        if abstract and abstract.lower() != "nan":
            evidencias.append(
                {
                    "gen": gen_norm,
                    "go_id": str(fila.get("GO_ID", "")).strip(),
                    "ruta_nombre": str(fila.get("Ruta_Nombre", "")).strip(),
                    "estado_scrnaseq": str(
                        fila.get("Estado_Original", "")
                    ).strip(),
                    "pmid": pmid,
                    "titulo": limpiar_texto(titulo),
                    "abstract": limpiar_texto(abstract),
                    "polaridad_go": fila.get("Polaridad_GO", None),
                }
            )

    if cache_actualizada:
        guardar_cache(cache)

    return evidencias


def construir_prompt_inferencia(ev: Dict[str, Any]) -> str:
    """Ensambla el prompt estructurado para guiar la inferencia determinista del LLM."""
    return f"""[CONTEXTO BIOMÉDICO]
- Tejido / Contexto patológico: Carcinoma escamocelular de cabeza y cuello (HNSC: laringe y faringe) y microambiente inmunitario.
- Gen diana: {ev['gen']}
- Estado de expresión diferencial (scRNA-seq): {ev['estado_scrnaseq']}
- Ruta biológica evaluada: {ev['ruta_nombre']} ({ev['go_id']})

[EVIDENCIA CIENTÍFICA (PMID: {ev['pmid']})]
Título: {ev['titulo']}
Resumen: {ev['abstract']}

[INSTRUCCIONES CLÍNICAS Y BIOINFORMÁTICAS]
Determina la contribución mecanística del gen {ev['gen']} sobre la activación o funcionamiento de la ruta biológica '{ev['ruta_nombre']}'.
Clasifica de acuerdo a las siguientes opciones estrictas:
- "+1": Si el gen estimula, activa o es un mediador positivo de la ruta.
- "-1": Si el gen inhibe, reprime o atenúa la ruta.
- "UNKNOWN": Si el abstract no contiene información concluyente, reporta efectos contradictorios, o describe el gen en un contexto biológico totalmente ajeno.

Responde ÚNICAMENTE con un objeto JSON válido con la siguiente estructura:
{{
  "pmid": "{ev['pmid']}",
  "gen": "{ev['gen']}",
  "signo_funcional": "+1" | "-1" | "UNKNOWN",
  "justificacion_literal": "Fragmento textual exacto del resumen que sustenta la decisión",
  "razonamiento_corto": "Explicación concisa en una sola frase del mecanismo deducido"
}}"""


def inferir_signo_funcional(
    evidencia: Dict[str, Any], api_key: Optional[str] = None
) -> Dict[str, Any]:
    """Envía la evidencia al modelo Llama-3 vía Groq con temperatura 0 y parseo JSON rígido."""
    if not GROQ_AVAILABLE:
        raise ImportError(
            "El paquete 'groq' no está instalado. Ejecuta: pip install groq"
        )

    key = api_key or os.environ.get("GROQ_API_KEY")
    if not key:
        raise ValueError(
            "No se encontró GROQ_API_KEY en las variables de entorno."
        )

    cliente = Groq(api_key=key)
    prompt = construir_prompt_inferencia(evidencia)

    respuesta = cliente.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un asistente bioinformático experto en regulación molecular en cáncer "
                    "(HNSC: laringe y faringe). Tu labor es extraer signos mecanísticos funcionales "
                    "de la literatura médica de forma estrictamente determinista y fundamentada en citas."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    try:
        resultado = json.loads(respuesta.choices[0].message.content)
        if resultado.get("signo_funcional") not in ["+1", "-1", "UNKNOWN"]:
            resultado["signo_funcional"] = "UNKNOWN"
        return resultado
    except Exception as err:
        return {
            "pmid": evidencia.get("pmid", ""),
            "gen": evidencia.get("gen", ""),
            "signo_funcional": "UNKNOWN",
            "justificacion_literal": f"Error parseando respuesta JSON del LLM: {err}",
            "razonamiento_corto": "Inferencia fallida.",
        }


def consultar_y_resolver_gen(
    ruta_excel: str,
    gen: str,
    go_id: Optional[str] = None,
    ejecutar_llm: bool = False,
) -> List[Dict[str, Any]]:
    """Función de alto nivel: recupera las evidencias de un gen y opcionalmente ejecuta el LLM."""
    evidencias = extraer_evidencias_gen(ruta_excel, gen, go_id)
    if not ejecutar_llm:
        return evidencias

    resultados = []
    for ev in evidencias:
        inferencia = inferir_signo_funcional(ev)
        resultado_completo = {**ev, "inferencia_llm": inferencia}
        resultados.append(resultado_completo)

    return resultados


if __name__ == "__main__":
    archivo_excel = SALIDA if os.path.exists(SALIDA) else "fase1_dataset_abstracts.xlsx"
    gen_ejemplo = "CD7"

    print(f"🔬 Extrayendo evidencias para el gen: {gen_ejemplo}...")
    try:
        evidencias_gen = extraer_evidencias_gen(archivo_excel, gen=gen_ejemplo)
        print(f"✅ Se encontraron {len(evidencias_gen)} evidencias con abstract.")

        if evidencias_gen:
            print("\n--- EJEMPLO DE PROMPT ESTRUCTURADO (PRIMERA EVIDENCIA) ---")
            print(construir_prompt_inferencia(evidencias_gen[0]))

            if os.environ.get("GROQ_API_KEY"):
                print("\n🤖 Ejecutando inferencia con LLM (Groq / Llama-3)...")
                res_inferencia = inferir_signo_funcional(evidencias_gen[0])
                print(json.dumps(res_inferencia, indent=2, ensure_ascii=False))
            else:
                print("\nℹ️ Para ejecutar la inferencia automática, exporta tu GROQ_API_KEY en el entorno.")
    except Exception as e:
        print(f"❌ Error durante la ejecución: {e}")