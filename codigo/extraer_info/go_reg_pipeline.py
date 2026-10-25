#!/usr/bin/env python3
"""
go_reg_pipeline.py  -  Pipeline "Offline-to-Online" GO -> PMID -> Abstract -> DuckDB

Fase OFFLINE  (determinista, reproducible, sin APIs frágiles):
    * goa_human.gaf.gz  (anotaciones GO humanas, release versionada)
    * go-basic.obo      (ontología: nombres, polaridad positively/negatively_regulates)
Fase ONLINE   (solo para lo que NO está en los ficheros estáticos):
    * Europe PMC REST (batch)  ->  fallback NCBI E-utilities efetch (batch)

Salida: DuckDB con tablas
    go_evidence   (gene, go_id, go_name, term_polarity, qualifier, evidence, pmid, ...)
    abstracts     (pmid, title, abstract, ...)
    llm_direction (tabla lista para que el LLM escriba +1/-1)
    v_llm_queue   (vista: pares gen-ruta-PMID con abstract y SIN veredicto aún)

Uso rápido:
    pip install requests duckdb
    python go_reg_pipeline.py run --genes GATA3 STAT3 --db data/pathways.duckdb
"""
from __future__ import annotations

import argparse
import gzip
import html
import json
import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

import duckdb
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger("go_reg")

# --------------------------------------------------------------------------- #
# 0. Configuración
# --------------------------------------------------------------------------- #
GAF_URL = "https://current.geneontology.org/annotations/goa_human.gaf.gz"
OBO_URL = "https://current.geneontology.org/ontology/go-basic.obo"
EPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Evidencia experimental/curada por humano. IBA/IEA/ISS... se excluyen por defecto
# (su "referencia" es un método computacional o un paper genérico, no evidencia física).
EXPERIMENTAL_EVIDENCE = {
    "EXP", "IDA", "IPI", "IMP", "IGI", "IEP",
    "HTP", "HDA", "HMP", "HGI", "HEP",
}
CURATED_EXTRA = {"TAS", "IC"}  # opcionales (--include-curated)

# PMIDs que aparecen como referencia "metodológica" y no como evidencia del gen.
# 21873635 = paper de PAINT/IBA (Gaudet 2011). Ampliable por --pmid-blacklist.
DEFAULT_PMID_BLACKLIST = {"21873635"}

DEFAULT_TERM_REGEX = r"\bregulation of\b"

GAF_NCOLS = 15  # GAF 2.x tiene 15-17 columnas; necesitamos >=15


class PipelineError(RuntimeError):
    """Error controlado del pipeline (mensaje apto para el usuario)."""


# --------------------------------------------------------------------------- #
# 1. HTTP robusto
# --------------------------------------------------------------------------- #
def build_session(contact_email: str | None = None) -> requests.Session:
    s = requests.Session()
    kwargs = dict(
        total=5, connect=5, read=5, backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        respect_retry_after_header=True,
    )
    methods = frozenset(["GET", "POST"])
    try:
        retry = Retry(allowed_methods=methods, **kwargs)
    except TypeError:  # urllib3 < 1.26
        retry = Retry(method_whitelist=methods, **kwargs)
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    ua = "go-reg-pipeline/1.0 (CiMUS)"
    if contact_email:
        ua += f" mailto:{contact_email}"
    s.headers.update({"User-Agent": ua})
    return s


# --------------------------------------------------------------------------- #
# 2. Descarga de recursos offline (con verificación de integridad)
# --------------------------------------------------------------------------- #
def download(url: str, dest: Path, session: requests.Session,
             max_age_days: float = 30, force: bool = False) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        age = (time.time() - dest.stat().st_mtime) / 86400
        if age <= max_age_days:
            log.info("Usando caché (%.1f d): %s", age, dest)
            return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    log.info("Descargando %s", url)
    try:
        with session.get(url, stream=True, timeout=(15, 120)) as r:
            r.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
    except requests.RequestException as exc:
        tmp.unlink(missing_ok=True)
        if dest.exists():
            log.warning("Descarga fallida (%s). Se usa copia local antigua.", exc)
            return dest
        raise PipelineError(f"No se pudo descargar {url}: {exc}") from exc
    if dest.suffix == ".gz":  # detecta descargas truncadas
        try:
            with gzip.open(tmp, "rb") as g:
                while g.read(1 << 20):
                    pass
        except (EOFError, OSError) as exc:
            tmp.unlink(missing_ok=True)
            raise PipelineError(f"Fichero gzip corrupto/truncado: {url}") from exc
    tmp.replace(dest)
    return dest


# --------------------------------------------------------------------------- #
# 3. Ontología (OBO) -> nombres + polaridad
# --------------------------------------------------------------------------- #
@dataclass
class GoTerm:
    id: str
    name: str = ""
    namespace: str = ""
    obsolete: bool = False
    relations: set[str] = field(default_factory=set)  # regulates / positively_... / negatively_...


@dataclass
class GoOntology:
    terms: dict[str, GoTerm]
    alt_ids: dict[str, str]
    version: str = ""

    def resolve(self, go_id: str) -> GoTerm | None:
        go_id = self.alt_ids.get(go_id, go_id)
        return self.terms.get(go_id)


_REL_RE = re.compile(r"^relationship:\s+(regulates|positively_regulates|negatively_regulates)\s+(GO:\d+)")


def parse_obo(path: Path) -> GoOntology:
    terms: dict[str, GoTerm] = {}
    alt: dict[str, str] = {}
    version = ""
    cur: GoTerm | None = None
    in_term = False
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                line = raw.strip()
                if line.startswith("data-version:"):
                    version = line.split(":", 1)[1].strip()
                if line == "[Term]":
                    in_term, cur = True, None
                    continue
                if line.startswith("[") and line.endswith("]"):
                    in_term, cur = False, None
                    continue
                if not in_term or not line:
                    continue
                if line.startswith("id: "):
                    cur = GoTerm(id=line[4:].strip())
                    terms[cur.id] = cur
                elif cur is None:
                    continue
                elif line.startswith("name: "):
                    cur.name = line[6:].strip()
                elif line.startswith("namespace: "):
                    cur.namespace = line[11:].strip()
                elif line.startswith("is_obsolete: true"):
                    cur.obsolete = True
                elif line.startswith("alt_id: "):
                    alt[line[8:].strip()] = cur.id
                else:
                    m = _REL_RE.match(line)
                    if m:
                        cur.relations.add(m.group(1))
    except OSError as exc:
        raise PipelineError(f"No se pudo leer el OBO {path}: {exc}") from exc
    if not terms:
        raise PipelineError(f"OBO vacío o inválido: {path}")
    log.info("OBO: %d términos (versión %s)", len(terms), version or "?")
    return GoOntology(terms, alt, version)


def term_polarity(term: GoTerm) -> int | None:
    """+1 positive regulation, -1 negative regulation, 0 regulation (sin signo), None = no regulatorio.
    Prioriza las relaciones formales de la ontología; el nombre es el respaldo."""
    n = term.name.lower()
    if "positively_regulates" in term.relations or n.startswith("positive regulation of"):
        return 1
    if "negatively_regulates" in term.relations or n.startswith("negative regulation of"):
        return -1
    if "regulates" in term.relations or n.startswith("regulation of"):
        return 0
    return None


def is_regulation_term(term: GoTerm, name_regex: re.Pattern[str]) -> bool:
    return term_polarity(term) is not None or bool(name_regex.search(term.name))


# --------------------------------------------------------------------------- #
# 4. GAF -> evidencias con PMID real
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class EvidenceRow:
    gene: str
    uniprot: str
    go_id: str
    go_name: str
    term_polarity: int | None
    qualifier: str
    evidence_code: str
    pmid: str
    assigned_by: str
    annot_date: str


def gaf_release(path: Path) -> str:
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.startswith("!"):
                    break
                if line.startswith("!date-generated:"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return ""


def iter_gaf(path: Path) -> Iterator[list[str]]:
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("!") or not line.strip():
                    continue
                cols = line.rstrip("\n").split("\t")
                if len(cols) < GAF_NCOLS:
                    continue
                yield cols
    except (OSError, EOFError) as exc:
        raise PipelineError(f"GAF ilegible ({path}): {exc}") from exc


_PMID_RE = re.compile(r"^PMID:(\d{1,9})$")


def extract_evidence(gaf_path: Path, onto: GoOntology, genes: Iterable[str], *,
                     evidence_codes: set[str] | None, name_regex: re.Pattern[str],
                     match_synonyms: bool = False,
                     pmid_blacklist: set[str] = frozenset()) -> tuple[list[EvidenceRow], Counter]:
    targets = {g.upper() for g in genes}
    stats: Counter = Counter()
    rows: dict[tuple, EvidenceRow] = {}
    for c in iter_gaf(gaf_path):
        symbol = c[2].upper()
        hit = symbol if symbol in targets else None
        if hit is None and match_synonyms:
            hit = next((s.upper() for s in c[10].split("|") if s.upper() in targets), None)
        if hit is None:
            continue
        stats["gaf_lines_target_genes"] += 1
        if c[8] != "P":                       # aspecto: biological_process
            stats["skip_not_BP"] += 1
            continue
        if not c[12].startswith("taxon:9606"):
            stats["skip_not_human"] += 1
            continue
        qualifier = c[3]
        if "NOT" in qualifier.split("|"):
            stats["skip_NOT"] += 1
            continue
        ev = c[6]
        if evidence_codes is not None and ev not in evidence_codes:
            stats["skip_evidence_code"] += 1
            continue
        term = onto.resolve(c[4])
        if term is None or term.obsolete:
            stats["skip_obsolete_or_unknown_term"] += 1
            continue
        if not is_regulation_term(term, name_regex):
            stats["skip_not_regulation"] += 1
            continue
        pmids = []
        for ref in c[5].split("|"):
            m = _PMID_RE.match(ref.strip())
            if m:
                pmids.append(m.group(1))
            else:
                stats["ref_discarded_non_pmid"] += 1   # GO_REF:, Reactome:, DOI:...
        pmids = [p for p in pmids if p not in pmid_blacklist]
        if not pmids:
            stats["skip_no_real_pmid"] += 1
            continue
        pol = term_polarity(term)
        for p in pmids:
            key = (hit, term.id, p, ev, qualifier)
            if key not in rows:
                rows[key] = EvidenceRow(hit, c[1], term.id, term.name, pol, qualifier,
                                        ev, p, c[14], c[13])
        stats["annotations_kept"] += 1
    return list(rows.values()), stats


# --------------------------------------------------------------------------- #
# 5. Abstracts: Europe PMC (batch) -> NCBI efetch (fallback)
# --------------------------------------------------------------------------- #
@dataclass
class Abstract:
    pmid: str
    title: str
    abstract: str
    journal: str = ""
    year: str = ""
    source: str = ""
    status: str = "ok"  # ok | no_abstract | not_found


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _chunks(seq: list, n: int) -> Iterator[list]:
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def fetch_europepmc(session: requests.Session, pmids: list[str], batch: int = 40,
                    delay: float = 0.2) -> dict[str, Abstract]:
    out: dict[str, Abstract] = {}
    for chunk in _chunks(pmids, batch):
        q = "(" + " OR ".join(f"EXT_ID:{p}" for p in chunk) + ") AND SRC:MED"
        params = {"query": q, "resultType": "core", "format": "json", "pageSize": 100}
        try:
            r = session.get(EPMC_SEARCH, params=params, timeout=(10, 60))
            r.raise_for_status()
            results = r.json().get("resultList", {}).get("result", [])
        except (requests.RequestException, ValueError) as exc:
            log.warning("Europe PMC falló para lote de %d PMIDs: %s", len(chunk), exc)
            continue
        for rec in results:
            pmid = str(rec.get("pmid") or rec.get("id") or "")
            if pmid not in chunk:
                continue
            ab = _clean(rec.get("abstractText"))
            out[pmid] = Abstract(pmid, _clean(rec.get("title")), ab,
                                 rec.get("journalTitle", ""), str(rec.get("pubYear", "")),
                                 "europepmc", "ok" if ab else "no_abstract")
        time.sleep(delay)
    return out


def fetch_ncbi(session: requests.Session, pmids: list[str], batch: int = 100,
               api_key: str | None = None, email: str | None = None) -> dict[str, Abstract]:
    out: dict[str, Abstract] = {}
    delay = 0.11 if api_key else 0.35  # 10 vs 3 req/s
    for chunk in _chunks(pmids, batch):
        data = {"db": "pubmed", "id": ",".join(chunk), "retmode": "xml", "tool": "go_reg_pipeline"}
        if api_key:
            data["api_key"] = api_key
        if email:
            data["email"] = email
        try:
            r = session.post(NCBI_EFETCH, data=data, timeout=(10, 90))
            r.raise_for_status()
            root = ET.fromstring(r.content)
        except (requests.RequestException, ET.ParseError) as exc:
            log.warning("NCBI efetch falló para lote de %d PMIDs: %s", len(chunk), exc)
            continue
        for art in root.findall(".//PubmedArticle"):
            pmid = (art.findtext("MedlineCitation/PMID") or "").strip()
            t = art.find(".//ArticleTitle")
            title = _clean("".join(t.itertext())) if t is not None else ""
            parts = []
            for at in art.findall(".//Abstract/AbstractText"):
                txt = _clean("".join(at.itertext()))
                lab = at.get("Label")
                if txt:
                    parts.append(f"{lab}: {txt}" if lab else txt)
            ab = " ".join(parts)
            out[pmid] = Abstract(pmid, title, ab,
                                 _clean(art.findtext(".//Journal/Title")),
                                 (art.findtext(".//JournalIssue/PubDate/Year") or ""),
                                 "ncbi", "ok" if ab else "no_abstract")
        time.sleep(delay)
    return out


def fetch_abstracts(session: requests.Session, pmids: list[str],
                    api_key: str | None, email: str | None) -> list[Abstract]:
    got = fetch_europepmc(session, pmids)
    need = [p for p in pmids if p not in got or got[p].status != "ok"]
    if need:
        log.info("Fallback NCBI para %d PMIDs", len(need))
        for p, a in fetch_ncbi(session, need, api_key=api_key, email=email).items():
            if p not in got or (a.status == "ok" and got[p].status != "ok"):
                got[p] = a
    for p in pmids:
        got.setdefault(p, Abstract(p, "", "", source="none", status="not_found"))
    return [got[p] for p in pmids]


# --------------------------------------------------------------------------- #
# 6. DuckDB
# --------------------------------------------------------------------------- #
SCHEMA = """
CREATE TABLE IF NOT EXISTS go_evidence (
    gene VARCHAR, uniprot VARCHAR, go_id VARCHAR, go_name VARCHAR,
    term_polarity TINYINT, qualifier VARCHAR, evidence_code VARCHAR, pmid VARCHAR,
    assigned_by VARCHAR, annot_date VARCHAR, gaf_release VARCHAR, go_version VARCHAR,
    PRIMARY KEY (gene, go_id, pmid, evidence_code, qualifier)
);
CREATE TABLE IF NOT EXISTS abstracts (
    pmid VARCHAR PRIMARY KEY, title VARCHAR, abstract VARCHAR, journal VARCHAR,
    year VARCHAR, source VARCHAR, status VARCHAR, fetched_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS llm_direction (
    gene VARCHAR, go_id VARCHAR, pmid VARCHAR, direction TINYINT,   -- +1 / -1 / 0 (no concluyente)
    confidence DOUBLE, rationale VARCHAR, context VARCHAR, model VARCHAR,
    created_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (gene, go_id, pmid, model)
);
CREATE OR REPLACE VIEW v_llm_queue AS
SELECT e.gene, e.go_id, e.go_name, e.term_polarity, e.qualifier, e.evidence_code,
       e.pmid, a.title, a.abstract
FROM go_evidence e
JOIN abstracts a ON a.pmid = e.pmid AND a.status = 'ok'
WHERE NOT EXISTS (SELECT 1 FROM llm_direction d
                  WHERE d.gene = e.gene AND d.go_id = e.go_id AND d.pmid = e.pmid);
"""


def open_db(path: Path) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        con = duckdb.connect(str(path))
        con.execute(SCHEMA)
        return con
    except duckdb.Error as exc:
        raise PipelineError(f"Error abriendo DuckDB {path}: {exc}") from exc


def save_evidence(con, rows: list[EvidenceRow], gaf_rel: str, go_ver: str) -> None:
    con.executemany(
        "INSERT OR IGNORE INTO go_evidence VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [(r.gene, r.uniprot, r.go_id, r.go_name, r.term_polarity, r.qualifier,
          r.evidence_code, r.pmid, r.assigned_by, r.annot_date, gaf_rel, go_ver) for r in rows])


def save_abstracts(con, abs_: list[Abstract]) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    con.executemany(
        "INSERT OR REPLACE INTO abstracts VALUES (?,?,?,?,?,?,?,?)",
        [(a.pmid, a.title, a.abstract, a.journal, a.year, a.source, a.status, now) for a in abs_])


def pending_pmids(con) -> list[str]:
    """PMIDs sin abstract o con intento fallido previo (not_found); 'no_abstract' no se reintenta."""
    q = """SELECT DISTINCT e.pmid FROM go_evidence e
           LEFT JOIN abstracts a ON a.pmid = e.pmid
           WHERE a.pmid IS NULL OR a.status = 'not_found' ORDER BY 1"""
    return [r[0] for r in con.execute(q).fetchall()]


def export_jsonl(con, path: Path) -> int:
    rows = con.execute("SELECT gene, go_id, go_name, term_polarity, qualifier, evidence_code, "
                       "pmid, title, abstract FROM v_llm_queue ORDER BY gene, go_id, pmid").fetchall()
    cols = ["gene", "go_id", "go_name", "term_polarity", "qualifier", "evidence_code",
            "pmid", "title", "abstract"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(dict(zip(cols, r)), ensure_ascii=False) + "\n")
    return len(rows)


# --------------------------------------------------------------------------- #
# 7. Orquestación / CLI
# --------------------------------------------------------------------------- #
def cmd_prepare(a, session):
    wd = Path(a.workdir)
    gaf = download(GAF_URL, wd / "goa_human.gaf.gz", session, a.max_age_days, a.force)
    obo = download(OBO_URL, wd / "go-basic.obo", session, a.max_age_days, a.force)
    return gaf, obo


def cmd_extract(a, gaf: Path, obo: Path, con):
    genes = list(a.genes or [])
    if a.genes_file:
        genes += [l.strip() for l in Path(a.genes_file).read_text().splitlines()
                  if l.strip() and not l.startswith("#")]
    if not genes:
        raise PipelineError("Indica genes con --genes o --genes-file")
    ev = None if a.all_evidence else set(EXPERIMENTAL_EVIDENCE)
    if ev is not None and a.include_curated:
        ev |= CURATED_EXTRA
    onto = parse_obo(obo)
    rows, stats = extract_evidence(
        gaf, onto, genes, evidence_codes=ev,
        name_regex=re.compile(a.term_regex, re.I),
        match_synonyms=a.match_synonyms,
        pmid_blacklist=DEFAULT_PMID_BLACKLIST | set(a.pmid_blacklist or []))
    save_evidence(con, rows, gaf_release(gaf), onto.version)
    log.info("Estadísticas de filtrado: %s", dict(stats))
    by_gene = Counter(r.gene for r in rows)
    for g in genes:
        n = by_gene.get(g.upper(), 0)
        (log.info if n else log.warning)("%-10s -> %d filas gen/ruta/PMID", g.upper(), n)
    if stats["gaf_lines_target_genes"] == 0:
        log.warning("Ninguna línea del GAF coincide con tus genes: revisa símbolos HGNC "
                    "(o usa --match-synonyms).")
    return rows


def cmd_abstracts(a, session, con):
    todo = pending_pmids(con)
    log.info("PMIDs pendientes de abstract: %d", len(todo))
    if not todo:
        return
    res = fetch_abstracts(session, todo,
                          api_key=a.ncbi_api_key or os.getenv("NCBI_API_KEY"),
                          email=a.email or os.getenv("NCBI_EMAIL"))
    save_abstracts(con, res)
    log.info("Abstracts: %s", dict(Counter(x.status for x in res)))


# --------------------------------------------------------------------------- #
# 6a. Visor de resultados (equivale a consultar la BD a mano)
# --------------------------------------------------------------------------- #
def print_table(headers: list[str], rows: list, maxw: int = 48) -> None:
    def fmt(v) -> str:
        s = "" if v is None else str(v).replace("\n", " ")
        return s if len(s) <= maxw else s[:maxw - 1] + "…"
    data = [[fmt(c) for c in r] for r in rows]
    widths = [max([len(h)] + [len(r[i]) for r in data]) for i, h in enumerate(headers)]
    print("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  ".join("-" * w for w in widths))
    for r in data:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)))
    print(f"({len(data)} filas)\n")


_POL = "CASE term_polarity WHEN 1 THEN '+1 positiva' WHEN -1 THEN '-1 negativa' ELSE ' 0 sin signo' END"


def rep_pathways(con, gene: str | None, limit: int) -> None:
    where, par = ("WHERE gene = ?", [gene]) if gene else ("", [])
    rows = con.execute(f"""
        SELECT gene, go_name, {_POL} AS polaridad_ruta, string_agg(DISTINCT evidence_code, ',') AS evidencia,
               count(DISTINCT pmid) AS pmids
        FROM go_evidence {where}
        GROUP BY gene, go_id, go_name, term_polarity
        ORDER BY gene, go_name LIMIT {int(limit)}""", par).fetchall()
    print_table(["GEN", "RUTA GO (regulación)", "POLARIDAD", "EVIDENCIA", "PMIDs"], rows, 60)


def rep_papers(con, gene: str | None, limit: int) -> None:
    where, par = ("WHERE e.gene = ?", [gene]) if gene else ("", [])
    rows = con.execute(f"""
        SELECT e.gene, e.go_name, e.evidence_code, e.pmid, a.status,
               a.title, left(a.abstract, 90) AS abstract_inicio
        FROM go_evidence e LEFT JOIN abstracts a ON a.pmid = e.pmid {where}
        ORDER BY e.gene, e.go_name, e.pmid LIMIT {int(limit)}""", par).fetchall()
    print_table(["GEN", "RUTA", "EVID", "PMID", "ESTADO", "TÍTULO", "ABSTRACT (inicio)"], rows, 40)


def rep_status(con) -> None:
    print("Estado de los abstracts (ok = descargado; no_abstract = el paper no tiene; "
          "not_found = no localizado):")
    print_table(["ESTADO", "FUENTE", "N"],
                con.execute("SELECT status, source, count(*) FROM abstracts GROUP BY status, source "
                            "ORDER BY 3 DESC").fetchall())
    print("Cola pendiente para el LLM (con abstract y sin veredicto):")
    print_table(["GEN", "PARES gen-ruta-PMID"],
                con.execute("SELECT gene, count(*) FROM v_llm_queue GROUP BY gene ORDER BY gene").fetchall())


def rep_sql(con, sql: str) -> None:
    if not re.match(r"^\s*(select|with|describe|show|pragma)\b", sql, re.I):
        print("Solo se permiten consultas de lectura (SELECT / WITH / DESCRIBE / SHOW).")
        return
    cur = con.execute(sql)
    print_table([d[0] for d in cur.description], cur.fetchall(), 60)


def export_csv(con, gene: str | None, path: Path) -> None:
    where, par = ("WHERE e.gene = ?", [gene]) if gene else ("", [])
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = str(path).replace("'", "''")
    con.execute(f"""COPY (SELECT e.gene, e.go_id, e.go_name, e.term_polarity, e.qualifier,
                         e.evidence_code, e.pmid, a.status, a.title, a.abstract
                  FROM go_evidence e LEFT JOIN abstracts a ON a.pmid = e.pmid {where}
                  ORDER BY e.gene, e.go_id, e.pmid) TO '{safe}' (HEADER, DELIMITER ',')""", par)
    print(f"CSV exportado: {path}")


def results_menu(db_path: Path) -> None:
    if not db_path.exists():
        print(f"No existe la base de datos {db_path}. Haz primero una búsqueda.")
        return
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        while True:
            genes = [r[0] for r in con.execute("SELECT DISTINCT gene FROM go_evidence ORDER BY 1").fetchall()]
            print(f"\n--- RESULTADOS ({db_path}) | genes en la BD: {', '.join(genes) or 'ninguno'} ---")
            print("  1) Resumen por gen")
            print("  2) Rutas GO de regulación (por gen)")
            print("  3) Papers: PMID, título y comienzo del abstract (por gen)")
            print("  4) Estado de abstracts y cola del LLM")
            print("  5) Consulta SQL libre (solo lectura)")
            print("  6) Exportar a CSV (gen/ruta/PMID/abstract)")
            print("  0) Volver")
            opt = _ask("Opción", "1")
            try:
                if opt == "0":
                    return
                elif opt == "1":
                    print_summary(con)
                elif opt in ("2", "3", "6"):
                    g = _ask("Gen (Enter = todos)").upper() or None
                    if opt == "2":
                        rep_pathways(con, g, int(_ask("Máx. filas", "50")))
                    elif opt == "3":
                        rep_papers(con, g, int(_ask("Máx. filas", "25")))
                    else:
                        export_csv(con, g, Path(_ask("Fichero de salida", "data/resultados.csv")))
                elif opt == "4":
                    rep_status(con)
                elif opt == "5":
                    print("Tablas: go_evidence, abstracts, llm_direction; vista: v_llm_queue")
                    rep_sql(con, _ask("SQL"))
                else:
                    print("Opción no válida.")
            except (duckdb.Error, ValueError) as exc:
                print(f"Error: {exc}")
    finally:
        con.close()


def cmd_report(a) -> None:
    db = Path(a.db)
    if not db.exists():
        raise PipelineError(f"No existe la base de datos {db}")
    con = duckdb.connect(str(db), read_only=True)
    try:
        g = a.gene.upper() if a.gene else None
        if a.sql:
            rep_sql(con, a.sql)
        elif a.csv:
            export_csv(con, g, Path(a.csv))
        elif g:
            rep_pathways(con, g, a.limit)
            rep_papers(con, g, a.limit)
        else:
            print_summary(con)
            rep_status(con)
    except duckdb.Error as exc:
        raise PipelineError(f"Error consultando la base de datos: {exc}") from exc
    finally:
        con.close()


def print_summary(con) -> None:
    rows = con.execute("""
        SELECT e.gene, count(*) AS filas, count(DISTINCT e.go_id) AS rutas,
               count(DISTINCT e.pmid) AS pmids,
               count(DISTINCT CASE WHEN a.status = 'ok' THEN e.pmid END) AS con_abstract
        FROM go_evidence e LEFT JOIN abstracts a ON a.pmid = e.pmid
        GROUP BY e.gene ORDER BY e.gene""").fetchall()
    print("\n" + "=" * 62)
    print("RESUMEN (acumulado en la base de datos)")
    print("=" * 62)
    print(f"{'GEN':<12}{'FILAS':>8}{'RUTAS GO':>11}{'PMIDs':>8}{'C/ABSTRACT':>12}")
    for g, f, r, p, ab in rows:
        print(f"{g:<12}{f:>8}{r:>11}{p:>8}{ab:>12}")
    if not rows:
        print("(sin resultados: revisa los símbolos HGNC o prueba la opción 'más evidencias')")
    print("=" * 62)


# --------------------------------------------------------------------------- #
# 6b. Interfaz interactiva (se activa al lanzar el script SIN argumentos)
# --------------------------------------------------------------------------- #
# Lista orientativa (propuesta de partida, NO validada por CiMUS): genes de
# células NK / inmunes con relevancia en tumores. Edítala libremente.
IMMUNE_PRESET: dict[str, list[str]] = {
    "Factores de transcripción": ["GATA3", "STAT3", "STAT1", "STAT4", "STAT5A", "STAT5B",
                                  "TBX21", "EOMES", "ID2", "TOX", "PRDM1", "NFIL3",
                                  "RUNX3", "IRF4", "IRF8"],
    "Receptores NK y señalización": ["NCR1", "NCR3", "NCR2", "KLRK1", "KLRC1", "KLRD1",
                                     "FCGR3A", "TYROBP", "CD247", "SYK", "LCP2", "VAV1",
                                     "PLCG2"],
    "Citocinas y receptores": ["IFNG", "TNF", "IL2RB", "IL15", "IL15RA", "IL18R1",
                               "IL12RB1", "IL10", "TGFB1", "TGFBR2", "SMAD3"],
    "Efectores citotóxicos": ["GZMB", "PRF1", "FASLG", "TNFSF10", "GNLY"],
    "Checkpoints inhibidores": ["PDCD1", "HAVCR2", "TIGIT", "LAG3", "CD96"],
    "Quimiocinas y migración": ["CXCR3", "CXCR4", "CCL5", "XCL1", "CX3CR1"],
}

_GENE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-\.]{0,19}$")


def parse_gene_text(text: str) -> tuple[list[str], list[str]]:
    """Admite separadores coma, espacio, punto y coma o salto de línea."""
    ok, bad, seen = [], [], set()
    for tok in re.split(r"[,\s;]+", text.strip()):
        if not tok:
            continue
        if not _GENE_TOKEN.match(tok):
            bad.append(tok)
            continue
        g = tok.upper()
        if g not in seen:
            seen.add(g)
            ok.append(g)
    return ok, bad


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    ans = input(f"{prompt}{suffix}: ").strip()
    return ans or default


def _choose_genes() -> list[str]:
    print("\n¿Cómo quieres indicar los genes?")
    print("  1) Escribirlos ahora (uno o varios, separados por coma o espacio)")
    print("  2) Elegir de la lista orientativa de genes inmunes/NK")
    print("  3) Cargarlos desde un fichero de texto (un símbolo por línea)")
    while True:
        opt = _ask("Opción", "1")
        genes: list[str] = []
        if opt == "1":
            genes, bad = parse_gene_text(_ask("Genes (ej. GATA3, STAT3)"))
            if bad:
                print(f"  ! Ignorados por formato no válido: {', '.join(bad)}")
        elif opt == "2":
            cats = list(IMMUNE_PRESET)
            for i, c in enumerate(cats, 1):
                print(f"  {i}) {c}: {', '.join(IMMUNE_PRESET[c])}")
            print(f"  {len(cats) + 1}) TODOS")
            sel = _ask("Categorías (números separados por coma)", str(len(cats) + 1))
            nums = {int(x) for x in re.split(r"[,\s]+", sel) if x.isdigit()}
            chosen = cats if (len(cats) + 1) in nums else [cats[n - 1] for n in sorted(nums)
                                                           if 1 <= n <= len(cats)]
            for c in chosen:
                genes += IMMUNE_PRESET[c]
            extra = _ask("¿Añadir genes propios? (vacío = no)")
            if extra:
                more, bad = parse_gene_text(extra)
                genes += more
                if bad:
                    print(f"  ! Ignorados: {', '.join(bad)}")
        elif opt == "3":
            fpath = Path(_ask("Ruta del fichero").strip('"'))
            try:
                content = "\n".join(l.split("#", 1)[0]          # ignora comentarios
                                    for l in fpath.read_text(encoding="utf-8-sig").splitlines())
                genes, bad = parse_gene_text(content)
                if bad:
                    print(f"  ! Ignorados por formato no válido: {', '.join(bad)}")
            except OSError as exc:
                print(f"  ! No se pudo leer el fichero: {exc}")
        else:
            print("  Opción no válida.")
            continue
        genes = list(dict.fromkeys(genes))
        if genes:
            return genes
        print("  No hay ningún gen válido, inténtalo de nuevo.")


def _banner() -> None:
    print("=" * 62)
    print(" Pipeline GO -> PMID -> Abstract  |  CiMUS (NK / HNSC)")
    print("=" * 62)


def interactive_args() -> list[str]:
    genes = _choose_genes()
    print(f"\nGenes seleccionados ({len(genes)}): {', '.join(genes)}")
    print("\nEvidencia a incluir:")
    print("  1) Solo experimental (EXP, IDA, IPI, IMP, IGI, IEP...)  [recomendado]")
    print("  2) Experimental + curada (añade TAS e IC)")
    print("  3) Todas (incluye IEA/IBA: añade mucho ruido computacional)")
    ev = _ask("Opción", "1")
    email = _ask("Email de contacto para NCBI/Europe PMC (vacío = omitir)")
    print("\nArchivo donde se guardan los resultados (se crea solo; pulsa Enter para aceptar):")
    db = _ask("Base de datos", "data/pathways.duckdb")
    argv = ["run", "--genes", *genes, "--db", db, "--jsonl", "data/llm_queue.jsonl"]
    if ev == "2":
        argv.append("--include-curated")
    elif ev == "3":
        argv.append("--all-evidence")
    if email:
        argv += ["--email", email]
    print("\nLanzando... (la primera vez descarga GAF y OBO, ~1-2 min)\n")
    return argv


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--workdir", default="data")
        sp.add_argument("--db", default="data/pathways.duckdb")
        sp.add_argument("--max-age-days", type=float, default=30)
        sp.add_argument("--force", action="store_true", help="re-descarga GAF/OBO")
        sp.add_argument("--email", help="contacto para NCBI/Europe PMC (recomendado)")
        sp.add_argument("--ncbi-api-key")

    def genes_opts(sp):
        sp.add_argument("--genes", nargs="+", help="símbolos HGNC, p.ej. GATA3 STAT3")
        sp.add_argument("--genes-file", help="un símbolo por línea")
        sp.add_argument("--all-evidence", action="store_true", help="no filtrar por código de evidencia")
        sp.add_argument("--include-curated", action="store_true", help="añade TAS e IC")
        sp.add_argument("--match-synonyms", action="store_true")
        sp.add_argument("--term-regex", default=DEFAULT_TERM_REGEX)
        sp.add_argument("--pmid-blacklist", nargs="*")

    rp = sub.add_parser("report", help="muestra/exporta las tablas de resultados")
    rp.add_argument("--db", default="data/pathways.duckdb")
    rp.add_argument("--gene", help="filtra por gen (rutas + papers)")
    rp.add_argument("--limit", type=int, default=50)
    rp.add_argument("--csv", help="exporta a CSV (todo o solo --gene)")
    rp.add_argument("--sql", help="consulta SQL de solo lectura")

    for name in ("prepare", "extract", "abstracts", "run"):
        sp = sub.add_parser(name)
        common(sp)
        if name in ("extract", "run"):
            genes_opts(sp)
        if name in ("abstracts", "run"):
            sp.add_argument("--jsonl", help="exporta la cola para el LLM (solo con abstract)")
    return p


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    t0 = time.perf_counter()
    session = build_session(getattr(a, "email", None))
    wd = Path(a.workdir)
    try:
        if a.cmd == "report":
            cmd_report(a)
            return 0
        if a.cmd == "prepare":
            cmd_prepare(a, session)
            return 0
        con = open_db(Path(a.db))
        try:
            if a.cmd in ("extract", "run"):
                gaf, obo = (wd / "goa_human.gaf.gz", wd / "go-basic.obo")
                if a.cmd == "run" or not (gaf.exists() and obo.exists()):
                    gaf, obo = cmd_prepare(a, session)
                cmd_extract(a, gaf, obo, con)
            if a.cmd in ("abstracts", "run"):
                cmd_abstracts(a, session, con)
                if getattr(a, "jsonl", None):
                    n = export_jsonl(con, Path(a.jsonl))
                    log.info("Cola LLM: %d registros -> %s", n, a.jsonl)
            print_summary(con)
            log.info("Tiempo total: %.1f s", time.perf_counter() - t0)
        finally:
            con.close()
        return 0
    except PipelineError as exc:
        log.error("%s", exc)
        return 2
    except KeyboardInterrupt:
        log.error("Interrumpido (el progreso en DuckDB se conserva; relanza para continuar)")
        return 130


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):      # tildes/ñ correctas en PowerShell
        try:
            _s.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass
    if len(sys.argv) == 1:                   # sin argumentos -> modo interactivo
        rc = 0
        _yes = ("s", "si", "sí", "y", "yes")
        try:
            while True:
                _banner()
                print("  1) Nueva búsqueda (genes -> rutas GO -> PMIDs -> abstracts)")
                print("  2) Ver resultados ya guardados")
                print("  0) Salir")
                opt = _ask("Opción", "1")
                if opt == "0":
                    break
                if opt == "2":
                    results_menu(Path(_ask("Base de datos", "data/pathways.duckdb")))
                    continue
                if opt != "1":
                    print("Opción no válida.")
                    continue
                argv = interactive_args()
                rc = main(argv)
                if rc == 0 and _ask("\n¿Ver los resultados ahora? (s/n)", "s").lower() in _yes:
                    results_menu(Path(argv[argv.index("--db") + 1]))
        except (KeyboardInterrupt, EOFError):
            print("\nSaliendo.")
        sys.exit(rc)
    sys.exit(main())
