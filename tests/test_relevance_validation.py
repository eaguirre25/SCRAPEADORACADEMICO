import importlib.util
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ev", ROOT / "scripts" / "evaluate_relevance_validation.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def test_weighted_precision_and_recall(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Muestra"
    ws.append(["record_id", "pertinente"])
    est = wb.create_sheet("Estratos")
    est.append(["record_id", "fuente", "decision_filtro"])
    pop = wb.create_sheet("Poblacion")
    pop.append(["fuente", "decision_filtro", "registros", "muestra"])
    # Incluidos: 3 de 4 pertinentes (población 400). No incluidos: 1 de 4 (población 100).
    for i, label in enumerate(["si", "si", "si", "no"]):
        ws.append([f"a{i}", label]); est.append([f"a{i}", "OpenAlex", "incluido"])
    for i, label in enumerate(["si", "no", "no", "no", "dudoso"]):
        ws.append([f"b{i}", label]); est.append([f"b{i}", "OpenAlex", "no incluido"])
    pop.append(["OpenAlex", "incluido", 400, 4])
    pop.append(["OpenAlex", "no incluido", 100, 5])
    path = tmp_path / "m.xlsx"
    wb.save(path)
    result = ev.evaluate(path)
    assert result["total"]["precision"] == 0.75
    assert result["total"]["exhaustividad"] == round(300 / (300 + 25), 3)
    assert result["estratos"]["OpenAlex / no incluido"]["dudoso"] == 1
