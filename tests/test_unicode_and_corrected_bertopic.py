from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

from topic_modeling.bertopic_diagnostics import classify_heterogeneity
from topic_modeling.config import load_config
from topic_modeling.text_cleaning import clean_for_vectorizer, normalize_unicode_text
from topic_modeling.vectorization import build_vectorizer


@pytest.mark.parametrize("value", ["gestión", "dirección", "educação", "Bogotá", "México", "Córdoba"])
def test_unicode_diacritics_are_preserved(value):
    assert normalize_unicode_text(value) == value


def test_unicode_normalization_handles_combining_entities_controls_and_typography():
    source = "gestio\u0301n&nbsp;\x00‘pública’\r\nCórdoba—México"
    assert normalize_unicode_text(source) == "gestión 'pública'\nCórdoba-México"


def test_vectorizer_is_multilingual_unicode_and_uses_ngrams():
    config = load_config("config/topic_modeling.yml")
    vectorizer = build_vectorizer(config)
    texts = ["gestión escolar democrática durante journal amp x0d como se participación comunitaria"] * 2
    texts.append("liderazgo directivo institucional con familias y docentes")
    matrix = vectorizer.fit_transform([clean_for_vectorizer(text)[0] for text in texts])
    terms = set(vectorizer.get_feature_names_out())
    assert vectorizer.ngram_range == (1, 3)
    assert "gestión" in terms
    assert "gestión escolar" in terms
    assert not {"amp", "journal", "x0d", "during", "como", "se"} & terms
    assert matrix.shape[1] > 0


def test_mixed_synthetic_cluster_is_not_called_coherent():
    status = classify_heterogeneity(documents=80, minimum_size=35, contamination_status="domain_relevant", language_status="multilingual_topic", dominant_source_share=0.5, silhouette_mean=-0.1, semantic_dispersion=0.58, borderline_share=0.52)
    assert status == "heterogeneous_candidate"


def test_preferred_solution_has_stability_and_preserves_outliers_when_outputs_exist():
    root = Path("output/topic_models/bertopic/metadata_multilingual")
    selected = root / "selected_parameters.json"
    preferred = root / "preferred_solution"
    if not selected.exists() or not preferred.exists(): pytest.skip("corrected execution not generated")
    payload = json.loads(selected.read_text(encoding="utf-8")); chosen = payload["selected"]
    assert chosen["solution_status"] == "preferred_provisional"
    assert chosen["stability_status"] == "computed_five_runs"
    assert chosen["stability_ari_mean"] != ""
    docs = list(__import__("csv").DictReader((preferred / "document_topics.csv").open(encoding="utf-8")))
    assert any(row["original_topic"] == "-1" and row["accepted_reassignment"].casefold() == "false" for row in docs)
    hierarchy = list(__import__("csv").DictReader((preferred / "document_topic_hierarchy.csv").open(encoding="utf-8")))
    assert all(row["parent_topic_id"] == row["macro_topic_id"] for row in hierarchy if row["macro_topic_id"])


@pytest.mark.skipif(os.getenv("RUN_EMBEDDING_INTEGRATION") != "1", reason="opt-in local model integration")
def test_parallel_multilingual_documents_are_semantically_close():
    from sentence_transformers import SentenceTransformer
    config = load_config("config/topic_modeling.yml")
    model = SentenceTransformer(config["bertopic"]["embedding_model"], cache_folder="cache/topic_models/embeddings/models")
    texts = ["liderazgo escolar y participación comunitaria", "school leadership and community participation", "liderança escolar e participação comunitária"]
    emb = model.encode(texts, normalize_embeddings=True)
    similarities = np.asarray(emb) @ np.asarray(emb).T
    assert min(similarities[0, 1], similarities[0, 2], similarities[1, 2]) > 0.55
