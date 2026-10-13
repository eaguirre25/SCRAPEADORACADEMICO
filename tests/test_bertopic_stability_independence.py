from topic_modeling.bertopic_search import summarize_stability_runs


def _row(seed, similarity):
    return {
        "base_seed": 42, "seed": seed,
        "adjusted_rand_index": similarity,
        "normalized_mutual_information": similarity,
        "topic_centroid_similarity": similarity,
        "jaccard_top_words": similarity,
        "topic_count": 10, "outlier_share": 0.2,
    }


def test_reference_self_comparison_cannot_inflate_stability():
    result = summarize_stability_runs([_row(42, 1.0), _row(117, 0.2), _row(233, 0.4)])
    assert result["stability_ari_mean"] == 0.3
    assert result["stability_nmi_mean"] == 0.3
    assert result["centroid_stability_mean"] == 0.3
    assert result["top_word_jaccard_mean"] == 0.3
    assert result["stability_independent_comparisons"] == 2


def test_reference_alone_is_insufficient_evidence():
    result = summarize_stability_runs([_row("42", 1.0)])
    assert result["stability_ari_mean"] == ""
    assert result["stability_status"] == "insufficient_independent_runs"


def test_run_notes_follow_actual_topic_count(tmp_path):
    import json
    from topic_modeling.corpus_builder import write_csv
    from topic_modeling.evaluation_metrics import rebuild_model_runs
    model = tmp_path / "bertopic/metadata_multilingual/preferred_solution"
    model.mkdir(parents=True)
    write_csv(model / "topics.csv", [
        {"topic_id": tid, "model": "BERTopic", "corpus": "metadata", "language": "multilingual"}
        for tid in [-1, 0, 7, 20]
    ])
    write_csv(model / "document_topics.csv", [{"document_id": "a", "topic_id": 7}])
    (model / "model_metadata.json").write_text(json.dumps({"generated_at_utc": "2026-10-10"}))
    rows = rebuild_model_runs({"paths": {"output_root": str(tmp_path)}})
    assert rows[0]["notes"].endswith("3 macrotemas.")
