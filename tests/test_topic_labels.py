from topic_modeling.topic_labels import automatic_label, resolve_label


def test_human_label_takes_precedence():
    human = {("stm", "2"): {"human_label": "Liderazgo distribuido", "label_status": "validated", "label_notes": "revisado"}}
    result = resolve_label("stm", 2, automatic_label(["school", "leadership"]), human)
    assert result["topic_label"] == "Liderazgo distribuido"
    assert result["label_status"] == "validated"
