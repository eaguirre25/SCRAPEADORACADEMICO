import pytest
from topic_modeling.language_detection import detect_language


@pytest.mark.parametrize("text, expected", [
    ("Los equipos directivos de las escuelas secundarias organizan el trabajo pedagógico y acompañan a los docentes en contextos de desigualdad social.", "es"),
    ("School principals coordinate teaching and support teachers in public secondary schools. The study investigates school leadership practices and community participation.", "en"),
    ("A gestão das escolas públicas envolve a participação dos professores e da comunidade. Este estudo analisa as práticas dos diretores escolares e a organização do trabalho pedagógico.", "pt"),
])
def test_supported_language_paragraphs(text, expected):
    pytest.importorskip("lingua")
    assert detect_language(text)[0] == expected


def test_turkish_is_not_forced_into_a_modeling_language():
    pytest.importorskip("lingua")
    text = "Okul müdürlerinin öğretmenlerle ilişkileri ve eğitim yönetimi uygulamaları araştırılmıştır. Bu çalışmada öğretmenlerin okul yöneticilerine ilişkin görüşleri incelenmiştir."
    code, _, status = detect_language(text)
    assert (code, status) == ("tr", "unsupported_language")


def test_short_ambiguous_text_remains_unknown():
    assert detect_language("school escola escuela")[0] == "und"
