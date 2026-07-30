import json

import numpy as np

from topic_modeling import bertopic_model
from topic_modeling.corpus_builder import read_csv, write_csv


def test_bertopic_cpu_smoke_with_cached_embeddings(tmp_path, monkeypatch):
    themes = [
        ("school leadership principal improvement", np.array([1.0, 0.0, 0.0, 0.0])),
        ("inclusive education disability participation", np.array([0.0, 1.0, 0.0, 0.0])),
        ("digital technology teacher learning", np.array([0.0, 0.0, 1.0, 0.0])),
        ("hospital clinical health patient", np.array([0.0, 0.0, 0.0, 1.0])),
    ]
    rows, embeddings = [], []
    rng = np.random.default_rng(42)
    for topic, (text, center) in enumerate(themes):
        for index in range(12):
            rows.append({
                "document_id": f"d-{topic}-{index}", "texto_modelado": f"{text} case {index}",
                "title": f"{text} {index}", "year": str(2020 + index % 6), "language": "en",
                "doi": "", "source": "fixture", "corpus_unit": "metadata",
            })
            embeddings.append(center + rng.normal(0, 0.015, len(center)))
    output = tmp_path / "output"
    write_csv(output / "corpus" / "modeling_corpus_metadata.csv", rows)
    config = {
        "project": {"seed": 42}, "paths": {"output_root": str(output), "cache_root": str(tmp_path / "cache"), "human_labels": str(tmp_path / "labels.csv")},
        "bertopic": {
            "embedding_model": "fixture", "batch_size": 8, "min_topic_size": 4, "min_samples": 2,
            "nr_topics": None, "calculate_probabilities": True, "low_memory": True,
            "ngram_min": 1, "ngram_max": 2, "min_df": 1, "max_df": 1.0, "max_features": 1000,
            "reduce_frequent_words": True,
            "umap": {"n_neighbors": 5, "n_components": 2, "min_dist": 0.0, "metric": "cosine"},
            "hdbscan": {"metric": "euclidean", "cluster_selection_method": "eom", "prediction_data": True},
        },
        "validation": {"ambiguous_probability_margin": 0.1},
    }
    monkeypatch.setattr(
        bertopic_model, "load_or_create_embeddings",
        lambda *_args, **_kwargs: (np.asarray(embeddings), {"fingerprint": "fixture", "dimension": 4}),
    )
    metadata = bertopic_model.run_bertopic(config)
    docs = read_csv(output / "bertopic" / "document_topics.csv")
    topics = read_csv(output / "bertopic" / "topics.csv")
    assert metadata["documents"] == 48
    assert len(docs) == 48
    assert len([row for row in topics if row["topic_id"] != "-1"]) >= 2
    assert {row["document_id"] for row in docs} == {row["document_id"] for row in rows}
    assert json.loads((output / "bertopic" / "model_metadata.json").read_text(encoding="utf-8"))["seed"] == 42
