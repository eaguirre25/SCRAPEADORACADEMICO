import apa_citation


def test_spanish_names_keep_both_surnames():
    assert apa_citation.format_author("Laura Cristina Barba Miranda", "es") == "Barba Miranda, L. C."
    assert apa_citation.format_author("Humberto Garcia Caucha", "es") == "Garcia Caucha, H."


def test_second_given_name_is_not_read_as_surname():
    # Sin la lista de nombres de pila "Isabel" se leeria como primer apellido.
    assert apa_citation.format_author("Ramona Isabel Ferreira", "es") == "Ferreira, R. I."


def test_english_names_use_a_single_surname():
    assert apa_citation.format_author("John Michael Smith", "en") == "Smith, J. M."


def test_already_inverted_names_are_respected():
    assert apa_citation.format_author("Palomino Huapaya, Juan Alberto") == "Palomino Huapaya, J. A."


def test_particles_travel_with_the_surname():
    assert apa_citation.format_author("Juan Moises de la Serna", "es") == "de la Serna, J. M."


def test_author_list_follows_apa_separators():
    names = ["Ana Perez", "Luis Gomez", "Marta Diaz"]
    assert apa_citation.format_author_list(names, "es") == "Perez, A., Gomez, L., & Diaz, M."


def test_author_list_truncates_beyond_twenty():
    names = [f"Nombre{i} Apellido{i}" for i in range(25)]
    listed = apa_citation.format_author_list(names, "es")
    assert listed.startswith("Apellido0, N.,")
    assert "Apellido18, N., ... Apellido24, N." in listed
    assert "Apellido19" not in listed and "Apellido23" not in listed


def test_journal_article_carries_visible_placeholders():
    citation = apa_citation.build_citation({
        "authors": "Laura Cristina Barba Miranda",
        "title": "Gestion escolar y liderazgo",
        "publication_year": "2021",
        "origin": "Revista EDUCARE",
        "document_type": "article",
        "doi": "10.46498/reduipb.v25i1.1462",
    })
    text = apa_citation.plain_text(citation)
    assert text.startswith("Barba Miranda, L. C. (2021). Gestion escolar y liderazgo.")
    assert "Revista EDUCARE, [vol]([num]), [pp.]." in text
    assert text.endswith("https://doi.org/10.46498/reduipb.v25i1.1462")
    assert citation.missing == ["volumen", "numero", "paginas"]
    assert citation.italic == "Revista EDUCARE"


def test_dissertation_uses_the_thesis_bracket():
    citation = apa_citation.build_citation({
        "authors": "Ana Guzman Olaya",
        "title": "Estrategia de gestion escolar",
        "publication_year": "2021",
        "origin": "Universidad de La Salle",
        "document_type": "dissertation",
        "url": "https://hdl.handle.net/20.500.14625/32317",
    })
    assert "[Tesis, Universidad de La Salle]." in apa_citation.plain_text(citation)
    assert citation.kind == "tesis"


def test_missing_author_moves_the_title_forward():
    citation = apa_citation.build_citation({
        "authors": "",
        "title": "Repensando la gestion escolar",
        "publication_year": "2021",
        "origin": "Revista X",
        "document_type": "article",
    })
    assert apa_citation.plain_text(citation).startswith("Repensando la gestion escolar. (2021).")


def test_repository_origin_is_not_reported_as_a_journal():
    citation = apa_citation.build_citation({
        "authors": "Ana Perez",
        "title": "Un documento",
        "publication_year": "2024",
        "origin": "CONICET Digital",
        "document_type": "article",
    })
    assert "[Revista]" in apa_citation.plain_text(citation)
    assert "revista" in citation.missing


def test_shouting_titles_become_sentence_case():
    assert apa_citation.sentence_case("PLATAFORMIZACAO DA GESTAO PUBLICA") == "Plataformizacao da gestao publica"
    assert apa_citation.sentence_case("Gestion escolar y TIC") == "Gestion escolar y TIC"


def test_escaped_markup_is_removed_from_the_title():
    citation = apa_citation.build_citation({
        "authors": "Ana Perez",
        "title": "Politicas de &lt;i&gt;accountability&lt;/i&gt; escolar",
        "publication_year": "2022",
        "origin": "Reforma y democracia.",
        "document_type": "article",
    })
    text = apa_citation.plain_text(citation)
    assert "Politicas de accountability escolar" in text
    # El punto final del nombre de revista no debe duplicarse ante el volumen.
    assert "Reforma y democracia, [vol]" in text


def test_html_flavour_italicises_the_container():
    citation = apa_citation.build_citation({
        "authors": "Ana Perez",
        "title": "Un titulo",
        "publication_year": "2020",
        "origin": "Revista Educacion",
        "document_type": "article",
    })
    assert "<em>Revista Educacion</em>" in apa_citation.citation_html(citation)
