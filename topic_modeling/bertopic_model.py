from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any

from .corpus_builder import read_csv, write_csv
from .embeddings import load_or_create_embeddings
from .metadata import base_metadata, write_metadata
from .topic_labels import automatic_label, load_human_labels, resolve_label


FUNCTIONAL_STOPWORDS = [
    "de", "la", "el", "en", "y", "a", "los", "del", "las", "por", "para", "con", "una", "un",
    "the", "and", "of", "in", "to", "for", "with", "on", "that", "this", "from",
    "que", "da", "do", "dos", "das", "em", "não", "com", "para", "uma",
    "dan", "yang", "untuk", "dengan", "dalam", "pada", "dari", "ini", "itu",
]


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


def run_bertopic(config: dict[str, Any], *, corpus_unit: str = "metadata", force_embeddings: bool = False) -> dict[str, Any]:
    import numpy as np
    from bertopic import BERTopic
    from bertopic.vectorizers import ClassTfidfTransformer
    from hdbscan import HDBSCAN
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP

    started = time.perf_counter()
    seed = int(config["project"]["seed"])
    random.seed(seed)
    np.random.seed(seed)
    root = Path(config["paths"]["output_root"])
    corpus_path = root / "corpus" / f"modeling_corpus_{corpus_unit}.csv"
    documents = read_csv(corpus_path)
    document_ids = [row["document_id"] for row in documents]
    texts = [row["texto_modelado"] for row in documents]
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
    vectorizer = CountVectorizer(
        ngram_range=(int(cfg["ngram_min"]), int(cfg["ngram_max"])), stop_words=FUNCTIONAL_STOPWORDS,
        min_df=int(cfg.get("min_df", 2)), max_df=float(cfg.get("max_df", 0.95)),
        max_features=int(cfg["max_features"]), strip_accents="unicode", token_pattern=r"(?u)\b[^\W\d_][\w-]+\b",
    )
    ctfidf = ClassTfidfTransformer(reduce_frequent_words=bool(cfg.get("reduce_frequent_words", True)))
    model = BERTopic(
        embedding_model=None, umap_model=umap_model, hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer, ctfidf_model=ctfidf, nr_topics=cfg.get("nr_topics", "auto"),
        calculate_probabilities=bool(cfg.get("calculate_probabilities", True)), verbose=True,
    )
    topics, probabilities = model.fit_transform(texts, embeddings=np.asarray(embeddings))
    out = root / "bertopic"
    out.mkdir(parents=True, exist_ok=True)
    human = load_human_labels(config["paths"]["human_labels"])
    info = model.get_topic_info()
    valid_topic_ids = sorted(int(topic) for topic in info["Topic"].tolist() if int(topic) >= 0)
    topic_rows: list[dict[str, Any]] = []
    representative_rows: list[dict[str, Any]] = []
    total = len(documents)
    for _, item in info.iterrows():
        topic_id = int(item["Topic"])
        words = [word for word, _ in (model.get_topic(topic_id) or [])]
        proposal = "Outliers" if topic_id == -1 else automatic_label(words)
        labels = resolve_label("bertopic", topic_id, proposal, human)
        reps = (model.get_representative_docs(topic_id) or []) if topic_id >= 0 else []
        topic_rows.append({
            "model": "bertopic", "topic_id": topic_id, **labels,
            "prevalence": round(100 * int(item["Count"]) / max(total, 1), 4),
            "document_count": int(item["Count"]), "top_words": " | ".join(words[:15]),
            "top_ngrams": " | ".join(word for word in words if " " in word)[:2000],
            "representative_titles": " | ".join(row["title"] for row in documents if row["texto_modelado"] in reps)[:4000],
            "coherence": "", "diversity": "", "stability": "", "is_outlier": topic_id == -1,
        })
        for rank, text in enumerate(reps, 1):
            try:
                idx = texts.index(text)
                representative_rows.append({"model": "bertopic", "topic_id": topic_id, "rank": rank, "document_id": document_ids[idx], "title": documents[idx]["title"]})
            except ValueError:
                continue
    document_rows: list[dict[str, Any]] = []
    margin_threshold = float(config["validation"]["ambiguous_probability_margin"])
    for index, (row, topic_id) in enumerate(zip(documents, topics, strict=True)):
        first, second_id, second, margin = _probability_fields(probabilities, valid_topic_ids, index, int(topic_id))
        document_rows.append({
            "document_id": row["document_id"], "model": "bertopic", "topic_id": int(topic_id),
            "topic_probability": first, "second_topic_id": second_id, "second_topic_probability": second,
            "probability_margin": margin, "is_outlier": int(topic_id) == -1,
            "is_ambiguous": margin != "" and float(margin) < margin_threshold,
            "year": row["year"], "language": row["language"], "title": row["title"], "doi": row["doi"],
            "source": row["source"], "corpus_unit": row["corpus_unit"],
            "topic_original": int(topic_id), "topic_after_outlier_reduction": int(topic_id), "outlier_reassigned": False,
        })
    write_csv(out / "topics.csv", topic_rows)
    write_csv(out / "document_topics.csv", document_rows)
    write_csv(out / "topic_words.csv", [
        {"model": "bertopic", "topic_id": topic_id, "rank": rank, "term": word, "weight": weight}
        for topic_id in valid_topic_ids for rank, (word, weight) in enumerate(model.get_topic(topic_id) or [], 1)
    ])
    write_csv(out / "representative_documents.csv", representative_rows)
    write_csv(out / "outliers.csv", [row for row in document_rows if row["is_outlier"]])
    model.save(str(out / "model"), serialization="safetensors", save_ctfidf=True)
    metadata = base_metadata(config, model="bertopic", documents=len(documents), discarded=0, elapsed_seconds=time.perf_counter() - started)
    metadata["embedding_cache"] = {key: value for key, value in embedding_manifest.items() if key not in {"document_ids", "text_hashes"}}
    metadata["outlier_count"] = sum(int(topic) == -1 for topic in topics)
    metadata["outlier_percentage"] = round(100 * metadata["outlier_count"] / max(len(topics), 1), 4)
    write_metadata(out / "model_metadata.json", metadata)
    return metadata
