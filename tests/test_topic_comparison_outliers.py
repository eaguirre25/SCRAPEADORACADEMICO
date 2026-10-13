from topic_modeling.corpus_builder import read_csv, write_csv
from topic_modeling.topic_comparison import align_topics, compare_models


def test_outliers_cannot_form_a_thematic_alignment_even_with_matching_words():
    stm_docs = [{"document_id": "a", "topic_id": "1", "topic_probability": "0.9"},
                {"document_id": "b", "topic_id": "1", "topic_probability": "0.9"}]
    bert_docs = [{"document_id": "a", "topic_id": "-1", "topic_probability": "0.9"},
                 {"document_id": "b", "topic_id": "0", "topic_probability": "0.9"}]
    stm_topics = [{"topic_id": "1", "top_words": "leadership", "representative_titles": "Shared title"}]
    bert_topics = [{"topic_id": "-1", "top_words": "leadership", "representative_titles": "Shared title"},
                   {"topic_id": "0", "top_words": "leadership", "representative_titles": "Shared title"}]
    rows = align_topics(stm_docs, bert_docs, stm_topics, bert_topics)
    assert len(rows) == 1
    assert rows[0]["bertopic_topic"] == "0"
    assert rows[0]["document_overlap"] == 1
    assert rows[0]["document_jaccard"] == 1
    assert rows[0]["relationship"] == "one_to_one"


def test_comparison_keeps_outlier_documents_and_exports_exclusion_audit(tmp_path):
    bert = tmp_path / "bertopic" / "metadata_multilingual" / "preferred_solution"
    stm = tmp_path / "stm" / "metadata_es_corrected"
    stm_docs = [{"document_id": "a", "topic_id": "1", "language": "es", "topic_probability": "0.9"},
                {"document_id": "b", "topic_id": "1", "language": "es", "topic_probability": "0.9"}]
    bert_docs = [{"document_id": "a", "topic_id": "-1", "language": "es", "topic_probability": "0.9"},
                 {"document_id": "b", "topic_id": "0", "language": "es", "topic_probability": "0.9"}]
    write_csv(stm / "document_topics.csv", stm_docs)
    write_csv(bert / "document_topics.csv", bert_docs)
    write_csv(stm / "topics.csv", [{"topic_id": "1", "model": "STM-METADATA-ES", "top_words": "leadership"}])
    write_csv(bert / "topics.csv", [{"topic_id": "0", "model": "BERTopic", "top_words": "leadership"}])
    summary = compare_models({"paths": {"output_root": str(tmp_path)}, "multilingual": {"stm_languages": ["es"]}})
    assert summary["shared_documents"] == 2
    assert summary["shared_documents_excluded_from_topic_alignment"] == 1
    assert summary["bertopic_outliers"] == 1
    docs = {row["publication_document_id"]: row for row in read_csv(tmp_path / "comparison" / "document_alignment.csv")}
    assert docs["a"]["relationship"] == "bertopic_outlier_not_aligned"
    assert float(docs["a"]["combined_alignment"]) == 0
    assert docs["b"]["relationship"] == "one_to_one"
    excluded = read_csv(tmp_path / "comparison" / "outlier_alignment_exclusions.csv")
    assert [row["publication_document_id"] for row in excluded] == ["a"]
