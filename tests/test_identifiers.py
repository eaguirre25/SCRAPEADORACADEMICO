from topic_modeling.identifiers import normalize_doi, stable_document_id


def test_doi_is_normalized_and_stable():
    left = stable_document_id({"doi": "https://doi.org/10.1234/ABC.1"})
    right = stable_document_id({"doi": "doi:10.1234/abc.1"})
    assert left == right == "doi:10.1234/abc.1"
    assert normalize_doi("https://doi.org/10.1234/ABC.1.") == "10.1234/abc.1"


def test_hash_fallback_is_stable():
    record = {"title": "Dirección escolar y mejora", "publication_year": "2024", "authors": "Pérez, Ana; López, B"}
    assert stable_document_id(record) == stable_document_id(dict(record))
    assert stable_document_id(record).startswith("hash:")

