#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
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

from topic_modeling.bertopic_model import run_bertopic
from topic_modeling.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run multilingual BERTopic with cached embeddings.")
    parser.add_argument("--config", default="config/topic_modeling.yml")
    parser.add_argument("--corpus-unit", choices=["metadata", "fulltext"], default="metadata")
    parser.add_argument("--force-embeddings", action="store_true")
    parser.add_argument("--output-name")
    parser.add_argument("--embedding-variant", choices=["weighted_fields", "title_abstract_only"], default="weighted_fields")
    parser.add_argument("--use-selected-parameters", action="store_true")
    parser.add_argument("--search-output-name", default="metadata_multilingual")
    parser.add_argument("--set", action="append", default=[], dest="overrides")
    args = parser.parse_args()
    config = load_config(args.config, args.overrides)
    if args.use_selected_parameters:
        output_name = args.output_name or ("metadata_multilingual" if args.corpus_unit == "metadata" else "fulltext_multilingual")
        selected_path = Path(config["paths"]["output_root"]) / "bertopic" / args.search_output_name / "selected_parameters.json"
        selected = json.loads(selected_path.read_text(encoding="utf-8"))["selected"]
        config["bertopic"]["umap"].update({key: selected[key] for key in ("n_neighbors", "n_components", "min_dist")})
        config["bertopic"]["min_topic_size"] = selected["min_cluster_size"]
        config["bertopic"]["min_samples"] = selected["min_samples"]
        config["bertopic"]["hdbscan"]["cluster_selection_method"] = selected["cluster_selection_method"]
    metadata = run_bertopic(
        config, corpus_unit=args.corpus_unit,
        force_embeddings=args.force_embeddings, output_name=args.output_name,
        embedding_variant=args.embedding_variant,
    )
    if args.use_selected_parameters and args.corpus_unit == "metadata":
        base = Path(config["paths"]["output_root"]) / "bertopic" / args.search_output_name
        preferred = Path(config["paths"]["output_root"]) / "bertopic" / (args.output_name or "metadata_multilingual")
        effective = preferred / "effective_configuration.json"
        if effective.exists():
            shutil.copy2(effective, base / "effective_configuration.json")
        if (base / "stability.csv").exists():
            shutil.copy2(base / "stability.csv", preferred / "stability.csv")
        topics_path = preferred / "topics.csv"
        if topics_path.exists():
            with topics_path.open(encoding="utf-8-sig", newline="") as handle:
                topic_rows = list(csv.DictReader(handle))
                fields = list(topic_rows[0]) if topic_rows else []
            for field in ("selection_status", "stability"):
                if field not in fields:
                    fields.append(field)
            selected_status = json.loads(selected_path.read_text(encoding="utf-8"))["selected"]
            for row in topic_rows:
                row["selection_status"] = selected_status.get("solution_status", "preferred_provisional")
                row["stability"] = selected_status.get("stability_ari_mean", "")
            with topics_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader(); writer.writerows(topic_rows)
    print(json.dumps(metadata, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
