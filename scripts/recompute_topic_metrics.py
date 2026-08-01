#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topic_modeling.config import load_config
from topic_modeling.evaluation_metrics import recompute_evaluation

parser = argparse.ArgumentParser(description="Recompute evaluation metrics from frozen topic-model artifacts.")
parser.add_argument("--config", default="config/topic_modeling.yml")
parser.add_argument("--model", choices=["preferred"], default="preferred")
parser.add_argument("--recompute-model", choices=["false", "true"], default="false")
args = parser.parse_args()
result = recompute_evaluation(load_config(args.config), recompute_model=args.recompute_model == "true")
print(json.dumps(result, ensure_ascii=False, indent=2))
