#!/usr/bin/env python3
"""
Chequeo liviano del dashboard y de los insumos STM.

No recalcula el STM. Verifica si los archivos necesarios existen y genera
un reporte JSON auditable para GitHub Actions.
"""
from __future__ import annotations

import csv
import json
import re
from html.parser import HTMLParser
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from dashboard_integrity import publication_audit
from keyword_network import clean_keywords, read_rules


DATA_DIR = Path("data")
DOCS_DIR = Path("docs")
OUTPUT_DIR = Path("output")
REPORT = DATA_DIR / "dashboard_healthcheck.json"


def read_rows(path):
    csv.field_size_limit(20_000_000)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def js_value(path, prefix):
    text = path.read_text(encoding="utf-8")
    return json.JSONDecoder().raw_decode(text.split(prefix, 1)[1].lstrip())[0]


class TopicCards(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cards = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "article" and "tm-card" in attrs.get("class", ""):
            self.cards.append(attrs)


def inspect_site(records):
    """Fail publication on identity, export or topic-label regressions."""
    audit = publication_audit(records)
    failures = []
    if any(audit["duplicate_identifiers"].values()) or audit["duplicate_publication_urls"]:
        failures.append("Duplicate publication identity in master records")
    if audit["missing_titles"]:
        failures.append("Records without titles")
    counts = {}
    exports = {
        "dashboard": (DOCS_DIR / "dashboard-articles.js", "window.StellarArticles ="),
        "article_table": (DOCS_DIR / "articulos.html", "const ARTICLES ="),
        "library": (DOCS_DIR / "library_articles.json", None),
    }
    rules = read_rules()
    excluded_visible = 0
    for name, (path, prefix) in exports.items():
        try:
            rows = js_value(path, prefix) if prefix else json.loads(path.read_text(encoding="utf-8"))
            counts[name] = len(rows)
            if len(rows) != len(records):
                failures.append(f"{name}: {len(rows)} exports for {len(records)} publications")
            for row in rows:
                raw = ";".join(row.get("kws", [])) if name == "dashboard" else row.get("keywords", "")
                excluded_visible += len(clean_keywords(raw, rules)[1])
        except (OSError, ValueError, IndexError) as exc:
            failures.append(f"{name}: unreadable export ({exc})")
    if excluded_visible:
        failures.append(f"{excluded_visible} excluded indexing terms remain visible")
    try:
        html = (DOCS_DIR / "index.html").read_text(encoding="utf-8")
        networks = js_value(DOCS_DIR / "index.html", "const NETWORKS =")
        cards = TopicCards()
        cards.feed(html)
        labels = {(m, str(t["id"])): t["label"] for m, n in networks.items() for t in n["topics"]["nodes"]}
        mismatches = [c for c in cards.cards if labels.get((c.get("data-model"), c.get("data-topic"))) != c.get("data-original-label")]
        if mismatches:
            failures.append(f"{len(mismatches)} topic card/network label mismatches")
        for asset in re.findall(r'<script[^>]+src="([^"]+)"', html):
            if not asset.startswith(("http:", "https:")) and not (DOCS_DIR / asset).exists():
                failures.append(f"Missing dashboard script: {asset}")
        for model, network in networks.items():
            if len(network["documents"]["nodes"]) != len(records):
                failures.append(f"{model}: network publication count differs from master")
        model_coverage = {m: {k: n.get(k) for k in ("modeled", "assigned", "outliers", "not_modeled", "unlinked")}
                          for m, n in networks.items()}
    except (OSError, ValueError, IndexError) as exc:
        failures.append(f"Unreadable network export: {exc}")
        model_coverage = {}
    return {**audit, "export_counts": counts, "models": model_coverage,
            "excluded_visible_terms": excluded_visible, "failures": failures,
            "status": "passed" if not failures else "failed"}


def count_csv(path: Path) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    csv.field_size_limit(20_000_000)
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            return sum(1 for _ in csv.DictReader(fh))
    except Exception:
        return 0


def file_info(path: Path) -> Dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }


def main() -> None:
    master = DATA_DIR / "master_records.csv"
    review = DATA_DIR / "review_records.csv"
    rejected = DATA_DIR / "rejected_records.csv"
    dashboard = DOCS_DIR / "index.html"
    article_table = DOCS_DIR / "articulos.html"
    stm_files = {
        "corpus": DATA_DIR / "corpus.csv.gz",
        "tabla_topicos": OUTPUT_DIR / "tabla_topicos.csv",
        "document_topics": OUTPUT_DIR / "document_topics.csv",
        "stm_model": OUTPUT_DIR / "stm_model.rds",
        "informe_stm": OUTPUT_DIR / "informe_stm.html",
    }

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dashboard": file_info(dashboard),
        "article_table": file_info(article_table),
        "records": {
            "master_high_relevance": count_csv(master),
            "review": count_csv(review),
            "rejected": count_csv(rejected),
        },
        "stm_inputs_outputs": {name: file_info(path) for name, path in stm_files.items()},
        "stm_status": "ok" if all(path.exists() and path.stat().st_size > 0 for path in stm_files.values()) else "missing_or_not_regenerated",
        "note": (
            "El workflow operativo genera docs/index.html desde data/master_records.csv. "
            "El STM requiere data/corpus.csv.gz y salida R en output/. Si esos archivos faltan, "
            "el dashboard de tres columnas funciona, pero la capa STM no queda actualizada."
        ),
    }

    report["integrity"] = inspect_site(read_rows(master))

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=== Dashboard healthcheck ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["integrity"]["failures"]:
        raise SystemExit("Dashboard integrity checks failed; publication blocked.")


if __name__ == "__main__":
    main()
