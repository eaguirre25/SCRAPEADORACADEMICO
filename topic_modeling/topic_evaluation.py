from __future__ import annotations

import math
import random
import re
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .corpus_builder import read_csv, write_csv


CONTAMINATION_TERMS = {
    "nursing", "hospital", "clinical", "patient", "tax", "taxation", "treasury", "accounting",
    "corruption", "entrepreneurship", "business", "mental", "health", "suicide", "mineral", "engineering",
    "koinonia", "pmid", "plos", "bmc", "isni", "scielo", "redalyc", "nbsp", "amp",
}


def topic_word_diversity(topic_words: list[dict[str, str]], top_n: int = 15) -> float:
    by_topic: dict[str, list[str]] = defaultdict(list)
    for row in topic_words:
        if len(by_topic[row["topic_id"]]) < top_n:
            by_topic[row["topic_id"]].append(row["term"].casefold())
    all_words = [word for words in by_topic.values() for word in words]
    return len(set(all_words)) / len(all_words) if all_words else 0.0


def _bootstrap_interval(values: list[float], samples: int, seed: int) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    rng = random.Random(seed)
    means = [sum(rng.choices(values, k=len(values))) / len(values) for _ in range(samples)]
    means.sort()
    return means[int(0.025 * (samples - 1))], means[int(0.975 * (samples - 1))]


def topics_over_time(rows: list[dict[str, str]], config: dict[str, Any], model: str) -> list[dict[str, Any]]:
    by_year: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("year"):
            by_year[row["year"]].append(row)
    result: list[dict[str, Any]] = []
    samples = int(config["validation"].get("bootstrap_samples", 500))
    end_year = str(config["project"]["end_year"])
    all_topics = sorted({row["topic_id"] for row in rows if row.get("topic_id") != "-1"})
    for year, year_rows in sorted(by_year.items()):
        outlier_share = sum(str(row.get("is_outlier", "")).casefold() == "true" for row in year_rows) / len(year_rows)
        for topic_id in all_topics:
            assigned = [row for row in year_rows if row["topic_id"] == topic_id]
            probabilities = [float(row.get("topic_probability") or 0.0) for row in assigned]
            indicator = [1.0 if row["topic_id"] == topic_id else 0.0 for row in year_rows]
            low, high = _bootstrap_interval(indicator, samples, int(config["project"]["seed"]) + int(float(year)))
            result.append({
                "model": model, "corpus": year_rows[0].get("corpus", year_rows[0].get("corpus_unit", "")),
                "topic_id": topic_id, "year": year, "documents_in_year": len(year_rows),
                "cluster_documents": len(assigned), "cluster_share": round(len(assigned) / len(year_rows), 6),
                "mean_assignment_probability": round(sum(probabilities) / len(probabilities), 6) if probabilities else 0,
                "outlier_share": round(outlier_share, 6), "lower_95": round(low, 6), "upper_95": round(high, 6),
                "uncertainty_method": "bootstrap_cluster_share", "year_complete": year != end_year,
            })
    return result


def temporal_accounting_issues(rows: list[dict[str, str]], model_family: str) -> list[str]:
    by_year: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_year[row.get("year", "")].append(row)
    issues: list[str] = []
    for year, year_rows in by_year.items():
        if not year_rows: continue
        expected = int(float(year_rows[0].get("documents_in_year") or 0))
        if model_family == "stm":
            dominant = sum(int(float(row.get("dominant_topic_documents") or 0)) for row in year_rows)
            mass = sum(float(row.get("effective_topic_mass") or 0) for row in year_rows)
            if dominant != expected: issues.append(f"{year}:dominant={dominant}:documents={expected}")
            if not math.isclose(mass, expected, rel_tol=1e-6, abs_tol=1e-5): issues.append(f"{year}:mass={mass}:documents={expected}")
        else:
            clustered = sum(int(float(row.get("cluster_documents") or 0)) for row in year_rows)
            if clustered > expected: issues.append(f"{year}:clusters={clustered}:documents={expected}")
    return issues


def _topic_similarity(topics: list[dict[str, str]]) -> dict[str, float]:
    terms = {
        row["topic_id"]: {part.strip().casefold() for part in row.get("top_words", "").split("|") if part.strip()}
        for row in topics if row.get("topic_id") != "-1"
    }
    similarities = []
    ids = sorted(terms)
    for pos, left in enumerate(ids):
        for right in ids[pos + 1:]:
            union = terms[left] | terms[right]
            similarities.append(len(terms[left] & terms[right]) / len(union) if union else 0.0)
    return {
        "mean_pairwise_topic_similarity": sum(similarities) / len(similarities) if similarities else 0.0,
        "maximum_pairwise_topic_similarity": max(similarities, default=0.0),
        "redundant_topic_pairs_0_5": sum(value >= 0.5 for value in similarities),
    }


def coherence_per_topic(topics: list[dict[str, str]], texts: list[str], top_n: int = 15) -> tuple[dict[str, dict[str, float]], str]:
    """Calculate corpus-based coherence where gensim is available; never invent missing metrics."""
    usable = [row for row in topics if row.get("topic_id") != "-1"]
    tokenized = [re.findall(r"[^\W\d_][\w-]+", text.casefold()) for text in texts if text.strip()]
    topic_terms = [[part.strip().casefold() for part in row.get("top_words", "").split("|") if part.strip()][:top_n] for row in usable]
    if not tokenized or not topic_terms:
        return {}, "not_computed_empty_corpus"
    try:
        from gensim.corpora import Dictionary
        from gensim.models import CoherenceModel
        dictionary = Dictionary(tokenized)
        bow = [dictionary.doc2bow(tokens) for tokens in tokenized]
        values = {}
        for measure in ("c_v", "c_npmi", "u_mass"):
            kwargs = {"topics": topic_terms, "dictionary": dictionary, "coherence": measure}
            if measure == "u_mass": kwargs["corpus"] = bow
            else:
                kwargs["texts"] = tokenized
                kwargs["processes"] = 1
            values[measure] = CoherenceModel(**kwargs).get_coherence_per_topic()
        return {
            row["topic_id"]: {measure: round(float(values[measure][index]), 6) for measure in values}
            for index, row in enumerate(usable)
        }, "computed_gensim"
    except (ImportError, RuntimeError, ValueError) as exc:
        return {}, f"not_computed:{type(exc).__name__}"


def _discover_models(root: Path) -> list[tuple[str, Path]]:
    models: list[tuple[str, Path]] = []
    for family in ("stm", "bertopic"):
        family_root = root / family
        if not family_root.exists():
            continue
        for child in family_root.rglob("topics.csv"):
            model_dir = child.parent
            relative = model_dir.relative_to(root).as_posix()
            if "archive" in model_dir.parts or not (model_dir / "document_topics.csv").exists():
                continue
            # A corrected STM run supersedes the same language/unit legacy run.
            if family == "stm" and not model_dir.name.endswith("_corrected"):
                corrected = model_dir.with_name(model_dir.name + "_corrected")
                if (corrected / "topics.csv").exists() and (corrected / "document_topics.csv").exists():
                    continue
            # The selected BERTopic solution is the sole current metadata run.
            if relative == "bertopic/metadata_multilingual" and (model_dir / "preferred_solution/topics.csv").exists():
                continue
            models.append((relative, model_dir))
    return models


def _run_info(model_key: str, path: Path) -> dict[str, Any]:
    metadata_path = path / "model_metadata.json"
    metadata: dict[str, Any] = {}
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            metadata = {}
    generated_at = metadata.get("generated_at_utc", "")
    run_id = hashlib.sha256(f"{model_key}|{generated_at}".encode("utf-8")).hexdigest()[:16]
    return {
        "run_id": run_id,
        "model_path": model_key,
        "is_current": True,
        "generated_at": generated_at,
        "commit": metadata.get("git_commit", ""),
        "status": metadata.get("selection_status", metadata.get("model_status", "current_provisional")),
    }


def evaluate_all(config: dict[str, Any]) -> dict[str, Any]:
    # Compatibility entrypoint.  Evaluation is now delegated to the frozen,
    # evaluation-only layer so direct callers cannot regenerate the obsolete
    # mixed-run tables below or fit a model accidentally.
    from .evaluation_metrics import recompute_evaluation
    return recompute_evaluation(config, recompute_model=False)

    # Legacy implementation retained temporarily for historical diffability;
    # unreachable by design.
    root = Path(config["paths"]["output_root"])
    model_metrics: list[dict[str, Any]] = []
    topic_metrics: list[dict[str, Any]] = []
    document_metrics: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []
    language_rows: list[dict[str, Any]] = []
    heterogeneity_rows: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []
    run_by_path: dict[str, dict[str, Any]] = {}
    for model_key, path in _discover_models(root):
        run_info = _run_info(model_key, path)
        run_rows.append(run_info)
        run_by_path[model_key] = run_info
        topics, docs = read_csv(path / "topics.csv"), read_csv(path / "document_topics.csv")
        words = read_csv(path / "topic_words.csv") if (path / "topic_words.csv").exists() else []
        model_name = topics[0].get("model", model_key) if topics else model_key
        corpus = topics[0].get("corpus", docs[0].get("corpus", docs[0].get("corpus_unit", ""))) if docs else ""
        corpus_rows = read_csv(root / "corpus" / f"modeling_corpus_{corpus}.csv") if corpus else []
        eligible_ids = {row.get("publication_document_id") or row.get("document_id") for row in docs}
        corpus_texts = [row.get("text_for_modeling") or row.get("texto_modelado", "") for row in corpus_rows
                        if (row.get("publication_document_id") or row.get("document_id")) in eligible_ids]
        coherence, coherence_status = coherence_per_topic(topics, corpus_texts, int(config["validation"]["top_n_words"]))
        counts = Counter(row["topic_id"] for row in docs)
        sizes = [value for key, value in counts.items() if key != "-1"]
        similarity = _topic_similarity(topics)
        model_metrics.extend([
            {"model": model_name, "model_path": model_key, "corpus": corpus, "metric": "documents", "value": len(docs), "applicability": "all"},
            {"model": model_name, "model_path": model_key, "corpus": corpus, "metric": "topics_excluding_outliers", "value": len(sizes), "applicability": "all"},
            {"model": model_name, "model_path": model_key, "corpus": corpus, "metric": "minimum_topic_size", "value": min(sizes) if sizes else 0, "applicability": "dominant STM assignment or BERTopic cluster"},
            {"model": model_name, "model_path": model_key, "corpus": corpus, "metric": "topic_word_diversity", "value": round(topic_word_diversity(words, int(config["validation"]["top_n_words"])), 6), "applicability": "lexical representation"},
            {"model": model_name, "model_path": model_key, "corpus": corpus, "metric": "outlier_percentage", "value": round(100 * counts.get("-1", 0) / max(len(docs), 1), 4), "applicability": "BERTopic only; STM returns 0"},
            {"model": model_name, "model_path": model_key, "corpus": corpus, "metric": "ambiguous_documents", "value": sum(row.get("is_ambiguous", "").casefold() == "true" for row in docs), "applicability": "model-specific confidence"},
            {"model": model_name, "model_path": model_key, "corpus": corpus, "metric": "coherence_computation_status", "value": coherence_status, "applicability": "lexical representation"},
            *({"model": model_name, "model_path": model_key, "corpus": corpus, "metric": key, "value": round(value, 6), "applicability": "lexical overlap"} for key, value in similarity.items()),
        ])
        for topic in topics:
            top_terms = {part.strip().casefold() for part in topic.get("top_words", "").split("|") if part.strip()}
            contamination = sorted(top_terms & CONTAMINATION_TERMS)
            topic_metrics.append({
                "model": model_name, "model_path": model_key, "corpus": corpus,
                "language": topic.get("language", ""), "topic_id": topic["topic_id"],
                "c_v": coherence.get(topic["topic_id"], {}).get("c_v", topic.get("c_v", "")),
                "c_npmi": coherence.get(topic["topic_id"], {}).get("c_npmi", topic.get("c_npmi", "")),
                "umass": coherence.get(topic["topic_id"], {}).get("u_mass", topic.get("umass", "")),
                "topic_diversity": topic.get("diversity", ""), "document_count": topic.get("document_count", ""),
                "prevalence_or_cluster_share": topic.get("prevalence", ""),
                "contamination_terms": " | ".join(contamination), "contamination_flag": bool(contamination),
                "human_validation_status": topic.get("validation_status", topic.get("label_status", "pending")),
            })
        for row in docs:
            document_metrics.append({
                "model": model_name, "model_path": model_key, "corpus": corpus,
                "document_id": row["document_id"], "publication_document_id": row.get("publication_document_id", row["document_id"]),
                "topic_id": row["topic_id"], "assignment_confidence": row.get("topic_probability", ""),
                "probability_margin": row.get("probability_margin", ""), "entropy": row.get("topic_entropy", ""),
                "silhouette": row.get("silhouette", ""), "distance_to_centroid": row.get("distance_to_centroid", ""),
                "local_consistency": row.get("local_consistency", ""), "ambiguous": row.get("is_ambiguous", ""),
                "is_outlier": row.get("is_outlier", ""), "language": row.get("language", ""),
            })
        diagnostics = read_csv(path / "k_diagnostics.csv") if (path / "k_diagnostics.csv").exists() else []
        for row in diagnostics:
            stability_rows.append({
                "model": model_name, "model_path": model_key, "corpus": corpus, "candidate": row.get("K", ""),
                "stability": row.get("stability", ""), "convergence_rate": row.get("convergence_rate", ""),
                "selection_status": row.get("selection_status", "provisional"), "human_review_status": row.get("human_review_status", "pending"),
            })
        if (path / "language_dependence.csv").exists(): language_rows.extend(read_csv(path / "language_dependence.csv"))
        if (path / "heterogeneity.csv").exists(): heterogeneity_rows.extend(read_csv(path / "heterogeneity.csv"))
        if model_key.startswith("bertopic/"):
            write_csv(path / "topics_over_time.csv", topics_over_time(docs, config, model_name))
        temporal_rows = read_csv(path / "topics_over_time.csv") if (path / "topics_over_time.csv").exists() else []
        temporal_issues = temporal_accounting_issues(temporal_rows, "stm" if model_key.startswith("stm") else "bertopic")
        model_metrics.append({
            "model": model_name, "model_path": model_key, "corpus": corpus, "metric": "temporal_accounting_issues",
            "value": " | ".join(temporal_issues), "applicability": "empty means annual counts and topic mass reconcile",
        })
    for collection in (model_metrics, topic_metrics, document_metrics, stability_rows):
        for row in collection:
            info = run_by_path.get(str(row.get("model_path", "")), {})
            row.update({key: info.get(key, "") for key in ("run_id", "is_current", "generated_at", "commit", "status")})
    evaluation = root / "evaluation"
    write_csv(evaluation / "model_runs.csv", run_rows)
    write_csv(evaluation / "model_metrics.csv", model_metrics)
    write_csv(evaluation / "topic_metrics.csv", topic_metrics)
    write_csv(evaluation / "document_metrics.csv", document_metrics)
    write_csv(evaluation / "stability.csv", stability_rows)
    write_csv(evaluation / "language_dependence.csv", language_rows)
    write_csv(evaluation / "heterogeneity.csv", heterogeneity_rows)
    return model_metrics
