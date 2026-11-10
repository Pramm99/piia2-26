"""Mantenimiento del gold set y plantilla de etiquetado a ciegas (spec «benchmark-gold-set»).

Unidad de caso: la pregunta (gen, PMID, proceso núcleo), la misma que responden los modelos. La etiqueta es el
efecto del gen sobre ese proceso según el abstract (INCREASES / DECREASES / NO_EFFECT / NO_CLEAR_EFFECT); el
signo sobre cada ruta lo compone el código igual que con los modelos.

El gold set (gold_casos.jsonl) tiene 100 casos de las dos listas de CIMUS: 65 de genes up y 35 de genes down,
sorteados por estrato de Polaridad_GO (con o sin signo), con un máximo de 5 por gen y CD7 / PMID 10652336
(receptor frente a ligando) dentro. Quedan fuera los pares aceptar_GO, los que el filtro previo cierra sin LLM
(no_menciona_gen) y el conjunto de desarrollo usado para ajustar el prompt (la ruta GO:0002443 y el gen ICAM1,
salvo CD7/10652336).

Uso (desde codigo/):
  python evaluacion/seleccionar_gold.py <excel de la Fase 1> [carpeta de datos de esa ejecución]
Rehace el gold set sobre una salida nueva de la Fase 1 SIN volver a sortear (ver actualizar) y escribe en
evaluacion/: gold_casos.jsonl (selección, con la información para evaluar; NO se enseña a los anotadores) y
plantilla_etiquetado.jsonl / .xlsx (a ciegas).
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CODIGO = AQUI.parent
sys.path.insert(0, str(CODIGO / "extraer_info"))
import config  # noqa: E402

if len(sys.argv) > 2:  # mismos OBO y cachés que la ejecución de la Fase 1 que generó el Excel
    datos = Path(sys.argv[2])
    config.OBO_FILE = str(datos / "go-basic.obo")
    config.MYGENE_CACHE = str(datos / "cache_mygene.json")
sys.path.insert(0, str(CODIGO))

import pandas as pd  # noqa: E402

from consulta_gen.casos import construir_casos  # noqa: E402
from consulta_gen.lectura import cargar_hoja, pendientes_de_llm  # noqa: E402

SEMILLA = 20261109
MAX_POR_GEN = 5
DESARROLLO_RUTA, DESARROLLO_GEN, DESARROLLO_DENTRO = "GO:0002443", "ICAM1", ("CD7", "10652336")


def caso_id(c):
    return f"{c.gen}|{c.pmid}|{c.nucleo_id}"


def polaridad_caso(c, pol):
    """(signo de GO +1/-1, ruta, factor efecto->ruta) de la primera ruta del caso con signo, o ('', '', None)."""
    for ruta, _, factor in c.rutas:
        p = pol.get((c.gen, c.pmid, ruta), "")
        if p in ("+1", "-1"):
            return p, ruta, factor
    return "", "", None


def _universo(ruta_excel):
    """(casos, polaridades GO, candidatos sin el conjunto de desarrollo, lista de CIMUS de cada gen) de las dos
    listas: «Activada» (genes up) y «Suprimida» (genes down). Un gen está en una sola."""
    df = pendientes_de_llm(cargar_hoja(ruta_excel))
    casos, _ = construir_casos(df)
    pol = {(str(g).upper(), str(p).split(".")[0], r): str(v)
           for g, p, r, v in zip(df["Gen"], df["PMID"], df["GO_ID"], df["Polaridad_GO"].fillna(""))}
    lista = {str(g).upper(): e for g, e in zip(df["Gen"], df["Estado_Original"])}
    desarrollo = {caso_id(c) for c in casos if (c.gen, c.pmid) != DESARROLLO_DENTRO
                  and (c.gen == DESARROLLO_GEN or any(r == DESARROLLO_RUTA for r, _, _ in c.rutas))}
    candidatos = [c for c in casos if caso_id(c) not in desarrollo]
    return casos, pol, candidatos, lista


def actualizar(ruta_excel, previos):
    """Rehace el gold set sobre una salida nueva de la Fase 1 SIN volver a sortearlo: cada caso que sigue
    existiendo conserva su id (y su etiqueta); cada uno que ya no existe se sustituye por un caso nuevo de la misma
    lista de CIMUS y del mismo estrato de GO (semilla fija, máx. 5 por gen), con id nuevo y la misma marca de doble
    etiquetado. Devuelve ([(id, caso, doble)], pol, ids que desaparecen, ids nuevos, nº de casos)."""
    casos, pol, candidatos, lista = _universo(ruta_excel)
    por_id = {caso_id(c): c for c in casos}
    filas, faltan = [], []
    for g in previos:
        c = por_id.get(g["caso"])
        if c:
            filas.append((g["id"], c, g["doble"]))
        else:
            faltan.append(g)
    usados = {caso_id(c) for _, c, _ in filas}
    por_gen = Counter(c.gen for _, c, _ in filas)
    libres = [c for c in candidatos if caso_id(c) not in usados]
    random.Random(SEMILLA).shuffle(libres)
    siguiente, nuevos = max(int(g["id"][1:]) for g in previos) + 1, []
    for g in faltan:
        for c in libres:
            misma_lista = g["gen"] not in lista or lista[c.gen] == lista[g["gen"]]
            if caso_id(c) not in usados and polaridad_caso(c, pol)[0] == g["polaridad_go"] and misma_lista \
                    and por_gen[c.gen] < MAX_POR_GEN:
                gid = f"G{siguiente:02d}"
                filas.append((gid, c, g["doble"]))
                usados.add(caso_id(c))
                por_gen[c.gen] += 1
                nuevos.append(gid)
                siguiente += 1
                break
    return filas, pol, [g["id"] for g in faltan], nuevos, len(casos)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    previos = [json.loads(l) for l in open(AQUI / "gold_casos.jsonl", encoding="utf-8")]
    filas, pol, quitados, nuevos, total = actualizar(args[0], previos)
    print(f"Desaparecen {quitados}; nuevos {nuevos}")
    filas.sort(key=lambda f: int(f[0][1:]))
    casos_out, plantilla = [], []
    for gid, c, doble in filas:
        casos_out.append({"id": gid, "caso": caso_id(c), "gen": c.gen, "pmid": c.pmid, "nucleo_id": c.nucleo_id,
                          "proceso": c.nucleo_nombre, "polaridad_go": polaridad_caso(c, pol)[0],
                          "ruta_go": polaridad_caso(c, pol)[1], "factor_ruta_go": polaridad_caso(c, pol)[2],
                          "rutas": [list(r) for r in c.rutas], "doble": doble})
        plantilla.append({"id": gid, "gen": c.gen, "otros_nombres": list(c.alias), "pmid": c.pmid,
                          "proceso": c.nucleo_nombre, "titulo": c.titulo,
                          "frases": {f"S{j}": f for j, f in enumerate(c.frases, 1)}, "doble": doble})
    (AQUI / "gold_casos.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in casos_out),
                                           encoding="utf-8")
    (AQUI / "plantilla_etiquetado.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in plantilla), encoding="utf-8")
    filas = [{"id": p["id"], "gen": p["gen"], "otros_nombres": ", ".join(p["otros_nombres"]), "pmid": p["pmid"],
              "proceso": p["proceso"], "titulo": p["titulo"],
              "abstract": "\n".join(f"[{k}] {v}" for k, v in p["frases"].items()),
              "doble_etiquetado": "sí" if p["doble"] else "", "efecto": "", "motivo": "", "id_frase": "", "cita": "",
              "confianza": "", "nota": "", "anotador": ""} for p in plantilla]  # campos de guia_etiquetado.md
    pd.DataFrame(filas).to_excel(AQUI / "plantilla_etiquetado.xlsx", index=False)
    estratos = {k: sum(x["polaridad_go"] == k for x in casos_out) for k in ("+1", "-1", "")}
    genes = pd.Series([x["gen"] for x in casos_out]).value_counts()
    print(f"{len(casos_out)} casos de {total}; estratos GO {estratos}; genes {genes.size}, "
          f"máx. por gen {genes.max()}; dobles {sum(x['doble'] for x in casos_out)}")
