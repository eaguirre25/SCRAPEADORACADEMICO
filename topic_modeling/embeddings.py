from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .text_cleaning import clean_for_embeddings


TEXT_CLEANING_VERSION = "unicode-nfc-v2"


def _model_revision(model: Any) -> str | None:
    try:
        return getattr(model._first_module().auto_model.config, "_commit_hash", None)
    except AttributeError:
        return None


def text_hashes(texts: list[str]) -> list[str]:
    return [hashlib.sha256(text.encode("utf-8")).hexdigest() for text in texts]


def corpus_fingerprint(document_ids: list[str], texts: list[str], model_name: str) -> str:
    digest = hashlib.sha256(f"{model_name}|{TEXT_CLEANING_VERSION}".encode())
    for document_id, text_hash in zip(document_ids, text_hashes(texts), strict=True):
        digest.update(document_id.encode())
        digest.update(text_hash.encode())
    return digest.hexdigest()


def load_or_create_embeddings(
    document_ids: list[str], texts: list[str], config: dict[str, Any], *, force: bool = False
):
    import numpy as np

    model_name = config["bertopic"]["embedding_model"]
    cache_root = Path(config["paths"]["cache_root"]) / "embeddings"
    cache_root.mkdir(parents=True, exist_ok=True)
    fingerprint = corpus_fingerprint(document_ids, texts, model_name)
    array_path = cache_root / f"{fingerprint}.npy"
    manifest_path = cache_root / f"{fingerprint}.json"
    if not force and array_path.exists() and manifest_path.exists():
        return np.load(array_path, mmap_mode="r"), json.loads(manifest_path.read_text(encoding="utf-8"))

    from sentence_transformers import SentenceTransformer

    texts = [clean_for_embeddings(text)[0] for text in texts]
    model = SentenceTransformer(model_name, cache_folder=str(cache_root / "models"))
    embeddings = model.encode(
        texts,
        batch_size=int(config["bertopic"].get("batch_size", 16)),
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    np.save(array_path, embeddings)
    manifest = {
        "fingerprint": fingerprint,
        "embedding_model": model_name,
        "dimension": int(embeddings.shape[1]),
        "documents": len(document_ids),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "document_ids": document_ids,
        "text_hashes": text_hashes(texts),
        "embedding_normalization": True, "batch_size": int(config["bertopic"].get("batch_size", 16)),
        "model_revision": _model_revision(model),
        "text_cleaning_version": TEXT_CLEANING_VERSION,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return embeddings, manifest


def load_or_create_metadata_embeddings(
    documents: list[dict[str, Any]], config: dict[str, Any], *, force: bool = False, variant: str = "weighted_fields"
):
    """Encode metadata fields separately and combine only fields available per publication."""
    import numpy as np

    model_name = config["bertopic"]["embedding_model"]
    cfg = config.get("metadata_embeddings", {})
    weights = {
        "title_text": float(cfg.get("title_weight", 0.35)),
        "abstract_text": float(cfg.get("abstract_weight", 0.50)),
        "keywords_text": 0.0 if variant == "title_abstract_only" else float(cfg.get("keywords_weight", 0.15)),
    }
    document_ids = [row["document_id"] for row in documents]
    cleaned_fields = [
        {field: clean_for_embeddings(str(row.get(field, "") or ""))[0] for field in weights}
        for row in documents
    ]
    signature_texts = ["\n".join(f"{field}:{row[field]}" for field in weights) for row in cleaned_fields]
    fingerprint = corpus_fingerprint(document_ids, signature_texts, model_name + json.dumps(weights, sort_keys=True))
    cache_root = Path(config["paths"]["cache_root"]) / "embeddings"
    cache_root.mkdir(parents=True, exist_ok=True)
    array_path = cache_root / f"{fingerprint}.npy"
    manifest_path = cache_root / f"{fingerprint}.json"
    if not force and array_path.exists() and manifest_path.exists():
        return np.load(array_path, mmap_mode="r"), json.loads(manifest_path.read_text(encoding="utf-8"))

    field_embeddings: dict[str, Any] = {}
    field_manifests: dict[str, Any] = {}
    for field, weight in weights.items():
        if weight <= 0:
            continue
        values = [row[field] for row in cleaned_fields]
        encoded, field_manifest = load_or_create_embeddings(document_ids, values, config, force=force)
        field_embeddings[field] = np.asarray(encoded)
        field_manifests[field] = {key: value for key, value in field_manifest.items() if key not in {"document_ids", "text_hashes"}}
    if not field_embeddings:
        raise ValueError("At least one metadata field must have a positive embedding weight")
    dimension = int(next(iter(field_embeddings.values())).shape[1])
    combined = np.zeros((len(documents), dimension), dtype=np.float32)
    denominators = np.zeros(len(documents), dtype=np.float32)
    for index, row in enumerate(cleaned_fields):
        for field, weight in weights.items():
            value = str(row.get(field, "") or "").strip()
            if weight > 0 and value:
                combined[index] += weight * field_embeddings[field][index]
                denominators[index] += weight
    if np.any(denominators == 0):
        raise ValueError("At least one metadata publication has no embeddable field")
    combined /= denominators[:, None]
    norms = np.linalg.norm(combined, axis=1, keepdims=True)
    combined /= np.maximum(norms, 1e-12)
    np.save(array_path, combined)
    manifest = {
        "fingerprint": fingerprint, "embedding_model": model_name, "dimension": dimension,
        "documents": len(document_ids), "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "document_ids": document_ids, "text_hashes": text_hashes(signature_texts),
        "combination": "weighted_field_average", "variant": variant, "weights": weights,
        "embedding_normalization": True, "batch_size": int(config["bertopic"].get("batch_size", 16)),
        "model_revision": next((value.get("model_revision") for value in field_manifests.values() if value.get("model_revision")), None),
        "text_cleaning_version": TEXT_CLEANING_VERSION,
        "field_embedding_manifests": field_manifests,
        "available_field_counts": {
            field: sum(bool(row.get(field, "")) for row in cleaned_fields) for field in weights
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return combined, manifest
