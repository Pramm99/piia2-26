"""Benchmark sobre el gold set (spec «benchmark-gold-set»).

  python evaluacion/evaluar_gold.py ejecutar <modelo> <excel Fase 1> [carpeta de datos] [presupuesto]   llama
  python evaluacion/evaluar_gold.py informe <etiquetas.jsonl> [<etiquetas_doble.jsonl>]    métricas, 0 llamadas
  (con --dir=<nombre> los registros van a data/<nombre>/ en vez de data/benchmark/;
   con --prompt=v2_veredicto se ejecuta la versión de producción en vez de v1_proceso_gen;
   con --comunes=N el informe usa solo los N primeros casos que han respondido todos los modelos)

ejecutar: cada modelo responde las preguntas del gold set con su forma de llamar más eficiente, por gen y
troceado con su presupuesto (v1_proceso_gen o v2_veredicto). Las respuestas van a data/benchmark/<modelo>/
(registro reanudable; si se corta por el límite diario, volver a lanzarlo solo hace lo pendiente).
informe: vuelve a validar las respuestas crudas del registro (sin llamar) y las compara con las etiquetas:
precisión de las respuestas dadas, cobertura, recall de UNKNOWN, matriz de confusión, JSON válido, citas
verificadas, acuerdo con Polaridad_GO, latencia y llamadas, con IC 95 % por bootstrap; kappa de Cohen entre
anotadores en los casos dobles; y calibración de los signos (confianza_modelo y confianza_final): tabla de
fiabilidad, ECE, AUROC y curva riesgo-cobertura por umbral.
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CODIGO = AQUI.parent
# --dir=<nombre>: carpeta de registros dentro de data/ (por defecto benchmark); se quita de sys.argv
_DIR = [a for a in sys.argv if a.startswith("--dir=")]
sys.argv = [a for a in sys.argv if not a.startswith("--dir=")]
_PROMPT = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--prompt=")]
sys.argv = [a for a in sys.argv if not a.startswith("--prompt=")]
# --comunes=N (informe): solo los N primeros casos del gold set que han respondido TODOS los modelos de la carpeta,
# para comparar sobre los mismos casos cuando alguna ejecución se cortó por el límite diario
_COMUNES = [int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--comunes=")]
sys.argv = [a for a in sys.argv if not a.startswith("--comunes=")]
BENCH = CODIGO / "data" / (_DIR[0].split("=", 1)[1] if _DIR else "benchmark")
sys.path.insert(0, str(CODIGO / "extraer_info"))
import config  # noqa: E402

if len(sys.argv) > 4 and sys.argv[1] == "ejecutar":
    config.OBO_FILE = str(Path(sys.argv[4]) / "go-basic.obo")
    config.MYGENE_CACHE = str(Path(sys.argv[4]) / "cache_mygene.json")
sys.path.insert(0, str(CODIGO))

from consulta_gen.confianza import confianza_final  # noqa: E402
from consulta_gen.esquema import V1_GEN, V2_VEREDICTO  # noqa: E402
from consulta_gen.prompt import CONFIG_V1_GEN, CONFIG_V2, construir_prompt  # noqa: E402
from consulta_gen.registro import Registro, clave  # noqa: E402
from consulta_gen.respuesta import validar_respuesta  # noqa: E402

A_SIGNO = {"INCREASES": "+1", "DECREASES": "-1", "NO_CLEAR_EFFECT": "UNKNOWN"}
CLASES = ("+1", "-1", "neutro", "UNKNOWN")
CONFIG = {V1_GEN: CONFIG_V1_GEN, V2_VEREDICTO: CONFIG_V2}[_PROMPT[0] if _PROMPT else V1_GEN]


def etiqueta(e):
    """Etiqueta del anotador -> clase: un NO_CLEAR_EFFECT con no_effect_found es neutro (el gen no cambia el
    proceso); el resto de NO_CLEAR_EFFECT, UNKNOWN."""
    return "neutro" if e["efecto"] == "NO_CLEAR_EFFECT" and e.get("motivo") == "no_effect_found" else A_SIGNO[e["efecto"]]
# Calibración: el otro modelo con el que se compara cada uno para confianza_final (la pareja propuesta para
# producción es gpt-oss + Gemini; las alternativas se emparejan con Gemini)
SEGUNDO_MODELO = {"groq-gpt-oss-120b": "gemini-3.5-flash-lite", "gemini-3.5-flash-lite": "groq-gpt-oss-120b",
                  "groq-qwen3.8-27b": "gemini-3.5-flash-lite", "ollama-qwen3-8b": "gemini-3.5-flash-lite",
                  "cerebras-gpt-oss-120b": "gemini-3.5-flash-lite"}
TRAMOS = ((0, 50), (50, 70), (70, 90), (90, 101))  # los de las anclas de la regla 13
UMBRALES = (0, 50, 60, 70, 80, 90)


def gold_casos():
    return [json.loads(l) for l in open(AQUI / "gold_casos.jsonl", encoding="utf-8")]


def construir_preguntas(ruta_excel):
    """(id, pregunta v1_proceso_gen) de cada caso del gold set, en su orden."""
    sys.path.insert(0, str(AQUI))
    from seleccionar_gold import _universo, caso_id
    elegidos = {caso_id(c): c for c in _universo(ruta_excel)[0]}  # por clave: vale también tras --actualizar
    return [(g["id"], construir_prompt(elegidos[g["caso"]], CONFIG)) for g in gold_casos()]


def ejecutar_modelo(modelo, ruta_excel, presupuesto=None):
    """presupuesto: tope de tokens por llamada distinto del de cliente.MODELOS (p. ej. Ollama con el contexto
    por defecto de 4.096 tokens, cuando no hay RAM para más: cada pregunta va sola)."""
    import dataclasses
    import time
    from consulta_gen.cliente import MODELOS, ClienteOpenAICompatible
    from consulta_gen.ejecucion import ejecutar
    cfg = MODELOS[modelo]
    if presupuesto:
        cfg = dataclasses.replace(cfg, presupuesto_llamada=presupuesto)
    preguntas = construir_preguntas(ruta_excel)
    destino = BENCH / modelo
    t0 = time.time()
    _, rs = ejecutar([p for _, p in preguntas], [ClienteOpenAICompatible(cfg)],
                     Registro(destino / "respuestas_llm.jsonl"), cada=5)
    destino.mkdir(parents=True, exist_ok=True)
    with open(destino / "ejecuciones.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "pared_s": round(time.time() - t0, 1),
                            "llamadas": rs.llamadas, "pendientes": rs.pendientes, "cortadas": rs.cortadas,
                            "agotados": rs.agotados, "tokens": rs.tokens}) + "\n")
    # Para el informe: la clave de registro de cada caso del gold set (así el informe no necesita la Fase 1)
    (destino / "claves.json").write_text(json.dumps({gid: list(clave(p, modelo)) for gid, p in preguntas}),
                                         encoding="utf-8")
    (destino / "prompts.json").write_text(json.dumps(
        {gid: {"frases": list(p.evidencia.frases), "titulo": p.evidencia.titulo} for gid, p in preguntas},
        ensure_ascii=False), encoding="utf-8")
    print(f"FIN {modelo}: llamadas {rs.llamadas}, pendientes {rs.pendientes}, tokens {rs.tokens}", flush=True)


# ------------------------------------------------------------------------------------------------ informe
def _regla_go_v2(s, caso):
    """v2_veredicto: como en producción (resultados.ruta_v2), un veredicto con cita verificada que coincide con la
    Polaridad_GO del caso se acepta aunque su confianza no llegue al umbral."""
    if (s.get("version") != V2_VEREDICTO or s["signo"] != "UNKNOWN" or not caso["polaridad_go"]
            or caso["factor_ruta_go"] is None or not s.get("cita_verificada") or s.get("signo_llm") not in ("+1", "-1")):
        return s
    if {"+1": 1, "-1": -1}[s["signo_llm"]] * caso["factor_ruta_go"] != int(caso["polaridad_go"]):
        return s
    motivos = [m for m in s["motivos"] if m != "baja_confianza"] + ["coincide_polaridad_GO"]
    return {**s, "signo": s["signo_llm"], "motivos": motivos, "estado": "resuelto"}


def _ic(valores, estadistico, n=2000, semilla=7):
    """IC 95 % por bootstrap (percentiles) de estadistico(lista)."""
    if not valores:
        return None, None
    rng, est = random.Random(semilla), []
    for _ in range(n):
        m = [valores[rng.randrange(len(valores))] for _ in valores]
        v = estadistico(m)
        if v is not None:
            est.append(v)
    est.sort()
    return (est[int(0.025 * len(est))], est[int(0.975 * len(est)) - 1]) if est else (None, None)


def _precision(pares):
    dados = [(g, m) for g, m in pares if m != "UNKNOWN"]
    return sum(g == m for g, m in dados) / len(dados) if dados else None


def _cobertura(pares):
    return sum(m != "UNKNOWN" for _, m in pares) / len(pares) if pares else None


def _recall_unk(pares):
    unk = [(g, m) for g, m in pares if g == "UNKNOWN"]
    return sum(m == "UNKNOWN" for _, m in unk) / len(unk) if unk else None


def _exactitud(pares):
    return sum(g == m for g, m in pares) / len(pares) if pares else None


def _kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def _fmt(v, ic=None):
    if v is None:
        return "—"
    s = f"{100 * v:.0f} %"
    return s + (f" ({100 * ic[0]:.0f}–{100 * ic[1]:.0f})" if ic and ic[0] is not None else "")


def _casos_comunes(gold, n):
    """Los n primeros casos (orden del gold set) que tienen respuesta de todos los modelos de BENCH."""
    respondidos = []
    for d in sorted(BENCH.iterdir()):
        if (d / "claves.json").exists():
            claves = json.loads((d / "claves.json").read_text(encoding="utf-8"))
            reg = Registro(d / "respuestas_llm.jsonl")
            respondidos.append({gid for gid in gold if reg.get(claves[gid]) is not None})
    comunes = [gid for gid in gold if all(gid in r for r in respondidos)]
    if len(comunes) < n:
        raise ValueError(f"Solo hay {len(comunes)} casos respondidos por todos los modelos (se pidieron {n})")
    elegidos = comunes[:n]
    print(f"Casos comunes a todos los modelos: {len(comunes)}; se usan los {n} primeros. "
          f"Fuera: {', '.join(g for g in gold if g not in elegidos)}")
    return {gid: gold[gid] for gid in elegidos}


def informe(ruta_etiquetas, ruta_doble=None):
    gold = {g["id"]: g for g in gold_casos()}
    etq = {e["id"]: e for e in map(json.loads, open(ruta_etiquetas, encoding="utf-8"))}
    falta = [g for g in gold if g not in etq]
    if falta:
        raise ValueError(f"Faltan etiquetas: {falta}")
    if _COMUNES:
        gold = _casos_comunes(gold, _COMUNES[0])
    verdad = {g: etiqueta(etq[g]) for g in gold}
    print(f"Gold set: {len(gold)} casos; etiquetas {dict(Counter(verdad.values()))}\n")

    if ruta_doble:
        dob = {e["id"]: etiqueta(e) for e in map(json.loads, open(ruta_doble, encoding="utf-8"))}
        ids = [g for g in dob if g in verdad]
        a, b = [verdad[g] for g in ids], [dob[g] for g in ids]
        print(f"Acuerdo entre anotadores ({len(ids)} casos dobles): {sum(x == y for x, y in zip(a, b))}/{len(ids)}, "
              f"kappa de Cohen {_kappa(a, b):.2f}")
        for g in ids:
            if verdad[g] != dob[g]:
                print(f"   {g}: {verdad[g]} frente a {dob[g]}")
        print()

    cab = ("| Modelo | Respondidas | JSON válido | Citas verificadas | Exactitud | Precisión (+1/−1 dados) | "
           "Cobertura | Recall UNKNOWN | Acuerdo GO | Llamadas | Latencia media | Tiempo total | "
           "Tokens (entrada+salida) |")
    print(cab)
    print("|" + "---|" * (cab.count("|") - 1))
    matrices, salidas = {}, {}
    for d in sorted(BENCH.iterdir()):
        if not (d / "claves.json").exists():
            continue
        modelo = d.name
        claves = json.loads((d / "claves.json").read_text(encoding="utf-8"))
        prompts = json.loads((d / "prompts.json").read_text(encoding="utf-8"))
        reg = Registro(d / "respuestas_llm.jsonl")
        pares, n_json, n_cita, n_firmadas, respondidas, go = [], 0, 0, 0, 0, []
        for gid in gold:
            linea = reg.get(claves[gid])
            if linea is None:
                continue
            respondidas += 1
            s = _regla_go_v2(validar_respuesta(_Prompt(gid, prompts[gid], claves[gid]), linea["respuesta_cruda"]), gold[gid])
            salidas.setdefault(modelo, {})[gid] = s
            n_json += "json_invalido" not in s["motivos"]
            if s.get("signo_llm") in ("+1", "-1", "neutro"):
                n_firmadas += 1
                n_cita += s["cita_verificada"]
            pares.append((verdad[gid], s["signo"]))
            if gold[gid]["polaridad_go"] and s["signo"] in ("+1", "-1"):  # signo sobre la ruta de la que sale GO
                ruta_signo = {"+1": 1, "-1": -1}[s["signo"]] * gold[gid]["factor_ruta_go"]
                go.append(int(gold[gid]["polaridad_go"]) == ruta_signo)
        lat = _latencias(d)
        tok = Counter()  # de todas las llamadas registradas (también las de ejecuciones cortadas a medias)
        for linea in map(json.loads, open(d / "llamadas_llm.jsonl", encoding="utf-8")):
            u = linea.get("tokens") or {}
            tok.update({"entrada": u.get("prompt_tokens") or 0, "salida": u.get("completion_tokens") or 0})
        print(f"| {modelo} | {respondidas}/{len(gold)} | {n_json}/{respondidas} | {n_cita}/{n_firmadas} | "
              f"{_fmt(_exactitud(pares), _ic(pares, _exactitud))} | {_fmt(_precision(pares), _ic(pares, _precision))} | "
              f"{_fmt(_cobertura(pares), _ic(pares, _cobertura))} | {_fmt(_recall_unk(pares), _ic(pares, _recall_unk))} | "
              f"{sum(go)}/{len(go)} | {len(lat)} | {sum(lat) / len(lat) if lat else 0:.1f} s | "
              f"{_tiempo_total(d, lat) / 60:.1f} min | {tok['entrada']}+{tok['salida']} |")
        matrices[modelo] = Counter(pares)
    print("\nMatrices de confusión (filas = etiqueta, columnas = modelo):")
    for modelo, m in matrices.items():
        print(f"  {modelo}")
        print("            " + "".join(f"{c:>9}" for c in CLASES))
        for g in CLASES:
            print(f"   {g:>8} " + "".join(f"{m[(g, c)]:>9}" for c in CLASES))
    calibracion(salidas, verdad)


# ------------------------------------------------------------------------------------------- calibración
def _auroc(puntos):
    """P(un signo correcto tiene más confianza que uno erróneo); empates = 0,5. None si falta una de las dos clases."""
    bien = [c for c, ok in puntos if ok]
    mal = [c for c, ok in puntos if not ok]
    if not bien or not mal:
        return None
    return sum((b > m) + 0.5 * (b == m) for b in bien for m in mal) / (len(bien) * len(mal))


def _ece(puntos):
    """Error de calibración esperado: media ponderada por tramo de |acierto − confianza media|."""
    total = 0.0
    for lo, hi in TRAMOS:
        t = [(c, ok) for c, ok in puntos if lo <= c < hi]
        if t:
            total += len(t) / len(puntos) * abs(sum(ok for _, ok in t) / len(t) - sum(c for c, _ in t) / len(t) / 100)
    return total


def calibracion(salidas, verdad):
    """Para cada modelo, sobre los signos que da (+1/−1): ¿acierta un X % de las respuestas con confianza X?
    Con pocos signos (13 en el gold set provisional) es orientativa."""
    print("\nCalibración de los signos dados (acierto = mismo signo que la etiqueta)")
    for modelo, sal in salidas.items():
        otro = salidas.get(SEGUNDO_MODELO.get(modelo), {})
        firmadas = [(gid, s) for gid, s in sal.items() if s["signo"] != "UNKNOWN"]
        revisar = sum("baja_confianza" in s["motivos"] for _, s in firmadas)
        print(f"\n  {modelo}: {len(firmadas)} signos, {revisar} con baja_confianza "
              f"(final con {SEGUNDO_MODELO.get(modelo, '—')} como segundo modelo)")
        for nombre, f in (("confianza_modelo", lambda gid, s: s.get("confianza_modelo")),
                          ("confianza_final", lambda gid, s: confianza_final(s, otro.get(gid)))):
            puntos = [(f(gid, s), s["signo"] == verdad[gid]) for gid, s in firmadas]
            puntos = [(c, ok) for c, ok in puntos if c is not None]
            if not puntos:
                print(f"    {nombre}: sin datos (respuestas anteriores a la regla 13)")
                continue
            auc = _auroc(puntos)
            print(f"    {nombre}: n={len(puntos)}, media {sum(c for c, _ in puntos) / len(puntos):.0f}, acierto "
                  f"{_fmt(sum(ok for _, ok in puntos) / len(puntos))}, ECE {100 * _ece(puntos):.0f} puntos, "
                  f"AUROC {'—' if auc is None else f'{auc:.2f}'}")
            print("      tramo    n  conf. media  acierto")
            for lo, hi in TRAMOS:
                t = [(c, ok) for c, ok in puntos if lo <= c < hi]
                if t:
                    print(f"      {lo:>3}-{min(hi, 100):<3} {len(t):>3}  {sum(c for c, _ in t) / len(t):>11.0f}  "
                          f"{_fmt(sum(ok for _, ok in t) / len(t)):>7}")
            print("      umbral  signos que se quedan  precisión")
            for u in UMBRALES:
                t = [ok for c, ok in puntos if c >= u]
                print(f"      ≥{u:<5} {len(t):>3}/{len(puntos):<3} ({_fmt(len(t) / len(puntos))})"
                      f"{'':>8}{_fmt(sum(t) / len(t)) if t else '—'}")


class _Prompt:
    """Lo mínimo que necesita validar_respuesta para v1_proceso_gen, sin volver a leer la Fase 1."""

    def __init__(self, gid, p, clave_registro):
        version, gen, pmid, nucleo, _, _ = clave_registro
        self.version = version
        self.evidencia = _Caso(gen, pmid, nucleo, p["titulo"], tuple(p["frases"]))


class _Caso:
    def __init__(self, gen, pmid, nucleo, titulo, frases):
        self.gen, self.pmid, self.go_id, self.nucleo_id, self.titulo, self.frases = gen, pmid, nucleo, nucleo, titulo, frases
        self.nucleo_nombre, self.rutas = "", ()


def _tiempo_total(d, lat):
    """Tiempo de pared de las ejecuciones completas (ejecuciones.jsonl, incluye las pausas por límite de ritmo);
    si alguna ejecución se cortó antes de escribir su línea, la suma de latencias, que es una cota inferior."""
    f = d / "ejecuciones.jsonl"
    pared = sum(json.loads(l)["pared_s"] for l in open(f, encoding="utf-8")) if f.exists() else 0
    return max(pared, sum(lat))


def _latencias(d):
    f = d / "llamadas_llm.jsonl"
    return [json.loads(l).get("segundos", 0) for l in open(f, encoding="utf-8")] if f.exists() else []


if __name__ == "__main__":
    if sys.argv[1] == "ejecutar":
        ejecutar_modelo(sys.argv[2], sys.argv[3], int(sys.argv[5]) if len(sys.argv) > 5 else None)
    else:
        informe(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
