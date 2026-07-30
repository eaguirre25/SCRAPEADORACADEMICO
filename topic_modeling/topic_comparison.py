from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .corpus_builder import read_csv, write_csv


def _truth(value: str) -> bool:
    return str(value).casefold() in {"1", "true", "yes", "si", "sí"}


def _terms(value: str) -> set[str]:
    return {item.strip().casefold() for item in value.split("|") if item.strip()}


def align_topics(stm_docs: list[dict[str, str]], bert_docs: list[dict[str, str]], stm_topics: list[dict[str, str]], bert_topics: list[dict[str, str]]) -> list[dict[str, Any]]:
    stm_by_doc = {row["document_id"]: row for row in stm_docs}
    bert_by_doc = {row["document_id"]: row for row in bert_docs}
    stm_sets: dict[str, set[str]] = defaultdict(set)
    bert_sets: dict[str, set[str]] = defaultdict(set)
    for doc_id in stm_by_doc.keys() & bert_by_doc.keys():
        stm_sets[stm_by_doc[doc_id]["topic_id"]].add(doc_id)
        bert_sets[bert_by_doc[doc_id]["topic_id"]].add(doc_id)
    stm_words = {row["topic_id"]: _terms(row.get("top_words", "")) for row in stm_topics}
    bert_words = {row["topic_id"]: _terms(row.get("top_words", "")) for row in bert_topics}
    rows: list[dict[str, Any]] = []
    for stm_id, left in stm_sets.items():
        for bert_id, right in bert_sets.items():
            overlap = len(left & right)
            union = len(left | right)
            jaccard = overlap / union if union else 0.0
            word_union = stm_words.get(stm_id, set()) | bert_words.get(bert_id, set())
            keyword = len(stm_words.get(stm_id, set()) & bert_words.get(bert_id, set())) / len(word_union) if word_union else 0.0
            combined = 0.7 * jaccard + 0.3 * keyword
            rows.append({
                "stm_topic": stm_id, "bertopic_topic": bert_id, "document_overlap": overlap,
                "jaccard_overlap": round(jaccard, 6), "centroid_similarity": "",
                "keyword_similarity": round(keyword, 6), "combined_similarity": round(combined, 6),
                "alignment_status": "no_match",
            })
    best_stm: dict[str, float] = defaultdict(float)
    best_bert: dict[str, float] = defaultdict(float)
    for row in rows:
        score = float(row["combined_similarity"])
        best_stm[row["stm_topic"]] = max(best_stm[row["stm_topic"]], score)
        best_bert[row["bertopic_topic"]] = max(best_bert[row["bertopic_topic"]], score)
    for row in rows:
        score = float(row["combined_similarity"])
        reciprocal = score > 0 and score == best_stm[row["stm_topic"]] == best_bert[row["bertopic_topic"]]
        if reciprocal and score >= 0.15:
            row["alignment_status"] = "one_to_one"
        elif score == best_stm[row["stm_topic"]] and score >= 0.08:
            row["alignment_status"] = "one_to_many"
        elif score == best_bert[row["bertopic_topic"]] and score >= 0.08:
            row["alignment_status"] = "many_to_one"
        elif score >= 0.03:
            row["alignment_status"] = "weak_match"
    return rows


def compare_models(config: dict[str, Any]) -> dict[str, int]:
    root = Path(config["paths"]["output_root"])
    required = [root / "stm" / "document_topics.csv", root / "bertopic" / "document_topics.csv"]
    if not all(path.exists() for path in required):
        raise FileNotFoundError("STM and BERTopic document outputs are required before comparison")
    stm_docs, bert_docs = (read_csv(path) for path in required)
    stm_topics = read_csv(root / "stm" / "topics.csv")
    bert_topics = read_csv(root / "bertopic" / "topics.csv")
    stm_by_doc, bert_by_doc = ({row["document_id"]: row for row in rows} for rows in (stm_docs, bert_docs))
    comparisons: list[dict[str, Any]] = []
    for doc_id in sorted(stm_by_doc.keys() & bert_by_doc.keys()):
        stm, bert = stm_by_doc[doc_id], bert_by_doc[doc_id]
        comparisons.append({
            "document_id": doc_id, "title": stm.get("title") or bert.get("title"), "year": stm.get("year") or bert.get("year"),
            "stm_topic": stm["topic_id"], "stm_proportion": stm.get("topic_probability", ""),
            "bertopic_topic": bert["topic_id"], "bertopic_probability": bert.get("topic_probability", ""),
            "bertopic_outlier": bert.get("is_outlier", ""), "semantic_agreement": "pending_topic_alignment",
            "ambiguous": _truth(stm.get("is_ambiguous", "")) or _truth(bert.get("is_ambiguous", "")),
        })
    alignment = align_topics(stm_docs, bert_docs, stm_topics, bert_topics)
    relation = {(row["stm_topic"], row["bertopic_topic"]): row for row in alignment}
    for row in comparisons:
        aligned = relation.get((row["stm_topic"], row["bertopic_topic"]))
        row["semantic_agreement"] = aligned["alignment_status"] if aligned else "no_match"
    out = root / "comparison"
    write_csv(out / "document_model_comparison.csv", comparisons)
    write_csv(out / "topic_alignment.csv", alignment)
    write_csv(out / "topic_similarity_matrix.csv", alignment)
    write_csv(out / "stable_documents.csv", [row for row in comparisons if row["semantic_agreement"] == "one_to_one" and not row["ambiguous"]])
    write_csv(out / "ambiguous_documents.csv", [row for row in comparisons if row["ambiguous"] or row["semantic_agreement"] in {"weak_match", "no_match"}])
    summary = [
        {"metric": "shared_documents", "value": len(comparisons)},
        {"metric": "stm_documents", "value": len(stm_docs)},
        {"metric": "bertopic_documents", "value": len(bert_docs)},
        {"metric": "bertopic_outliers", "value": sum(_truth(row.get("is_outlier", "")) for row in bert_docs)},
        {"metric": "one_to_one_alignments", "value": sum(row["alignment_status"] == "one_to_one" for row in alignment)},
    ]
    write_csv(out / "model_summary.csv", summary)
    return {row["metric"]: int(row["value"]) for row in summary}
