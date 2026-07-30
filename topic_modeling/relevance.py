from __future__ import annotations

import re
from typing import Any

from .identifiers import clean_value, normalize_text


SCHOOL_TERMS = (
    "school", "schools", "escolar", "escuela", "colegio", "secondary education", "primary education",
    "educação básica", "gestão escolar", "direção escolar", "kepala sekolah", "school principal",
)
DOMAIN_TERMS = (
    "school leadership", "educational leadership", "liderazgo escolar", "liderazgo educativo", "dirección escolar",
    "gestión escolar", "gestión educativa", "school management", "school administration", "principal leadership",
    "equipo directivo", "supervisión escolar", "organización escolar", "gestão escolar", "gestão educacional",
)
FALSE_POSITIVE_TERMS = (
    "nursing", "hospital", "patient", "clinical", "medical student", "mental health", "tax management",
    "taxation", "treasury", "accounting", "corporate leadership", "business management", "entrepreneurship",
    "industrial quality", "human resources management", "university administration", "higher education management",
)
INCLUDE_PROTOTYPES = [
    "school principals leadership and management of primary and secondary schools",
    "dirección gestión y liderazgo escolar equipos directivos supervisión y organización de escuelas",
    "direção gestão e liderança de escolas de educação básica",
    "kepemimpinan kepala sekolah dan manajemen sekolah",
]
EXCLUDE_PROTOTYPES = [
    "hospital nursing clinical leadership health administration patient care",
    "business corporate management accounting taxation treasury entrepreneurship",
    "generic artificial intelligence engineering and university administration unrelated to schools",
]


def _contains(text: str, terms: tuple[str, ...]) -> list[str]:
    folded = normalize_text(text)
    return [term for term in terms if normalize_text(term) in folded]


def semantic_relevance_scores(texts: list[str]) -> list[tuple[float, float]]:
    if not texts:
        return []
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        return [(0.0, 0.0) for _ in texts]
    corpus = texts + INCLUDE_PROTOTYPES + EXCLUDE_PROTOTYPES
    matrix = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True, strip_accents="unicode").fit_transform(corpus)
    doc_matrix = matrix[: len(texts)]
    include = matrix[len(texts): len(texts) + len(INCLUDE_PROTOTYPES)]
    exclude = matrix[len(texts) + len(INCLUDE_PROTOTYPES):]
    include_scores = cosine_similarity(doc_matrix, include).max(axis=1)
    exclude_scores = cosine_similarity(doc_matrix, exclude).max(axis=1)
    return [(float(a), float(b)) for a, b in zip(include_scores, exclude_scores, strict=True)]


def classify_relevance(records: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    cfg = config.get("relevance", {})
    texts = [" ".join(clean_value(row.get(field)) for field in ("title", "abstract", "keywords")) for row in records]
    semantic = semantic_relevance_scores(texts) if cfg.get("semantic_enabled", True) else [(0.0, 0.0)] * len(records)
    decisions: list[dict[str, Any]] = []
    for row, text, (include_similarity, exclude_similarity) in zip(records, texts, semantic, strict=True):
        school_hits = _contains(text, SCHOOL_TERMS)
        domain_hits = _contains(text, DOMAIN_TERMS)
        false_hits = _contains(text, FALSE_POSITIVE_TERMS)
        rule_score = min(1.0, 0.45 * bool(school_hits) + 0.65 * bool(domain_hits) - 0.7 * bool(false_hits and not school_hits))
        combined = rule_score + include_similarity - exclude_similarity
        if domain_hits and not (false_hits and not school_hits):
            status = "included"
        elif false_hits and not school_hits and combined <= float(cfg.get("clear_exclude_threshold", -0.6)) + 0.35:
            status = "excluded"
        elif combined >= float(cfg.get("clear_include_threshold", 0.6)):
            status = "included"
        elif combined <= float(cfg.get("clear_exclude_threshold", -0.6)):
            status = "excluded"
        elif false_hits or school_hits or include_similarity > 0.05:
            status = "borderline"
        else:
            status = "manual_review"
        reasons = []
        if domain_hits: reasons.append("domain_phrase")
        if school_hits: reasons.append("school_context")
        if false_hits: reasons.append("false_positive_risk")
        if not reasons: reasons.append("insufficient_domain_evidence")
        decisions.append({
            "publication_document_id": row.get("publication_document_id") or row["document_id"], "relevance_status": status,
            "relevance_score": round(combined, 6), "rule_score": round(rule_score, 6),
            "semantic_include_similarity": round(include_similarity, 6),
            "semantic_exclude_similarity": round(exclude_similarity, 6),
            "relevance_reason": ";".join(reasons),
            "relevance_evidence": " | ".join((domain_hits + school_hits + false_hits)[:12]),
            "automatic_decision": status, "human_decision": "", "review_status": "pending_human_review",
        })
    return decisions
