import csv
from pathlib import Path

from topic_modeling.topic_evaluation import _discover_models


ROOT = Path(__file__).resolve().parents[1]


def _rows(relative):
    with (ROOT / relative).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_provisional_labels_cover_selected_topics_without_claiming_validation():
    rows = _rows("output/topic_models/validation/topic_label_proposals.csv")
    assert {int(row["topic_id"]) for row in rows} == set(range(14))
    assert all(row["proposed_human_label"] for row in rows)
    assert all(row["label_status"] == "proposed_pending_documentary_validation" for row in rows)


def test_review_templates_have_no_prefilled_human_answers():
    for relative in (
        "output/topic_models/validation/topic_document_review.csv",
        "output/topic_models/validation/word_intrusion.csv",
        "output/topic_models/validation/topic_intrusion.csv",
        "output/topic_models/validation/outlier_review_sample.csv",
    ):
        rows = _rows(relative)
        assert rows
        human_fields = [field for field in rows[0] if field.startswith("human_")]
        assert human_fields
        assert all(not row[field].strip() for row in rows for field in human_fields)


def test_selected_solution_reconciles_and_dossiers_exist():
    docs = _rows("output/topic_models/bertopic/metadata_multilingual/preferred_solution/document_topics.csv")
    assert len(docs) == 2182
    assert sum(row["topic_id"] != "-1" for row in docs) == 1340
    assert sum(row["topic_id"] == "-1" for row in docs) == 842
    dossiers = ROOT / "output/topic_models/validation/topic_dossiers"
    assert {path.name for path in dossiers.glob("T*.md")} == {f"T{topic:02d}.md" for topic in range(14)}


def test_model_discovery_prefers_corrected_stm_runs():
    discovered = {key for key, _ in _discover_models(ROOT / "output/topic_models")}
    for language in ("es", "en", "pt"):
        assert f"stm/metadata_{language}_corrected" in discovered
        assert f"stm/metadata_{language}" not in discovered
    assert "bertopic/metadata_multilingual/preferred_solution" in discovered
    assert "bertopic/metadata_multilingual" not in discovered
