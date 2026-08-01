import csv
from pathlib import Path

from topic_modeling.evaluation_metrics import (
    classify_heterogeneity,
    compute_topic_coherence,
    contamination_metrics,
    lexical_metrics,
    metadata_metrics,
)


ROOT = Path(__file__).resolve().parents[1]


def read_rows(relative):
    with (ROOT / relative).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def coherence_config():
    return {"bertopic": {"ngram_min": 1, "ngram_max": 3, "min_df": 1, "max_df": 1.0, "max_features": 5000}}


def test_coherent_topic_scores_better_than_mixed_topic_with_ngrams():
    texts = [
        "school management leadership school management leadership" for _ in range(30)
    ] + ["banana fruit yellow" for _ in range(10)] + ["quantum particle wave" for _ in range(10)]
    metrics, summary = compute_topic_coherence(
        {0: ["school management", "school", "management", "leadership"], 1: ["school", "banana", "quantum"]},
        texts, coherence_config(),
    )
    assert summary["ngram_strategy"] == "literal_vectorizer_tokens"
    assert metrics[0]["coherence_status"] == metrics[1]["coherence_status"] == "computed"
    assert metrics[0]["coherence_cv"] > metrics[1]["coherence_cv"]
    assert "school management" in metrics[0]["coherence_terms_used"]


def test_global_diversity_is_separate_and_topic_exclusivity_varies():
    rows = []
    values = {0: ["school", "leadership", "director"], 1: ["school", "quality", "management"], 2: ["family", "parents", "participation"]}
    for topic, terms in values.items():
        for rank, term in enumerate(terms, 1): rows.append({"topic_id": str(topic), "rank": str(rank), "term": term, "weight": str(1/rank)})
    per_topic, global_value = lexical_metrics(rows, 3)
    assert 0 < global_value < 1
    assert per_topic[2]["topic_unique_term_share"] > per_topic[0]["topic_unique_term_share"]
    assert len({row["topic_unique_term_share"] for row in per_topic.values()}) > 1


def test_missing_country_does_not_become_total_concentration():
    docs = [{"document_id": str(i), "source": "OpenAlex", "country": ""} for i in range(20)]
    result = metadata_metrics(docs, {"country_field": "country", "source_field": "source"}, {"evaluation": {"metadata": {"minimum_known_documents": 10, "minimum_coverage": .3}}})
    assert result["country_coverage"] == 0
    assert result["dominant_country_share_known"] == ""
    assert result["country_entropy"] == ""
    assert result["country_status"] == "insufficient_metadata"
    assert result["source_status"] == "insufficient_categories"


def test_contamination_uses_document_evidence_and_never_auto_validates_zero():
    clean = [{"document_id": str(i), "title": "School leadership", "abstract": "Management in schools", "relevance_status": "included", "relevance_score": "1"} for i in range(10)]
    clean_metrics, _ = contamination_metrics(clean)
    assert clean_metrics["contamination_share"] == 0
    assert clean_metrics["contamination_status"] == "pending_human_review"
    mixed = clean + [{"document_id": "x", "title": "Clinical hospital management", "abstract": "Patients and nursing", "relevance_status": "borderline", "relevance_score": "0"}]
    mixed_metrics, candidates = contamination_metrics(mixed)
    assert "x" in candidates
    assert mixed_metrics["contamination_share"] > 0
    assert mixed_metrics["borderline_relevance_share"] > 0


def test_heterogeneity_combines_negative_silhouette_and_borderline_signals():
    cfg = {"evaluation": {"heterogeneity": {"negative_silhouette_high": .2, "borderline_high": .3, "borderline_candidate": .25, "coherence_low": .3, "contamination_high": .2, "language_concentration": .85, "source_concentration_excess": .15}}}
    base = {"silhouette_document_count": 50, "coherence_status": "computed", "coherence_cv": .5, "contamination_share": 0, "dominant_language_share_known": .6, "source_status": "insufficient_categories", "source_concentration_excess": ""}
    status, _ = classify_heterogeneity({**base, "silhouette_negative_share": .25, "borderline_document_share": .31}, cfg)
    assert status == "heterogeneous_candidate"
    compact, _ = classify_heterogeneity({**base, "silhouette_negative_share": 0, "borderline_document_share": .05}, cfg)
    assert compact == "coherent_candidate"


def test_model_runs_have_one_preferred_and_archived_are_not_main_metrics():
    runs = read_rows("output/topic_models/evaluation/model_runs.csv")
    assert sum(row["is_preferred_model"].lower() == "true" for row in runs) == 1
    assert all(row["is_archived"].lower() != "true" for row in runs if row["is_preferred_model"].lower() == "true")
    archived_ids = {row["run_id"] for row in runs if row["is_archived"].lower() == "true"}
    metrics = read_rows("output/topic_models/evaluation/model_metrics.csv")
    assert not archived_ids & {row["run_id"] for row in metrics}
    keys = [(row["run_id"], row["model"], row["metric"]) for row in metrics]
    assert len(keys) == len(set(keys))


def test_dashboard_contains_valid_missing_metric_language():
    source = (ROOT / "generate_dashboard.py").read_text(encoding="utf-8")
    assert "No disponible por cobertura insuficiente" in source
    assert "Metadatos insuficientes para evaluar concentración territorial" in source
    assert "Modelo principal" in source and "Modelos comparativos" in source and "Históricos" in source
