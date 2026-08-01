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
    clean_env = (env or os.environ).copy()
    clean_env.pop("SSLKEYLOGFILE", None)
    if os.name == "nt":
        python_root = str(Path(sys.executable).resolve().parent)
        clean_env["PATH"] = python_root + os.pathsep + clean_env.get("PATH", "")
    subprocess.run(command, cwd=ROOT, env=clean_env, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Orchestrate the hybrid topic-modeling pipeline.")
    parser.add_argument("--config", default="config/topic_modeling.yml")
    parser.add_argument("--mode", choices=["corpus", "stm", "bertopic", "evaluation_only", "compare", "dashboard", "full"], default="full")
    parser.add_argument("--corpus-unit", choices=["metadata", "fulltext"], default="metadata")
    parser.add_argument("--force-embeddings", action="store_true")
    parser.add_argument("--run-stability", action="store_true")
    parser.add_argument("--preliminary", action="store_true", help="Fit explicitly provisional STM models without stability runs.")
    parser.add_argument("--fixed-k", type=int, help="Optional fixed K for a preliminary STM fit.")
    parser.add_argument("--stm-languages", nargs="+", default=["es", "en", "pt"])
    parser.add_argument("--search-parameters", action="store_true", help="Run the staged BERTopic parameter search before fitting.")
    args = parser.parse_args()
    py = sys.executable
    if args.mode in {"corpus", "full"}:
        run([py, "scripts/build_modeling_corpus.py", "--config", args.config])
    if args.mode in {"stm", "full"}:
        env = os.environ.copy()
        env["RUN_STABILITY"] = str(args.run_stability).lower()
        for language in args.stm_languages:
            command = ["Rscript", "stm_analysis.R", "--config", args.config, "--corpus-unit", args.corpus_unit,
                       "--language", language, "--output-name", f"{args.corpus_unit}_{language}_corrected"]
            if args.preliminary:
                command.append("--preliminary")
            fixed_k = args.fixed_k or (4 if args.preliminary and language == "pt" else 16 if args.preliminary else None)
            if fixed_k:
                command.extend(["--fixed-k", str(fixed_k)])
            run(command, env)
    if args.mode in {"bertopic", "full"}:
        if args.search_parameters and args.corpus_unit == "metadata":
            run([py, "scripts/search_bertopic_macro_solutions.py", "--config", args.config])
            run([py, "scripts/run_bertopic_stability.py", "--config", args.config, "--finalists-only"])
        command = [py, "scripts/run_bertopic.py", "--config", args.config, "--corpus-unit", args.corpus_unit]
        if args.search_parameters:
            command.append("--use-selected-parameters")
            if args.corpus_unit == "metadata":
                command.extend(["--output-name", "metadata_multilingual/preferred_solution"])
        if args.force_embeddings:
            command.append("--force-embeddings")
        run(command)
    if args.mode in {"compare", "full"}:
        for script in ("evaluate_topic_models.py", "compare_topic_models.py", "export_topic_dashboard.py"):
            run([py, f"scripts/{script}", "--config", args.config])
    if args.mode == "evaluation_only":
        run([py, "scripts/audit_topic_evaluation.py", "--config", args.config])
        run([py, "scripts/recompute_topic_metrics.py", "--config", args.config, "--model", "preferred", "--recompute-model", "false"])
        run([py, "scripts/rebuild_model_runs.py", "--config", args.config])
    if args.mode in {"dashboard", "full"}:
        run([py, "scripts/generate_topic_validation_review.py"])
        run([py, "generate_dashboard.py"])


if __name__ == "__main__":
    main()
