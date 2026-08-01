import sys
import types

import numpy as np

from topic_modeling.deduplication import audit_and_resolve_duplicates
from topic_modeling.embeddings import load_or_create_metadata_embeddings
from topic_modeling.relevance import classify_relevance
from topic_modeling.topic_evaluation import temporal_accounting_issues, topics_over_time


def test_canonical_publications_merge_only_exact_high_confidence_duplicates():
    rows = [
        {"record_id": "a", "doi": "https://doi.org/10.1/ABC", "title": "School leadership", "publication_year": "2024", "authors": "Ana Pérez", "abstract": "short"},
        {"record_id": "b", "doi": "10.1/abc", "title": "School leadership expanded", "publication_year": "2024", "authors": "Ana Pérez", "abstract": "a more complete abstract"},
        {"record_id": "c", "doi": "", "title": "School leadership practices", "publication_year": "2024", "authors": "Ana Pérez"},
    ]
    canonical, exact, probable, resolution = audit_and_resolve_duplicates(rows)
    assert len(canonical) == 2
    assert len(exact) == 2
    assert {row["publication_document_id"] for row in exact} == {"doi:10.1/abc"}
    assert {row["decision"] for row in resolution} == {"kept_canonical", "merged_exact"}
    assert probable == []


def test_relevance_rules_separate_school_domain_from_known_false_positives():
    records = [
        {"document_id": "school", "title": "School principal leadership and school improvement", "abstract": "Management of secondary schools", "keywords": "school leadership"},
        {"document_id": "nursing", "title": "Clinical nursing leadership", "abstract": "Hospital patient care management", "keywords": "nursing"},
        {"document_id": "tax", "title": "Tax management and accounting", "abstract": "Treasury administration", "keywords": "taxation"},
        {"document_id": "higher", "title": "University administration", "abstract": "Higher education management", "keywords": "university"},
        {"document_id": "ambiguous", "title": "Leadership practices", "abstract": "An organizational qualitative study", "keywords": "leadership"},
    ]
    decisions = {row["publication_document_id"]: row for row in classify_relevance(records, {"relevance": {}})}
    assert decisions["school"]["relevance_status"] == "included"
    assert decisions["nursing"]["relevance_status"] == "excluded"
    assert decisions["tax"]["relevance_status"] == "excluded"
    assert decisions["higher"]["relevance_status"] in {"excluded", "borderline"}
    assert decisions["ambiguous"]["relevance_status"] in {"borderline", "manual_review"}


def test_metadata_embeddings_are_weighted_by_available_fields(tmp_path, monkeypatch):
    vectors = {"title": [1.0, 0.0], "abstract": [0.0, 1.0], "keywords": [1.0, 1.0]}

    class FakeSentenceTransformer:
        def __init__(self, *_args, **_kwargs):
            pass
        def encode(self, texts, **_kwargs):
            return np.asarray([vectors[text] for text in texts], dtype=np.float32)

    monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer))
    documents = [{"document_id": "d1", "title_text": "title", "abstract_text": "abstract", "keywords_text": "keywords"}]
    config = {
        "paths": {"cache_root": str(tmp_path)},
        "bertopic": {"embedding_model": "fixture", "batch_size": 8},
        "metadata_embeddings": {"title_weight": 0.5, "abstract_weight": 0.5, "keywords_weight": 0.0},
    }
    embedded, manifest = load_or_create_metadata_embeddings(documents, config, force=True)
    np.testing.assert_allclose(embedded[0], np.asarray([1, 1]) / np.sqrt(2), atol=1e-6)
    assert manifest["combination"] == "weighted_field_average"


def test_multilingual_embeddings_place_parallel_school_documents_nearby(tmp_path, monkeypatch):
    vectors = {
        "dirección escolar": [1.0, 0.01], "school leadership": [0.99, 0.02],
        "gestão escolar": [0.98, 0.01], "hospital nursing": [0.0, 1.0],
    }

    class FakeMultilingualModel:
        def __init__(self, *_args, **_kwargs):
            pass
        def encode(self, texts, **_kwargs):
            return np.asarray([vectors[text] for text in texts], dtype=np.float32)

    monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(SentenceTransformer=FakeMultilingualModel))
    documents = [
        {"document_id": "es", "title_text": "dirección escolar", "abstract_text": "", "keywords_text": ""},
        {"document_id": "en", "title_text": "school leadership", "abstract_text": "", "keywords_text": ""},
        {"document_id": "pt", "title_text": "gestão escolar", "abstract_text": "", "keywords_text": ""},
        {"document_id": "off", "title_text": "hospital nursing", "abstract_text": "", "keywords_text": ""},
    ]
    config = {
        "paths": {"cache_root": str(tmp_path)}, "bertopic": {"embedding_model": "multilingual-fixture", "batch_size": 8},
        "metadata_embeddings": {"title_weight": 1.0, "abstract_weight": 0.0, "keywords_weight": 0.0},
    }
    embedded, _ = load_or_create_metadata_embeddings(documents, config, force=True)
    school_similarity = embedded[:3] @ embedded[:3].T
    off_topic_similarity = embedded[:3] @ embedded[3]
    assert np.min(school_similarity[np.triu_indices(3, 1)]) > 0.99
    assert np.max(off_topic_similarity) < 0.05


def test_bertopic_temporal_counts_do_not_double_count_documents():
    rows = [
        {"document_id": "a", "topic_id": "0", "year": "2024", "topic_probability": "0.8", "is_outlier": "false", "corpus": "metadata"},
        {"document_id": "b", "topic_id": "1", "year": "2024", "topic_probability": "0.7", "is_outlier": "false", "corpus": "metadata"},
        {"document_id": "c", "topic_id": "-1", "year": "2024", "topic_probability": "0.2", "is_outlier": "true", "corpus": "metadata"},
    ]
    config = {"validation": {"bootstrap_samples": 20}, "project": {"seed": 42, "end_year": 2026}}
    result = topics_over_time(rows, config, "fixture")
    assert {row["documents_in_year"] for row in result} == {3}
    assert sum(row["cluster_documents"] for row in result) == 2
    assert {row["outlier_share"] for row in result} == {round(1 / 3, 6)}


def test_stm_temporal_dominant_counts_and_effective_mass_reconcile():
    rows = [
        {"year": "2024", "documents_in_year": "3", "dominant_topic_documents": "2", "effective_topic_mass": "1.4"},
        {"year": "2024", "documents_in_year": "3", "dominant_topic_documents": "1", "effective_topic_mass": "1.6"},
    ]
    assert temporal_accounting_issues(rows, "stm") == []
    rows[1]["dominant_topic_documents"] = "2"
    assert "dominant=4" in temporal_accounting_issues(rows, "stm")[0]
