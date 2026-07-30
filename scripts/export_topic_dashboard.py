#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topic_modeling.config import load_config
from topic_modeling.exports import export_validation_template

parser = argparse.ArgumentParser()
parser.add_argument("--config", default="config/topic_modeling.yml")
args = parser.parse_args()
print(f"validation_topics={export_validation_template(load_config(args.config))}")
