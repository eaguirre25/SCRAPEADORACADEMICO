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
