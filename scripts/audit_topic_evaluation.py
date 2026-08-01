#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topic_modeling.config import load_config
from topic_modeling.evaluation_metrics import build_evaluation_audit

parser = argparse.ArgumentParser(description="Audit topic-evaluation functions, inputs and outputs without fitting models.")
parser.add_argument("--config", default="config/topic_modeling.yml")
args = parser.parse_args()
config = load_config(args.config)
target = Path(config["paths"]["output_root"]) / "evaluation/evaluation_audit.json"
audit = build_evaluation_audit(config, corrections_applied=False)
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
print(target)
