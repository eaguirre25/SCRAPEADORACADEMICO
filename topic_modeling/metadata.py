from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


def package_versions(names: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in names:
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = "not-installed"
    return result


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, encoding="utf-8").strip()
    except Exception:
        return "unknown"


def base_metadata(config: dict[str, Any], *, model: str, documents: int, discarded: int, elapsed_seconds: float) -> dict[str, Any]:
    return {
        "model": model,
        "seed": int(config["project"]["seed"]),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "documents": documents,
        "discarded_documents": discarded,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "embedding_model": config["bertopic"].get("embedding_model"),
        "configuration": config,
        "packages": package_versions(["bertopic", "sentence-transformers", "umap-learn", "hdbscan", "scikit-learn", "numpy", "pandas"]),
    }


def write_metadata(path: str | Path, metadata: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

