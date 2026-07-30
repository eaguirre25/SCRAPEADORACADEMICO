from topic_modeling.topic_comparison import align_topics


def test_alignment_finds_shared_document_cluster():
    stm_docs = [{"document_id": "a", "topic_id": "1"}, {"document_id": "b", "topic_id": "1"}]
    bert_docs = [{"document_id": "a", "topic_id": "4"}, {"document_id": "b", "topic_id": "4"}]
    stm_topics = [{"topic_id": "1", "top_words": "liderazgo | escuela"}]
    bert_topics = [{"topic_id": "4", "top_words": "liderazgo | gestión"}]
    rows = align_topics(stm_docs, bert_docs, stm_topics, bert_topics)
    assert rows[0]["jaccard_overlap"] == 1.0
    assert rows[0]["alignment_status"] == "one_to_one"
