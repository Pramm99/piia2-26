"""Selección del gold set y plantilla de etiquetado a ciegas (spec «benchmark-gold-set»).

Unidad de caso: la pregunta (gen, PMID, proceso núcleo), la misma que responden v2_veredicto y
v1_proceso_gen. La etiqueta es el efecto del gen sobre ese proceso según el abstract (INCREASES / DECREASES /
NO_CLEAR_EFFECT); el signo sobre cada ruta lo compone el código igual que con los modelos.

Muestra (semilla fija): 60 casos de las rutas activadas, sin los pares aceptar_GO ni los que el filtro previo
cierra sin LLM (no_menciona_gen):
  - 21 con Polaridad_GO de signo conocido en alguna de sus rutas (11 «+1» y 10 «-1», por la primera ruta con signo);
  - 39 sin ella;
  - como máximo 5 por gen;
  - CD7 / PMID 10652336 (receptor frente a ligando) siempre dentro.
Se excluyen los casos usados en las pruebas de coste (ruta GO:0002443 e ICAM1), salvo CD7/10652336: quedan
como conjunto de desarrollo para ajustar el prompt.
12 casos (20 %) se marcan para doble etiquetado.

Uso (desde codigo/):
  python evaluacion/seleccionar_gold.py <excel de la Fase 1> [carpeta de datos de esa ejecución] [--actualizar|--v4]
Con --actualizar no se vuelve a sortear: se conservan los casos del gold_casos.jsonl actual que siguen existiendo
en el Excel nuevo y solo se sustituyen los que han desaparecido (ver actualizar).
Con --v4 el gold pasa a tener genes up y down (ver version_up_down): 65 casos up del gold v3 (los 60 de la muestra
aleatoria del v2, los NO_EFFECT y el resto sorteado) y 35 casos nuevos de las rutas suprimidas (genes down).
Escribe en evaluacion/: gold_casos.jsonl (selección, con la información para evaluar; NO se enseña a los
anotadores) y plantilla_etiquetado.jsonl / .xlsx (a ciegas).
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
N_GO_POS, N_GO_NEG, N_SIN_GO, MAX_POR_GEN, N_DOBLE = 11, 10, 39, 5, 12
FORZADO = ("CD7", "10652336")
DESARROLLO_RUTA, DESARROLLO_GEN = "GO:0002443", "ICAM1"
# --v4: 65 up + 35 down; los estratos GO de los down, en la proporción de la muestra original (11/10/39 de 60)
N_UP_V4, CUPO_DOWN = 65, {"+1": 6, "-1": 6, "": 23}
ETIQUETAS = AQUI / "etiquetas_provisionales"


def caso_id(c):
    return f"{c.gen}|{c.pmid}|{c.nucleo_id}"


def polaridad_caso(c, pol):
    """(signo de GO +1/-1, ruta, factor efecto->ruta) de la primera ruta del caso con signo, o ('', '', None)."""
    for ruta, _, factor in c.rutas:
        p = pol.get((c.gen, c.pmid, ruta), "")
        if p in ("+1", "-1"):
            return p, ruta, factor
    return "", "", None


def _universo(ruta_excel, lista="Activada"):
    """(casos, polaridades GO, candidatos sin el conjunto de desarrollo, caso forzado, nº de desarrollo) de una
    lista de CIMUS: «Activada» (genes up) o «Suprimida» (genes down)."""
    df = pendientes_de_llm(cargar_hoja(ruta_excel))
    df = df[df["Estado_Original"] == lista]
    casos, _ = construir_casos(df)
    pol = {(str(g).upper(), str(p).split(".")[0], r): str(v)
           for g, p, r, v in zip(df["Gen"], df["PMID"], df["GO_ID"], df["Polaridad_GO"].fillna(""))}
    forzado = [c for c in casos if (c.gen, c.pmid) == FORZADO][:1]
    desarrollo = {caso_id(c) for c in casos
                  if c.gen == DESARROLLO_GEN or any(r == DESARROLLO_RUTA for r, _, _ in c.rutas)}
    candidatos = [c for c in casos if caso_id(c) not in desarrollo]
    return casos, pol, candidatos, forzado, len(desarrollo)


def actualizar(ruta_excel, previos):
    """Rehace el gold set sobre una salida nueva de la Fase 1 SIN volver a sortearlo: cada caso que sigue
    existiendo conserva su id (y su etiqueta); cada uno que ya no existe se sustituye por un caso nuevo del mismo
    estrato de GO (semilla fija, máx. 5 por gen), con id nuevo y la misma marca de doble etiquetado.
    Devuelve ([(id, caso, doble)], pol, ids que desaparecen, ids nuevos, nº de casos, nº de desarrollo)."""
    casos, pol, candidatos, _, n_dev = _universo(ruta_excel)
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
    random.Random(SEMILLA + 2).shuffle(libres)
    siguiente, nuevos = max(int(g["id"][1:]) for g in previos) + 1, []
    for g in faltan:
        for c in libres:
            if caso_id(c) not in usados and polaridad_caso(c, pol)[0] == g["polaridad_go"] \
                    and por_gen[c.gen] < MAX_POR_GEN:
                gid = f"G{siguiente:02d}"
                filas.append((gid, c, g["doble"]))
                usados.add(caso_id(c))
                por_gen[c.gen] += 1
                nuevos.append(gid)
                siguiente += 1
                break
    return filas, pol, [g["id"] for g in faltan], nuevos, len(casos), n_dev


def _sortear(candidatos, pol, cupo, elegidos, semilla):
    """Añade a elegidos casos al azar por estrato de GO hasta llenar el cupo, con máx. MAX_POR_GEN por gen."""
    candidatos = list(candidatos)
    random.Random(semilla).shuffle(candidatos)
    cupo, por_gen = dict(cupo), Counter(c.gen for c in elegidos)
    for c in candidatos:
        estrato = polaridad_caso(c, pol)[0]
        if cupo[estrato] > 0 and por_gen[c.gen] < MAX_POR_GEN:
            elegidos.append(c)
            cupo[estrato] -= 1
            por_gen[c.gen] += 1
    if any(cupo.values()):
        raise ValueError(f"No hay casos suficientes para el cupo: faltan {cupo}")
    return elegidos


def version_up_down(ruta_excel, previos):
    """Gold v4: N_UP_V4 casos up del gold actual y los casos down de CUPO_DOWN, nuevos.
    Up: se conservan los 60 de la muestra aleatoria del v2 (los añadidos en el v3 se buscaron por contener una
    negación) y los NO_EFFECT, la clase rara; el resto hasta N_UP_V4 se sortea entre los demás añadidos del v3.
    Down: sorteo por estrato de GO entre las preguntas de las rutas suprimidas, con id nuevo y doble etiquetado.
    Devuelve ([(id, caso, doble)], pol, nº de casos up, nº de casos down)."""
    ids_v2 = {e["id"] for e in map(json.loads, open(ETIQUETAS / "gold_provisional_v2.jsonl", encoding="utf-8"))}
    neutros = {e["id"] for e in map(json.loads, open(ETIQUETAS / "gold_provisional_v3.jsonl", encoding="utf-8"))
               if e["efecto"] == "NO_EFFECT"}
    casos_up, pol_up, _, _, _ = _universo(ruta_excel, "Activada")
    por_id = {caso_id(c): c for c in casos_up}
    faltan = [g["id"] for g in previos if g["caso"] not in por_id]
    if faltan:
        raise ValueError(f"Casos del gold que ya no existen en el Excel: {faltan}")
    fijos = [g for g in previos if g["id"] in ids_v2 | neutros]
    resto = [g for g in previos if g["id"] not in ids_v2 | neutros]
    sorteados = random.Random(SEMILLA + 3).sample(resto, N_UP_V4 - len(fijos))
    filas = [(g["id"], por_id[g["caso"]], g["doble"]) for g in fijos + sorteados]

    casos_down, pol_down, candidatos, _, _ = _universo(ruta_excel, "Suprimida")
    down = sorted(_sortear(candidatos, pol_down, CUPO_DOWN, [], SEMILLA + 4), key=caso_id)
    siguiente = max(int(g["id"][1:]) for g in previos) + 1
    filas += [(f"G{siguiente + i}", c, True) for i, c in enumerate(down)]
    return filas, {**pol_up, **pol_down}, len(casos_up), len(casos_down)


def seleccionar(ruta_excel):
    casos, pol, candidatos, forzado, n_dev = _universo(ruta_excel)

    cupo = {"+1": N_GO_POS, "-1": N_GO_NEG, "": N_SIN_GO}
    for c in forzado:
        cupo[polaridad_caso(c, pol)[0]] -= 1
    elegidos = _sortear(candidatos, pol, cupo, list(forzado), SEMILLA)
    elegidos.sort(key=caso_id)
    dobles = set(caso_id(c) for c in random.Random(SEMILLA + 1).sample(elegidos, N_DOBLE))
    return elegidos, pol, dobles, len(casos), n_dev


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--actualizar" in sys.argv:
        previos = [json.loads(l) for l in open(AQUI / "gold_casos.jsonl", encoding="utf-8")]
        filas, pol, quitados, nuevos, total, n_dev = actualizar(args[0], previos)
        print(f"Actualización: desaparecen {quitados}; nuevos {nuevos}")
    elif "--v4" in sys.argv:
        previos = [json.loads(l) for l in open(AQUI / "gold_casos.jsonl", encoding="utf-8")]
        filas, pol, n_up, n_down = version_up_down(args[0], previos)
        total, n_dev = f"{n_up} up + {n_down} down", 0
    else:
        elegidos, pol, dobles, total, n_dev = seleccionar(args[0])
        filas = [(f"G{i:02d}", c, caso_id(c) in dobles) for i, c in enumerate(elegidos, 1)]
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
    print(f"{len(casos_out)} casos de {total} (desarrollo excluido: {n_dev}); estratos GO {estratos}; "
          f"genes {genes.size}, máx. por gen {genes.max()}; dobles {sum(x['doble'] for x in casos_out)}")
