"""Salida final de la Fase 2 (spec de inferencia, paso 7): contraste entre modelos y con GO, por pregunta y por ruta.

Por pregunta (gen, PMID, proceso núcleo):
  - el signo es el del modelo principal; se guardan los signos de los dos modelos;
  - si el secundario da otro signo (opuesto, o UNKNOWN frente a un signo), se añade discrepancia_entre_modelos
    y el caso queda en revisar (ADR-003). Una respuesta del secundario con json_invalido no cuenta como
    discrepancia: no dice nada sobre el abstract, solo que ese modelo falló el formato;
  - confianza_final (confianza.py) usa la respuesta del secundario;
  - si el principal no ha respondido todavía (límite del plan gratuito), el estado es «pendiente», no UNKNOWN.
Por ruta (gen, ruta, PMID), lo que lee el scoring:
  - signo_ruta = efecto × factor de la ruta (composición de casos.py, calculada en respuesta.py);
  - si signo_ruta y la Polaridad_GO de esa anotación (Con_abstract, mismo gen, ruta y PMID) son +1/-1 y
    difieren, se añade discrepancia_polaridad_GO y la fila queda en revisar. Una Polaridad_GO «conflicto» o
    con los dos signos entre las filas del PMID no se contrasta.
Los casos cerrados sin LLM por el filtro previo salen como UNKNOWN con no_menciona_gen.
"""
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from .confianza import confianza_final
from .esquema import (ESTADO_NO_CONCLUYENTE, ESTADO_PENDIENTE, ESTADO_RESUELTO, ESTADO_REVISAR, MOTIVOS_REVISAR,
                      SIGNO_DESCONOCIDO, SIGNO_NEGATIVO, SIGNO_POSITIVO, CasoProceso)
from .limpieza import normalizar_pmid, valor_texto

FICHERO_RESULTADOS = Path(__file__).resolve().parent.parent / "data" / "fase2_resultados.xlsx"
SIGNOS = (SIGNO_POSITIVO, SIGNO_NEGATIVO)


def _estado(signo: str, motivos: Sequence[str]) -> str:
    if any(m in MOTIVOS_REVISAR for m in motivos):
        return ESTADO_REVISAR
    return ESTADO_RESUELTO if signo != SIGNO_DESCONOCIDO else ESTADO_NO_CONCLUYENTE


def _valida(salida: Optional[Dict]) -> bool:
    return salida is not None and "json_invalido" not in salida["motivos"]


def contrastar(principal: Optional[Dict], secundaria: Optional[Dict] = None) -> Dict:
    """Salidas validadas (respuesta.validar_respuesta) de los dos modelos para la misma pregunta -> resultado.
    principal None = pendiente; secundaria None = sin segundo modelo o pendiente."""
    sec = secundaria["signo"] if secundaria is not None else None
    if principal is None:
        return {"signo": SIGNO_DESCONOCIDO, "estado": ESTADO_PENDIENTE, "motivos": [], "confianza_final": None,
                "signo_principal": None, "signo_secundario": sec}
    motivos = list(principal["motivos"])
    if _valida(secundaria) and _valida(principal) and secundaria["signo"] != principal["signo"]:
        motivos.append("discrepancia_entre_modelos")
    return {"signo": principal["signo"], "estado": _estado(principal["signo"], motivos), "motivos": motivos,
            "confianza_final": confianza_final(principal, secundaria if _valida(secundaria) else None),
            "signo_principal": principal["signo"], "signo_secundario": sec}


def polaridades_go(df: pd.DataFrame) -> Dict[Tuple[str, str, str], str]:
    """(gen, GO_ID ruta, PMID) -> «+1» / «-1» de las filas de Con_abstract (las anotaciones GO de ese PMID).
    Si las filas no dan un único signo, no hay polaridad con la que contrastar."""
    vistos: Dict[Tuple[str, str, str], set] = {}
    for g, r, p, pol in zip(df["Gen"], df["GO_ID"], df["PMID"], df["Polaridad_GO"]):
        vistos.setdefault((valor_texto(g).upper(), valor_texto(r), normalizar_pmid(p)), set()).add(valor_texto(pol))
    return {k: next(iter(v)) for k, v in vistos.items() if len(v) == 1 and next(iter(v)) in SIGNOS}


def _destinos(df: pd.DataFrame) -> Dict[Tuple[str, str], str]:
    if "Destino" not in df.columns:
        return {}
    return {(valor_texto(g).upper(), valor_texto(r)): valor_texto(d) for g, r, d in zip(df["Gen"], df["GO_ID"], df["Destino"])}


def _texto(motivos: Iterable[str]) -> str:
    return "|".join(motivos)


def tablas(resultados, principal: str, secundario: Optional[str], cerrados: Sequence[CasoProceso],
           df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """resultados: ejecucion.ejecutar (ResultadoCaso). -> (hoja Preguntas, hoja Por_ruta)."""
    pol_go, destinos = polaridades_go(df), _destinos(df)
    preguntas, rutas = [], []
    filas = [(r.prompt.evidencia, r.salidas.get(principal), r.salidas.get(secundario) if secundario else None)
             for r in resultados]
    for caso, p, s in filas:
        c = contrastar(p, s)
        p = p or {}
        preguntas.append({
            "Gen": caso.gen, "PMID": caso.pmid, "Proceso_ID": caso.nucleo_id, "Proceso": caso.nucleo_nombre,
            "Signo": c["signo"], "Estado": c["estado"], "Motivos": _texto(c["motivos"]),
            "Confianza_modelo": p.get("confianza_modelo"), "Confianza_final": c["confianza_final"],
            "Signo_principal": c["signo_principal"], "Signo_secundario": c["signo_secundario"],
            "Efecto": p.get("efecto"), "Id_frase": p.get("id_frase"), "Cita": p.get("justificacion_literal"),
            "Cita_verificada": p.get("cita_verificada"), "Tipo_evidencia": p.get("tipo_evidencia"),
            "Organismo": p.get("organismo"), "Tipo_celular": p.get("tipo_celular"),
            "Razonamiento": p.get("razonamiento_corto"), "Termino_origen": caso.termino_origen,
            "Respaldo_ruta": caso.respaldo_ruta, "Modelo_principal": principal, "Modelo_secundario": secundario})
        por_ruta = {r["go_id"]: r for r in p.get("rutas", [])}
        for go_id, nombre_ruta, _ in caso.rutas:
            r = por_ruta.get(go_id, {})
            signo_ruta = r.get("signo_ruta", SIGNO_DESCONOCIDO)
            motivos = c["motivos"] + ([r["motivo_ruta"]] if r.get("motivo_ruta") else [])
            pol = pol_go.get((caso.gen, go_id, caso.pmid), "")
            if signo_ruta in SIGNOS and pol and pol != signo_ruta:
                motivos.append("discrepancia_polaridad_GO")
            estado = c["estado"] if c["estado"] == ESTADO_PENDIENTE else _estado(signo_ruta, motivos)
            rutas.append({
                "Gen": caso.gen, "GO_ID": go_id, "Ruta_Nombre": nombre_ruta, "PMID": caso.pmid,
                "Proceso_ID": caso.nucleo_id, "Proceso": caso.nucleo_nombre, "Signo_ruta": signo_ruta,
                "Estado": estado, "Motivos": _texto(motivos),
                "Confianza_final": c["confianza_final"] if signo_ruta in SIGNOS else None,
                "Polaridad_GO": pol, "Destino": destinos.get((caso.gen, go_id), ""),
                "Signo_principal": c["signo_principal"], "Signo_secundario": c["signo_secundario"],
                "Id_frase": p.get("id_frase"), "Cita": p.get("justificacion_literal")})
    for caso in cerrados:  # filtro previo: UNKNOWN sin llamar al LLM
        base = {"Gen": caso.gen, "PMID": caso.pmid, "Proceso_ID": caso.nucleo_id, "Proceso": caso.nucleo_nombre,
                "Estado": ESTADO_NO_CONCLUYENTE, "Motivos": "no_menciona_gen"}
        preguntas.append({**base, "Signo": SIGNO_DESCONOCIDO})
        for go_id, nombre_ruta, _ in caso.rutas:
            rutas.append({**base, "GO_ID": go_id, "Ruta_Nombre": nombre_ruta, "Signo_ruta": SIGNO_DESCONOCIDO,
                          "Polaridad_GO": pol_go.get((caso.gen, go_id, caso.pmid), ""),
                          "Destino": destinos.get((caso.gen, go_id), "")})
    return pd.DataFrame(preguntas), pd.DataFrame(rutas)


def escribir(df_preguntas: pd.DataFrame, df_rutas: pd.DataFrame, ruta: Path = FICHERO_RESULTADOS) -> Path:
    """Excel de salida (regenerable desde el registro, ADR-004): hojas Por_ruta, Preguntas y Resumen."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    resumen = pd.concat([
        df_rutas.groupby(["Estado", "Signo_ruta"]).size().rename("Filas_por_ruta"),
        df_preguntas.groupby(["Estado", "Signo"]).size().rename("Preguntas").rename_axis(["Estado", "Signo_ruta"]),
    ], axis=1).fillna(0).astype(int).reset_index().rename(columns={"Signo_ruta": "Signo"})
    with pd.ExcelWriter(ruta) as w:
        df_rutas.to_excel(w, sheet_name="Por_ruta", index=False)
        df_preguntas.to_excel(w, sheet_name="Preguntas", index=False)
        resumen.to_excel(w, sheet_name="Resumen", index=False)
    return ruta
