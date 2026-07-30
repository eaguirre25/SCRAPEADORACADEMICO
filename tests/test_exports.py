from topic_modeling.corpus_builder import read_csv, write_csv
from topic_modeling.exports import export_method_report, export_validation_template


def test_validation_export_preserves_human_review(tmp_path):
    root = tmp_path / "output"
    write_csv(root / "stm" / "topics.csv", [{"topic_id": "1", "automatic_label": "Escuela", "human_label": ""}])
    config = {"paths": {"output_root": str(root)}}
    assert export_validation_template(config) == 1
    template = root / "validation" / "topic_validation_template.csv"
    rows = read_csv(template)
    rows[0]["human_label"] = "Liderazgo escolar"
    rows[0]["validation_status"] = "validated"
    write_csv(template, rows)
    export_validation_template(config)
    preserved = read_csv(template)[0]
    assert preserved["human_label"] == "Liderazgo escolar"
    assert preserved["validation_status"] == "validated"


def test_method_report_is_created(tmp_path):
    config = {"paths": {"output_root": str(tmp_path)}, "project": {"seed": 42, "start_year": 2020, "end_year": 2026}}
    target = export_method_report(config)
    assert target.exists()
    assert "no son equivalentes" in target.read_text(encoding="utf-8")
