#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topic_modeling.config import load_config
from topic_modeling.evaluation_metrics import recompute_evaluation

parser = argparse.ArgumentParser()
parser.add_argument("--config", default="config/topic_modeling.yml")
args = parser.parse_args()
print(json.dumps(recompute_evaluation(load_config(args.config), recompute_model=False), ensure_ascii=False, indent=2))
