"""Candidatos a caso NEUTRO para el gold set (el gen NO cambia el proceso según el abstract).

Los abstracts casi nunca informan de que un gen no cambia un proceso, así que un sorteo al azar apenas da casos
neutros y la clase no se puede medir. Este script busca, entre las preguntas de las dos listas de CIMUS que no
están en el gold set ni en el conjunto de desarrollo, abstracts con una frase de negación («did not affect», «was
dispensable», «no role», «unchanged»...) que nombra al gen. Son solo candidatos: la etiqueta la ponen después
anotadores a ciegas, y solo entran en el gold set los que estos etiquetan como NO_EFFECT.

  python evaluacion/buscar_neutros.py <excel de la Fase 1> <carpeta de datos de esa ejecución>
Escribe evaluacion/candidatos_neutros.jsonl (orden aleatorio con semilla fija, máx. 2 por gen).
"""
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.argv = sys.argv[:3]
import seleccionar_gold as S  # noqa: E402  (configura OBO y cachés con los argumentos)

SEMILLA = 20261110
MAX_POR_GEN = 2
NEGACION = re.compile(
    r"\b(did not|does not|do not|didn't|doesn't|had no|has no|have no|without any|no significant|"
    r"not significantly|was dispensable|were dispensable|is dispensable|are dispensable|dispensable for|"
    r"not required|not necessary|unaffected|not affected|no effect|no change|no difference|not alter|"
    r"failed to (?:affect|alter|change|influence|modify)|independent(?:ly)? of|normal|comparable|similar(?:ly)? to|"
    r"intact|unchanged|unaltered|not impaired|"
    r"no (?:role|impact|influence|requirement|detectable|measurable|significant)|did not differ|"
    r"was not (?:required|necessary|needed|involved)|not involved|redundant|nor)\b", re.IGNORECASE)


def menciona(frase, c):
    nombres = [c.gen] + list(c.alias)
    return any(re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", frase, re.IGNORECASE) for n in nombres)


def candidatos(ruta_excel):
    _, pol, libres, _ = S._universo(ruta_excel)
    en_gold = {json.loads(l)["caso"] for l in open(AQUI / "gold_casos.jsonl", encoding="utf-8")}
    out = []
    for c in libres:
        if S.caso_id(c) in en_gold:
            continue
        frases = [(f"S{i}", f) for i, f in enumerate(c.frases, 1)]
        hits = [(i, f) for i, f in frases if NEGACION.search(f) and menciona(f, c)]
        if hits:
            out.append((c, hits))
    random.Random(SEMILLA).shuffle(out)
    por_gen, elegidos = Counter(), []
    for c, hits in out:
        if por_gen[c.gen] < MAX_POR_GEN:
            por_gen[c.gen] += 1
            elegidos.append((c, hits))
    return elegidos, pol, len(out)


if __name__ == "__main__":
    elegidos, pol, total = candidatos(sys.argv[1])
    with open(AQUI / "candidatos_neutros.jsonl", "w", encoding="utf-8") as f:
        for c, hits in elegidos:
            p = S.polaridad_caso(c, pol)
            f.write(json.dumps({"caso": S.caso_id(c), "gen": c.gen, "pmid": c.pmid, "nucleo_id": c.nucleo_id,
                                "proceso": c.nucleo_nombre, "polaridad_go": p[0], "ruta_go": p[1],
                                "factor_ruta_go": p[2], "rutas": [list(r) for r in c.rutas],
                                "otros_nombres": list(c.alias), "titulo": c.titulo,
                                "frases": {f"S{j}": x for j, x in enumerate(c.frases, 1)},
                                "frases_negacion": [i for i, _ in hits]}, ensure_ascii=False) + "\n")
    print(f"{total} preguntas con una negación que nombra al gen; {len(elegidos)} candidatos")
