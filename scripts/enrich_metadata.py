#!/usr/bin/env python3
"""Recupera metadatos faltantes de los registros de CONICET Digital.

Los registros cosechados del buscador de CONICET traen título, autores,
resumen y handle, pero no DOI, revista, volumen, número, páginas, palabras
clave ni tipo documental; además, el año corresponde a la fecha de carga en
el repositorio y no a la de publicación.

El script busca cada registro por título y autores en fuentes alternativas y
solo completa datos cuando la coincidencia es inequívoca:

1. CONICET OAI-PMH por handle (si el repositorio responde).
2. OpenAlex (búsqueda por título).
3. Crossref (búsqueda bibliográfica por título y primer apellido).
4. Crossref por DOI, para volumen, número y páginas cuando ya hay DOI.

Reglas de aceptación (todas a la vez): similitud de título >= 0,90, al menos
un apellido en común y año encontrado no posterior al año de carga (ni más de
15 años anterior). Los casos parecidos que no cumplen todo quedan en «revisar»
y no se aplican. Nunca se sobrescriben autores, título ni resumen.

Salidas:
- data/metadata_enrichment.csv: una fila por registro consultado, con el
  candidato, las puntuaciones, el año original y si se aplicó. Funciona
  también como caché: los registros ya consultados no se vuelven a pedir.
- data/metadata_enrichment_report.json: resumen de la corrida.
- data/master_records.csv (con --apply): DOI, revista, tipo, palabras clave,
  año y fecha de publicación de las coincidencias aceptadas.

Volumen, número y páginas no tienen columna en el maestro (main.py reescribe
su esquema); apa_citation.py los lee de data/metadata_enrichment.csv.

Las decisiones manuales van en config/metadata_enrichment_overrides.csv
(record_id,decision,nota) con decision «aceptar» o «rechazar».
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data" / "master_records.csv"
ENRICHMENT = ROOT / "data" / "metadata_enrichment.csv"
REPORT = ROOT / "data" / "metadata_enrichment_report.json"
OVERRIDES = ROOT / "config" / "metadata_enrichment_overrides.csv"

TITLE_ACCEPT = 0.90
TITLE_REVIEW = 0.80
MAX_YEARS_BEFORE_DEPOSIT = 15

ENRICHMENT_FIELDS = [
    "record_id", "status", "applied", "decision_reason", "match_source",
    "title_similarity", "author_overlap", "original_year", "found_year",
    "found_date", "doi", "journal", "volume", "issue", "pages",
    "document_type", "keywords", "openalex_id", "is_oa", "pdf_url",
    "match_title", "match_authors", "handle", "queried_at",
]
CANDIDATE_FIELDS = [
    "match_source", "found_year", "found_date", "doi", "journal", "volume",
    "issue", "pages", "document_type", "keywords", "openalex_id", "is_oa",
    "pdf_url", "match_title", "match_authors",
]

REPOSITORY_MARKERS = (
    "conicet", "openalex", "la referencia", "zenodo", "sedici", "repositorio",
    "repositor", "digital library", "dspace", "redalyc", "core.ac.uk",
)

csv.field_size_limit(sys.maxsize)


# ── Normalización y coincidencia ──────────────────────────────────────────────
def strip_accents(value: str) -> str:
    return unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()


def norm(value: Any) -> str:
    text = strip_accents(str(value or "")).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def title_similarity(left: str, right: str) -> float:
    a, b = norm(left), norm(right)
    if not a or not b:
        return 0.0
    best = SequenceMatcher(None, a, b).ratio()
    # Un título puede llegar sin subtítulo o con la traducción agregada.
    for x, y in ((a, b), (b, a)):
        if len(x) >= 30 and y.startswith(x):
            best = max(best, 0.95)
    for x, y in ((left, right), (right, left)):
        head = norm(re.split(r"[:.;?¿]", str(x or ""))[0])
        if len(head) >= 30:
            best = max(best, SequenceMatcher(None, head, norm(y)[: len(head)]).ratio() * 0.97)
    return round(best, 3)


def surnames(authors: str) -> set[str]:
    """Apellidos de «Apellido, Nombre; ...» o «Nombre Apellido; ...»."""
    out: set[str] = set()
    for part in re.split(r";|\|", authors or ""):
        part = part.strip()
        if not part:
            continue
        family = part.split(",")[0] if "," in part else part.split()[-1]
        out.update(tok for tok in norm(family).split() if len(tok) >= 3)
    return out


def author_tokens(names: Iterable[str]) -> set[str]:
    return {tok for name in names for tok in norm(name).split() if len(tok) >= 3}


def year_of(value: Any) -> str:
    match = re.search(r"\b(19\d{2}|20\d{2})\b", str(value or ""))
    return match.group(1) if match else ""


def evaluate(record: Dict[str, str], cand: Dict[str, Any]) -> Dict[str, Any]:
    """Puntúa un candidato y decide aceptado / revisar / descartado."""
    sim = title_similarity(record.get("title", ""), cand.get("match_title", ""))
    own = surnames(record.get("authors", ""))
    theirs = author_tokens(cand.get("authors_list", []))
    overlap = len(own & theirs)
    has_authors = bool(own) and bool(theirs)
    deposit = year_of(record.get("publication_year"))
    found = year_of(cand.get("found_year"))
    year_ok = True
    if deposit and found:
        year_ok = int(deposit) - MAX_YEARS_BEFORE_DEPOSIT <= int(found) <= int(deposit)
    reasons = []
    if sim < TITLE_ACCEPT:
        reasons.append(f"título {sim:.2f} < {TITLE_ACCEPT:.2f}")
    if has_authors and overlap == 0:
        reasons.append("sin apellidos en común")
    if not has_authors:
        reasons.append("sin autores para comparar")
    if not year_ok:
        reasons.append(f"año {found} incompatible con carga {deposit}")
    if not reasons:
        status = "aceptado"
    elif sim >= TITLE_REVIEW and (overlap or sim >= 0.95):
        status = "revisar"
    else:
        status = "descartado"
    return {"status": status, "title_similarity": sim, "author_overlap": overlap,
            "decision_reason": "; ".join(reasons) or "título, autoría y año coinciden"}


# ── Tipos documentales ────────────────────────────────────────────────────────
TYPE_MAP = {
    "article": "article", "journal-article": "article", "review": "article",
    "book-chapter": "book-chapter", "book-section": "book-chapter", "book-part": "book-chapter",
    "bookpart": "book-chapter", "book": "book", "monograph": "book", "edited-book": "book",
    "dissertation": "dissertation", "doctoralthesis": "dissertation", "masterthesis": "dissertation",
    "bachelorthesis": "dissertation", "thesis": "dissertation",
    "proceedings-article": "conference-paper", "conferenceobject": "conference-paper",
    "conference-paper": "conference-paper", "report": "report", "workingpaper": "report",
    "preprint": "preprint", "posted-content": "preprint", "dataset": "dataset",
}


def map_type(raw: str) -> str:
    key = str(raw or "").strip().lower().rsplit("/", 1)[-1].replace(" ", "")
    return TYPE_MAP.get(key, "")


def is_repository(name: str) -> bool:
    low = strip_accents(str(name or "")).lower()
    return any(marker in low for marker in REPOSITORY_MARKERS)


def pages_from(first: Any, last: Any) -> str:
    first, last = str(first or "").strip(), str(last or "").strip()
    if first and last and first != last:
        return f"{first}-{last}"
    return first


def normalize_doi(value: Any) -> str:
    doi = str(value or "").strip()
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi, flags=re.I)
    return doi.lower()


# ── Fuentes ───────────────────────────────────────────────────────────────────
class SourceUnavailable(Exception):
    """La fuente no respondió: el registro se reintenta en la próxima corrida."""


def ok_json(resp, source: str) -> dict:
    if resp is None or resp.status_code != 200:
        raise SourceUnavailable(source)
    return resp.json()


class Http:
    def __init__(self, email: str, pause: float):
        import requests  # importación diferida: las pruebas no la necesitan

        self.session = requests.Session()
        self.session.headers["User-Agent"] = f"scrapeadoracademico-enrichment/1.0 (mailto:{email})"
        self.email = email
        self.pause = pause
        self.failures: Dict[str, int] = {}

    def get(self, url: str, params: Optional[dict] = None, timeout: int = 30):
        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=timeout)
                time.sleep(self.pause)
                if resp.status_code == 429 or resp.status_code >= 500:
                    time.sleep(2 ** attempt * 2)
                    continue
                return resp
            except Exception:
                time.sleep(2 ** attempt)
        host = re.sub(r"^https?://([^/]+).*", r"\1", url)
        self.failures[host] = self.failures.get(host, 0) + 1
        return None


def openalex_candidates(http: Http, record: Dict[str, str]) -> List[Dict[str, Any]]:
    title = re.sub(r"[,:|]", " ", record.get("title", ""))[:250]
    resp = http.get("https://api.openalex.org/works",
                    {"search": title, "per-page": 5, "mailto": http.email})
    out = []
    for work in ok_json(resp, "OpenAlex").get("results", []):
        locations = [work.get("primary_location") or {}] + list(work.get("locations") or [])
        journal_loc = next((loc for loc in locations
                            if (loc.get("source") or {}).get("type") in ("journal", "book series", "conference")), None)
        source = ((journal_loc or work.get("primary_location") or {}).get("source") or {})
        journal = source.get("display_name") or ""
        if is_repository(journal):
            journal = ""
        biblio = work.get("biblio") or {}
        oa = work.get("open_access") or {}
        out.append({
            "match_source": "OpenAlex",
            "match_title": work.get("display_name") or work.get("title") or "",
            "authors_list": [((a.get("author") or {}).get("display_name") or "") for a in work.get("authorships") or []],
            "found_year": str(work.get("publication_year") or ""),
            "found_date": work.get("publication_date") or "",
            "doi": normalize_doi(work.get("doi")),
            "journal": journal,
            "volume": str(biblio.get("volume") or ""),
            "issue": str(biblio.get("issue") or ""),
            "pages": pages_from(biblio.get("first_page"), biblio.get("last_page")),
            "document_type": map_type(work.get("type_crossref") or work.get("type")),
            "keywords": "; ".join(k.get("display_name", "") for k in (work.get("keywords") or [])[:10] if k.get("display_name")),
            "openalex_id": work.get("id") or "",
            "is_oa": str(bool(oa.get("is_oa"))) if oa else "",
            "pdf_url": oa.get("oa_url") or "",
        })
    return out


def _crossref_item(item: Dict[str, Any]) -> Dict[str, Any]:
    parts = ((item.get("issued") or {}).get("date-parts") or [[None]])[0]
    date = "-".join(f"{int(p):02d}" if i else str(p) for i, p in enumerate(parts) if p)
    authors = [" ".join(x for x in (a.get("given"), a.get("family")) if x) or a.get("name", "")
               for a in item.get("author") or []]
    journal = (item.get("container-title") or [""])[0]
    return {
        "match_source": "Crossref",
        "match_title": (item.get("title") or [""])[0],
        "authors_list": authors,
        "found_year": str(parts[0] or "") if parts else "",
        "found_date": date,
        "doi": normalize_doi(item.get("DOI")),
        "journal": "" if is_repository(journal) else journal,
        "volume": str(item.get("volume") or ""),
        "issue": str(item.get("issue") or ""),
        "pages": str(item.get("page") or item.get("article-number") or ""),
        "document_type": map_type(item.get("type")),
        "keywords": "; ".join((item.get("subject") or [])[:10]),
        "openalex_id": "", "is_oa": "", "pdf_url": "",
    }


def crossref_candidates(http: Http, record: Dict[str, str]) -> List[Dict[str, Any]]:
    first = sorted(surnames(record.get("authors", "")))[:1]
    query = " ".join([record.get("title", "")[:250]] + first)
    resp = http.get("https://api.crossref.org/works",
                    {"query.bibliographic": query, "rows": 5, "mailto": http.email})
    return [_crossref_item(item) for item in ok_json(resp, "Crossref").get("message", {}).get("items", [])]


def crossref_by_doi(http: Http, doi: str) -> Optional[Dict[str, Any]]:
    resp = http.get(f"https://api.crossref.org/works/{doi}", {"mailto": http.email})
    if resp is None or resp.status_code != 200:
        return None
    return _crossref_item(resp.json().get("message", {}))


def conicet_handle(record: Dict[str, str]) -> str:
    match = re.search(r"(11336/\d+)", " ".join([record.get("url", ""), record.get("record_id", "")]))
    return match.group(1) if match else ""


def conicet_oai(http: Http, handle: str) -> Optional[Dict[str, Any]]:
    resp = http.get("https://ri.conicet.gov.ar/oai/request",
                    {"verb": "GetRecord", "metadataPrefix": "oai_dc",
                     "identifier": f"oai:ri.conicet.gov.ar:{handle}"}, timeout=20)
    if resp is None or resp.status_code != 200 or b"<oai_dc:dc" not in resp.content:
        return None
    root = ET.fromstring(resp.content)
    dc = "{http://purl.org/dc/elements/1.1/}"
    values = lambda tag: [(el.text or "").strip() for el in root.iter(dc + tag) if (el.text or "").strip()]
    years = sorted(y for y in (year_of(d) for d in values("date")) if y)
    doi = ""
    for ident in values("identifier") + values("relation"):
        if "10." in ident and ("doi" in ident.lower() or ident.startswith("10.")):
            doi = normalize_doi(re.sub(r"^.*?(10\.\d{4,}/\S+)$", r"\1", ident))
            break
    source = (values("source") or [""])[0]
    return {
        "match_source": "CONICET OAI-PMH",
        "match_title": (values("title") or [""])[0],
        "authors_list": values("creator"),
        "found_year": years[0] if years else "",
        "found_date": "",
        "doi": doi,
        "journal": source.split(";")[0].strip(),
        "volume": "", "issue": "", "pages": "",
        "document_type": next((map_type(t) for t in values("type") if map_type(t)), ""),
        "keywords": "; ".join(values("subject")[:10]),
        "openalex_id": "", "is_oa": "", "pdf_url": "",
    }


# ── Selección y aplicación ────────────────────────────────────────────────────
def choose(record: Dict[str, str], candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    scored = [{**cand, **evaluate(record, cand)} for cand in candidates if cand.get("match_title")]
    rank = {"aceptado": 2, "revisar": 1, "descartado": 0}
    scored.sort(key=lambda c: (rank[c["status"]], bool(c.get("doi")), c["title_similarity"]), reverse=True)
    if not scored:
        return {"status": "sin_coincidencia", "decision_reason": "sin resultados en las fuentes"}
    best = scored[0]
    if best["status"] == "descartado":
        return {"status": "sin_coincidencia", "decision_reason": "resultados sin coincidencia suficiente",
                "title_similarity": best["title_similarity"], "match_title": best["match_title"],
                "match_source": best["match_source"]}
    # Completar con otros candidatos aceptados de la misma obra (mismo DOI o sin DOI).
    for other in scored[1:]:
        if other["status"] != "aceptado" or best["status"] != "aceptado":
            continue
        if other.get("doi") and best.get("doi") and other["doi"] != best["doi"]:
            continue
        for key in ("doi", "journal", "volume", "issue", "pages", "document_type", "keywords", "found_date"):
            if not best.get(key) and other.get(key):
                best[key] = other[key]
    return best


def lookup(http: Http, record: Dict[str, str], conicet_up: bool) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = []
    failed: List[str] = []
    handle = conicet_handle(record)
    if conicet_up and handle:
        cand = conicet_oai(http, handle)
        if cand:
            candidates.append(cand)
    for search in (openalex_candidates, crossref_candidates):
        try:
            candidates += search(http, record)
        except SourceUnavailable as exc:
            failed.append(str(exc))
        best = choose(record, candidates)
        if best["status"] == "aceptado":
            break
    if failed and best["status"] != "aceptado":
        # Sin respuesta de alguna fuente no se puede afirmar que no haya coincidencia.
        raise SourceUnavailable(", ".join(failed))
    if best["status"] == "aceptado" and best.get("doi") and not (best.get("volume") or best.get("pages")):
        extra = crossref_by_doi(http, best["doi"])
        if extra:
            for key in ("volume", "issue", "pages", "journal", "document_type"):
                if not best.get(key) and extra.get(key):
                    best[key] = extra[key]
    return best


def apply_to_row(row: Dict[str, str], result: Dict[str, str]) -> List[str]:
    """Completa campos del maestro. Devuelve la lista de campos modificados."""
    changed = []

    def put(field: str, value: str, overwrite: bool = False) -> None:
        if value and (overwrite or not str(row.get(field, "") or "").strip()) and row.get(field) != value:
            row[field] = value
            changed.append(field)

    put("doi", result.get("doi", ""))
    origin = str(row.get("origin", "") or "")
    if result.get("journal") and (not origin.strip() or all(is_repository(p) for p in origin.split("|"))):
        put("origin", result["journal"], overwrite=True)
    put("document_type", result.get("document_type", ""))
    put("keywords", result.get("keywords", ""))
    # El año de CONICET es el de carga en el repositorio: se reemplaza.
    put("publication_year", year_of(result.get("found_year")), overwrite=True)
    if result.get("found_date"):
        put("publication_date", result["found_date"], overwrite=True)
    put("openalex_id", result.get("openalex_id", ""))
    put("pdf_url", result.get("pdf_url", ""))
    if result.get("is_oa") == "True":
        put("is_oa", "True", overwrite=True)
    return changed


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    if not path.exists():
        return [], []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: List[str], rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_overrides(path: Optional[Path] = None) -> Dict[str, str]:
    _, rows = read_csv(path or OVERRIDES)
    return {r["record_id"].strip(): r.get("decision", "").strip().lower() for r in rows if r.get("record_id")}


def final_status(entry: Dict[str, str], overrides: Dict[str, str]) -> bool:
    decision = overrides.get(entry["record_id"], "")
    if decision == "rechazar":
        return False
    if decision == "aceptar":
        return entry.get("status") in ("aceptado", "revisar")
    return entry.get("status") == "aceptado"


def is_target(row: Dict[str, str]) -> bool:
    return "conicet" in str(row.get("source", "")).lower()


def relevance_shift(before: Dict[str, str], after: Dict[str, str]) -> Optional[str]:
    try:
        sys.path.insert(0, str(ROOT))
        from relevance_filter import classify_relevance
    except Exception:
        return None
    a, b = classify_relevance(before)[0], classify_relevance(after)[0]
    return None if a == b else f"{a}→{b}"


def run(args: argparse.Namespace, http_factory: Callable[[], Http] = None) -> Dict[str, Any]:
    fields, master = read_csv(MASTER)
    _, previous = read_csv(ENRICHMENT)
    cache = {r["record_id"]: r for r in previous}
    overrides = load_overrides()
    targets = [r for r in master if is_target(r)]
    pending = [r for r in targets if r["record_id"] not in cache
               or cache[r["record_id"]]["status"] == "error"
               or (args.retry_missing and cache[r["record_id"]]["status"] == "sin_coincidencia")]
    if args.limit:
        pending = pending[: args.limit]

    http = None
    conicet_up = False
    if pending and not args.offline:
        http = (http_factory or (lambda: Http(args.email, args.pause)))()
        probe = http.get("https://ri.conicet.gov.ar/oai/request", {"verb": "Identify"}, timeout=15)
        conicet_up = bool(probe is not None and probe.status_code == 200 and b"Identify" in probe.content)
        print(f"CONICET OAI-PMH {'disponible' if conicet_up else 'no responde: se usan OpenAlex y Crossref'}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    queried = 0
    if http:
        consecutive_errors = 0
        for i, row in enumerate(pending, 1):
            if consecutive_errors >= 10:
                print("Diez errores seguidos: las fuentes no responden; se reintentará en la próxima corrida.")
                break
            queried += 1
            try:
                result = lookup(http, row, conicet_up)
                consecutive_errors = 0
            except SourceUnavailable as exc:
                result = {"status": "error", "decision_reason": f"sin respuesta de {exc}"}
                consecutive_errors += 1
            except Exception as exc:  # una respuesta rara no debe frenar la corrida
                result = {"status": "error", "decision_reason": f"{type(exc).__name__}: {exc}"[:200]}
            entry = {k: str(result.get(k, "") or "") for k in ENRICHMENT_FIELDS}
            entry.update({
                "record_id": row["record_id"],
                "original_year": cache.get(row["record_id"], {}).get("original_year") or row.get("publication_year", ""),
                "match_authors": "; ".join(result.get("authors_list", []))[:500] if result.get("authors_list") else "",
                "handle": conicet_handle(row), "queried_at": now,
            })
            cache[row["record_id"]] = entry
            if i % 25 == 0:
                print(f"  {i}/{len(pending)} consultados")
                write_csv(ENRICHMENT, ENRICHMENT_FIELDS, list(cache.values()))

    applied_fields: Dict[str, int] = {}
    shifts: List[Dict[str, str]] = []
    target_ids = {r["record_id"] for r in targets}
    for row in master:
        entry = cache.get(row["record_id"])
        if not entry or row["record_id"] not in target_ids:
            continue
        ok = final_status(entry, overrides)
        entry["applied"] = "si" if ok else "no"
        if not ok:
            continue
        # El año original se conserva para que reaplicar sea idempotente.
        result = {**entry, "found_year": entry.get("found_year") or entry.get("original_year")}
        before = dict(row)
        changed = apply_to_row(row, result)
        for field in changed:
            applied_fields[field] = applied_fields.get(field, 0) + 1
        if changed:
            shift = relevance_shift(before, row)
            if shift:
                shifts.append({"record_id": row["record_id"], "title": row.get("title", "")[:120], "cambio": shift})

    entries = [cache[r["record_id"]] for r in targets if r["record_id"] in cache]
    counts: Dict[str, int] = {}
    for e in entries:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    applied = [e for e in entries if e.get("applied") == "si"]
    report = {
        "generated_at": now,
        "conicet_oai_available": conicet_up,
        "targets": len(targets),
        "queried_this_run": queried,
        "status_counts": counts,
        "applied_records": len(applied),
        "with_doi": sum(1 for e in applied if e.get("doi")),
        "with_journal": sum(1 for e in applied if e.get("journal")),
        "with_volume_or_pages": sum(1 for e in applied if e.get("volume") or e.get("pages")),
        "year_changed": sum(1 for e in applied if e.get("found_year") and e["found_year"] != e.get("original_year")),
        "master_fields_changed": applied_fields,
        "relevance_shifts": shifts,
        "http_failures": http.failures if http else {},
        "rules": {"title_accept": TITLE_ACCEPT, "title_review": TITLE_REVIEW,
                  "max_years_before_deposit": MAX_YEARS_BEFORE_DEPOSIT,
                  "never_overwritten": ["title", "authors", "abstract"]},
    }
    write_csv(ENRICHMENT, ENRICHMENT_FIELDS, sorted(cache.values(), key=lambda r: r["record_id"]))
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.apply:
        write_csv(MASTER, fields, master)
    print(json.dumps({k: report[k] for k in ("targets", "queried_this_run", "status_counts", "applied_records",
                                             "with_doi", "with_journal", "with_volume_or_pages", "year_changed")},
                     ensure_ascii=False))
    return report


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="escribir los datos aceptados en el maestro")
    parser.add_argument("--retry-missing", action="store_true", help="volver a consultar los registros sin coincidencia")
    parser.add_argument("--offline", action="store_true", help="no consultar fuentes; solo reaplicar la caché")
    parser.add_argument("--limit", type=int, default=0, help="máximo de registros a consultar en esta corrida")
    parser.add_argument("--pause", type=float, default=0.15, help="pausa entre pedidos, en segundos")
    parser.add_argument("--email", default=os.environ.get("CONTACT_EMAIL")
                        or "scrapeadoracademico@users.noreply.github.com")
    run(parser.parse_args(argv))


if __name__ == "__main__":
    main()
