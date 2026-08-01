#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if os.name == "nt":
    os.environ.pop("SSLKEYLOGFILE", None)
    python_root = str(Path(sys.executable).resolve().parent)
    os.environ["PATH"] = python_root + os.pathsep + os.environ.get("PATH", "")
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from topic_modeling.bertopic_search import search_bertopic_parameters
from topic_modeling.config import load_config


parser = argparse.ArgumentParser()
parser.add_argument("--config", default="config/topic_modeling.yml")
parser.add_argument("--corpus-unit", choices=["metadata", "fulltext"], default="metadata")
parser.add_argument("--output-name", default="metadata_multilingual")
parser.add_argument("--force-embeddings", action="store_true")
args = parser.parse_args()
rows = search_bertopic_parameters(
    load_config(args.config), corpus_unit=args.corpus_unit, output_name=args.output_name,
    force_embeddings=args.force_embeddings,
)
print(json.dumps(rows[:3], ensure_ascii=False, indent=2))
