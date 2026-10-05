import json

import build_weekly_reports as bw

EMAIL = """## Selección semanal — 27 de septiembre de 2026

Esta semana prioricé trabajos sobre territorio.

1. **Hallinger, P. (2026). The myths of instructional leadership: Conceptual drift. _School Leadership & Management_. https://doi.org/10.1080/13632434.2026.2697983**
DOI: 10.1080/13632434.2026.2697983
Por qué importa: critica el principal-centrismo.

2. **Grissom, J. A., & Doughty, M. (2026). _Understanding professional learning for principals_. Vanderbilt University. https://doi.org/10.59656/EL-LS3669.001**
   Informe basado en 63 entrevistas.

### Prioridad de lectura
Empezaría por **Hallinger**.

**Estado de biblioteca:** la sincronización quedó pendiente.
"""


def test_parses_email_markdown():
    r = bw.parse_markdown(EMAIL, "2026-09-27")
    assert r["title"] == "Selección semanal — 27 de septiembre de 2026"
    assert r["intro"] == "Esta semana prioricé trabajos sobre territorio."
    assert r["priority"] == "Empezaría por Hallinger."
    a, b = r["items"]
    assert a["authors"] == "Hallinger, P." and a["year"] == 2026
    assert a["title"] == "The myths of instructional leadership: Conceptual drift"
    assert a["doi"] == "10.1080/13632434.2026.2697983" and a["why"] == "critica el principal-centrismo."
    assert "**" not in a["apa"] and "_" not in a["apa"].replace("https://", "")
    assert b["title"] == "Understanding professional learning for principals"
    assert b["authors"] == "Grissom, J. A.; Doughty, M." and b["doi"] == "10.59656/el-ls3669.001"
    assert b["why"] == "Informe basado en 63 entrevistas."


def test_build_merges_json_and_markdown_sorted(tmp_path, monkeypatch):
    src = tmp_path / "weekly"
    src.mkdir()
    (src / "2026-09-27.md").write_text(EMAIL, encoding="utf-8")
    (src / "2026-08-16.json").write_text(json.dumps({"date": "2026-08-16", "title": "Vieja", "items": [{"title": "x"}]}), encoding="utf-8")
    (src / "notas.md").write_text("ignorar", encoding="utf-8")
    (src / "2026-10-04.md").write_text("Sin ítems reconocibles", encoding="utf-8")
    out = tmp_path / "weekly_reports.json"
    monkeypatch.setattr(bw, "SRC", src)
    monkeypatch.setattr(bw, "OUT", out)
    bw.main()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [r["date"] for r in data] == ["2026-08-16", "2026-09-27"]
