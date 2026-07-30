from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .deduplication import audit_and_resolve_duplicates
from .identifiers import clean_value, first_author, normalize_doi, normalize_text, stable_document_id
from .language_detection import detect_language
from .relevance import classify_relevance
from .text_cleaning import (
    artifact_counts,
    clean_for_display,
    clean_for_embeddings,
    clean_for_stm,
    split_academic_sections,
)


PUBLICATION_FIELDS = [
    "document_id", "doi_normalized", "title", "abstract", "keywords", "year", "authors", "first_author",
    "journal", "source", "source_database", "country", "language_metadata", "language_detected",
    "language_confidence", "publication_type", "educational_level", "has_pdf", "has_fulltext",
    "pdf_path_or_id", "fulltext_status", "relevance_status", "relevance_score", "relevance_reason",
    "duplicate_group_id", "metadata_text_available", "fulltext_available",
]


@dataclass
class BuildResult:
    publications: list[dict[str, Any]]
    metadata: list[dict[str, Any]]
    fulltext: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    excluded: list[dict[str, Any]]
    exact_duplicates: list[dict[str, Any]]
    probable_duplicates: list[dict[str, Any]]
    duplicate_resolution_log: list[dict[str, Any]]
    cleaning_audit: list[dict[str, Any]]
    relevance_decisions: list[dict[str, Any]]
    relevance_borderline: list[dict[str, Any]]

    @property
    def duplicates(self) -> list[dict[str, Any]]:
        return self.exact_duplicates


def read_csv(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    if not source.exists():
        return []
    csv.field_size_limit(50_000_000)
    with source.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: str | Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    fields = fields or list(dict.fromkeys(key for row in rows for key in row))
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        if fields:
            writer.writeheader()
            writer.writerows(rows)


def weighted_metadata_text(record: dict[str, Any], weights: dict[str, int]) -> tuple[str, str]:
    """Compatibility helper for explicit STM weighting experiments only."""
    title = clean_value(record.get("title"))
    abstract = clean_value(record.get("abstract"))
    keywords = clean_value(record.get("keywords"))
    segments: list[str] = []
    for name, value in (("title", title), ("keywords", keywords), ("abstract", abstract)):
        if value:
            segments.extend([value] * max(1, int(weights.get(name, 1))))
    strategy = "title_keywords_abstract" if abstract or keywords else ("title_only" if title else "missing")
    cleaned, _ = clean_for_embeddings(" ".join(segments))
    return cleaned, strategy


def metadata_text(record: dict[str, Any]) -> tuple[str, str]:
    fields = [(name, clean_value(record.get(name))) for name in ("title", "abstract", "keywords")]
    available = [value for _, value in fields if value]
    cleaned, _ = clean_for_embeddings("\n\n".join(available))
    return cleaned, "+".join(name for name, value in fields if value) or "missing"


def _year_allowed(value: Any, start: int, end: int) -> bool:
    try:
        return start <= int(float(clean_value(value))) <= end
    except (TypeError, ValueError):
        return False


def _publication_from_record(row: dict[str, Any]) -> dict[str, Any]:
    publication_id = clean_value(row.get("publication_document_id")) or stable_document_id(row)
    title = clean_for_display(clean_value(row.get("title")))
    abstract = clean_value(row.get("abstract"))
    keywords = clean_value(row.get("keywords"))
    language, confidence, _ = detect_language(" ".join((title, abstract, keywords)))
    return {
        "document_id": publication_id, "doi_normalized": normalize_doi(row.get("doi")), "title": title,
        "abstract": abstract, "keywords": keywords, "year": clean_value(row.get("publication_year")),
        "authors": clean_value(row.get("authors")), "first_author": first_author(row.get("authors")),
        "journal": clean_value(row.get("origin")), "source": clean_value(row.get("source")),
        "source_database": clean_value(row.get("source")), "country": clean_value(row.get("country")),
        "language_metadata": clean_value(row.get("language")), "language_detected": language,
        "language_confidence": "" if confidence is None else round(confidence, 6),
        "publication_type": clean_value(row.get("document_type")), "educational_level": "",
        "has_pdf": bool(clean_value(row.get("pdf_url"))), "has_fulltext": False,
        "pdf_path_or_id": clean_value(row.get("pdf_url")), "fulltext_status": "not_linked",
        "relevance_status": "", "relevance_score": "", "relevance_reason": "",
        "duplicate_group_id": clean_value(row.get("duplicate_group_id")),
        "metadata_text_available": bool(title and (abstract or keywords)), "fulltext_available": False,
        "record_id": clean_value(row.get("record_id")), "openalex_id": clean_value(row.get("openalex_id")),
        "url": clean_value(row.get("url")), "pdf_url": clean_value(row.get("pdf_url")),
    }


def _fulltext_id(row: dict[str, Any], index: int) -> str:
    basis = "|".join((clean_value(row.get("filename")), normalize_doi(row.get("doi")), normalize_text(row.get("titulo")), str(index)))
    return "fulltext:" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


def _select_fulltext(sections: dict[str, str], fallback: str, strategy: str) -> tuple[str, str]:
    if strategy == "abstract_only" and sections.get("abstract"):
        return sections["abstract"], "abstract_only"
    if strategy in {"abstract_introduction_conclusions", "introduction_conclusions"}:
        names = ("introduction", "conclusions") if strategy == "introduction_conclusions" else ("abstract", "introduction", "conclusions")
        selected = [sections[name] for name in names if sections.get(name)]
        if selected:
            return "\n\n".join(selected), strategy
    body = sections.get("body") or "\n\n".join(value for name, value in sections.items() if name not in {"references", "appendices"}) or fallback
    return body, "fulltext_without_references_fallback"


def _stratified_sample(rows: list[dict[str, Any]], size: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    strata: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        strata[(row.get("relevance_status", ""), row.get("language_detected", ""), row.get("source_database", ""))].append(row)
    for values in strata.values():
        rng.shuffle(values)
    sample: list[dict[str, Any]] = []
    keys = sorted(strata)
    while len(sample) < min(size, len(rows)) and keys:
        remaining = []
        for key in keys:
            if strata[key] and len(sample) < size:
                sample.append(strata[key].pop())
            if strata[key]:
                remaining.append(key)
        keys = remaining
    return sample


def build_corpora(config: dict[str, Any]) -> BuildResult:
    paths, corpus_cfg = config["paths"], config["corpus"]
    records = read_csv(paths["bibliographic_records"])
    pdf_rows = read_csv(paths["corpus_pdf"])
    canonical_records, exact, probable, resolution = audit_and_resolve_duplicates(records)
    publications = [_publication_from_record(row) for row in canonical_records]
    pub_by_id = {row["document_id"]: row for row in publications}
    by_doi: dict[str, list[str]] = defaultdict(list)
    by_title: dict[str, list[str]] = defaultdict(list)
    for row in publications:
        if row["doi_normalized"]:
            by_doi[row["doi_normalized"]].append(row["document_id"])
        if normalize_text(row["title"]):
            by_title[normalize_text(row["title"])].append(row["document_id"])

    relationships: list[dict[str, Any]] = []
    pdf_candidates: dict[str, list[tuple[dict[str, Any], str, str]]] = defaultdict(list)
    unresolved_relationships: set[str] = set()
    for index, pdf in enumerate(pdf_rows):
        fulltext_id = _fulltext_id(pdf, index)
        doi_matches = by_doi.get(normalize_doi(pdf.get("doi")), []) if normalize_doi(pdf.get("doi")) else []
        title_matches = by_title.get(normalize_text(pdf.get("titulo")), []) if normalize_text(pdf.get("titulo")) else []
        candidates = sorted(set(doi_matches or title_matches))
        match_method = "doi_normalized" if doi_matches else ("title_normalized_exact" if title_matches else "unmatched")
        relationship_status = "matched" if len(candidates) == 1 else ("ambiguous" if len(candidates) > 1 else "unmatched")
        publication_id = candidates[0] if len(candidates) == 1 else ""
        if not publication_id and relationship_status == "unmatched":
            synthetic = {
                "doi": pdf.get("doi"), "title": pdf.get("titulo"), "titulo": pdf.get("titulo"),
                "publication_year": pdf.get("anio"), "anio": pdf.get("anio"), "authors": pdf.get("autores"),
                "autores": pdf.get("autores"), "filename": pdf.get("filename"),
            }
            publication_id = stable_document_id(synthetic)
            if publication_id not in pub_by_id:
                language, confidence, _ = detect_language(clean_value(pdf.get("texto"))[:10000])
                new_pub = {
                    "document_id": publication_id, "doi_normalized": normalize_doi(pdf.get("doi")),
                    "title": clean_for_display(clean_value(pdf.get("titulo"))), "abstract": "", "keywords": "",
                    "year": clean_value(pdf.get("anio")), "authors": clean_value(pdf.get("autores")),
                    "first_author": first_author(pdf.get("autores")), "journal": clean_value(pdf.get("revista")),
                    "source": "PDF corpus only", "source_database": "PDF corpus only", "country": "",
                    "language_metadata": "", "language_detected": language,
                    "language_confidence": "" if confidence is None else round(confidence, 6), "publication_type": "",
                    "educational_level": "", "has_pdf": True, "has_fulltext": False,
                    "pdf_path_or_id": clean_value(pdf.get("filename")), "fulltext_status": "unmatched_metadata",
                    "relevance_status": "manual_review", "relevance_score": "", "relevance_reason": "pdf_without_metadata_match",
                    "duplicate_group_id": "", "metadata_text_available": False, "fulltext_available": False,
                    "record_id": "", "openalex_id": "", "url": "", "pdf_url": "",
                }
                publications.append(new_pub); pub_by_id[publication_id] = new_pub
                if new_pub["doi_normalized"]: by_doi[new_pub["doi_normalized"]].append(publication_id)
                if normalize_text(new_pub["title"]): by_title[normalize_text(new_pub["title"])].append(publication_id)
            relationship_status, match_method = "pdf_only_publication", "standalone_pdf_record"
        if relationship_status == "ambiguous":
            unresolved_relationships.add(fulltext_id)
        relationships.append({
            "metadata_document_id": publication_id if relationship_status == "matched" else "",
            "fulltext_document_id": fulltext_id, "publication_document_id": publication_id,
            "match_method": match_method, "match_status": relationship_status,
            "candidate_publication_ids": " | ".join(candidates), "doi_normalized": normalize_doi(pdf.get("doi")),
            "title": clean_value(pdf.get("titulo")), "filename": clean_value(pdf.get("filename")),
        })
        if publication_id:
            pdf_candidates[publication_id].append((pdf, fulltext_id, relationship_status))

    relevance_input = [row for row in publications if row["source_database"] != "PDF corpus only"]
    decisions = classify_relevance(relevance_input, config)
    decisions_by_id = {row["publication_document_id"]: row for row in decisions}
    for publication in publications:
        decision = decisions_by_id.get(publication["document_id"])
        if decision:
            publication.update({key: decision[key] for key in ("relevance_status", "relevance_score", "relevance_reason")})

    start, end = int(config["project"]["start_year"]), int(config["project"]["end_year"])
    exclusions: list[dict[str, Any]] = []
    for relationship in relationships:
        if relationship["match_status"] == "ambiguous":
            exclusions.append({
                "publication_document_id": "", "representation_id": relationship["fulltext_document_id"],
                "corpus": "fulltext", "stage": "relationship",
                "reason": "ambiguous_metadata_fulltext_relationship", "title": relationship["title"],
                "filename": relationship["filename"], "reviewable": True,
            })
    cleaning: list[dict[str, Any]] = []
    metadata_rows: list[dict[str, Any]] = []
    metadata_min = int(corpus_cfg.get("metadata_minimum_characters", 80))
    for publication in publications:
        publication_id = publication["document_id"]
        text, strategy = metadata_text(publication)
        reasons = []
        if publication["source_database"] == "PDF corpus only": reasons.append("metadata_unavailable_pdf_only")
        if not _year_allowed(publication["year"], start, end): reasons.append("year_outside_configured_period")
        if len(text) < metadata_min: reasons.append("metadata_below_minimum_characters")
        if publication["relevance_status"] != "included": reasons.append(f"relevance_{publication['relevance_status'] or 'unclassified'}")
        if reasons:
            exclusions.append({
                "publication_document_id": publication_id, "representation_id": publication_id,
                "corpus": "metadata", "stage": "eligibility", "reason": ";".join(reasons),
                "title": publication["title"], "reviewable": True,
            })
            continue
        cleaned_stm, _ = clean_for_stm(text)
        metadata_rows.append({
            "publication_document_id": publication_id, "metadata_document_id": publication_id,
            "fulltext_document_id": "", "document_id": publication_id, "corpus_unit": "metadata",
            "unidad_modelado": "metadata", "text_for_modeling": text, "texto_modelado": text,
            "text_for_stm": cleaned_stm, "modeling_strategy": strategy, "title": publication["title"],
            "abstract": publication["abstract"], "keywords": publication["keywords"], "year": publication["year"],
            "authors": publication["authors"], "doi": publication["doi_normalized"], "record_id": publication["record_id"],
            "source": publication["source_database"], "url": publication["url"], "pdf_url": publication["pdf_url"],
            "language": publication["language_detected"], "language_probability": publication["language_confidence"],
            "language_detection_status": "ok" if publication["language_detected"] != "und" else "undetected",
            "text_characters": len(text), "text_tokens": len(text.split()),
            "title_text": publication["title"], "abstract_text": publication["abstract"], "keywords_text": publication["keywords"],
            "stm_weighting_strategy": config.get("metadata_corpus", {}).get("stm_strategy", "unweighted"),
            "relevance_status": publication["relevance_status"], "relevance_score": publication["relevance_score"],
        })
        cleaning.append({
            "publication_document_id": publication_id, "representation_id": publication_id, "corpus": "metadata",
            "original_characters": len(" ".join((publication["title"], publication["abstract"], publication["keywords"]))),
            "cleaned_characters": len(text), "removed_fraction": 0,
            **artifact_counts(" ".join((publication["title"], publication["abstract"], publication["keywords"]))),
        })

    fulltext_rows: list[dict[str, Any]] = []
    max_chars = int(corpus_cfg.get("full_text_max_characters", 120000))
    fulltext_min = int(corpus_cfg.get("minimum_characters", 200))
    strategy_requested = config.get("fulltext_strategy", {}).get("default", "abstract_introduction_conclusions")
    for publication_id, candidates in pdf_candidates.items():
        # A publication is one analytical unit: keep the longest eligible extraction and log every alternative.
        ordered = sorted(candidates, key=lambda item: len(clean_value(item[0].get("texto"))), reverse=True)
        selected = False
        for pdf, fulltext_id, relation_status in ordered:
            raw = clean_value(pdf.get("texto"))
            status = clean_value(pdf.get("status"))
            if fulltext_id in unresolved_relationships:
                reason = "ambiguous_metadata_fulltext_relationship"
            elif status != "ok":
                reason = status or "invalid_extraction_status"
            elif selected:
                reason = "duplicate_fulltext_representation"
            else:
                cleaned, removal = clean_for_embeddings(raw, strip_references=bool(corpus_cfg.get("remove_references", True)))
                sections = split_academic_sections(cleaned)
                selected_text, used_strategy = _select_fulltext(sections, cleaned, strategy_requested)
                truncated = len(selected_text) > max_chars
                selected_text = selected_text[:max_chars]
                publication = pub_by_id[publication_id]
                publication["has_pdf"] = True
                publication["pdf_path_or_id"] = clean_value(pdf.get("filename"))
                publication["has_fulltext"] = status == "ok" and len(cleaned) >= fulltext_min
                model_year = publication["year"] or clean_value(pdf.get("anio"))
                if publication["relevance_status"] != "included":
                    reason = f"relevance_{publication['relevance_status'] or 'unclassified'}"
                elif not _year_allowed(model_year, start, end):
                    reason = "year_outside_configured_period"
                elif len(selected_text) < fulltext_min:
                    reason = "fulltext_below_minimum_characters"
                else:
                    selected = True
                    language, confidence, language_status = detect_language(selected_text)
                    cleaned_stm, _ = clean_for_stm(selected_text)
                    fulltext_rows.append({
                        "publication_document_id": publication_id, "metadata_document_id": publication_id if publication["source_database"] != "PDF corpus only" else "",
                        "fulltext_document_id": fulltext_id, "document_id": publication_id, "corpus_unit": "fulltext",
                        "unidad_modelado": "fulltext", "text_for_modeling": selected_text, "texto_modelado": selected_text,
                        "text_for_stm": cleaned_stm, "modeling_strategy": used_strategy, "title": publication["title"],
                        "abstract": publication["abstract"], "keywords": publication["keywords"], "year": model_year,
                        "authors": publication["authors"], "doi": publication["doi_normalized"], "record_id": publication["record_id"],
                        "source": publication["source_database"], "url": publication["url"], "pdf_url": publication["pdf_url"],
                        "language": language, "language_probability": "" if confidence is None else round(confidence, 6),
                        "language_detection_status": language_status, "text_characters": len(selected_text),
                        "text_tokens": len(selected_text.split()), "filename": clean_value(pdf.get("filename")),
                        "pages": clean_value(pdf.get("paginas")), "sections_detected": " | ".join(sections),
                        "section_characters": json.dumps({key: len(value) for key, value in sections.items()}, ensure_ascii=False),
                        "references_detected": removal.detected, "reference_cut_position": removal.cut_position or "",
                        "reference_removed_fraction": round(removal.removed_fraction, 6), "truncated": truncated,
                        "truncation_fraction": round(max(0, len(_select_fulltext(sections, cleaned, strategy_requested)[0]) - max_chars) / max(len(_select_fulltext(sections, cleaned, strategy_requested)[0]), 1), 6),
                        "relevance_status": publication["relevance_status"], "fulltext_is_secondary": True,
                    })
                    publication["fulltext_available"] = True
                    publication["fulltext_status"] = "eligible_secondary"
                    counts = artifact_counts(raw)
                    cleaning.append({
                        "publication_document_id": publication_id, "representation_id": fulltext_id, "corpus": "fulltext",
                        "original_characters": len(raw), "cleaned_characters": len(selected_text),
                        "removed_fraction": round(1 - len(selected_text) / max(len(raw), 1), 6), **counts,
                    })
                    continue
                publication["fulltext_status"] = reason
            exclusions.append({
                "publication_document_id": publication_id, "representation_id": fulltext_id, "corpus": "fulltext",
                "stage": "eligibility", "reason": reason, "title": clean_value(pdf.get("titulo")),
                "filename": clean_value(pdf.get("filename")), "reviewable": True,
            })

    borderline = [
        {**publication, **decisions_by_id.get(publication["document_id"], {})}
        for publication in publications if publication.get("relevance_status") in {"borderline", "manual_review"}
    ]
    return BuildResult(publications, metadata_rows, fulltext_rows, relationships, exclusions, exact, probable, resolution, cleaning, decisions, borderline)


def _distribution(rows: list[dict[str, Any]], field: str) -> str:
    return json.dumps(dict(sorted(Counter(clean_value(row.get(field)) or "missing" for row in rows).items())), ensure_ascii=False)


def _residual_artifact_candidates(rows: list[dict[str, Any]], limit: int = 500) -> list[dict[str, Any]]:
    candidates: Counter[tuple[str, str]] = Counter()
    for row in rows:
        text = clean_value(row.get("text_for_modeling"))[:50000]
        for token in re.findall(r"(?u)\b[^\W_]+\b", text.casefold()):
            reason = ""
            if len(token) >= 24:
                reason = "very_long_possible_concatenation"
            elif len(token) >= 12 and any(char.isdigit() for char in token) and any(char.isalpha() for char in token):
                reason = "mixed_alphanumeric_identifier"
            elif re.search(r"(.)\1{3,}", token):
                reason = "repeated_character_sequence"
            elif len(token) >= 16:
                vowels = sum(char in "aeiouáéíóúüãõàâêô" for char in token)
                if vowels / len(token) < 0.18:
                    reason = "low_readability_long_token"
            if reason:
                candidates[(token, reason)] += 1
    return [
        {"token": token, "frequency": frequency, "reason": reason, "review_status": "pending_human_review"}
        for (token, reason), frequency in candidates.most_common(limit)
    ]


def export_corpora(config: dict[str, Any], result: BuildResult) -> None:
    root = Path(config["paths"]["output_root"]) / "corpus"
    write_csv(root / "publications_master.csv", result.publications, PUBLICATION_FIELDS)
    write_csv(root / "modeling_corpus_metadata.csv", result.metadata)
    write_csv(root / "modeling_corpus_fulltext.csv", result.fulltext)
    write_csv(root / "corpus_relationships.csv", result.relationships)
    write_csv(root / "exclusions.csv", result.excluded)
    write_csv(root / "excluded_documents.csv", result.excluded)
    write_csv(root / "exact_duplicates.csv", result.exact_duplicates)
    write_csv(root / "probable_duplicates.csv", result.probable_duplicates)
    write_csv(root / "duplicate_resolution_log.csv", result.duplicate_resolution_log)
    write_csv(root / "deduplication_report.csv", result.exact_duplicates)
    write_csv(root / "cleaning_audit.csv", result.cleaning_audit)
    write_csv(root / "relevance_decisions.csv", result.relevance_decisions)
    write_csv(root / "relevance_borderline.csv", result.relevance_borderline)

    removed_totals = Counter()
    for row in result.cleaning_audit:
        for key in ("urls", "dois", "issn", "licenses", "repository_ids", "emails", "bibliographic_ids", "editorial_lines", "broken_tokens"):
            removed_totals[key] += int(row.get(key, 0) or 0)
    write_csv(root / "frequent_removed_patterns.csv", [
        {"pattern_type": key, "occurrences": value, "action": "removed_before_modeling"} for key, value in removed_totals.most_common()
    ])
    write_csv(root / "residual_artifact_candidates.csv", _residual_artifact_candidates(result.metadata + result.fulltext),
              ["token", "frequency", "reason", "review_status"])

    sample_size = int(config.get("relevance", {}).get("validation_sample_size", 200))
    validation_sample = _stratified_sample(result.publications, sample_size, int(config["project"]["seed"]))
    validation_path = root / "relevance_validation_sample.csv"
    review_fields = ["human_relevance_status", "reviewer", "human_relevance_status_2", "reviewer_2", "review_notes"]
    previous_reviews = {row.get("document_id", ""): row for row in read_csv(validation_path)} if validation_path.exists() else {}
    for row in validation_sample:
        old = previous_reviews.get(row["document_id"], {})
        row.update({field: old.get(field, "") for field in review_fields})
    validation_fields = PUBLICATION_FIELDS + review_fields
    write_csv(validation_path, validation_sample, validation_fields)

    valid_states = {"included", "borderline", "excluded", "manual_review"}
    reviewed = [row for row in validation_sample if row.get("human_relevance_status") in valid_states]
    errors = []
    for row in reviewed:
        automatic = row.get("relevance_status", ""); human = row.get("human_relevance_status", "")
        if automatic != human:
            errors.append({
                "publication_document_id": row["document_id"], "automatic_status": automatic,
                "human_status": human, "error_type": f"{automatic}_as_{human}",
                "language": row.get("language_detected", ""), "source": row.get("source_database", ""),
                "notes": row.get("review_notes", ""),
            })
    write_csv(root / "relevance_error_analysis.csv", errors, [
        "publication_document_id", "automatic_status", "human_status", "error_type", "language", "source", "notes"
    ])
    tp = sum(row.get("relevance_status") == "included" and row.get("human_relevance_status") == "included" for row in reviewed)
    fp = sum(row.get("relevance_status") == "included" and row.get("human_relevance_status") != "included" for row in reviewed)
    fn = sum(row.get("relevance_status") != "included" and row.get("human_relevance_status") == "included" for row in reviewed)
    tn = len(reviewed) - tp - fp - fn
    precision = tp / (tp + fp) if tp + fp else ""
    recall = tp / (tp + fn) if tp + fn else ""
    f1 = 2 * precision * recall / (precision + recall) if precision != "" and recall != "" and precision + recall else ""
    double_coded = [row for row in validation_sample if row.get("human_relevance_status") in valid_states and row.get("human_relevance_status_2") in valid_states]
    agreement = sum(row["human_relevance_status"] == row["human_relevance_status_2"] for row in double_coded) / len(double_coded) if double_coded else ""
    kappa = ""
    if double_coded:
        first_counts = Counter(row["human_relevance_status"] for row in double_coded)
        second_counts = Counter(row["human_relevance_status_2"] for row in double_coded)
        expected = sum(first_counts[state] * second_counts[state] for state in valid_states) / len(double_coded) ** 2
        kappa = (agreement - expected) / (1 - expected) if expected < 1 else ""
    write_csv(root / "relevance_validation_metrics.csv", [
        {"metric": "reviewed_documents", "value": len(reviewed)}, {"metric": "true_positive", "value": tp},
        {"metric": "false_positive", "value": fp}, {"metric": "false_negative", "value": fn},
        {"metric": "true_negative", "value": tn}, {"metric": "precision", "value": precision},
        {"metric": "recall", "value": recall}, {"metric": "f1", "value": f1},
        {"metric": "double_coded_documents", "value": len(double_coded)},
        {"metric": "inter_reviewer_agreement", "value": agreement}, {"metric": "cohen_kappa", "value": kappa},
        {"metric": "validation_status", "value": "validated" if len(reviewed) == len(validation_sample) and len(double_coded) else "pending_human_review"},
    ], ["metric", "value"])

    unique = result.publications
    metadata_ids = {row["publication_document_id"] for row in result.metadata}
    fulltext_ids = {row["publication_document_id"] for row in result.fulltext}
    unique_metadata = [row for row in unique if row["document_id"] in metadata_ids]
    unique_fulltext = [row for row in unique if row["document_id"] in fulltext_ids]
    metrics = [
        {"metric_group": "unique_publication_metrics", "metric": "unique_publications_observed", "value": len(unique)},
        {"metric_group": "metadata_metrics", "metric": "metadata_eligible_publications", "value": len(metadata_ids)},
        {"metric_group": "fulltext_metrics", "metric": "fulltext_candidates", "value": len(result.relationships)},
        {"metric_group": "fulltext_metrics", "metric": "fulltext_eligible", "value": len(fulltext_ids)},
        {"metric_group": "intersection_metrics", "metric": "metadata_fulltext_intersection", "value": len(metadata_ids & fulltext_ids)},
        {"metric_group": "representation_metrics", "metric": "modeling_representations", "value": len(result.metadata) + len(result.fulltext)},
        {"metric_group": "exclusion_metrics", "metric": "excluded_representations", "value": len(result.excluded)},
        {"metric_group": "duplicate_metrics", "metric": "exact_duplicate_rows", "value": len(result.exact_duplicates)},
        {"metric_group": "duplicate_metrics", "metric": "probable_duplicate_pairs", "value": len(result.probable_duplicates)},
        {"metric_group": "distribution", "metric": "year_distribution_unique_publications", "value": _distribution(unique, "year")},
        {"metric_group": "distribution", "metric": "year_distribution_metadata", "value": _distribution(unique_metadata, "year")},
        {"metric_group": "distribution", "metric": "year_distribution_fulltext", "value": _distribution(unique_fulltext, "year")},
        {"metric_group": "distribution", "metric": "language_distribution_metadata", "value": _distribution(result.metadata, "language")},
        {"metric_group": "distribution", "metric": "language_distribution_fulltext", "value": _distribution(result.fulltext, "language")},
    ]
    write_csv(root / "corpus_quality_report.csv", metrics, ["metric_group", "metric", "value"])

    coverage_rows = []
    years = range(int(config["project"]["start_year"]), int(config["project"]["end_year"]) + 1)
    for year in years:
        metadata_count = sum(str(row["year"]) == str(year) for row in result.metadata)
        fulltext_count = sum(str(row["year"]) == str(year) for row in result.fulltext if row["publication_document_id"] in metadata_ids)
        coverage_rows.append({
            "year": year, "unique_metadata_publications": metadata_count,
            "unique_publications_with_fulltext": fulltext_count,
            "fulltext_coverage_in_year": round(fulltext_count / metadata_count, 6) if metadata_count else 0,
            "year_complete": year != int(config["project"]["end_year"]),
        })
    write_csv(root / "annual_coverage.csv", coverage_rows)
    fulltext_exclusions = [row for row in result.excluded if row.get("corpus") == "fulltext"]
    removed_by_cleaning_ids = {
        row.get("representation_id") for row in fulltext_exclusions
        if "below_minimum" in str(row.get("reason", "")) or "error:" in str(row.get("reason", ""))
        or "invalid_extraction" in str(row.get("reason", ""))
    }
    write_csv(root / "fulltext_preprocessing_counts.csv", [
        {"metric": "fulltext_candidates", "value": len(result.relationships), "status": "computed"},
        {"metric": "fulltext_eligible", "value": len(fulltext_ids), "status": "computed_after_relationship_relevance_cleaning"},
        {"metric": "removed_by_cleaning", "value": len(removed_by_cleaning_ids), "status": "computed"},
        {"metric": "removed_by_textProcessor", "value": "", "status": "pending_STM_FULLTEXT_execution"},
        {"metric": "removed_by_prepDocuments", "value": "", "status": "pending_STM_FULLTEXT_execution"},
        {"metric": "fulltext_in_final_model", "value": "", "status": "pending_STM_FULLTEXT_execution"},
    ], ["metric", "value", "status"])
