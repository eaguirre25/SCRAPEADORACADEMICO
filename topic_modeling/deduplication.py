from __future__ import annotations

import hashlib
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

from .identifiers import clean_value, first_author, normalize_doi, normalize_text, stable_document_id


def _group_id(kind: str, value: str) -> str:
    return f"{kind}:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _best_record(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def completeness(row: dict[str, Any]) -> tuple[int, int, int]:
        populated = sum(bool(clean_value(row.get(field))) for field in (
            "doi", "title", "abstract", "keywords", "authors", "publication_year", "url", "pdf_url"
        ))
        return populated, len(clean_value(row.get("abstract"))), len(clean_value(row.get("keywords")))

    return max(rows, key=completeness)


def audit_and_resolve_duplicates(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve only high-confidence duplicates and preserve all uncertain pairs for review."""
    parent = list(range(len(records)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    doi_groups: dict[str, list[int]] = defaultdict(list)
    strong_groups: dict[str, list[int]] = defaultdict(list)
    title_year_groups: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(records):
        doi = normalize_doi(row.get("doi"))
        title = normalize_text(row.get("title"))
        year = clean_value(row.get("publication_year"))
        author = first_author(row.get("authors"))
        if doi:
            doi_groups[doi].append(index)
        if title and year and author:
            strong_groups[f"{title}|{year}|{author}"].append(index)
        if title and year:
            title_year_groups[f"{title}|{year}"].append(index)
    for groups in (doi_groups, strong_groups):
        for indexes in groups.values():
            for other in indexes[1:]:
                union(indexes[0], other)

    components: dict[int, list[int]] = defaultdict(list)
    for index in range(len(records)):
        components[find(index)].append(index)

    canonical: list[dict[str, Any]] = []
    exact: list[dict[str, Any]] = []
    resolution: list[dict[str, Any]] = []
    source_to_publication: dict[int, str] = {}
    for indexes in components.values():
        rows = [records[index] for index in indexes]
        best = _best_record(rows)
        kept = dict(best)
        if len(rows) > 1 and not normalize_doi(kept.get("doi")):
            publication_id = stable_document_id({
                "title": kept.get("title"), "publication_year": kept.get("publication_year"),
                "authors": kept.get("authors"),
            })
        else:
            publication_id = stable_document_id(kept)
        duplicate_group_id = _group_id("duplicate", "|".join(sorted(clean_value(r.get("record_id")) for r in rows))) if len(rows) > 1 else ""
        kept["publication_document_id"] = publication_id
        kept["duplicate_group_id"] = duplicate_group_id
        canonical.append(kept)
        for index, row in zip(indexes, rows, strict=True):
            source_to_publication[index] = publication_id
            if len(rows) > 1:
                rule = "doi_normalized" if normalize_doi(row.get("doi")) else "title_year_first_author"
                exact.append({
                    "duplicate_group_id": duplicate_group_id, "publication_document_id": publication_id,
                    "source_record_id": clean_value(row.get("record_id")), "rule": rule,
                    "doi_normalized": normalize_doi(row.get("doi")), "title": clean_value(row.get("title")),
                    "year": clean_value(row.get("publication_year")), "first_author": first_author(row.get("authors")),
                })
                resolution.append({
                    "duplicate_group_id": duplicate_group_id, "source_record_id": clean_value(row.get("record_id")),
                    "publication_document_id": publication_id,
                    "decision": "merged_exact" if row is not best else "kept_canonical",
                    "decision_basis": rule, "review_status": "algorithmic_high_confidence",
                })

    probable: list[dict[str, Any]] = []
    # Blocking by year and first title character keeps the audit tractable and reproducible.
    blocks: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, row in enumerate(records):
        title = normalize_text(row.get("title"))
        year = clean_value(row.get("publication_year"))
        if len(title) >= 20 and year:
            blocks[(year, title[:1])].append(index)
    seen_pairs: set[tuple[str, str]] = set()
    for indexes in blocks.values():
        for left_pos, left in enumerate(indexes):
            left_title = normalize_text(records[left].get("title"))
            for right in indexes[left_pos + 1:]:
                if find(left) == find(right):
                    continue
                right_title = normalize_text(records[right].get("title"))
                if abs(len(left_title) - len(right_title)) > max(15, int(0.2 * max(len(left_title), len(right_title)))):
                    continue
                similarity = SequenceMatcher(None, left_title, right_title).ratio()
                if similarity < 0.92:
                    continue
                left_id, right_id = source_to_publication[left], source_to_publication[right]
                pair = tuple(sorted((left_id, right_id)))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                probable.append({
                    "probable_group_id": _group_id("probable", "|".join(pair)),
                    "publication_document_id_a": left_id, "publication_document_id_b": right_id,
                    "title_a": clean_value(records[left].get("title")), "title_b": clean_value(records[right].get("title")),
                    "year": clean_value(records[left].get("publication_year")),
                    "first_author_a": first_author(records[left].get("authors")),
                    "first_author_b": first_author(records[right].get("authors")),
                    "title_similarity": round(similarity, 6), "decision": "manual_review",
                })
    return canonical, exact, probable, resolution
