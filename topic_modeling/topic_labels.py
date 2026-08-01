from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def automatic_label(words: list[str], limit: int = 4) -> str:
    selected = [word.replace("_", " ").strip() for word in words if word.strip()][:limit]
    return " · ".join(selected) if selected else "Tópico sin etiqueta"


def load_human_labels(path: str | Path) -> dict[tuple[str, str], dict[str, str]]:
    source = Path(path)
    if not source.exists():
        return {}
    with source.open(encoding="utf-8-sig", newline="") as handle:
        return {(row["model"], row["topic_id"]): row for row in csv.DictReader(handle) if row.get("model") and row.get("topic_id")}


def resolve_label(model: str, topic_id: int, proposal: str, human: dict[tuple[str, str], dict[str, str]]) -> dict[str, Any]:
    existing = human.get((model, str(topic_id)), {})
    human_label = existing.get("human_label", "").strip()
    status = existing.get("label_status", "pending").strip() or "pending"
    return {
        "automatic_label": proposal,
        "human_label": human_label,
        "topic_label": human_label or proposal,
        "label_status": status,
        "label_notes": existing.get("label_notes", ""),
    }

