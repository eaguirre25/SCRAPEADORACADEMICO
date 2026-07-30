from __future__ import annotations

import csv
import json
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .identifiers import clean_value, normalize_doi, normalize_text, stable_document_id
from .language_detection import detect_language
from .text_cleaning import clean_for_bertopic, clean_for_display


@dataclass
class BuildResult:
    metadata: list[dict[str, Any]]
    fulltext: list[dict[str, Any]]
    excluded: list[dict[str, Any]]
    duplicates: list[dict[str, Any]]


def read_csv(path: str | Path) -> list[dict[str, str]]:
    csv.field_size_limit(20_000_000)
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: str | Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    fields = fields or list(dict.fromkeys(key for row in rows for key in row))
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def weighted_metadata_text(record: dict[str, Any], weights: dict[str, int]) -> tuple[str, str]:
    title = clean_value(record.get("title"))
    abstract = clean_value(record.get("abstract"))
    keywords = clean_value(record.get("keywords"))
    segments: list[str] = []
    for name, value in (("title", title), ("keywords", keywords), ("abstract", abstract)):
        if value:
            segments.extend([value] * max(1, int(weights.get(name, 1))))
    if abstract or keywords:
        strategy = "title_keywords_abstract"
    elif title:
        strategy = "title_only"
    else:
        strategy = "missing"
    cleaned, _ = clean_for_bertopic(" ".join(segments))
    return cleaned, strategy


def _index_bibliography(records: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_doi: dict[str, dict[str, Any]] = {}
    by_title: dict[str, dict[str, Any]] = {}
    for row in records:
        doi = normalize_doi(row.get("doi"))
        title = normalize_text(row.get("title"))
        if doi:
            by_doi.setdefault(doi, row)
        if title:
            by_title.setdefault(title, row)
    return by_doi, by_title


def _common(record: dict[str, Any], document_id: str, unit: str, text: str, strategy: str) -> dict[str, Any]:
    language, probability, language_status = detect_language(text)
    return {
        "document_id": document_id,
        "corpus_unit": unit,
        "unidad_modelado": unit,
        "texto_modelado": text,
        "modeling_strategy": strategy,
        "title": clean_for_display(clean_value(record.get("title") or record.get("titulo"))),
        "abstract": clean_value(record.get("abstract")),
        "keywords": clean_value(record.get("keywords")),
        "year": clean_value(record.get("publication_year") or record.get("anio")),
        "authors": clean_value(record.get("authors") or record.get("autores")),
        "doi": normalize_doi(record.get("doi")),
        "record_id": clean_value(record.get("record_id")),
        "source": clean_value(record.get("source")),
        "url": clean_value(record.get("url")),
        "pdf_url": clean_value(record.get("pdf_url")),
        "language": language,
        "language_probability": probability if probability is not None else "",
        "language_detection_status": language_status,
        "text_characters": len(text),
    }


def build_corpora(config: dict[str, Any]) -> BuildResult:
    paths = config["paths"]
    corpus_cfg = config["corpus"]
    weights = config["metadata_corpus"]["field_weights"]
    bibliography = read_csv(paths["bibliographic_records"])
    pdf_rows = read_csv(paths["corpus_pdf"])
    by_doi, by_title = _index_bibliography(bibliography)
    metadata: list[dict[str, Any]] = []
    fulltext: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    start_year = int(config["project"]["start_year"])
    end_year = int(config["project"]["end_year"])

    def year_allowed(value: Any) -> bool:
        text = clean_value(value)
        try:
            return start_year <= int(float(text)) <= end_year
        except (TypeError, ValueError):
            return False

    for row in bibliography:
        try:
            doc_id = stable_document_id(row)
        except ValueError as exc:
            excluded.append({"corpus_unit": "metadata", "reason": str(exc), "title": row.get("title", "")})
            continue
        if not year_allowed(row.get("publication_year")):
            excluded.append({"document_id": doc_id, "corpus_unit": "metadata", "reason": "year_outside_configured_period", "title": row.get("title", "")})
            continue
        text, strategy = weighted_metadata_text(row, weights)
        if len(text) < int(corpus_cfg["minimum_characters"]) and strategy != "title_only":
            excluded.append({"document_id": doc_id, "corpus_unit": "metadata", "reason": "below_minimum_characters", "title": row.get("title", "")})
            continue
        if not text:
            excluded.append({"document_id": doc_id, "corpus_unit": "metadata", "reason": "missing_modeling_text", "title": row.get("title", "")})
            continue
        if doc_id in seen:
            duplicates.append({"document_id": doc_id, "corpus_unit": "metadata", "kept_title": seen[doc_id], "duplicate_title": row.get("title", "")})
            continue
        seen[doc_id] = clean_value(row.get("title"))
        metadata.append(_common(row, doc_id, "metadata", text, strategy))

    max_chars = int(corpus_cfg.get("full_text_max_characters", 120000))
    for pdf in pdf_rows:
        if clean_value(pdf.get("status")) != "ok":
            excluded.append({"corpus_unit": "full_text", "reason": clean_value(pdf.get("status")) or "invalid_status", "title": pdf.get("titulo", ""), "filename": pdf.get("filename", "")})
            continue
        bibliographic = by_doi.get(normalize_doi(pdf.get("doi"))) or by_title.get(normalize_text(pdf.get("titulo"))) or {}
        merged = dict(pdf)
        merged.update({key: value for key, value in bibliographic.items() if clean_value(value)})
        try:
            doc_id = stable_document_id(merged)
        except ValueError as exc:
            excluded.append({"corpus_unit": "full_text", "reason": str(exc), "title": pdf.get("titulo", ""), "filename": pdf.get("filename", "")})
            continue
        if not year_allowed(merged.get("publication_year") or merged.get("anio")):
            excluded.append({"document_id": doc_id, "corpus_unit": "full_text", "reason": "year_outside_configured_period", "title": pdf.get("titulo", ""), "filename": pdf.get("filename", "")})
            continue
        text, removal = clean_for_bertopic(
            clean_value(pdf.get("texto")), strip_references=bool(corpus_cfg.get("remove_references_from_full_text", True))
        )
        text = text[:max_chars]
        if len(text) < int(corpus_cfg["minimum_characters"]):
            excluded.append({"document_id": doc_id, "corpus_unit": "full_text", "reason": "below_minimum_characters", "title": pdf.get("titulo", ""), "filename": pdf.get("filename", "")})
            continue
        out = _common(merged, doc_id, "full_text", text, "full_text")
        out.update({
            "filename": clean_value(pdf.get("filename")),
            "pages": clean_value(pdf.get("paginas")),
            "references_detected": removal.detected,
            "reference_cut_position": removal.cut_position if removal.cut_position is not None else "",
            "reference_removed_fraction": round(removal.removed_fraction, 6),
        })
        fulltext.append(out)
    return BuildResult(metadata, fulltext, excluded, duplicates)


def export_corpora(config: dict[str, Any], result: BuildResult) -> None:
    root = Path(config["paths"]["output_root"]) / "corpus"
    write_csv(root / "modeling_corpus_metadata.csv", result.metadata)
    write_csv(root / "modeling_corpus_fulltext.csv", result.fulltext)
    write_csv(root / "excluded_documents.csv", result.excluded)
    write_csv(root / "deduplication_report.csv", result.duplicates)
    all_rows = result.metadata + result.fulltext
    years = Counter(row["year"] or "missing" for row in all_rows)
    languages = Counter(row["language"] for row in all_rows)
    lengths = [int(row["text_characters"]) for row in all_rows]
    quality = [
        {"metric": "bibliographic_records_modeled", "value": len(result.metadata)},
        {"metric": "fulltext_records_modeled", "value": len(result.fulltext)},
        {"metric": "excluded_documents", "value": len(result.excluded)},
        {"metric": "duplicates_detected", "value": len(result.duplicates)},
        {"metric": "median_text_characters", "value": statistics.median(lengths) if lengths else 0},
        {"metric": "pdf_coverage_pct", "value": round(100 * len(result.fulltext) / max(len(result.metadata), 1), 2)},
        {"metric": "year_distribution", "value": json.dumps(dict(sorted(years.items())), ensure_ascii=False)},
        {"metric": "language_distribution", "value": json.dumps(dict(sorted(languages.items())), ensure_ascii=False)},
    ]
    write_csv(root / "corpus_quality_report.csv", quality, ["metric", "value"])
