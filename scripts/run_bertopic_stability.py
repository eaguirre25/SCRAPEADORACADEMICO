#!/usr/bin/env python3
import argparse, json, os, sys
from pathlib import Path
if os.name=="nt": os.environ.pop("SSLKEYLOGFILE",None); os.environ["PATH"]=str(Path(sys.executable).resolve().parent)+os.pathsep+os.environ.get("PATH","")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from topic_modeling.bertopic_search import run_bertopic_stability
from topic_modeling.config import load_config
p=argparse.ArgumentParser(); p.add_argument("--config",default="config/topic_modeling.yml"); p.add_argument("--finalists-only",action="store_true"); a=p.parse_args()
print(json.dumps(run_bertopic_stability(load_config(a.config),finalists_only=a.finalists_only),ensure_ascii=False,indent=2))
