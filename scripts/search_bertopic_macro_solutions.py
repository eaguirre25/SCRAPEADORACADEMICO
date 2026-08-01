#!/usr/bin/env python3
import argparse, json, os, sys
from pathlib import Path
if os.name=="nt":
    os.environ.pop("SSLKEYLOGFILE",None); os.environ["PATH"]=str(Path(sys.executable).resolve().parent)+os.pathsep+os.environ.get("PATH","")
    try:
        import truststore; truststore.inject_into_ssl()
    except ImportError: pass
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from topic_modeling.bertopic_search import search_bertopic_parameters
from topic_modeling.config import load_config
p=argparse.ArgumentParser(); p.add_argument("--config",default="config/topic_modeling.yml"); p.add_argument("--force-embeddings",action="store_true"); a=p.parse_args()
rows=search_bertopic_parameters(load_config(a.config),force_embeddings=a.force_embeddings); print(json.dumps(rows[:5],ensure_ascii=False,indent=2))
