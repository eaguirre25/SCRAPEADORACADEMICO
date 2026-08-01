from __future__ import annotations

import itertools
import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .corpus_builder import read_csv, write_csv
from .embeddings import load_or_create_embeddings, load_or_create_metadata_embeddings
from .vectorization import build_vectorizer


CONTAMINATION_TOKENS = {"hospital", "patient", "clinical", "nursing", "tax", "accounting", "mineral", "suicide"}


def _entropy(values: list[str]) -> float:
    counts = Counter(values); total = sum(counts.values())
    return -sum((n / total) * math.log(n / total) for n in counts.values()) if total else 0.0


def _cluster_terms(texts: list[str], labels, config: dict[str, Any], top_n: int = 15) -> dict[int, list[str]]:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfTransformer

    valid_labels = sorted(int(x) for x in set(labels) if int(x) >= 0)
    if not valid_labels:
        return {}
    vectorizer = build_vectorizer(config)
    try:
        matrix = vectorizer.fit_transform(texts)
    except ValueError:
        return {}
    grouped = []
    labels_array = np.asarray(labels)
    for label in valid_labels:
        grouped.append(np.asarray(matrix[labels_array == label].sum(axis=0)).ravel())
    weights = TfidfTransformer(norm="l2", use_idf=True, sublinear_tf=True).fit_transform(np.asarray(grouped)).toarray()
    names = vectorizer.get_feature_names_out()
    return {label: [str(names[i]) for i in weights[pos].argsort()[::-1][:top_n] if weights[pos, i] > 0]
            for pos, label in enumerate(valid_labels)}


def _evaluate(labels, reduced, embeddings, languages, texts, config: dict[str, Any], min_cluster_size: int) -> dict[str, Any]:
    import numpy as np
    from sklearn.metrics import normalized_mutual_info_score, silhouette_score

    labels = np.asarray(labels); valid = labels >= 0
    counts = Counter(labels[valid].tolist()); sizes = sorted(counts.values())
    cluster_count = len(counts); outlier_share = float(np.mean(~valid))
    silhouette = float(silhouette_score(reduced[valid], labels[valid])) if valid.sum() > cluster_count > 1 else -1.0
    language_nmi = float(normalized_mutual_info_score(np.asarray(languages)[valid], labels[valid])) if valid.any() else 1.0
    terms = _cluster_terms(texts, labels, config)
    flat = [term for values in terms.values() for term in values]
    diversity = len(set(flat)) / len(flat) if flat else 0.0
    contaminated = sum(bool(set(values) & CONTAMINATION_TOKENS) for values in terms.values())
    language_concentrated = 0
    for label in counts:
        selected = [languages[i] for i in np.where(labels == label)[0]]
        if selected and max(Counter(selected).values()) / len(selected) > 0.85:
            language_concentrated += 1
    dbcv: float | str = ""
    try:
        from hdbscan.validity import validity_index
        dbcv = float(validity_index(np.asarray(reduced, dtype=np.float64), labels, metric="euclidean"))
    except (ImportError, ValueError, TypeError):
        pass
    minimum_share = sum(size <= min_cluster_size * 1.10 for size in sizes) / len(sizes) if sizes else 1.0
    return {
        "clusters": cluster_count, "outlier_share": round(outlier_share, 6), "clustered_documents": int(valid.sum()),
        "minimum_cluster_size_observed": min(sizes) if sizes else 0,
        "median_cluster_size": float(np.median(sizes)) if sizes else 0,
        "maximum_cluster_size": max(sizes) if sizes else 0,
        "maximum_cluster_share": round((max(sizes) / int(valid.sum())) if sizes and valid.sum() else 1.0, 6),
        "clusters_at_minimum_size_share": round(minimum_share, 6),
        "silhouette": round(silhouette, 6), "dbcv": "" if dbcv == "" else round(float(dbcv), 6),
        "topic_diversity": round(diversity, 6), "language_cluster_nmi": round(language_nmi, 6),
        "language_concentrated_topics": language_concentrated,
        "contaminated_topic_candidates": contaminated,
        "recovery_share": round(float(valid.mean()), 6),
        "mean_language_entropy": round(sum(_entropy([languages[i] for i in np.where(labels == label)[0]]) for label in counts) / max(len(counts), 1), 6),
    }


def _rejection_reasons(row: dict[str, Any], thresholds: dict[str, Any]) -> list[str]:
    reasons = []
    if row["outlier_share"] > float(thresholds["reject_outlier_share_above"]): reasons.append("outlier_share")
    if row["clusters"] > int(thresholds["reject_topics_above"]): reasons.append("too_many_topics")
    if row["clusters"] < int(thresholds["reject_topics_below"]): reasons.append("too_few_topics")
    if row["median_cluster_size"] < float(thresholds["reject_median_cluster_below"]): reasons.append("small_median_cluster")
    if row["clusters_at_minimum_size_share"] > float(thresholds["reject_minimum_size_share_above"]): reasons.append("too_many_minimum_size_clusters")
    if row["maximum_cluster_share"] > float(thresholds.get("reject_maximum_cluster_share_above", 1.0)): reasons.append("dominant_giant_cluster")
    return reasons


def _ranking_score(row: dict[str, Any], target_min: int, target_max: int) -> float:
    topic_penalty = 0 if target_min <= row["clusters"] <= target_max else min(abs(row["clusters"] - target_min), abs(row["clusters"] - target_max)) / 20
    dbcv = float(row["dbcv"] or 0)
    return (0.28 * row["silhouette"] + 0.18 * dbcv + 0.16 * row["topic_diversity"] +
            0.18 * row["recovery_share"] - 0.10 * row["language_cluster_nmi"] -
            0.05 * row["clusters_at_minimum_size_share"] - 0.05 * topic_penalty)


def _load_inputs(config: dict[str, Any], corpus_unit: str, force_embeddings: bool):
    import numpy as np
    root = Path(config["paths"]["output_root"])
    documents = read_csv(root / "corpus" / f"modeling_corpus_{corpus_unit}.csv")
    texts = [row.get("text_for_vectorizer") or row.get("text_for_modeling") or row["texto_modelado"] for row in documents]
    if corpus_unit == "metadata":
        embeddings, manifest = load_or_create_metadata_embeddings(documents, config, force=force_embeddings)
    else:
        embeddings, manifest = load_or_create_embeddings([row["document_id"] for row in documents], texts, config, force=force_embeddings)
    return root, documents, texts, np.asarray(embeddings), manifest


def search_bertopic_parameters(config: dict[str, Any], *, corpus_unit: str = "metadata", output_name: str = "metadata_multilingual", force_embeddings: bool = False) -> list[dict[str, Any]]:
    from hdbscan import HDBSCAN
    from umap import UMAP

    root, documents, texts, embeddings, manifest = _load_inputs(config, corpus_unit, force_embeddings)
    languages = [row.get("language") or "und" for row in documents]
    cfg = config["bertopic"]; search = cfg["parameter_search"]; macro = cfg["macro_search"]
    seed = int(config["project"]["seed"]); rows: list[dict[str, Any]] = []
    umap_specs = list(itertools.product(search["umap_neighbors"], search["umap_components"], search["umap_min_dist"]))
    cluster_specs = [(25, 5), (35, 5), (35, 10), (50, 5), (50, 10)]
    reduced_cache = {}
    for neighbors, components, min_dist in umap_specs:
        key = (int(neighbors), int(components), float(min_dist)); started = time.perf_counter()
        reduced = UMAP(n_neighbors=key[0], n_components=key[1], min_dist=key[2], metric="cosine", random_state=seed, low_memory=True).fit_transform(embeddings)
        reduced_cache[key] = reduced
        # One broad baseline per UMAP; deeper HDBSCAN search is applied to the best geometries below.
        labels = HDBSCAN(min_cluster_size=35, min_samples=5, metric="euclidean", cluster_selection_method="eom", prediction_data=True).fit_predict(reduced)
        metrics = _evaluate(labels, reduced, embeddings, languages, texts, config, 35)
        row = {"phase": "macro_umap_screen", "n_neighbors": key[0], "n_components": key[1], "min_dist": key[2],
               "min_cluster_size": 35, "min_samples": 5, "cluster_selection_method": "eom", **metrics,
               "elapsed_seconds": round(time.perf_counter() - started, 3), "seed": seed}
        row["rejection_reasons"] = " | ".join(_rejection_reasons(row, macro)); rows.append(row)
    best_geometries = sorted(rows, key=lambda row: _ranking_score(row, int(macro["target_min_topics"]), int(macro["target_max_topics"])), reverse=True)[:3]
    seen = {(r["n_neighbors"], r["n_components"], r["min_dist"], r["min_cluster_size"], r["min_samples"]) for r in rows}
    for base in best_geometries:
        key = (base["n_neighbors"], base["n_components"], base["min_dist"]); reduced = reduced_cache[key]
        for min_cluster, min_samples in cluster_specs:
            signature = (*key, min_cluster, min_samples)
            if signature in seen: continue
            started = time.perf_counter()
            labels = HDBSCAN(min_cluster_size=min_cluster, min_samples=min_samples, metric="euclidean", cluster_selection_method="eom", prediction_data=True).fit_predict(reduced)
            metrics = _evaluate(labels, reduced, embeddings, languages, texts, config, min_cluster)
            row = {"phase": "macro_hdbscan_screen", "n_neighbors": key[0], "n_components": key[1], "min_dist": key[2],
                   "min_cluster_size": min_cluster, "min_samples": min_samples, "cluster_selection_method": "eom", **metrics,
                   "elapsed_seconds": round(time.perf_counter() - started, 3), "seed": seed}
            row["rejection_reasons"] = " | ".join(_rejection_reasons(row, macro)); rows.append(row); seen.add(signature)
    for row in rows:
        row["multi_criteria_score"] = round(_ranking_score(row, int(macro["target_min_topics"]), int(macro["target_max_topics"])), 6)
    rows.sort(key=lambda row: (bool(row["rejection_reasons"]), -row["multi_criteria_score"]))
    competitive = [row for row in rows if not row["rejection_reasons"]]
    if not competitive:
        competitive = sorted(rows, key=lambda row: (len(row["rejection_reasons"].split(" | ")), -row["multi_criteria_score"]))[: int(macro["finalists"])]
    finalists = {id(row) for row in competitive[: int(macro["finalists"])]}
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
        row["solution_status"] = "competitive" if id(row) in finalists else "rejected"
        row["human_review_status"] = "pending"
        row["stability_status"] = "pending"
    out = root / "bertopic" / output_name; write_csv(out / "candidate_solutions.csv", rows); write_csv(out / "parameter_search.csv", rows)
    selected = next((row for row in rows if row["solution_status"] == "competitive"), rows[0] if rows else {})
    (out / "selected_parameters.json").write_text(json.dumps({
        "status": "human_review_required", "selection_basis": "multi-criteria macro screen; stability pending",
        "embedding_manifest": {k: v for k, v in manifest.items() if k not in {"document_ids", "text_hashes"}}, "selected": selected,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


def run_bertopic_stability(config: dict[str, Any], *, corpus_unit: str = "metadata", output_name: str = "metadata_multilingual", finalists_only: bool = True) -> list[dict[str, Any]]:
    import numpy as np
    from hdbscan import HDBSCAN
    from scipy.optimize import linear_sum_assignment
    from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
    from sklearn.metrics.pairwise import cosine_similarity
    from umap import UMAP

    root, documents, texts, embeddings, _ = _load_inputs(config, corpus_unit, False)
    out = root / "bertopic" / output_name; candidates = read_csv(out / "candidate_solutions.csv")
    if finalists_only: candidates = [row for row in candidates if row.get("solution_status") == "competitive"]
    seeds = [int(x) for x in config["bertopic"]["macro_search"]["seeds"]]
    detail: list[dict[str, Any]] = []; summaries: dict[str, dict[str, Any]] = {}
    for c_index, candidate in enumerate(candidates):
        solution_id = f"S{c_index + 1}"
        runs = []
        for seed in seeds:
            reduced = UMAP(n_neighbors=int(candidate["n_neighbors"]), n_components=int(candidate["n_components"]), min_dist=float(candidate["min_dist"]), metric="cosine", random_state=seed, low_memory=True).fit_transform(embeddings)
            clusterer = HDBSCAN(min_cluster_size=int(candidate["min_cluster_size"]), min_samples=int(candidate["min_samples"]), metric="euclidean", cluster_selection_method="eom", prediction_data=True).fit(reduced)
            labels = clusterer.labels_; runs.append((seed, labels, reduced, _cluster_terms(texts, labels, config)))
        base_seed, base_labels, _, base_terms = runs[0]
        aris=[]; nmis=[]; centroid_scores=[]; word_scores=[]; outliers=[]; counts=[]
        for seed, labels, _, terms in runs:
            ari=float(adjusted_rand_score(base_labels, labels)); nmi=float(normalized_mutual_info_score(base_labels, labels))
            aris.append(ari); nmis.append(nmi); outliers.append(float(np.mean(labels < 0))); counts.append(len(set(labels)) - (-1 in labels))
            base_ids=sorted(x for x in set(base_labels) if x>=0); ids=sorted(x for x in set(labels) if x>=0)
            if base_ids and ids:
                a=np.vstack([embeddings[base_labels==x].mean(axis=0) for x in base_ids]); b=np.vstack([embeddings[labels==x].mean(axis=0) for x in ids])
                sim=cosine_similarity(a,b); rr,cc=linear_sum_assignment(-sim); centroid=float(sim[rr,cc].mean())
                jacc=[]
                for i,j in zip(rr,cc):
                    left=set(base_terms.get(base_ids[i],[])); right=set(terms.get(ids[j],[])); jacc.append(len(left&right)/len(left|right) if left|right else 0)
                word=float(np.mean(jacc)) if jacc else 0.0
            else: centroid=0.0; word=0.0
            centroid_scores.append(centroid); word_scores.append(word)
            detail.append({"solution_id":solution_id,"base_seed":base_seed,"seed":seed,"adjusted_rand_index":round(ari,6),"normalized_mutual_information":round(nmi,6),"topic_centroid_similarity":round(centroid,6),"jaccard_top_words":round(word,6),"topic_count":counts[-1],"outlier_share":round(outliers[-1],6),"alignment_method":"Hungarian","status":"computed"})
        summaries[solution_id]={"stability_ari_mean":round(float(np.mean(aris)),6),"stability_nmi_mean":round(float(np.mean(nmis)),6),"centroid_stability_mean":round(float(np.mean(centroid_scores)),6),"top_word_jaccard_mean":round(float(np.mean(word_scores)),6),"topic_count_variation":round(float(np.std(counts)),6),"outlier_variation":round(float(np.std(outliers)),6),"stability_status":"computed_five_runs"}
    write_csv(out / "stability_runs.csv", detail)
    for index,row in enumerate(candidates):
        solution_id=f"S{index+1}"; row.update({"solution_id":solution_id, **summaries[solution_id]})
        row["solution_status"]="competitive"
    candidates.sort(key=lambda r:(float(r.get("stability_ari_mean") or 0)+float(r.get("stability_nmi_mean") or 0)+float(r.get("multi_criteria_score") or 0)),reverse=True)
    if candidates: candidates[0]["solution_status"]="preferred_provisional"
    all_rows=read_csv(out / "candidate_solutions.csv")
    signatures={(r["n_neighbors"],r["n_components"],r["min_dist"],r["min_cluster_size"],r["min_samples"]):r for r in candidates}
    for row in all_rows:
        key=(row["n_neighbors"],row["n_components"],row["min_dist"],row["min_cluster_size"],row["min_samples"])
        if key in signatures: row.update(signatures[key])
    write_csv(out / "candidate_solutions.csv", all_rows); write_csv(out / "stability.csv", candidates)
    preferred=next((r for r in candidates if r["solution_status"]=="preferred_provisional"), candidates[0] if candidates else {})
    selected_path=out/"selected_parameters.json"; payload=json.loads(selected_path.read_text(encoding="utf-8")); payload.update({"status":"human_review_required","selection_basis":"multi-criteria macro screen plus five-run stability","selected":preferred}); selected_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    return candidates
