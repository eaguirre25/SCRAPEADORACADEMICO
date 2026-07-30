#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from topic_modeling.bertopic_model import run_bertopic
from topic_modeling.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run multilingual BERTopic with cached embeddings.")
    parser.add_argument("--config", default="config/topic_modeling.yml")
    parser.add_argument("--corpus-unit", choices=["metadata", "fulltext"], default="metadata")
    parser.add_argument("--force-embeddings", action="store_true")
    parser.add_argument("--set", action="append", default=[], dest="overrides")
    args = parser.parse_args()
    metadata = run_bertopic(load_config(args.config, args.overrides), corpus_unit=args.corpus_unit, force_embeddings=args.force_embeddings)
    print(json.dumps(metadata, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
