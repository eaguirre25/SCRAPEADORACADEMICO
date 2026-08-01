from topic_modeling.text_cleaning import clean_for_bertopic, clean_for_stm, remove_references


def test_bertopic_keeps_domain_language_and_removes_metadata():
    text, _ = clean_for_bertopic("La gestión escolar mejora. https://example.org DOI: 10.1234/abc")
    assert "gestión escolar" in text
    assert "https" not in text
    assert "10.1234" not in text


def test_reference_heading_is_cut_only_late_in_document():
    body = "Introducción\n" + ("contenido escolar " * 100)
    result = remove_references(body + "\nREFERENCIAS\nAutor, 2020")
    assert result.detected
    assert "Autor" not in result.text
    early = remove_references("REFERENCIAS\n" + body)
    assert not early.detected


def test_stm_removes_punctuation_but_not_domain_by_default():
    text, _ = clean_for_stm("Dirección escolar: liderazgo, gestión y participación.")
    assert "dirección escolar" in text
    assert ":" not in text

