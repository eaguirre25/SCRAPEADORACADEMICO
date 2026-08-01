from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .corpus_builder import read_csv, write_csv


def _truth(value: str) -> bool:
    return str(value).casefold() in {"1", "true", "yes", "si", "sí"}


def _terms(value: str) -> set[str]:
    return {item.strip().casefold() for item in value.split("|") if item.strip()}


def align_topics(
    stm_docs: list[dict[str, str]], bert_docs: list[dict[str, str]],
    stm_topics: list[dict[str, str]], bert_topics: list[dict[str, str]],
    *, language: str = "",
) -> list[dict[str, Any]]:
    stm_by_doc = {row.get("publication_document_id") or row["document_id"]: row for row in stm_docs}
    bert_by_doc = {row.get("publication_document_id") or row["document_id"]: row for row in bert_docs}
    shared = stm_by_doc.keys() & bert_by_doc.keys()
    stm_sets: dict[str, set[str]] = defaultdict(set); bert_sets: dict[str, set[str]] = defaultdict(set)
    for doc_id in shared:
        stm_sets[stm_by_doc[doc_id]["topic_id"]].add(doc_id); bert_sets[bert_by_doc[doc_id]["topic_id"]].add(doc_id)
    stm_words = {row["topic_id"]: _terms(row.get("top_words", "")) for row in stm_topics}
    bert_words = {row["topic_id"]: _terms(row.get("top_words", "")) for row in bert_topics}
    stm_reps = {row["topic_id"]: _terms(row.get("representative_titles", "")) for row in stm_topics}
    bert_reps = {row["topic_id"]: _terms(row.get("representative_titles", "")) for row in bert_topics}
    rows: list[dict[str, Any]] = []
    for stm_id, left in stm_sets.items():
        for bert_id, right in bert_sets.items():
            overlap = left & right; union = left | right
            document_jaccard = len(overlap) / len(union) if union else 0.0
            word_union = stm_words.get(stm_id, set()) | bert_words.get(bert_id, set())
            keyword = len(stm_words.get(stm_id, set()) & bert_words.get(bert_id, set())) / len(word_union) if word_union else 0.0
            rep_union = stm_reps.get(stm_id, set()) | bert_reps.get(bert_id, set())
            rep_similarity = len(stm_reps.get(stm_id, set()) & bert_reps.get(bert_id, set())) / len(rep_union) if rep_union else 0.0
            weighted_overlap = sum(
                min(float(stm_by_doc[doc].get("topic_probability") or 0), float(bert_by_doc[doc].get("topic_probability") or 0))
                for doc in overlap
            ) / max(len(union), 1)
            combined = 0.40 * document_jaccard + 0.25 * weighted_overlap + 0.25 * keyword + 0.10 * rep_similarity
            rows.append({
                "stm_model": stm_topics[0].get("model", "STM") if stm_topics else "STM",
                "bertopic_model": bert_topics[0].get("model", "BERTopic") if bert_topics else "BERTopic",
                "corpus": "metadata", "language": language, "stm_topic": stm_id, "bertopic_topic": bert_id,
                "document_overlap": len(overlap), "document_jaccard": round(document_jaccard, 6),
                "jaccard_overlap": round(document_jaccard, 6),
                "weighted_theta_overlap": round(weighted_overlap, 6), "centroid_similarity": "not_computed",
                "keyword_similarity": round(keyword, 6), "representative_document_similarity": round(rep_similarity, 6),
                "combined_alignment": round(combined, 6), "relationship": "no_match",
                "alignment_status": "no_match",
                "comparability_status": "comparable_same_publications_unit_period_filter_language",
                "human_review_status": "pending",
            })
    best_stm = {topic: max((row["combined_alignment"] for row in rows if row["stm_topic"] == topic), default=0) for topic in stm_sets}
    best_bert = {topic: max((row["combined_alignment"] for row in rows if row["bertopic_topic"] == topic), default=0) for topic in bert_sets}
    for row in rows:
        score = row["combined_alignment"]
        reciprocal = score > 0 and score == best_stm[row["stm_topic"]] == best_bert[row["bertopic_topic"]]
        if reciprocal and score >= 0.15: row["relationship"] = "one_to_one"
        elif score == best_stm[row["stm_topic"]] and score >= 0.08: row["relationship"] = "STM_split_by_BERTopic"
        elif score == best_bert[row["bertopic_topic"]] and score >= 0.08: row["relationship"] = "BERTopic_combines_STM"
        elif score >= 0.05: row["relationship"] = "partial_overlap"
        elif language and score >= 0.02: row["relationship"] = "language_specific_match"
        elif score > 0: row["relationship"] = "weak_match"
        row["alignment_status"] = row["relationship"]
    return rows


def compare_models(config: dict[str, Any]) -> dict[str, int]:
    root = Path(config["paths"]["output_root"])
    bert_base = root / "bertopic" / "metadata_multilingual"
    bert_path = bert_base / "preferred_solution" if (bert_base / "preferred_solution" / "document_topics.csv").exists() else bert_base
    if not (bert_path / "document_topics.csv").exists():
        raise FileNotFoundError("BERTopic metadata multilingual output is required")
    bert_docs = read_csv(bert_path / "document_topics.csv"); bert_topics = read_csv(bert_path / "topics.csv")
    all_alignment: list[dict[str, Any]] = []; document_alignment: list[dict[str, Any]] = []
    for language in config.get("multilingual", {}).get("stm_languages", ["es", "en", "pt"]):
        corrected = root / "stm" / f"metadata_{language}_corrected"
        stm_path = corrected if (corrected / "document_topics.csv").exists() else root / "stm" / f"metadata_{language}"
        if not (stm_path / "document_topics.csv").exists():
            continue
        stm_docs = read_csv(stm_path / "document_topics.csv"); stm_topics = read_csv(stm_path / "topics.csv")
        bert_language_docs = [row for row in bert_docs if row.get("language") == language]
        alignment = align_topics(stm_docs, bert_language_docs, stm_topics, bert_topics, language=language)
        all_alignment.extend(alignment)
        relation = {(row["stm_topic"], row["bertopic_topic"]): row for row in alignment}
        stm_by = {row.get("publication_document_id") or row["document_id"]: row for row in stm_docs}
        bert_by = {row.get("publication_document_id") or row["document_id"]: row for row in bert_language_docs}
        for document_id in sorted(stm_by.keys() & bert_by.keys()):
            stm, bert = stm_by[document_id], bert_by[document_id]
            aligned = relation.get((stm["topic_id"], bert["topic_id"]), {})
            document_alignment.append({
                "publication_document_id": document_id, "title": stm.get("title") or bert.get("title"),
                "year": stm.get("year") or bert.get("year"), "language": language, "corpus": "metadata",
                "stm_model": stm.get("model", ""), "stm_topic": stm["topic_id"],
                "stm_probability": stm.get("topic_probability", ""), "bertopic_model": bert.get("model", ""),
                "bertopic_topic": bert["topic_id"], "bertopic_probability": bert.get("topic_probability", ""),
                "bertopic_outlier": bert.get("is_outlier", ""), "relationship": aligned.get("relationship", "no_match"),
                "combined_alignment": aligned.get("combined_alignment", 0),
                "ambiguous": _truth(stm.get("is_ambiguous", "")) or _truth(bert.get("is_ambiguous", "")),
                "human_review_status": "pending",
            })
    out = root / "comparison"
    write_csv(out / "stm_bertopic_alignment.csv", all_alignment)
    write_csv(out / "topic_relationships.csv", all_alignment)
    write_csv(out / "document_alignment.csv", document_alignment)
    # Compatibility aliases for the existing dashboard while it migrates.
    write_csv(out / "topic_alignment.csv", all_alignment)
    write_csv(out / "document_model_comparison.csv", document_alignment)
    summary = [
        {"metric": "shared_documents", "value": len(document_alignment)},
        {"metric": "stm_language_models_compared", "value": len({row["stm_model"] for row in all_alignment})},
        {"metric": "bertopic_documents", "value": len(bert_docs)},
        {"metric": "bertopic_outliers", "value": sum(_truth(row.get("is_outlier", "")) for row in bert_docs)},
        {"metric": "one_to_one_alignments", "value": sum(row["relationship"] == "one_to_one" for row in all_alignment)},
        {"metric": "comparison_status", "value": "exploratory_pending_human_review"},
    ]
    write_csv(out / "model_summary.csv", summary)
    return {row["metric"]: int(row["value"]) for row in summary if str(row["value"]).isdigit()}
