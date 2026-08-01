from topic_modeling.topic_evaluation import topic_word_diversity, topics_over_time


def test_topic_word_diversity():
    words = [
        {"topic_id": "1", "term": "school"}, {"topic_id": "1", "term": "leadership"},
        {"topic_id": "2", "term": "school"}, {"topic_id": "2", "term": "inclusion"},
    ]
    assert topic_word_diversity(words) == 0.75


def test_topics_over_time_marks_final_year_incomplete():
    cfg = {"project": {"seed": 42, "end_year": 2026}, "validation": {"bootstrap_samples": 10}}
    rows = [{"topic_id": "1", "year": "2026", "topic_probability": "0.8", "is_outlier": "False"}]
    result = topics_over_time(rows, cfg, "bertopic")
    assert result[0]["year_complete"] is False
