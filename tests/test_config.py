from pathlib import Path

from topic_modeling.config import load_config


def test_config_loads_and_overrides():
    config = load_config(Path("config/topic_modeling.yml"), ["project.seed=7", "bertopic.calculate_probabilities=false"])
    assert config["project"]["seed"] == 7
    assert config["bertopic"]["calculate_probabilities"] is False

