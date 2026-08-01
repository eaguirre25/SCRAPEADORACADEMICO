import json
import sys
import types
from pathlib import Path

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
                "text_for_vectorizer": f"{text} case {index}", "title_text": f"{text} {index}", "abstract_text": text,
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
            "ambiguity": {"margin_below": 0.08, "membership_below": 0.35, "centroid_similarity_below": 0.35, "outlier_score_above": 0.8},
            "macro_search": {"subcluster_minimum_documents": 60},
            "umap": {"n_neighbors": 5, "n_components": 2, "min_dist": 0.0, "metric": "cosine"},
            "hdbscan": {"metric": "euclidean", "cluster_selection_method": "eom", "prediction_data": True},
        },
        "validation": {"ambiguous_probability_margin": 0.1},
        "metadata_embeddings": {"combine_fields_as_embeddings": True},
        "multilingual": {"language_topic_threshold": 0.8},
    }

    class FakeInfo:
        def __init__(self):
            self.rows = [{"Topic": topic, "Count": 12} for topic in range(4)]
        def __getitem__(self, key):
            return types.SimpleNamespace(tolist=lambda: [row[key] for row in self.rows])
        def iterrows(self):
            return enumerate(self.rows)

    class FakeUMAP:
        def __init__(self, **kwargs):
            self.embedding_ = None
            self.n_neighbors=kwargs["n_neighbors"]; self.n_components=kwargs["n_components"]; self.min_dist=kwargs["min_dist"]; self.metric=kwargs["metric"]; self.low_memory=kwargs["low_memory"]

    class FakeHDBSCAN:
        def __init__(self, **kwargs):
            for key,value in kwargs.items(): setattr(self,key,value)

    class FakeCTFIDF:
        def __init__(self, **_kwargs):
            pass

    class FakeBERTopic:
        def __init__(self, *, umap_model, hdbscan_model, **_kwargs):
            self.umap_model = umap_model
            self.hdbscan_model = hdbscan_model
            self.c_tf_idf_ = None
        def fit_transform(self, texts, embeddings):
            topics = np.repeat(np.arange(4), 12)
            probabilities = np.full((len(texts), 4), 0.02)
            probabilities[np.arange(len(texts)), topics] = 0.94
            self.umap_model.embedding_ = np.asarray(embeddings)[:, :2]
            self.hdbscan_model.probabilities_ = np.full(len(texts), 0.94)
            self.hdbscan_model.outlier_scores_ = np.full(len(texts), 0.05)
            return topics.tolist(), probabilities
        def get_topic_info(self):
            return FakeInfo()
        def get_topic(self, topic_id):
            return [(themes[topic_id][0].split()[0], 1.0), ("education", 0.8)]
        def get_representative_docs(self, topic_id):
            return [rows[topic_id * 12]["texto_modelado"]]
        def get_topics(self):
            return {topic: self.get_topic(topic) for topic in range(4)}
        def save(self, path, **_kwargs):
            Path(path).mkdir(parents=True, exist_ok=True)

    monkeypatch.setitem(sys.modules, "bertopic", types.SimpleNamespace(BERTopic=FakeBERTopic))
    monkeypatch.setitem(sys.modules, "bertopic.vectorizers", types.SimpleNamespace(ClassTfidfTransformer=FakeCTFIDF))
    monkeypatch.setitem(sys.modules, "hdbscan", types.SimpleNamespace(HDBSCAN=FakeHDBSCAN))
    monkeypatch.setitem(sys.modules, "umap", types.SimpleNamespace(UMAP=FakeUMAP))
    monkeypatch.setattr(
        bertopic_model, "load_or_create_metadata_embeddings",
        lambda *_args, **_kwargs: (np.asarray(embeddings), {"fingerprint": "fixture", "dimension": 4}),
    )
    monkeypatch.setattr(bertopic_model, "load_or_create_embeddings", lambda *_args, **_kwargs: (np.asarray(embeddings), {"fingerprint": "fixture", "dimension": 4}))
    metadata = bertopic_model.run_bertopic(config)
    model_output = output / "bertopic" / "metadata_multilingual"
    docs = read_csv(model_output / "document_topics.csv")
    topics = read_csv(model_output / "topics.csv")
    assert metadata["documents"] == 48
    assert len(docs) == 48
    assert len([row for row in topics if row["topic_id"] != "-1"]) >= 2
    assert {row["document_id"] for row in docs} == {row["document_id"] for row in rows}
    assert json.loads((model_output / "model_metadata.json").read_text(encoding="utf-8"))["seed"] == 42
