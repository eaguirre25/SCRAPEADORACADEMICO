from __future__ import annotations

import itertools
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .corpus_builder import read_csv, write_csv
from .embeddings import load_or_create_embeddings, load_or_create_metadata_embeddings


def _evaluate(labels, reduced, languages) -> dict[str, Any]:
    import numpy as np
    from sklearn.metrics import normalized_mutual_info_score, silhouette_score

    labels = np.asarray(labels)
    valid = labels >= 0
    counts = Counter(labels[valid].tolist())
    cluster_count = len(counts)
    outlier_share = float(np.mean(~valid))
    silhouette = float(silhouette_score(reduced[valid], labels[valid])) if valid.sum() > cluster_count > 1 else -1.0
    concentration = max(counts.values()) / valid.sum() if counts else 1.0
    language_nmi = float(normalized_mutual_info_score([languages[i] for i in np.where(valid)[0]], labels[valid])) if valid.any() else 1.0
    sizes = sorted(counts.values())
    median = sizes[len(sizes) // 2] if sizes else 0
    return {
        "clusters": cluster_count, "outlier_share": round(outlier_share, 6),
        "minimum_cluster_size_observed": min(sizes) if sizes else 0, "median_cluster_size": median,
        "maximum_cluster_share": round(concentration, 6), "silhouette": round(silhouette, 6),
        "language_cluster_nmi": round(language_nmi, 6),
        "preliminary_score": round(silhouette - 0.35 * abs(outlier_share - 0.20) - 0.25 * concentration - 0.30 * language_nmi, 6),
    }


def search_bertopic_parameters(
    config: dict[str, Any], *, corpus_unit: str = "metadata", output_name: str = "metadata_multilingual",
    force_embeddings: bool = False,
) -> list[dict[str, Any]]:
    import numpy as np
    from hdbscan import HDBSCAN
    from umap import UMAP

    root = Path(config["paths"]["output_root"])
    documents = read_csv(root / "corpus" / f"modeling_corpus_{corpus_unit}.csv")
    ids = [row["document_id"] for row in documents]
    texts = [row.get("text_for_modeling") or row["texto_modelado"] for row in documents]
    if corpus_unit == "metadata":
        embeddings, manifest = load_or_create_metadata_embeddings(documents, config, force=force_embeddings)
    else:
        embeddings, manifest = load_or_create_embeddings(ids, texts, config, force=force_embeddings)
    embeddings = np.asarray(embeddings)
    languages = [row.get("language") or "und" for row in documents]
    cfg = config["bertopic"]["parameter_search"]
    seed = int(config["project"]["seed"])
    max_candidates = int(cfg.get("staged_max_candidates", 12))
    baseline_min_cluster = int(config["bertopic"].get("min_topic_size", 20))
    baseline_min_samples = int(config["bertopic"].get("min_samples", 5))
    baseline_method = config["bertopic"]["hdbscan"].get("cluster_selection_method", "eom")
    umap_candidates = list(itertools.product(cfg["umap_neighbors"], cfg["umap_components"], cfg["umap_min_dist"]))
    rows: list[dict[str, Any]] = []
    reduced_cache: dict[tuple[int, int, float], Any] = {}
    for neighbors, components, min_dist in umap_candidates[: min(6, max_candidates)]:
        started = time.perf_counter()
        key = (int(neighbors), int(components), float(min_dist))
        reduced = UMAP(
            n_neighbors=key[0], n_components=key[1], min_dist=key[2], metric="cosine",
            random_state=seed, low_memory=True,
        ).fit_transform(embeddings)
        reduced_cache[key] = reduced
        labels = HDBSCAN(
            min_cluster_size=baseline_min_cluster, min_samples=baseline_min_samples,
            metric="euclidean", cluster_selection_method=baseline_method,
        ).fit_predict(reduced)
        rows.append({
            "phase": "umap_screen", "n_neighbors": key[0], "n_components": key[1], "min_dist": key[2],
            "min_cluster_size": baseline_min_cluster, "min_samples": baseline_min_samples,
            "cluster_selection_method": baseline_method, **_evaluate(labels, reduced, languages),
            "elapsed_seconds": round(time.perf_counter() - started, 3), "seed": seed,
        })
    best_umap = sorted(rows, key=lambda row: row["preliminary_score"], reverse=True)[:2]
    hdb_candidates = list(itertools.product(cfg["min_cluster_size"], cfg["min_samples"], cfg["cluster_selection_method"]))
    for base in best_umap:
        key = (int(base["n_neighbors"]), int(base["n_components"]), float(base["min_dist"]))
        reduced = reduced_cache[key]
        for min_cluster, min_samples, method in hdb_candidates:
            if len(rows) >= max_candidates:
                break
            started = time.perf_counter()
            labels = HDBSCAN(
                min_cluster_size=int(min_cluster), min_samples=int(min_samples), metric="euclidean",
                cluster_selection_method=str(method),
            ).fit_predict(reduced)
            rows.append({
                "phase": "hdbscan_screen", "n_neighbors": key[0], "n_components": key[1], "min_dist": key[2],
                "min_cluster_size": int(min_cluster), "min_samples": int(min_samples),
                "cluster_selection_method": str(method), **_evaluate(labels, reduced, languages),
                "elapsed_seconds": round(time.perf_counter() - started, 3), "seed": seed,
            })
    rows.sort(key=lambda row: row["preliminary_score"], reverse=True)
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
        row["selection_status"] = "preliminary_candidate" if rank <= 3 else "screened"
        row["human_review_status"] = "pending"
    out = root / "bertopic" / output_name
    write_csv(out / "parameter_search.csv", rows)
    selected = rows[0] if rows else {}
    (out / "selected_parameters.json").write_text(json.dumps({
        "status": "provisional", "selection_basis": "automatic preliminary screen; human review and stability pending",
        "embedding_manifest": {key: value for key, value in manifest.items() if key not in {"document_ids", "text_hashes"}},
        "selected": selected,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows

