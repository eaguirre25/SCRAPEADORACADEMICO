from topic_modeling.corpus_builder import weighted_metadata_text


def test_weighted_metadata_skips_null_strings():
    text, strategy = weighted_metadata_text(
        {"title": "Dirección escolar", "keywords": "nan", "abstract": "Participación comunitaria"},
        {"title": 3, "keywords": 2, "abstract": 1},
    )
    assert text.count("Dirección escolar") == 3
    assert "nan" not in text
    assert strategy == "title_keywords_abstract"

