from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml


def _coerce(value: str) -> Any:
    try:
        return yaml.safe_load(value)
    except yaml.YAMLError:
        return value


def _set_nested(config: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    node = config
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def load_config(path: str | Path, overrides: list[str] | None = None) -> dict[str, Any]:
    source = Path(path)
    with source.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    config = copy.deepcopy(config)
    for key, value in os.environ.items():
        if key.startswith("TOPIC_MODELING__"):
            dotted = key.removeprefix("TOPIC_MODELING__").lower().replace("__", ".")
            _set_nested(config, dotted, _coerce(value))
    for override in overrides or []:
        if "=" not in override:
            raise ValueError(f"Invalid override {override!r}; expected key=value")
        key, value = override.split("=", 1)
        _set_nested(config, key, _coerce(value))
    required = ["project", "paths", "corpus", "stm", "bertopic", "validation"]
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError("Missing configuration sections: " + ", ".join(missing))
    return config

