from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime, timezone

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


def export_method_report(config: dict[str, Any]) -> Path:
    root = Path(config["paths"]["output_root"])
    quality_path = root / "corpus" / "corpus_quality_report.csv"
    metrics_path = root / "evaluation" / "model_metrics.csv"
    alignment_path = root / "comparison" / "model_summary.csv"
    quality = read_csv(quality_path) if quality_path.exists() else []
    metrics = read_csv(metrics_path) if metrics_path.exists() else []
    alignment = read_csv(alignment_path) if alignment_path.exists() else []

    def table(rows: list[dict[str, Any]], first: str, second: str) -> str:
        if not rows:
            return "Datos todavía no generados."
        lines = [f"| {first} | {second} |", "|---|---:|"]
        lines.extend(f"| {row.get(first, '')} | {row.get(second, '')} |" for row in rows)
        return "\n".join(lines)

    target = root / "reports" / "topic_modeling_report.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "# Informe reproducible de modelado temático\n\n"
        f"Generado: {datetime.now(timezone.utc).isoformat()}  \nSemilla: {config['project']['seed']}  \n"
        f"Período: {config['project']['start_year']}–{config['project']['end_year']} (último año incompleto)\n\n"
        "## Calidad y cobertura del corpus\n\n" + table(quality, "metric", "value") + "\n\n"
        "## Métricas de modelos\n\n" + table(metrics, "metric", "value") + "\n\n"
        "## Comparación STM–BERTopic\n\n" + table(alignment, "metric", "value") + "\n\n"
        "## Interpretación y limitaciones\n\n"
        "La prevalencia STM y el tamaño de cluster BERTopic no son equivalentes. Los outliers se conservan. "
        "Las etiquetas son propuestas hasta su validación humana. Cambios por año pueden reflejar cobertura, idioma, fuente o disponibilidad de PDF. "
        "La presencia de temas ajenos a dirección escolar indica contaminación potencial del corpus y debe revisarse sin eliminar registros silenciosamente.\n",
        encoding="utf-8",
    )
    return target
