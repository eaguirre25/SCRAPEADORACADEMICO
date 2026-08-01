from __future__ import annotations

import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .corpus_builder import read_csv, write_csv


VALIDATION_FIELDS = [
    "model", "corpus", "language", "topic_id", "automatic_descriptor", "proposed_label", "human_label",
    "top_words", "top_ngrams", "representative_titles", "borderline_titles", "coherence_rating",
    "semantic_purity_rating", "distinctiveness_rating", "relevance_rating", "language_dependence_rating",
    "merge_required", "split_required", "exclude_required", "notes", "reviewer", "status", "validation_status",
]


def _model_dirs(root: Path) -> list[Path]:
    result = []
    for family in ("stm", "bertopic"):
        base = root / family
        if not base.exists(): continue
        result.extend(
            candidate.parent for candidate in base.rglob("topics.csv")
            if "archive" not in candidate.parent.parts
        )
    return result


def export_validation_template(config: dict[str, Any]) -> int:
    root = Path(config["paths"]["output_root"]); validation = root / "validation"
    target = validation / "topic_validation.csv"
    compatibility_target = validation / "topic_validation_template.csv"
    previous_rows = read_csv(target) if target.exists() else []
    if compatibility_target.exists():
        previous_rows.extend(read_csv(compatibility_target))
    previous = {(row["model"], row.get("corpus", ""), row.get("language", ""), row["topic_id"]): row for row in previous_rows}
    rows: list[dict[str, Any]] = []
    all_topics: list[dict[str, str]] = []
    all_docs: list[dict[str, str]] = []
    for model_dir in _model_dirs(root):
        topics = read_csv(model_dir / "topics.csv"); docs = read_csv(model_dir / "document_topics.csv") if (model_dir / "document_topics.csv").exists() else []
        all_topics.extend(topics); all_docs.extend(docs)
        by_topic: dict[str, list[dict[str, str]]] = {}
        for doc in docs: by_topic.setdefault(doc["topic_id"], []).append(doc)
        for topic in topics:
            model = topic.get("model", model_dir.name); corpus = topic.get("corpus", ""); language = topic.get("language", "")
            key = (model, corpus, language, topic["topic_id"]); old = previous.get(key, {})
            topic_docs = by_topic.get(topic["topic_id"], [])
            validation_cfg = config.get("validation", {})
            borderline = sorted(topic_docs, key=lambda row: float(row.get("probability_margin") or 0))[: int(validation_cfg.get("borderline_documents", 10))]
            rows.append({
                "model": model, "corpus": corpus, "language": language, "topic_id": topic["topic_id"],
                "automatic_descriptor": topic.get("automatic_label", topic.get("topic_label", "")),
                "proposed_label": topic.get("topic_label", ""), "human_label": old.get("human_label", topic.get("human_label", "")),
                "top_words": topic.get("top_words", ""), "top_ngrams": topic.get("top_ngrams", ""),
                "representative_titles": topic.get("representative_titles", ""),
                "borderline_titles": " | ".join(row.get("title", "") for row in borderline),
                **{field: old.get(field, "") for field in VALIDATION_FIELDS[11:-1]},
                "status": old.get("status", old.get("validation_status", "pending_human_review")),
                "validation_status": old.get("validation_status", old.get("status", "pending_human_review")),
            })
    write_csv(target, rows, VALIDATION_FIELDS)
    write_csv(compatibility_target, rows, VALIDATION_FIELDS)

    rng = random.Random(int(config.get("project", {}).get("seed", 42)))
    topic_terms = {
        (row.get("model", ""), row.get("corpus", ""), row.get("language", ""), row["topic_id"]):
        [part.strip() for part in row.get("top_words", "").split("|") if part.strip()]
        for row in all_topics if row.get("topic_id") != "-1"
    }
    word_intrusion = []
    for key, words in topic_terms.items():
        alternatives = [word for other, terms in topic_terms.items() if other != key for word in terms[:5] if word not in words]
        if len(words) < 5 or not alternatives: continue
        intruder = rng.choice(alternatives); candidates = words[:5] + [intruder]; rng.shuffle(candidates)
        word_intrusion.append({
            "model": key[0], "corpus": key[1], "language": key[2], "topic_id": key[3],
            "candidate_terms_randomized": " | ".join(candidates), "intruder_answer_key": intruder,
            "human_selected_intruder": "", "correct": "", "reviewer": "", "status": "pending",
        })
    write_csv(validation / "word_intrusion.csv", word_intrusion)

    topic_ids_by_model: dict[str, list[str]] = {}
    for row in all_topics: topic_ids_by_model.setdefault(row.get("model", ""), []).append(row["topic_id"])
    topic_intrusion = []
    sample_docs = sorted(all_docs, key=lambda row: float(row.get("probability_margin") or 0))[: min(200, len(all_docs))]
    for row in sample_docs:
        options = [row.get("topic_id", ""), row.get("second_topic_id", "")]
        alternatives = [value for value in topic_ids_by_model.get(row.get("model", ""), []) if value not in options and value != "-1"]
        if not alternatives: continue
        intruder = rng.choice(alternatives); options.append(intruder); rng.shuffle(options)
        topic_intrusion.append({
            "model": row.get("model", ""), "corpus": row.get("corpus", row.get("corpus_unit", "")),
            "document_id": row["document_id"], "title": row.get("title", ""), "abstract": "",
            "candidate_topics_randomized": " | ".join(options), "principal_topic_answer_key": row.get("topic_id", ""),
            "intruder_answer_key": intruder, "human_selected_topic": "", "reviewer": "", "status": "pending",
        })
    write_csv(validation / "topic_intrusion.csv", topic_intrusion)
    return len(rows)


def export_method_report(config: dict[str, Any]) -> Path:
    root = Path(config["paths"]["output_root"])
    quality = read_csv(root / "corpus" / "corpus_quality_report.csv")
    metrics = read_csv(root / "evaluation" / "model_metrics.csv")
    alignment = read_csv(root / "comparison" / "model_summary.csv")
    runs = read_csv(root / "evaluation" / "model_runs.csv")
    priority = read_csv(root / "evaluation" / "topic_review_priority.csv")

    def table(rows: list[dict[str, Any]], columns: list[str]) -> str:
        if not rows: return "Datos todavía no generados."
        lines = ["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
        lines.extend("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |" for row in rows)
        return "\n".join(lines)

    preferred = [row for row in runs if row.get("is_preferred_model", "").casefold() == "true"]
    comparative = [row for row in runs if row.get("is_latest_for_model", "").casefold() == "true" and row.get("is_archived", "").casefold() != "true" and row.get("is_preferred_model", "").casefold() != "true"]
    historical = [row for row in runs if row.get("is_archived", "").casefold() == "true"]
    latest_ids = {row["run_id"] for row in runs if row.get("is_latest_for_model", "").casefold() == "true" and row.get("is_archived", "").casefold() != "true"}
    main_metrics = [row for row in metrics if row.get("run_id") in latest_ids]
    target = root / "reports" / "topic_modeling_report.md"; target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "# Informe reproducible de modelado temático\n\n"
        f"Generado: {datetime.now(timezone.utc).isoformat()}\n\nSemilla: {config['project']['seed']}\n\n"
        f"Período: {config['project']['start_year']}–{config['project']['end_year']} (2026 incompleto)\n\n"
        "## Resumen técnico\n\n**BERTopic metadata multilingüe es el único modelo principal vigente: 14 macrotemas, solución preferida provisional y validación humana pendiente.** Las STM corregidas se presentan sólo como modelos comparativos y los históricos quedan separados.\n\n"
        "## Modelo principal vigente\n\n" + table(preferred, ["run_id", "model_name", "corpus_unit", "language", "status", "validation_status"]) + "\n\n"
        "## Modelos comparativos\n\n" + table(comparative, ["run_id", "model_name", "language", "status", "validation_status"]) + "\n\n"
        "## Ejecuciones históricas\n\n" + table(historical, ["run_id", "model_name", "model_path", "generated_at", "status"]) + "\n\n"
        "## Calidad y cobertura del corpus\n\n" + table(quality, ["metric_group", "metric", "value"]) + "\n\n"
        "## Métricas de modelos vigentes\n\n" + table(main_metrics, ["run_id", "model", "corpus", "metric", "value", "applicability"]) + "\n\n"
        "## Prioridad de revisión\n\n" + table(priority, ["priority_rank", "topic_id", "review_priority_score", "priority_reason"]) + "\n\n"
        "## Comparación STM–BERTopic\n\n" + table(alignment, ["metric", "value"]) + "\n\n"
        "## Alcance, limitaciones y próximos pasos\n\n"
        "STM estima masa temática promedio y mezclas por publicación; BERTopic produce agrupamientos documentales semánticos. "
        "Los resultados no son equivalentes y sus medidas no son intercambiables. Los corpus metadata y full text son representaciones separadas de publicaciones relacionadas, no documentos sumables. "
        "El país estructurado no está disponible; `source` significa proveedor/repositorio bibliográfico. Los outliers se conservan, 2026 es parcial y las decisiones de relevancia, fusión, división y etiquetado esperan revisión humana. Consulte `metric_definitions.md` y `evaluation_audit.json` para auditar fórmulas y cobertura.\n",
        encoding="utf-8",
    )
    return target
