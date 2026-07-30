#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from topic_modeling.config import load_config
from topic_modeling.corpus_builder import build_corpora, export_corpora


def main() -> None:
    parser = argparse.ArgumentParser(description="Build metadata and full-text analytical corpora.")
    parser.add_argument("--config", default="config/topic_modeling.yml")
    parser.add_argument("--set", action="append", default=[], dest="overrides", help="Override dotted.key=value")
    args = parser.parse_args()
    config = load_config(args.config, args.overrides)
    result = build_corpora(config)
    export_corpora(config, result)
    print(f"metadata={len(result.metadata)} fulltext={len(result.fulltext)} excluded={len(result.excluded)} duplicates={len(result.duplicates)}")


if __name__ == "__main__":
    main()
