from __future__ import annotations

import json
import hashlib
import platform
import random
import shutil
import time
from pathlib import Path
from typing import Any

from .corpus_builder import read_csv, write_csv
from .embeddings import load_or_create_embeddings, load_or_create_metadata_embeddings
from .metadata import base_metadata, write_metadata
from .topic_labels import automatic_label, load_human_labels, resolve_label
from .vectorization import build_vectorizer, effective_vectorizer_parameters
from .embeddings import TEXT_CLEANING_VERSION


def _probability_fields(probabilities: Any, topic_ids: list[int], index: int, assigned: int) -> tuple[float | str, int | str, float | str, float | str]:
    if probabilities is None:
        return "", "", "", ""
    import numpy as np

    row = np.asarray(probabilities[index])
    if row.ndim == 0:
        return float(row), "", "", ""
    order = np.argsort(row)[::-1]
    first = float(row[order[0]]) if len(order) else 0.0
    second = float(row[order[1]]) if len(order) > 1 else 0.0
    second_topic = topic_ids[int(order[1])] if len(order) > 1 and int(order[1]) < len(topic_ids) else ""
    return first, second_topic, second, first - second


def run_bertopic(
    config: dict[str, Any], *, corpus_unit: str = "metadata", force_embeddings: bool = False,
    output_name: str | None = None, embedding_variant: str = "weighted_fields",
) -> dict[str, Any]:
    import numpy as np
    from bertopic import BERTopic
    from bertopic.vectorizers import ClassTfidfTransformer
    from hdbscan import HDBSCAN
    from umap import UMAP

    started = time.perf_counter()
    seed = int(config["project"]["seed"])
    random.seed(seed)
    np.random.seed(seed)
    root = Path(config["paths"]["output_root"])
    corpus_path = root / "corpus" / f"modeling_corpus_{corpus_unit}.csv"
    documents = read_csv(corpus_path)
    document_ids = [row["document_id"] for row in documents]
    texts = [row.get("text_for_vectorizer") or row.get("text_for_modeling") or row["texto_modelado"] for row in documents]
    if corpus_unit == "metadata" and config.get("metadata_embeddings", {}).get("combine_fields_as_embeddings", True):
        embeddings, embedding_manifest = load_or_create_metadata_embeddings(
            documents, config, force=force_embeddings, variant=embedding_variant
        )
    else:
        embeddings, embedding_manifest = load_or_create_embeddings(document_ids, texts, config, force=force_embeddings)
    cfg = config["bertopic"]
    umap_cfg = cfg["umap"]
    hdb_cfg = cfg["hdbscan"]
    umap_model = UMAP(
        n_neighbors=int(umap_cfg["n_neighbors"]), n_components=int(umap_cfg["n_components"]),
        min_dist=float(umap_cfg["min_dist"]), metric=umap_cfg["metric"], random_state=seed,
        low_memory=bool(cfg.get("low_memory", True)),
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size=int(cfg["min_topic_size"]), min_samples=int(cfg["min_samples"]),
        metric=hdb_cfg["metric"], cluster_selection_method=hdb_cfg["cluster_selection_method"],
        prediction_data=bool(hdb_cfg.get("prediction_data", True)),
    )
    vectorizer = build_vectorizer(config)
    ctfidf = ClassTfidfTransformer(reduce_frequent_words=bool(cfg.get("reduce_frequent_words", True)))
    representation_model = None
    representation_components = {"MainRepresentation": "c-TF-IDF", "SecondaryRepresentation": "not_available", "NgramRepresentation": "CountVectorizer(1,3)", "RepresentativeDocuments": "BERTopic"}
    try:
        from bertopic.representation import KeyBERTInspired
        representation_model = {"KeyBERT": KeyBERTInspired()}
        representation_components["SecondaryRepresentation"] = "KeyBERTInspired"
    except ImportError:
        pass
    model = BERTopic(
        embedding_model=cfg["embedding_model"] if representation_model else None, umap_model=umap_model, hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer, ctfidf_model=ctfidf, nr_topics=cfg.get("nr_topics", "auto"),
        calculate_probabilities=bool(cfg.get("calculate_probabilities", True)), verbose=True,
        representation_model=representation_model,
    )
    topics, probabilities = model.fit_transform(texts, embeddings=np.asarray(embeddings))
    reduced_topics = list(topics)
    outlier_reduction_warning = ""
    if bool(cfg.get("reduce_outliers", True)) and -1 in topics and probabilities is not None:
        try:
            reduced_topics = list(model.reduce_outliers(texts, topics, probabilities=probabilities, strategy="probabilities"))
        except (TypeError, ValueError) as exc:
            outlier_reduction_warning = f"Alternative outlier reduction was not available: {exc}"
    output_name = output_name or ("metadata_multilingual" if corpus_unit == "metadata" else "fulltext_multilingual")
    out = root / "bertopic" / output_name
    out.mkdir(parents=True, exist_ok=True)
    human = load_human_labels(config["paths"]["human_labels"])
    info = model.get_topic_info()
    valid_topic_ids = sorted(int(topic) for topic in info["Topic"].tolist() if int(topic) >= 0)
    topic_rows: list[dict[str, Any]] = []
    representative_rows: list[dict[str, Any]] = []
    total = len(documents)
    model_label = f"BERTopic-{corpus_unit.upper()}-MULTILINGUAL"
    for _, item in info.iterrows():
        topic_id = int(item["Topic"])
        words = [word for word, _ in (model.get_topic(topic_id) or [])]
        proposal = "Outliers" if topic_id == -1 else automatic_label(words)
        labels = resolve_label("bertopic", topic_id, proposal, human)
        reps = (model.get_representative_docs(topic_id) or []) if topic_id >= 0 else []
        topic_rows.append({
            "model": model_label, "corpus": corpus_unit, "language": "multilingual", "topic_id": topic_id, **labels,
            "prevalence": round(100 * int(item["Count"]) / max(total, 1), 4),
            "document_count": int(item["Count"]), "top_words": " | ".join(words[:15]),
            "top_ngrams": " | ".join(word for word in words if " " in word)[:2000],
            "representative_titles": " | ".join(row["title"] for row in documents if row["texto_modelado"] in reps)[:4000],
            "coherence": "", "diversity": "", "stability": "", "is_outlier": topic_id == -1,
        })
        for rank, text in enumerate(reps, 1):
            try:
                idx = texts.index(text)
                representative_rows.append({"model": model_label, "corpus": corpus_unit, "topic_id": topic_id, "rank": rank, "document_id": document_ids[idx], "title": documents[idx]["title"]})
            except ValueError:
                continue
    document_rows: list[dict[str, Any]] = []
    ambiguity_cfg = cfg.get("ambiguity", {})
    fitted_hdbscan = getattr(model, "hdbscan_model", hdbscan_model)
    membership_values = np.asarray(getattr(fitted_hdbscan, "probabilities_", np.ones(len(documents))))
    outlier_scores = np.asarray(getattr(fitted_hdbscan, "outlier_scores_", np.zeros(len(documents))))
    for index, (row, topic_id) in enumerate(zip(documents, topics, strict=True)):
        first, second_id, second, margin = _probability_fields(probabilities, valid_topic_ids, index, int(topic_id))
        reduced_topic = int(reduced_topics[index])
        membership = float(membership_values[index]) if int(topic_id) >= 0 else 0.0
        outlier_score = float(outlier_scores[index]) if index < len(outlier_scores) else 0.0
        document_rows.append({
            "document_id": row["document_id"], "publication_document_id": row.get("publication_document_id", row["document_id"]),
            "model": model_label, "corpus": corpus_unit, "topic_id": int(topic_id),
            "topic_probability": membership, "hdbscan_membership_strength": round(membership, 6),
            "bertopic_topic_distribution_max": first, "bertopic_second_topic_id": second_id,
            "bertopic_second_distribution": second, "probability_margin": margin,
            "outlier_score": round(outlier_score, 6), "is_outlier": int(topic_id) == -1,
            "is_ambiguous": False,
            "year": row["year"], "language": row["language"], "title": row["title"], "doi": row["doi"],
            "source": row["source"], "corpus_unit": row["corpus_unit"],
            "topic_original": int(topic_id), "topic_after_outlier_reduction": reduced_topic,
            "outlier_reassigned": False, "original_topic": int(topic_id),
            "suggested_topic": "", "reassignment_method": "", "reassignment_confidence": "",
            "accepted_reassignment": False,
            "relevance_status": row.get("relevance_status", ""), "relevance_score": row.get("relevance_score", ""),
        })

    # Document-level geometry is not equivalent to STM probabilities; retain it under explicit names.
    from sklearn.metrics import silhouette_samples
    from sklearn.neighbors import NearestNeighbors
    reduced = np.asarray(model.umap_model.embedding_)
    semantic_embeddings = np.asarray(embeddings)
    labels_array = np.asarray(topics)
    valid_mask = labels_array >= 0
    silhouette_values = np.full(len(documents), np.nan)
    if valid_mask.sum() > len(set(labels_array[valid_mask])) > 1:
        silhouette_values[valid_mask] = silhouette_samples(reduced[valid_mask], labels_array[valid_mask])
    centroid_distances = np.full(len(documents), np.nan)
    centroid_rows: list[dict[str, Any]] = []
    semantic_centroids: dict[int, Any] = {}
    for topic_id in sorted(set(labels_array[valid_mask])):
        indexes = np.where(labels_array == topic_id)[0]
        centroid = reduced[indexes].mean(axis=0)
        semantic_centroid = semantic_embeddings[indexes].mean(axis=0)
        semantic_centroid /= max(float(np.linalg.norm(semantic_centroid)), 1e-12)
        semantic_centroids[int(topic_id)] = semantic_centroid
        centroid_distances[indexes] = np.linalg.norm(reduced[indexes] - centroid, axis=1)
        for rank, doc_index in enumerate(indexes[np.argsort(centroid_distances[indexes])[:10]], 1):
            centroid_rows.append({
                "model": model_label, "corpus": corpus_unit, "topic_id": int(topic_id), "rank": rank,
                "document_id": document_ids[int(doc_index)], "title": documents[int(doc_index)]["title"],
                "distance_to_centroid": round(float(centroid_distances[int(doc_index)]), 6),
            })
    centroid_ids = sorted(semantic_centroids)
    centroid_matrix = np.vstack([semantic_centroids[topic] for topic in centroid_ids]) if centroid_ids else np.empty((0, semantic_embeddings.shape[1]))
    semantic_similarity = semantic_embeddings @ centroid_matrix.T if len(centroid_matrix) else np.empty((len(documents), 0))
    neighbors = NearestNeighbors(n_neighbors=min(11, len(documents))).fit(reduced)
    neighbor_indexes = neighbors.kneighbors(return_distance=False)
    for index, row in enumerate(document_rows):
        local = neighbor_indexes[index][neighbor_indexes[index] != index][:10]
        row["silhouette"] = "" if np.isnan(silhouette_values[index]) else round(float(silhouette_values[index]), 6)
        row["distance_to_centroid"] = "" if np.isnan(centroid_distances[index]) else round(float(centroid_distances[index]), 6)
        row["local_consistency"] = round(float(np.mean(labels_array[local] == labels_array[index])), 6) if len(local) else ""
        if semantic_similarity.shape[1]:
            order = np.argsort(semantic_similarity[index])[::-1]
            nearest = centroid_ids[int(order[0])]; second_nearest = centroid_ids[int(order[1])] if len(order) > 1 else ""
            nearest_similarity = float(semantic_similarity[index, order[0]])
            second_similarity = float(semantic_similarity[index, order[1]]) if len(order) > 1 else 0.0
            row["nearest_topic"] = nearest; row["nearest_centroid_similarity"] = round(nearest_similarity, 6)
            row["second_nearest_topic"] = second_nearest; row["second_nearest_centroid_similarity"] = round(second_similarity, 6)
            row["assignment_margin"] = round(nearest_similarity - second_similarity, 6)
            assigned_centroid = semantic_centroids.get(int(row["topic_id"]))
            row["semantic_distance_to_centroid"] = "" if assigned_centroid is None else round(1 - float(semantic_embeddings[index] @ assigned_centroid), 6)
            if int(row["topic_id"]) == -1:
                row["suggested_topic"] = nearest; row["reassignment_method"] = "nearest_semantic_centroid"
                row["reassignment_confidence"] = round(nearest_similarity, 6)
            from .bertopic_diagnostics import ambiguity_flag
            row["is_ambiguous"] = ambiguity_flag(row, config)
    write_csv(out / "topics.csv", topic_rows)
    write_csv(out / "document_topics.csv", document_rows)
    write_csv(out / "topic_words.csv", [
        {"model": model_label, "corpus": corpus_unit, "topic_id": topic_id, "rank": rank, "term": word, "weight": weight}
        for topic_id in valid_topic_ids for rank, (word, weight) in enumerate(model.get_topic(topic_id) or [], 1)
    ])
    write_csv(out / "representative_documents.csv", representative_rows)
    write_csv(out / "central_documents.csv", centroid_rows)
    write_csv(out / "outliers.csv", [row for row in document_rows if row["is_outlier"]])
    low_confidence = sorted(document_rows, key=lambda row: float(row.get("hdbscan_membership_strength") or 0))
    write_csv(out / "low_confidence_documents.csv", low_confidence[: 10 * max(len(valid_topic_ids), 1)])
    borderline = sorted(document_rows, key=lambda row: float(row.get("assignment_margin") or 0))
    write_csv(out / "borderline_documents.csv", borderline[: 10 * max(len(valid_topic_ids), 1)])
    from sklearn.metrics.pairwise import cosine_similarity

    similarity_rows: list[dict[str, Any]] = []
    topic_order = sorted(int(topic) for topic in model.get_topics())
    if getattr(model, "c_tf_idf_", None) is not None:
        similarities = cosine_similarity(model.c_tf_idf_)
        for left_index, left_topic in enumerate(topic_order):
            for right_index in range(left_index + 1, len(topic_order)):
                right_topic = topic_order[right_index]
                score = float(similarities[left_index, right_index])
                similarity_rows.append({
                    "topic_a": left_topic, "topic_b": right_topic, "ctfidf_similarity": round(score, 6),
                    "merge_candidate": score >= float(cfg.get("merge_candidate_similarity", 0.8)),
                    "review_status": "pending_human_review",
                })
    write_csv(out / "topic_similarity.csv", similarity_rows)
    write_csv(out / "merge_history.csv", [], ["timestamp", "topic_a", "topic_b", "decision", "reviewer", "notes"])
    hierarchy_warning = ""
    if bool(cfg.get("hierarchy_enabled", True)) and len(valid_topic_ids) > 1:
        try:
            hierarchy = model.hierarchical_topics(texts)
            hierarchy.to_csv(out / "agglomerative_hierarchy.csv", index=False, encoding="utf-8-sig")
        except (AttributeError, TypeError, ValueError) as exc:
            hierarchy_warning = f"Topic hierarchy was not available: {exc}"
            write_csv(out / "agglomerative_hierarchy.csv", [], ["Parent_ID", "Parent_Name", "Topics", "Child_Left_ID", "Child_Right_ID", "Distance"])
    # Language dependence is diagnostic, never an automatic topic interpretation.
    language_rows: list[dict[str, Any]] = []
    for topic_id in sorted(set(int(topic) for topic in topics if int(topic) >= 0)):
        topic_docs = [row for row in document_rows if int(row["topic_id"]) == topic_id]
        counts: dict[str, int] = {}
        for row in topic_docs:
            counts[row.get("language") or "und"] = counts.get(row.get("language") or "und", 0) + 1
        shares = [count / len(topic_docs) for count in counts.values()]
        entropy = -sum(share * np.log(share) for share in shares if share > 0)
        dominant_language, dominant_count = max(counts.items(), key=lambda item: item[1])
        dominant_share = dominant_count / len(topic_docs)
        language_rows.append({
            "model": model_label, "corpus": corpus_unit, "topic_id": topic_id,
            "topic_language_distribution": json.dumps(counts, ensure_ascii=False),
            "topic_language_entropy": round(float(entropy), 6), "dominant_language": dominant_language,
            "dominant_language_share": round(dominant_share, 6),
            "potentially_language_driven": dominant_share > float(config.get("multilingual", {}).get("language_topic_threshold", 0.8)),
            "classification": "pending_human_review",
        })
    write_csv(out / "language_dependence.csv", language_rows)
    heterogeneity_rows = []
    for topic_id in valid_topic_ids:
        topic_docs = [row for row in document_rows if int(row["topic_id"]) == topic_id]
        sil = [float(row["silhouette"]) for row in topic_docs if row.get("silhouette") != ""]
        mean_sil = sum(sil) / len(sil) if sil else 0.0
        language = next((row for row in language_rows if row["topic_id"] == topic_id), {})
        if len(topic_docs) < int(config["validation"].get("minimum_topic_documents", 5)):
            status = "too_small"
        elif language.get("potentially_language_driven") and mean_sil < 0.1:
            status = "language_driven"
        elif mean_sil < 0:
            status = "heterogeneous"
        elif mean_sil < 0.1:
            status = "broad_but_interpretable"
        else:
            status = "coherent"
        heterogeneity_rows.append({
            "model": model_label, "corpus": corpus_unit, "topic_id": topic_id, "documents": len(topic_docs),
            "mean_silhouette": round(mean_sil, 6),
            "mean_distance_to_centroid": round(sum(float(row["distance_to_centroid"]) for row in topic_docs if row.get("distance_to_centroid") != "") / max(sum(row.get("distance_to_centroid") != "" for row in topic_docs), 1), 6),
            "status": status, "review_status": "pending_human_review",
        })
    write_csv(out / "heterogeneity.csv", heterogeneity_rows)
    # Recompute diagnostics with distinct semantic, lexical, linguistic, source and relevance signals.
    from .bertopic_diagnostics import (
        build_document_hierarchy, export_outlier_analysis, export_review_sets, export_topic_diagnostics,
    )
    title_embeddings, _ = load_or_create_embeddings(document_ids, [row.get("title_text") or row.get("title", "") for row in documents], config, force=force_embeddings)
    abstract_embeddings, _ = load_or_create_embeddings(document_ids, [row.get("abstract_text") or "" for row in documents], config, force=force_embeddings)
    topic_terms = {topic_id: [word for word, _ in (model.get_topic(topic_id) or [])] for topic_id in valid_topic_ids}
    export_topic_diagnostics(out, documents, document_rows, semantic_embeddings, title_embeddings, abstract_embeddings, topic_terms, config)
    export_outlier_analysis(out, documents, document_rows)
    build_document_hierarchy(out, documents, document_rows, semantic_embeddings, topic_rows, config)
    export_review_sets(out, document_rows, int(config["validation"].get("representative_documents", 10)), seed)

    vectorizer_parameters = effective_vectorizer_parameters(vectorizer)
    stopword_input = vectorizer_parameters.pop("stop_words_sha256_input", "")
    effective_configuration = {
        "embedding_model_name": embedding_manifest.get("embedding_model"),
        "embedding_model_revision": embedding_manifest.get("model_revision"),
        "embedding_dimension": embedding_manifest.get("dimension"),
        "embedding_batch_size": embedding_manifest.get("batch_size"),
        "embedding_normalization": embedding_manifest.get("embedding_normalization"),
        "field_weights": embedding_manifest.get("weights", {}),
        "umap_class": f"{type(umap_model).__module__}.{type(umap_model).__name__}",
        "umap_parameters": {"n_neighbors": umap_model.n_neighbors, "n_components": umap_model.n_components, "min_dist": umap_model.min_dist, "metric": umap_model.metric, "random_state": seed, "low_memory": umap_model.low_memory},
        "hdbscan_class": f"{type(hdbscan_model).__module__}.{type(hdbscan_model).__name__}",
        "hdbscan_parameters": {"min_cluster_size": hdbscan_model.min_cluster_size, "min_samples": hdbscan_model.min_samples, "metric": hdbscan_model.metric, "cluster_selection_method": hdbscan_model.cluster_selection_method, "prediction_data": hdbscan_model.prediction_data},
        "vectorizer_class": f"{type(vectorizer).__module__}.{type(vectorizer).__name__}",
        "vectorizer_parameters": vectorizer_parameters,
        "stopwords_sha256": hashlib.sha256(stopword_input.encode("utf-8")).hexdigest(),
        "ctfidf_parameters": ctfidf.get_params() if hasattr(ctfidf, "get_params") else {"reduce_frequent_words": bool(cfg.get("reduce_frequent_words", True))},
        "representation_models": representation_components,
        "bertopic_parameters": {"embedding_model": cfg["embedding_model"] if representation_model else None, "nr_topics": cfg.get("nr_topics"), "calculate_probabilities": bool(cfg.get("calculate_probabilities", True)), "language_parameter_used": False},
        "multilingual_components": {"embeddings": True, "stopwords": True, "vectorization": True, "representation": True, "evaluation": True},
        "seed": seed, "python_version": platform.python_version(),
        "package_versions": base_metadata(config, model=model_label, documents=len(documents), discarded=0, elapsed_seconds=0).get("packages", {}),
        "corpus_hash": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
        "text_cleaning_version": TEXT_CLEANING_VERSION,
        "embedding_cache_hash": embedding_manifest.get("fingerprint"),
    }
    (out / "effective_configuration.json").write_text(json.dumps(effective_configuration, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    model_path = out / "model"
    model_save_warning = ""
    try:
        model.save(str(model_path), serialization="safetensors", save_ctfidf=True)
        model_save_mode = "safetensors_with_ctfidf"
    except TypeError as exc:
        # BERTopic 0.17.x can leave NumPy scalar values in the c-TF-IDF
        # configuration. Preserve the fitted model and record the fallback.
        if model_path.exists():
            shutil.rmtree(model_path)
        model.save(str(model_path), serialization="safetensors", save_ctfidf=False)
        model_save_mode = "safetensors_without_ctfidf"
        model_save_warning = f"c-TF-IDF state was not serialized: {exc}"
    metadata = base_metadata(config, model=model_label, documents=len(documents), discarded=0, elapsed_seconds=time.perf_counter() - started)
    metadata["corpus"] = corpus_unit
    metadata["output_name"] = output_name
    metadata["validation_status"] = "exploratory"
    metadata["embedding_cache"] = {key: value for key, value in embedding_manifest.items() if key not in {"document_ids", "text_hashes"}}
    metadata["outlier_count"] = sum(int(topic) == -1 for topic in topics)
    metadata["outlier_percentage"] = round(100 * metadata["outlier_count"] / max(len(topics), 1), 4)
    metadata["model_save_mode"] = model_save_mode
    metadata["warnings"] = [warning for warning in (model_save_warning, outlier_reduction_warning, hierarchy_warning) if warning]
    metadata["outliers_reassigned_in_alternative"] = sum(row["outlier_reassigned"] for row in document_rows)
    metadata["effective_configuration_path"] = "effective_configuration.json"
    metadata["macro_topics"] = len(valid_topic_ids)
    metadata["subtopics"] = len(read_csv(out / "subtopics.csv"))
    metadata["ambiguity_rule"] = "outlier OR low semantic margin OR low HDBSCAN membership OR low centroid similarity OR high outlier score"
    write_metadata(out / "model_metadata.json", metadata)
    return metadata
