import update_assistant_counts as u


def test_counts_are_replaced_everywhere_and_idempotent():
    html = ('<title>Notebook - 2.124 Obras</title><span>(2.124 FUENTES)</span>'
            '<div>📚 <b>2.087</b> Artículos Scrapeados</div><div>📖 <b>37</b> Libros y Textos</div>'
            '<p>tus <b>2.124 materiales</b> y 2.124 obras</p>')
    out = u.update(html, 4252, 37)
    assert "2.124" not in out and "2.087" not in out
    assert out.count("4.289") == 4 and "<b>4.252</b> Artículos" in out and "<b>37</b> Libros" in out
    assert u.update(out, 4252, 37) == out
