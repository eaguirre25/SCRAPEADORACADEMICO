from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def text_hashes(texts: list[str]) -> list[str]:
    return [hashlib.sha256(text.encode("utf-8")).hexdigest() for text in texts]


def corpus_fingerprint(document_ids: list[str], texts: list[str], model_name: str) -> str:
    digest = hashlib.sha256(model_name.encode())
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
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return embeddings, manifest

