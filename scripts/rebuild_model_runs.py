#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topic_modeling.config import load_config
from topic_modeling.evaluation_metrics import rebuild_model_runs

parser = argparse.ArgumentParser(description="Rebuild model run lineage without fitting any model.")
parser.add_argument("--config", default="config/topic_modeling.yml")
args = parser.parse_args()
rows = rebuild_model_runs(load_config(args.config))
print(json.dumps({"runs": len(rows), "preferred": sum(bool(row["is_preferred_model"]) for row in rows)}, ensure_ascii=False))
