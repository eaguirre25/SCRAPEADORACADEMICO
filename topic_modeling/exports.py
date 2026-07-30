from __future__ import annotations

from pathlib import Path
from typing import Any

from .corpus_builder import read_csv, write_csv


VALIDATION_FIELDS = [
    "model", "topic_id", "automatic_label", "human_label", "coherence_rating",
    "internal_consistency_rating", "distinctiveness_rating", "relevance_to_school_leadership",
    "merge_with", "split_required", "exclude_topic", "reviewer_notes", "validation_status",
]


def export_validation_template(config: dict[str, Any]) -> int:
    root = Path(config["paths"]["output_root"])
    target = root / "validation" / "topic_validation_template.csv"
    previous = {(row["model"], row["topic_id"]): row for row in read_csv(target)} if target.exists() else {}
    rows: list[dict[str, Any]] = []
    for model in ("stm", "bertopic"):
        source = root / model / "topics.csv"
        if not source.exists():
            continue
        for topic in read_csv(source):
            key = (model, topic["topic_id"])
            old = previous.get(key, {})
            rows.append({
                "model": model, "topic_id": topic["topic_id"], "automatic_label": topic.get("automatic_label", ""),
                "human_label": old.get("human_label", topic.get("human_label", "")),
                **{name: old.get(name, "") for name in VALIDATION_FIELDS[4:-1]},
                "validation_status": old.get("validation_status", "pending"),
            })
    write_csv(target, rows, VALIDATION_FIELDS)
    return len(rows)
