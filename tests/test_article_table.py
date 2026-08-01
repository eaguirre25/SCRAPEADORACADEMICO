from pathlib import Path

import generate_article_table


def test_generated_article_table_has_valid_css_and_javascript_braces(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "docs"
    data_dir.mkdir()
    output_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(generate_article_table, "DATA_DIR", data_dir)
    monkeypatch.setattr(generate_article_table, "OUT_DIR", output_dir)

    generate_article_table.main()

    html = (output_dir / "articulos.html").read_text(encoding="utf-8")
    assert "{{" not in html
    assert ":root{--bg:" in html
    assert "function render(){" in html
    assert "const ARTICLES = [];" in html
    assert "Buscar en título, autor, resumen, palabras clave o texto completo" in html
    assert '<script src="fulltext_search_index.js"></script>' in html
    assert "function fullTextMatches(q){" in html
    assert "function highlightHtml(value){" in html
    assert "<mark>" in html

    index_js = (output_dir / "fulltext_search_index.js").read_text(encoding="utf-8")
    assert "window.FULLTEXT_SEARCH_INDEX={};" in index_js
    assert 'window.FULLTEXT_SEARCH_META={"documents":0,"terms":0};' in index_js


def test_fulltext_index_links_pdf_text_to_the_article_by_doi():
    articles = [
        {"doi": "10.1000/first", "title": "Primer artículo"},
        {"doi": "10.1000/second", "title": "Segundo artículo"},
    ]
    corpus = [
        {"doi": "10.1000/FIRST", "texto": "Hallazgo microscópico exclusivo"},
        {"doi": "10.1000/unknown", "texto": "No debe incorporarse"},
    ]

    index, document_count = generate_article_table.build_fulltext_index(articles, corpus)

    assert document_count == 1
    assert index["microscopico"] == [0]
    assert index["exclusivo"] == [0]
    assert "incorporarse" not in index
