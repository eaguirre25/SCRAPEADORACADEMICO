from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .corpus_builder import read_csv, write_csv
from .vectorization import build_vectorizer


PREFERRED_RELATIVE = Path("bertopic/metadata_multilingual/preferred_solution")
COUNTRY_CANDIDATES = (
    "study_country", "country", "country_code", "affiliation_country",
    "location_country", "pais_estudio", "pais", "país",
)
SOURCE_CANDIDATES = ("source", "repository", "provider", "database")
CONTAMINATION_PATTERNS = {
    "clinical_or_hospital": r"\b(?:clinical|hospital|patient|patients|nursing|nurse|healthcare|hospitalar|enfermagem|enfermería)\b",
    "medical_training": r"\bmedical\s+(?:student|students|school|training)\b|\bfacultad\s+de\s+medicina\b",
    "tax_or_accounting": r"\b(?:taxation|tax administration|treasury|contabilidad|accounting)\b",
    "mining": r"\b(?:mineral|mining|minería)\b",
    "suicide": r"\b(?:suicide|suicidio)\b",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def _json_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _truthy(value: Any) -> bool:
    return str(value).casefold() in {"true", "1", "yes", "sí", "si"}


def _entropy(values: list[str]) -> float | None:
    if not values:
        return None
    counts = Counter(values)
    if len(counts) < 2:
        return None
    total = sum(counts.values())
    return -sum((count / total) * math.log(count / total) for count in counts.values())


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(math.floor(position)); upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def _round(value: float | None, digits: int = 6) -> float | str:
    return "" if value is None or not math.isfinite(value) else round(value, digits)


def discover_metadata_fields(rows: list[dict[str, str]]) -> dict[str, Any]:
    columns = set(rows[0]) if rows else set()
    country = next((field for field in COUNTRY_CANDIDATES if field in columns), "")
    source = next((field for field in SOURCE_CANDIDATES if field in columns), "")
    return {
        "country_field": country,
        "country_semantics": "country_of_study_or_affiliation" if country else "not_available",
        "source_field": source,
        "source_semantics": "bibliographic_provider_or_repository" if source else "not_available",
        "journal_field": next((field for field in ("journal", "venue", "host_venue") if field in columns), ""),
        "affiliation_field": next((field for field in ("affiliation", "institutions", "author_affiliations") if field in columns), ""),
    }


def compute_topic_coherence(
    topic_terms: dict[int, list[str]], texts: list[str], config: dict[str, Any]
) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    """Compute c_v, c_npmi and u_mass with the same Unicode/ngram analyzer.

    Bigrams and trigrams remain literal tokens containing spaces.  The corpus
    analyzer produces the same literal tokens, so terms such as ``gestión
    escolar`` are never compared against an incompatible unigram-only corpus.
    """
    diagnostics: dict[int, dict[str, Any]] = {}
    nonempty = [str(text) for text in texts if str(text).strip()]
    if not nonempty:
        for topic_id, terms in topic_terms.items():
            diagnostics[topic_id] = _coherence_empty(topic_id, terms, "empty_corpus")
        return diagnostics, {"status": "empty_corpus", "documents": 0, "vocabulary": 0}
    try:
        vectorizer = build_vectorizer(config)
        vectorizer.fit(nonempty)
        vocabulary = set(vectorizer.get_feature_names_out())
        analyzer = vectorizer.build_analyzer()
        tokenized = [[token for token in analyzer(text) if token in vocabulary] for text in nonempty]
        tokenized = [tokens for tokens in tokenized if tokens]
    except (ImportError, ValueError) as exc:
        status = "empty_corpus" if isinstance(exc, ValueError) else "error"
        for topic_id, terms in topic_terms.items():
            diagnostics[topic_id] = _coherence_empty(topic_id, terms, status, type(exc).__name__)
        return diagnostics, {"status": status, "documents": 0, "vocabulary": 0, "error": type(exc).__name__}
    if not tokenized:
        for topic_id, terms in topic_terms.items():
            diagnostics[topic_id] = _coherence_empty(topic_id, terms, "empty_corpus")
        return diagnostics, {"status": "empty_corpus", "documents": 0, "vocabulary": len(vocabulary)}
    try:
        from gensim.corpora import Dictionary
        from gensim.models import CoherenceModel

        dictionary = Dictionary(tokenized)
        bow = [dictionary.doc2bow(tokens) for tokens in tokenized]
        computable: list[int] = []
        used_by_topic: dict[int, list[str]] = {}
        for topic_id, raw_terms in topic_terms.items():
            normalized = [str(term).casefold().strip() for term in raw_terms if str(term).strip()]
            used = [term for term in normalized if term in dictionary.token2id]
            missing = [term for term in normalized if term not in dictionary.token2id]
            if len(used) < 2:
                diagnostics[topic_id] = {
                    "topic_id": topic_id, "coherence_cv": "", "coherence_npmi": "", "coherence_umass": "",
                    "coherence_status": "insufficient_terms" if dictionary else "dictionary_mismatch",
                    "coherence_terms_used": " | ".join(used), "coherence_terms_missing": " | ".join(missing),
                    "coherence_terms_used_count": len(used), "coherence_terms_missing_count": len(missing),
                    "coherence_document_count": len(tokenized), "coherence_error": "",
                }
            else:
                computable.append(topic_id); used_by_topic[topic_id] = used
                diagnostics[topic_id] = {
                    "topic_id": topic_id, "coherence_terms_used": " | ".join(used),
                    "coherence_terms_missing": " | ".join(missing), "coherence_terms_used_count": len(used),
                    "coherence_terms_missing_count": len(missing), "coherence_document_count": len(tokenized),
                    "coherence_status": "computed", "coherence_error": "",
                }
        if computable:
            ordered_topics = [used_by_topic[topic_id] for topic_id in computable]
            measures: dict[str, list[float]] = {}
            for name in ("c_v", "c_npmi", "u_mass"):
                kwargs: dict[str, Any] = {"topics": ordered_topics, "dictionary": dictionary, "coherence": name}
                if name == "u_mass": kwargs["corpus"] = bow
                else:
                    kwargs["texts"] = tokenized; kwargs["processes"] = 1
                measures[name] = CoherenceModel(**kwargs).get_coherence_per_topic()
            for position, topic_id in enumerate(computable):
                diagnostics[topic_id].update({
                    "coherence_cv": _round(float(measures["c_v"][position])),
                    "coherence_npmi": _round(float(measures["c_npmi"][position])),
                    "coherence_umass": _round(float(measures["u_mass"][position])),
                })
        return diagnostics, {
            "status": "computed" if computable else "dictionary_mismatch",
            "documents": len(tokenized), "vocabulary": len(dictionary), "ngram_strategy": "literal_vectorizer_tokens",
        }
    except (ImportError, RuntimeError, ValueError, ZeroDivisionError) as exc:
        for topic_id, terms in topic_terms.items():
            diagnostics[topic_id] = _coherence_empty(topic_id, terms, "error", type(exc).__name__)
        return diagnostics, {"status": "error", "documents": len(tokenized), "vocabulary": len(vocabulary), "error": type(exc).__name__}


def _coherence_empty(topic_id: int, terms: list[str], status: str, error: str = "") -> dict[str, Any]:
    return {
        "topic_id": topic_id, "coherence_cv": "", "coherence_npmi": "", "coherence_umass": "",
        "coherence_status": status, "coherence_terms_used": "", "coherence_terms_missing": " | ".join(terms),
        "coherence_terms_used_count": 0, "coherence_terms_missing_count": len(terms),
        "coherence_document_count": 0, "coherence_error": error,
    }


def lexical_metrics(topic_words: list[dict[str, str]], top_n: int = 10) -> tuple[dict[int, dict[str, Any]], float]:
    terms: dict[int, list[str]] = defaultdict(list)
    weights: dict[int, list[float]] = defaultdict(list)
    for row in sorted(topic_words, key=lambda item: (int(item["topic_id"]), int(item.get("rank") or 999))):
        topic_id = int(row["topic_id"])
        if topic_id < 0 or len(terms[topic_id]) >= top_n:
            continue
        terms[topic_id].append(row["term"].casefold().strip())
        weights[topic_id].append(float(row.get("weight") or 0))
    occurrences = Counter(term for values in terms.values() for term in values)
    all_terms = [term for values in terms.values() for term in values]
    global_diversity = len(set(all_terms)) / len(all_terms) if all_terms else 0.0
    results: dict[int, dict[str, Any]] = {}
    for topic_id, values in terms.items():
        unique_share = sum(occurrences[term] == 1 for term in values) / len(values) if values else 0.0
        similarities = []
        for other_id, other in terms.items():
            if other_id == topic_id:
                continue
            union = set(values) | set(other)
            similarities.append((other_id, len(set(values) & set(other)) / len(union) if union else 0.0))
        similarities.sort(key=lambda item: item[1], reverse=True)
        raw_weights = [max(value, 0.0) for value in weights[topic_id]]
        total = sum(raw_weights)
        probabilities = [value / total for value in raw_weights if value > 0] if total else []
        entropy = -sum(value * math.log(value) for value in probabilities) if probabilities else None
        results[topic_id] = {
            "topic_unique_term_share": round(unique_share, 6),
            "topic_shared_term_share": round(1 - unique_share, 6),
            "mean_lexical_similarity_to_other_topics": round(sum(value for _, value in similarities) / len(similarities), 6) if similarities else 0.0,
            "maximum_lexical_similarity_to_other_topics": round(similarities[0][1], 6) if similarities else 0.0,
            "most_similar_topic": similarities[0][0] if similarities else "",
            "topic_term_entropy": _round(entropy),
        }
    return results, round(global_diversity, 6)


def metadata_metrics(topic_docs: list[dict[str, str]], fields: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    thresholds = config.get("evaluation", {}).get("metadata", {})
    minimum = int(thresholds.get("minimum_known_documents", 10))
    minimum_coverage = float(thresholds.get("minimum_coverage", 0.30))
    total = len(topic_docs)

    def one(field: str, prefix: str) -> dict[str, Any]:
        known = [doc.get(field, "").strip() for doc in topic_docs if field and doc.get(field, "").strip()]
        coverage = len(known) / total if total else 0.0
        counts = Counter(known)
        dominant, dominant_count = counts.most_common(1)[0] if counts else ("", 0)
        if not field:
            status = "missing_column"
        elif len(known) < minimum or coverage < minimum_coverage:
            status = "insufficient_metadata"
        elif len(counts) < 2:
            status = "insufficient_categories"
        else:
            status = "computed"
        entropy = _entropy(known) if status == "computed" else None
        return {
            f"documents_with_{prefix}": len(known), f"{prefix}_coverage": round(coverage, 6),
            f"{prefix}_metadata_coverage": round(coverage, 6),
            f"dominant_{prefix}": dominant, f"dominant_{prefix}_share_known": _round(dominant_count / len(known) if known else None),
            f"{prefix}_entropy": _round(entropy), f"{prefix}_status": status,
        }

    return {"documents_total": total, **one(fields.get("country_field", ""), "country"), **one(fields.get("source_field", ""), "source")}


def contamination_metrics(topic_docs: list[dict[str, str]]) -> tuple[dict[str, Any], set[str]]:
    total = len(topic_docs)
    statuses = [doc.get("relevance_status", "").strip() for doc in topic_docs]
    covered = [value for value in statuses if value]
    candidates: set[str] = set()
    reasons: dict[str, list[str]] = defaultdict(list)
    borderline_titles = []
    for doc in topic_docs:
        doc_id = doc.get("document_id", "")
        status = doc.get("relevance_status", "").strip()
        if status in {"borderline", "manual_review", "excluded", "excluded_candidate"}:
            candidates.add(doc_id); reasons[doc_id].append(f"relevance_status:{status}")
        if _truthy(doc.get("contamination_candidate", "")):
            candidates.add(doc_id); reasons[doc_id].append("contamination_candidate")
        text = f"{doc.get('title', '')} {doc.get('abstract', '')}".casefold()
        for name, pattern in CONTAMINATION_PATTERNS.items():
            if re.search(pattern, text, flags=re.IGNORECASE):
                candidates.add(doc_id); reasons[doc_id].append(name)
        if status in {"borderline", "manual_review"}:
            borderline_titles.append(doc.get("title", ""))
    included = sum(value == "included" for value in statuses) / total if total else 0.0
    borderline = sum(value == "borderline" for value in statuses) / total if total else 0.0
    excluded = sum(value in {"excluded", "excluded_candidate"} for value in statuses) / total if total else 0.0
    manual = sum(value == "manual_review" for value in statuses) / total if total else 0.0
    share = len(candidates) / total if total else 0.0
    coverage = len(covered) / total if total else 0.0
    if coverage < 0.30:
        status = "insufficient_evidence"
    elif excluded > 0.20 or share > 0.25:
        status = "out_of_domain_candidate"
    elif excluded > 0.05 or share > 0.10:
        status = "contaminated_candidate"
    elif share > 0.02 or borderline + manual > 0.10:
        status = "mixed_relevance_candidate"
    else:
        status = "pending_human_review"
    representative = []
    for doc in topic_docs:
        if doc.get("document_id", "") in candidates:
            representative.append(f"{doc.get('title','')} [{','.join(reasons[doc.get('document_id','')])}]")
    scores = [_float(doc.get("relevance_score")) for doc in topic_docs]
    scores = [value for value in scores if value is not None]
    return ({
        "included_document_share": round(included, 6), "borderline_relevance_share": round(borderline, 6),
        "excluded_candidate_share": round(excluded, 6), "manual_review_share": round(manual, 6),
        "domain_similarity_mean": "", "domain_similarity_min": "", "domain_similarity_status": "not_available_relevance_score_is_not_similarity",
        "relevance_score_mean": _round(sum(scores) / len(scores) if scores else None),
        "relevance_score_min": _round(min(scores) if scores else None),
        "contamination_candidate_count": len(candidates), "contamination_share": round(share, 6),
        "relevance_metadata_coverage": round(coverage, 6), "contamination_status": status,
        "representative_contamination_candidates": " | ".join(representative[:10]),
        "borderline_relevance_documents": " | ".join(borderline_titles[:10]),
    }, candidates)


def classify_heterogeneity(metrics: dict[str, Any], config: dict[str, Any]) -> tuple[str, str]:
    cfg = config.get("evaluation", {}).get("heterogeneity", {})
    neg = float(metrics.get("silhouette_negative_share") or 0)
    borderline = float(metrics.get("borderline_document_share") or 0)
    coherence = _float(metrics.get("coherence_cv"))
    contamination = float(metrics.get("contamination_share") or 0)
    language_share = float(metrics.get("dominant_language_share_known") or 0)
    source_excess = _float(metrics.get("source_concentration_excess"))
    source_status = metrics.get("source_status")
    if not metrics.get("silhouette_document_count") or metrics.get("coherence_status") != "computed":
        return "insufficient_evidence", "missing silhouette or coherence evidence"
    signals = []
    if neg > float(cfg.get("negative_silhouette_high", 0.20)): signals.append("negative_silhouette_high")
    if borderline > float(cfg.get("borderline_high", 0.30)): signals.append("borderline_high")
    if coherence is not None and coherence < float(cfg.get("coherence_low", 0.30)): signals.append("coherence_low")
    if contamination > float(cfg.get("contamination_high", 0.20)): signals.append("contamination_high")
    if "contamination_high" in signals:
        return "contaminated_candidate", " | ".join(signals)
    if "negative_silhouette_high" in signals or len(signals) >= 2:
        return "heterogeneous_candidate", " | ".join(signals)
    if borderline > float(cfg.get("borderline_candidate", 0.25)):
        return "borderline_heavy_candidate", "borderline share above configured threshold"
    if language_share > float(cfg.get("language_concentration", 0.85)):
        return "language_concentrated_candidate", "dominant language share above configured threshold"
    if source_status == "computed" and source_excess is not None and source_excess > float(cfg.get("source_concentration_excess", 0.15)):
        return "source_concentrated_candidate", "bibliographic provider concentration exceeds its corpus baseline"
    if neg > float(cfg.get("negative_silhouette_broad", 0.10)) or borderline > float(cfg.get("borderline_broad", 0.15)):
        return "broad_but_interpretable", "moderate dispersion; central interpretation remains plausible"
    return "coherent_candidate", "no configured warning threshold exceeded"


def rebuild_model_runs(config: dict[str, Any]) -> list[dict[str, Any]]:
    root = Path(config["paths"]["output_root"])
    candidates: list[dict[str, Any]] = []
    for family in ("stm", "bertopic"):
        for topics_path in (root / family).rglob("topics.csv"):
            model_dir = topics_path.parent
            if not (model_dir / "document_topics.csv").exists():
                continue
            topics = read_csv(topics_path)
            if not topics:
                continue
            metadata = {}
            metadata_path = model_dir / "model_metadata.json"
            if metadata_path.exists():
                try: metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError): metadata = {}
            first = topics[0]
            relative = model_dir.relative_to(root).as_posix()
            corpus = first.get("corpus") or metadata.get("corpus") or ("full_text" if relative == "stm" else "")
            language = first.get("language") or metadata.get("language") or ("multilingual" if family == "bertopic" else "all")
            generated = metadata.get("generated_at_utc", "")
            archived = "archive" in model_dir.parts or "pre_unicode_fix" in model_dir.parts or relative == "stm"
            if family == "stm" and model_dir.name.startswith("metadata_") and not model_dir.name.endswith("_corrected"):
                corrected = model_dir.with_name(model_dir.name + "_corrected")
                archived = archived or (corrected / "topics.csv").exists()
            configuration = metadata.get("configuration", {})
            corpus_file = root / "corpus" / f"modeling_corpus_{corpus}.csv"
            status = metadata.get("selection_status") or metadata.get("model_status") or first.get("selection_status") or "historical_provisional"
            validation_status = "pending_human_review"
            if "stability_nonconverged" in status: validation_status = "stability_nonconverged"
            if "exploratory_small_corpus" in status: validation_status = "exploratory_small_corpus_stability_nonconverged"
            candidates.append({
                "model_family": "BERTopic" if family == "bertopic" else "STM",
                "model_name": first.get("model") or metadata.get("model") or model_dir.name,
                "model_path": relative, "corpus_unit": corpus, "language": language,
                "generated_at": generated, "git_commit": metadata.get("git_commit", ""),
                "configuration_hash": _json_hash(configuration) if configuration else "",
                "corpus_hash": sha256_file(corpus_file), "status": status, "is_archived": archived,
                "validation_status": validation_status,
            })
    by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        by_key[(row["model_family"], row["corpus_unit"], row["language"])].append(row)
    for group in by_key.values():
        non_archived = [row for row in group if not row["is_archived"]]
        latest_pool = non_archived or group
        latest = max(latest_pool, key=lambda row: row.get("generated_at", ""))
        for row in group:
            row["is_latest_for_model"] = row is latest
            row["is_preferred_model"] = row["model_path"] == PREFERRED_RELATIVE.as_posix()
            row["is_dashboard_active"] = bool(row["is_preferred_model"] or (
                row["model_family"] == "STM" and row["is_latest_for_model"] and not row["is_archived"] and row["corpus_unit"] == "metadata"
            ))
            row["notes"] = (
                "Modelo principal vigente; solución preferred_provisional de 14 macrotemas."
                if row["is_preferred_model"] else
                "Ejecución histórica excluida de las tablas principales." if row["is_archived"] else
                "Modelo comparativo vigente."
            )
            row["run_id"] = hashlib.sha256(
                f"{row['model_path']}|{row['generated_at']}|{row['configuration_hash']}|{row['corpus_hash']}".encode("utf-8")
            ).hexdigest()[:16]
    candidates.sort(key=lambda row: (not row["is_preferred_model"], row["model_family"], row["language"], row["generated_at"]), reverse=False)
    fields = [
        "run_id", "model_family", "model_name", "model_path", "corpus_unit", "language", "generated_at",
        "git_commit", "configuration_hash", "corpus_hash", "status", "is_latest_for_model", "is_preferred_model",
        "is_dashboard_active", "is_archived", "validation_status", "notes",
    ]
    write_csv(root / "evaluation/model_runs.csv", candidates, fields)
    return candidates


def _current_run_dirs(root: Path, runs: list[dict[str, Any]]) -> list[tuple[dict[str, Any], Path]]:
    return [
        (row, root / row["model_path"]) for row in runs
        if row["is_latest_for_model"] and not row["is_archived"]
    ]


def recompute_evaluation(config: dict[str, Any], recompute_model: bool = False) -> dict[str, Any]:
    if recompute_model:
        raise ValueError("This command is evaluation_only; BERTopic re-estimation is intentionally disabled.")
    root = Path(config["paths"]["output_root"])
    evaluation = root / "evaluation"; evaluation.mkdir(parents=True, exist_ok=True)
    preferred = root / PREFERRED_RELATIVE
    frozen_before = {name: sha256_file(preferred / name) for name in (
        "document_topics.csv", "topics.csv", "topic_words.csv", "document_topic_hierarchy.csv", "subtopics.csv", "outliers.csv"
    )}
    runs = rebuild_model_runs(config)
    current = _current_run_dirs(root, runs)
    preferred_run = next(row for row in runs if row["is_preferred_model"])
    topics = [row for row in read_csv(preferred / "topics.csv") if int(row["topic_id"]) >= 0]
    docs = read_csv(preferred / "document_topics.csv")
    corpus_rows = read_csv(root / "corpus/modeling_corpus_metadata.csv")
    corpus_by_id = {row["document_id"]: row for row in corpus_rows}
    if len(corpus_by_id) != len(corpus_rows) or {row["document_id"] for row in docs} != set(corpus_by_id):
        raise ValueError("Preferred BERTopic documents do not join one-to-one with the metadata corpus.")
    joined = [{**corpus_by_id[row["document_id"]], **row} for row in docs]
    topic_words = read_csv(preferred / "topic_words.csv")
    terms_by_topic: dict[int, list[str]] = defaultdict(list)
    for row in sorted(topic_words, key=lambda item: (int(item["topic_id"]), int(item.get("rank") or 999))):
        tid = int(row["topic_id"])
        if tid >= 0 and len(terms_by_topic[tid]) < int(config["validation"].get("top_n_words", 15)):
            terms_by_topic[tid].append(row["term"])
    coherence, coherence_global = compute_topic_coherence(
        dict(terms_by_topic), [row.get("text_for_vectorizer") or row.get("text_for_modeling", "") for row in corpus_rows], config
    )
    lexical, global_diversity = lexical_metrics(topic_words, 10)
    fields = discover_metadata_fields(corpus_rows)
    global_source_values = [row.get(fields.get("source_field", ""), "").strip() for row in corpus_rows if fields.get("source_field") and row.get(fields.get("source_field", ""), "").strip()]
    global_source_counts = Counter(global_source_values)
    by_topic: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in joined:
        if int(row["topic_id"]) >= 0: by_topic[int(row["topic_id"])].append(row)
    old_language = {int(row["topic_id"]): row for row in read_csv(preferred / "language_dependence.csv")}
    metadata_rows=[]; coherence_rows=[]; heterogeneity=[]; language_rows=[]; priority_rows=[]; preferred_topic_metrics=[]
    contamination_by_topic: dict[int, set[str]] = {}
    topic_by_id = {int(row["topic_id"]): row for row in topics}
    for topic_id in range(14):
        topic_docs = by_topic[topic_id]
        meta = metadata_metrics(topic_docs, fields, config)
        if meta.get("dominant_source") and global_source_values:
            global_share = global_source_counts[meta["dominant_source"]] / len(global_source_values)
            topic_share = _float(meta.get("dominant_source_share_known"), 0.0) or 0.0
            meta["dominant_source_global_share"] = round(global_share, 6)
            meta["source_concentration_excess"] = round(topic_share - global_share, 6)
        else:
            meta["dominant_source_global_share"] = ""; meta["source_concentration_excess"] = ""
        contam, candidate_ids = contamination_metrics(topic_docs); contamination_by_topic[topic_id] = candidate_ids
        coh = coherence[topic_id]; lex = lexical[topic_id]
        sil = [float(row["silhouette"]) for row in topic_docs if row.get("silhouette", "") != ""]
        distances = [float(row["distance_to_centroid"]) for row in topic_docs if row.get("distance_to_centroid", "") != ""]
        ambiguous = sum(_truthy(row.get("is_ambiguous")) for row in topic_docs) / len(topic_docs)
        low = sum(float(row.get("hdbscan_membership_strength") or 0) < 0.35 for row in topic_docs) / len(topic_docs)
        languages = [row.get("language", "").strip() for row in topic_docs if row.get("language", "").strip()]
        language_counts = Counter(languages); dominant_language, dom_language_count = language_counts.most_common(1)[0]
        lang_entropy = _entropy(languages)
        hetero = {
            "model": topic_by_id[topic_id]["model"], "corpus": "metadata", "topic_id": topic_id,
            "documents": len(topic_docs), "silhouette_document_count": len(sil),
            "silhouette_mean": _round(sum(sil)/len(sil) if sil else None), "silhouette_median": _round(_percentile(sil, .5)),
            "silhouette_min": _round(min(sil) if sil else None),
            "silhouette_negative_share": _round(sum(value < 0 for value in sil)/len(sil) if sil else None),
            "silhouette_below_0_1_share": _round(sum(value < .1 for value in sil)/len(sil) if sil else None),
            "contains_negative_silhouette_documents": bool(any(value < 0 for value in sil)),
            "negative_silhouette_document_count": sum(value < 0 for value in sil),
            "distance_to_centroid_mean": _round(sum(distances)/len(distances) if distances else None),
            "distance_to_centroid_p90": _round(_percentile(distances, .9)),
            "borderline_document_share": round(ambiguous, 6), "low_confidence_document_share": round(low, 6),
            "coherence_cv": coh["coherence_cv"], "coherence_npmi": coh["coherence_npmi"], "coherence_umass": coh["coherence_umass"],
            "coherence_status": coh["coherence_status"], **lex,
            "language_entropy": _round(lang_entropy), "dominant_language": dominant_language,
            "dominant_language_share_known": round(dom_language_count/len(languages), 6),
            **meta, **contam, "review_status": "pending_human_review",
        }
        status, reasons = classify_heterogeneity(hetero, config); hetero["status"] = status; hetero["status_reasons"] = reasons
        heterogeneity.append(hetero)
        metadata_rows.append({"model": hetero["model"], "topic_id": topic_id, **meta, **fields})
        coherence_rows.append({"model": hetero["model"], **coh, "ngram_strategy": "literal_vectorizer_tokens"})
        old = old_language.get(topic_id, {})
        lang_status = "multilingual_candidate" if len(language_counts) > 1 and dom_language_count/len(languages) < .80 else "language_concentrated_candidate"
        language_rows.append({
            "model": hetero["model"], "corpus": "metadata", "topic_id": topic_id,
            "topic_language_distribution": json.dumps(language_counts, ensure_ascii=False, sort_keys=True),
            "dominant_language": dominant_language, "dominant_language_share_known": round(dom_language_count/len(languages), 6),
            "language_coverage": round(len(languages)/len(topic_docs), 6), "language_entropy": _round(lang_entropy),
            "language_mutual_information": old.get("language_mutual_information", ""),
            "cross_language_nearest_neighbors": old.get("cross_language_nearest_neighbors", ""),
            "cross_language_centroid_similarity": old.get("cross_language_centroid_similarity", ""),
            **{key: meta[key] for key in meta if "country" in key or "source" in key},
            "classification": lang_status, "review_status": "pending_human_review",
        })
        coherence_penalty = 1 - max(0.0, min(1.0, float(coh["coherence_cv"] or 0))) if coh["coherence_status"] == "computed" else 1.0
        metadata_coverage = (float(meta["country_coverage"]) + float(meta["source_coverage"]))/2
        score = 100 * (
            .30*ambiguous + .25*float(hetero["silhouette_negative_share"] or 0) + .15*low +
            .15*coherence_penalty + .10*float(contam["contamination_share"]) + .05*(1-metadata_coverage)
        )
        reasons_list=[]
        if ambiguous>.25: reasons_list.append("alta proporción fronteriza")
        if float(hetero["silhouette_negative_share"] or 0)>.10: reasons_list.append("siluetas negativas")
        if coh["coherence_status"]!="computed": reasons_list.append("coherencia no disponible")
        if float(contam["contamination_share"])>.02: reasons_list.append("candidatos de contaminación")
        if meta["country_status"]!="computed": reasons_list.append("país sin cobertura suficiente")
        if status not in {"coherent_candidate"}: reasons_list.append(status)
        priority_rows.append({
            "topic_id": topic_id, "review_priority_score": round(score, 3), "borderline_share": round(ambiguous,6),
            "low_confidence_share": round(low,6), "negative_silhouette_share": hetero["silhouette_negative_share"],
            "coherence_cv": coh["coherence_cv"], "contamination_share": contam["contamination_share"],
            "language_concentration": round(dom_language_count/len(languages),6), "metadata_coverage": round(metadata_coverage,6),
            "priority_reason": " | ".join(reasons_list) or "sin alerta principal",
        })
        preferred_topic_metrics.append({
            "model": hetero["model"], "model_path": PREFERRED_RELATIVE.as_posix(), "corpus": "metadata",
            "language": "multilingual", "topic_id": topic_id, **{k: coh[k] for k in ("coherence_cv","coherence_npmi","coherence_umass","coherence_status","coherence_terms_used_count","coherence_terms_missing_count","coherence_document_count")},
            **lex, "document_count": len(topic_docs), "prevalence_or_cluster_share": topic_by_id[topic_id].get("prevalence", ""),
            "contamination_candidate_count": contam["contamination_candidate_count"], "contamination_share": contam["contamination_share"],
            "human_validation_status": "pending_human_review", "run_id": preferred_run["run_id"],
            "is_latest_for_model": True, "is_preferred_model": True, "status": preferred_run["status"],
        })
    priority_rows.sort(key=lambda row: float(row["review_priority_score"]), reverse=True)
    for rank, row in enumerate(priority_rows, 1): row["priority_rank"] = rank
    write_csv(evaluation/"heterogeneity.csv", heterogeneity)
    write_csv(evaluation/"language_dependence.csv", language_rows)
    write_csv(evaluation/"metadata_coverage.csv", metadata_rows)
    write_csv(evaluation/"coherence_diagnostics.csv", coherence_rows)
    write_csv(evaluation/"topic_review_priority.csv", priority_rows)

    model_metrics=[]; topic_metrics=list(preferred_topic_metrics); document_metrics=[]; stability=[]
    for run, model_dir in current:
        run_topics=read_csv(model_dir/"topics.csv"); run_docs=read_csv(model_dir/"document_topics.csv")
        counts=Counter(row["topic_id"] for row in run_docs); sizes=[value for key,value in counts.items() if key!="-1"]
        base={"model":run["model_name"],"model_path":run["model_path"],"corpus":run["corpus_unit"],"run_id":run["run_id"],"is_latest_for_model":True,"is_preferred_model":run["is_preferred_model"],"status":run["status"]}
        metrics=[("documents",len(run_docs),"all"),("topics_excluding_outliers",len(sizes),"all"),("minimum_topic_size",min(sizes) if sizes else 0,"dominant assignment or cluster")]
        if run["is_preferred_model"]:
            metrics.extend([("model_topic_diversity_top10",global_diversity,"lexical representation"),("outlier_percentage",round(100*counts.get("-1",0)/len(run_docs),4),"BERTopic")])
        for metric,value,applicability in metrics: model_metrics.append({**base,"metric":metric,"value":value,"applicability":applicability})
        if not run["is_preferred_model"]:
            for topic in run_topics:
                if topic.get("topic_id")=="-1": continue
                topic_metrics.append({**base,"language":run["language"],"topic_id":topic["topic_id"],"coherence_cv":topic.get("coherence",""),"coherence_npmi":"","coherence_umass":"","coherence_status":"not_recomputed_comparative_model","topic_unique_term_share":"","topic_shared_term_share":"","mean_lexical_similarity_to_other_topics":"","maximum_lexical_similarity_to_other_topics":"","most_similar_topic":"","topic_term_entropy":"","document_count":topic.get("document_count",""),"prevalence_or_cluster_share":topic.get("prevalence",""),"contamination_candidate_count":"","contamination_share":"","human_validation_status":topic.get("label_status","pending_human_review")})
        for doc in run_docs:
            candidate = doc.get("document_id","") in contamination_by_topic.get(int(doc.get("topic_id") or -1),set()) if run["is_preferred_model"] else ""
            document_metrics.append({**base,"document_id":doc["document_id"],"publication_document_id":doc.get("publication_document_id",doc["document_id"]),"topic_id":doc["topic_id"],"assignment_confidence":doc.get("topic_probability",""),"probability_margin":doc.get("probability_margin",""),"silhouette":doc.get("silhouette",""),"distance_to_centroid":doc.get("distance_to_centroid",""),"local_consistency":doc.get("local_consistency",""),"ambiguous":doc.get("is_ambiguous",""),"is_outlier":doc.get("is_outlier",""),"language":doc.get("language",run["language"]),"relevance_status":corpus_by_id.get(doc["document_id"],{}).get("relevance_status","") if run["corpus_unit"]=="metadata" else "","relevance_score":corpus_by_id.get(doc["document_id"],{}).get("relevance_score","") if run["corpus_unit"]=="metadata" else "","contamination_candidate":candidate})
        diag_path=model_dir/"k_diagnostics.csv"
        if diag_path.exists():
            for row in read_csv(diag_path): stability.append({**base,"candidate":row.get("K",""),"stability_ari":row.get("stability",""),"stability_nmi":"","convergence_rate":row.get("convergence_rate",""),"selection_status":row.get("selection_status",run["status"]),"validation_status":run["validation_status"]})
        elif run["is_preferred_model"]:
            for row in read_csv(model_dir/"stability.csv"):
                stability.append({**base,"candidate":row.get("solution_id",""),"stability_ari":row.get("stability_ari_mean",""),"stability_nmi":row.get("stability_nmi_mean",""),"convergence_rate":"","selection_status":row.get("solution_status",""),"validation_status":"pending_human_review"})
    # Enforce the requested uniqueness grain.
    seen=set()
    for row in model_metrics:
        key=(row["run_id"],row["model"],row["metric"])
        if key in seen: raise ValueError(f"Duplicate model metric: {key}")
        seen.add(key)
    write_csv(evaluation/"model_metrics.csv",model_metrics)
    write_csv(evaluation/"topic_metrics.csv",topic_metrics)
    write_csv(evaluation/"document_metrics.csv",document_metrics)
    write_csv(evaluation/"stability.csv",stability)
    frozen_after={name:sha256_file(preferred/name) for name in frozen_before}
    if frozen_before!=frozen_after: raise RuntimeError("Evaluation-only run changed frozen BERTopic artifacts.")
    audit=build_evaluation_audit(config, corrections_applied=True, extra={"frozen_hashes_before":frozen_before,"frozen_hashes_after":frozen_after,"coherence_global":coherence_global,"metadata_fields":fields,"join_coverage":len(joined)/len(docs)})
    (evaluation/"evaluation_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
    write_metric_definitions(evaluation/"metric_definitions.md")
    return {"status":"evaluation_only_complete","preferred_topics":14,"documents":len(docs),"frozen":frozen_before==frozen_after,"priority_top5":[row["topic_id"] for row in priority_rows[:5]]}


def build_evaluation_audit(config: dict[str, Any], corrections_applied: bool = False, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    root=Path(config["paths"]["output_root"]); evaluation=root/"evaluation"
    responsibilities=[
        ("coherence_cv/coherence_npmi/coherence_umass","topic_modeling.evaluation_metrics.compute_topic_coherence",["text_for_vectorizer","topic_words.term"],["coherence_diagnostics.csv","topic_metrics.csv","heterogeneity.csv"]),
        ("lexical_diversity_and_exclusivity","topic_modeling.evaluation_metrics.lexical_metrics",["topic_words.term","topic_words.weight"],["model_metrics.csv","topic_metrics.csv","heterogeneity.csv"]),
        ("country_and_source_coverage","topic_modeling.evaluation_metrics.metadata_metrics",["document_id","source","country candidates"],["metadata_coverage.csv","language_dependence.csv","heterogeneity.csv"]),
        ("contamination","topic_modeling.evaluation_metrics.contamination_metrics",["relevance_status","relevance_score","title","abstract"],["document_metrics.csv","topic_metrics.csv","heterogeneity.csv"]),
        ("heterogeneity_status","topic_modeling.evaluation_metrics.classify_heterogeneity",["silhouette","distance_to_centroid","is_ambiguous","coherence","metadata coverage"],["heterogeneity.csv","topic_review_priority.csv"]),
        ("model_run_selection","topic_modeling.evaluation_metrics.rebuild_model_runs",["model_metadata.json","topics.csv","corpus files"],["model_runs.csv"]),
    ]
    files={}
    for path in evaluation.glob("*.csv"):
        rows=read_csv(path); columns=list(rows[0]) if rows else []
        missing={column:sum(str(row.get(column,"")) in {"","NA","NaN","nan","None"} for row in rows) for column in columns}
        constant={column:len({str(row.get(column,"")) for row in rows})<=1 for column in columns}
        files[path.name]={"rows":len(rows),"columns":columns,"missing_values":missing,"constant_columns":[key for key,value in constant.items() if value]}
    corrections = [
        "Coherence now uses the production Unicode CountVectorizer analyzer with literal 1–3 grams and explicit status fields.",
        "Global top-10 diversity is model-level; per-topic exclusivity, sharing, lexical similarity and entropy are separate.",
        "Missing country values remain missing; entropy is gated by coverage, known count and category count.",
        "Source is documented as bibliographic provider/repository and concentration is compared with the corpus baseline.",
        "Contamination aggregates document evidence and never maps a zero share to automatic domain validity.",
        "Heterogeneity includes negative silhouettes, borderline and low-confidence shares plus lexical and metadata evidence.",
        "Run lineage separates latest, preferred, dashboard-active and archived states; archived runs are excluded from main metrics.",
    ] if corrections_applied else []
    return {"generated_at":datetime.now(timezone.utc).isoformat(),"mode":"evaluation_only","corrections_applied":corrections_applied,"correction_details":corrections,"responsibilities":[{"metric":a,"function":b,"input_columns":c,"output_files":d} for a,b,c,d in responsibilities],"files":files,"warnings":["No structured country field exists in modeling_corpus_metadata.csv.","source identifies bibliographic provider/repository, not journal or country.","relevance_score is a rule score and is not exported as domain similarity.","All topic states remain candidates pending human review."],**(extra or {})}


def write_metric_definitions(path: Path) -> None:
    path.write_text("""# Definiciones de métricas de evaluación

Todas las métricas describen la solución provisional; ninguna valida sustantivamente un tópico.

| Métrica | Nivel | Definición y fórmula | Rango e interpretación | Faltantes, aplicabilidad y limitaciones | Código responsable |
|---|---|---|---|---|---|
| `coherence_cv` | tópico | Coherencia c_v de las 15 palabras c-TF-IDF, usando tokens Unicode y n-gramas literales del mismo `CountVectorizer`. | Habitualmente 0–1; mayor indica mayor coaparición contextual. | NA si hay menos de dos términos compatibles, corpus vacío, desajuste o error. No prueba validez sustantiva. | `compute_topic_coherence` |
| `coherence_npmi` | tópico | NPMI medio de coaparición de los términos del tópico. | -1 a 1; mayor es mejor. | Mismo tratamiento de NA que c_v; sensible a términos raros. | `compute_topic_coherence` |
| `coherence_umass` | tópico | Log-probabilidad condicional basada en bolsa de palabras del corpus. | ≤0 normalmente; valores menos negativos son mejores. | Sólo comparable con igual corpus y preprocesamiento. | `compute_topic_coherence` |
| `model_topic_diversity_top10` | modelo | Términos únicos entre los top 10 de todos los tópicos / total de términos top 10. | 0–1; mayor implica menor repetición global. | Se publica únicamente a nivel modelo. | `lexical_metrics` |
| `topic_unique_term_share` | tópico | Proporción de top 10 que no aparece en los top 10 de ningún otro tópico. | 0–1; mayor implica más exclusividad léxica. | No equivale a coherencia ni pureza semántica. | `lexical_metrics` |
| `topic_shared_term_share` | tópico | 1 menos `topic_unique_term_share`. | 0–1; mayor implica más términos compartidos. | Complementaria, no métrica global. | `lexical_metrics` |
| `silhouette_mean` | tópico | Media de siluetas de documentos asignados. | -1 a 1; mayor separación relativa. | Sólo documentos agrupados con valor calculado. | `recompute_evaluation` |
| `silhouette_negative_share` | tópico | Documentos con silueta <0 / documentos con silueta. | 0–1; alto indica asignaciones más cercanas a otro cluster. | No reasigna documentos. | `recompute_evaluation` |
| `borderline_document_share` | tópico | Documentos marcados `is_ambiguous` / documentos del tópico. | 0–1; alto prioriza revisión. | Depende de umbrales configurados de margen, pertenencia y consistencia local. | `recompute_evaluation` |
| `low_confidence_document_share` | tópico | Documentos con fuerza HDBSCAN <0,35 / documentos del tópico. | 0–1. | No es probabilidad posterior. | `recompute_evaluation` |
| `country_entropy` | tópico | Entropía de categorías de país conocidas. | ≥0; mayor implica mayor diversidad. | NA si cobertura <30%, menos de 10 conocidos, menos de dos categorías o columna ausente. | `metadata_metrics` |
| `source_entropy` | tópico | Entropía del proveedor/repositorio bibliográfico conocido. | ≥0; mayor implica mayor diversidad de procedencia. | No es revista. NA con cobertura/categorías insuficientes. | `metadata_metrics` |
| `contamination_share` | tópico | Documentos candidatos por estado de relevancia o señales léxicas de alta precisión / total. | 0–1; es señal de revisión, no tasa validada. | Nunca implica relevancia automática cuando vale cero. | `contamination_metrics` |
| `stability_ari` | modelo/candidato | ARI medio entre réplicas o estabilidad STM registrada. | -1 a 1; mayor es más estable. | NA en réplicas no convergentes. | exportación de estabilidad + `recompute_evaluation` |
| `stability_nmi` | modelo/candidato | NMI medio entre réplicas BERTopic. | 0–1; mayor es más estable. | No disponible para STM en la ejecución actual. | exportación de estabilidad + `recompute_evaluation` |
""",encoding="utf-8")
