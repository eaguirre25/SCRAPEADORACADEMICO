from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .corpus_builder import read_csv, write_csv


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
    for year, year_rows in sorted(by_year.items()):
        topic_ids = sorted({row["topic_id"] for row in year_rows})
        for topic_id in topic_ids:
            values = [float(row.get("topic_probability") or 1.0) if row["topic_id"] == topic_id else 0.0 for row in year_rows]
            count = sum(row["topic_id"] == topic_id for row in year_rows)
            low, high = _bootstrap_interval(values, samples, int(config["project"]["seed"]) + int(float(year)))
            outliers = sum(str(row.get("is_outlier", "")).casefold() == "true" for row in year_rows)
            result.append({
                "model": model, "topic_id": topic_id, "year": year, "document_count": count,
                "documents_in_year": len(year_rows), "percentage_of_year": round(100 * count / len(year_rows), 4),
                "mean_probability_or_prevalence": round(sum(values) / len(values), 6),
                "ci95_low": round(low, 6), "ci95_high": round(high, 6), "coverage_in_year": 1.0,
                "outlier_percentage": round(100 * outliers / len(year_rows), 4), "year_complete": year != end_year,
            })
    return result


def evaluate_model(config: dict[str, Any], model: str) -> list[dict[str, Any]]:
    root = Path(config["paths"]["output_root"])
    topics_path, docs_path, words_path = (root / model / name for name in ("topics.csv", "document_topics.csv", "topic_words.csv"))
    if not topics_path.exists() or not docs_path.exists():
        return []
    topics, docs = read_csv(topics_path), read_csv(docs_path)
    words = read_csv(words_path) if words_path.exists() else []
    counts = Counter(row["topic_id"] for row in docs)
    non_outlier = [value for key, value in counts.items() if key != "-1"]
    entropy_values: list[float] = []
    for row in docs:
        p = float(row.get("topic_probability") or 1.0)
        if 0 < p <= 1:
            entropy_values.append(-p * math.log(p))
    metrics = [
        {"model": model, "metric": "documents", "value": len(docs)},
        {"model": model, "metric": "topics_excluding_outliers", "value": len(non_outlier)},
        {"model": model, "metric": "minimum_topic_size", "value": min(non_outlier) if non_outlier else 0},
        {"model": model, "metric": "median_topic_size", "value": sorted(non_outlier)[len(non_outlier) // 2] if non_outlier else 0},
        {"model": model, "metric": "maximum_topic_size", "value": max(non_outlier) if non_outlier else 0},
        {"model": model, "metric": "topic_word_diversity", "value": round(topic_word_diversity(words, int(config["validation"]["top_n_words"])), 6)},
        {"model": model, "metric": "outlier_percentage", "value": round(100 * counts.get("-1", 0) / max(len(docs), 1), 4)},
        {"model": model, "metric": "ambiguous_documents", "value": sum(row.get("is_ambiguous", "").casefold() == "true" for row in docs)},
        {"model": model, "metric": "mean_partial_assignment_entropy", "value": round(sum(entropy_values) / max(len(entropy_values), 1), 6)},
    ]
    write_csv(root / model / "topics_over_time.csv", topics_over_time(docs, config, model))
    return metrics


def evaluate_all(config: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = evaluate_model(config, "stm") + evaluate_model(config, "bertopic")
    write_csv(Path(config["paths"]["output_root"]) / "evaluation" / "model_metrics.csv", metrics)
    return metrics
