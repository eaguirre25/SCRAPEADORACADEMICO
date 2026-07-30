#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Orchestrate the hybrid topic-modeling pipeline.")
    parser.add_argument("--config", default="config/topic_modeling.yml")
    parser.add_argument("--mode", choices=["corpus", "stm", "bertopic", "compare", "dashboard", "full"], default="full")
    parser.add_argument("--corpus-unit", choices=["metadata", "fulltext"], default="metadata")
    parser.add_argument("--force-embeddings", action="store_true")
    parser.add_argument("--run-stability", action="store_true")
    args = parser.parse_args()
    py = sys.executable
    if args.mode in {"corpus", "full"}:
        run([py, "scripts/build_modeling_corpus.py", "--config", args.config])
    if args.mode in {"stm", "full"}:
        env = os.environ.copy()
        env["RUN_STABILITY"] = str(args.run_stability).lower()
        run(["Rscript", "stm_analysis.R", "--config", args.config], env)
    if args.mode in {"bertopic", "full"}:
        command = [py, "scripts/run_bertopic.py", "--config", args.config, "--corpus-unit", args.corpus_unit]
        if args.force_embeddings:
            command.append("--force-embeddings")
        run(command)
    if args.mode in {"compare", "full"}:
        for script in ("evaluate_topic_models.py", "compare_topic_models.py", "export_topic_dashboard.py"):
            run([py, f"scripts/{script}", "--config", args.config])
    if args.mode in {"dashboard", "full"}:
        run([py, "generate_dashboard.py"])


if __name__ == "__main__":
    main()
