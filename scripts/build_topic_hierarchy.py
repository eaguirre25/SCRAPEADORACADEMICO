#!/usr/bin/env python3
"""Rebuild the preferred BERTopic hierarchy without refitting embeddings or clusters."""
from __future__ import annotations

import argparse
import runpy
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--config", default="config/topic_modeling.yml")
args = parser.parse_args()
sys.argv = ["evaluate_topic_quality.py", "--config", args.config]
runpy.run_path("scripts/evaluate_topic_quality.py", run_name="__main__")

