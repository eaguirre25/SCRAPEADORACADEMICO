#!/usr/bin/env python3
"""
Chequeo liviano del dashboard y de los insumos STM.

No recalcula el STM. Verifica si los archivos necesarios existen y genera
un reporte JSON auditable para GitHub Actions.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any


DATA_DIR = Path("data")
DOCS_DIR = Path("docs")
OUTPUT_DIR = Path("output")
REPORT = DATA_DIR / "dashboard_healthcheck.json"


def count_csv(path: Path) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    csv.field_size_limit(20_000_000)
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            return sum(1 for _ in csv.DictReader(fh))
    except Exception:
        return 0


def file_info(path: Path) -> Dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }


def main() -> None:
    master = DATA_DIR / "master_records.csv"
    review = DATA_DIR / "review_records.csv"
    rejected = DATA_DIR / "rejected_records.csv"
    dashboard = DOCS_DIR / "index.html"
    stm_files = {
        "corpus": DATA_DIR / "corpus.csv",
        "tabla_topicos": OUTPUT_DIR / "tabla_topicos.csv",
        "document_topics": OUTPUT_DIR / "document_topics.csv",
        "stm_model": OUTPUT_DIR / "stm_model.rds",
        "informe_stm": OUTPUT_DIR / "informe_stm.html",
    }

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dashboard": file_info(dashboard),
        "records": {
            "master_high_relevance": count_csv(master),
            "review": count_csv(review),
            "rejected": count_csv(rejected),
        },
        "stm_inputs_outputs": {name: file_info(path) for name, path in stm_files.items()},
        "stm_status": "ok" if all(path.exists() and path.stat().st_size > 0 for path in stm_files.values()) else "missing_or_not_regenerated",
        "note": (
            "El workflow operativo genera docs/index.html desde data/master_records.csv. "
            "El STM requiere data/corpus.csv y salida R en output/. Si esos archivos faltan, "
            "el dashboard de tres columnas funciona, pero la capa STM no queda actualizada."
        ),
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=== Dashboard healthcheck ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
