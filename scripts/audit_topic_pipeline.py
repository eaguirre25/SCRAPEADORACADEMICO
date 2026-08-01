#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from topic_modeling.config import load_config
from topic_modeling.pipeline_audit import audit_topic_pipeline
p=argparse.ArgumentParser(); p.add_argument("--config",default="config/topic_modeling.yml"); a=p.parse_args()
print(json.dumps(audit_topic_pipeline(load_config(a.config)),ensure_ascii=False,indent=2))
