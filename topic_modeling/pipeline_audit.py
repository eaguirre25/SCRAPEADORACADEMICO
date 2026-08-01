from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .corpus_builder import read_csv


def audit_topic_pipeline(config: dict[str, Any]) -> dict[str, Any]:
    root = Path(config["paths"]["output_root"]); old = root / "bertopic" / "metadata_multilingual"
    metadata = json.loads((old / "model_metadata.json").read_text(encoding="utf-8")) if (old / "model_metadata.json").exists() else {}
    internal = json.loads((old / "model" / "config.json").read_text(encoding="utf-8")) if (old / "model" / "config.json").exists() else {}
    selected = json.loads((old / "selected_parameters.json").read_text(encoding="utf-8")) if (old / "selected_parameters.json").exists() else {}
    docs = read_csv(old / "document_topics.csv"); topics = read_csv(old / "topics.csv"); heterogeneity = read_csv(old / "heterogeneity.csv")
    language = read_csv(old / "language_dependence.csv"); stability = read_csv(root / "evaluation" / "stability.csv")
    outliers = sum(row.get("topic_id") == "-1" for row in docs); ambiguous = sum(row.get("is_ambiguous", "").casefold() == "true" for row in docs)
    report = {
        "status": "needs_revision",
        "configuration_effective_previous": selected.get("selected", {}),
        "configuration_declared_previous": config.get("bertopic", {}),
        "serialized_internal_defaults_not_effective": internal,
        "findings": {
            "unicode_loss": "CountVectorizer(strip_accents='unicode') removed diacritics from c-TF-IDF terms; identifiers.normalize_text transliterated only matching keys; a small number of source abstracts were already damaged upstream.",
            "probability_and_ambiguity": "topic_probability stored the maximum BERTopic distribution for every row and ambiguity used only a <0.10 top-two margin; HDBSCAN membership, outlier score and centroid similarity were not separated.",
            "heterogeneity": "Mean UMAP silhouette plus one language condition produced coarse labels; no lexical, source, country, contamination or review-set evidence was combined.",
            "contamination": "A fixed intersection between top words and a short contamination vocabulary; document-level relevance evidence was not aggregated.",
            "language_dependence": "Dominant-language share >0.80 only; geography, source and cross-language semantic neighbors were absent.",
            "stability": "The preliminary command explicitly omitted --run-stability; the selected BERTopic candidate was never replicated.",
            "cluster_generation": "The preliminary score selected UMAP(10,10,0.0)+HDBSCAN(min_cluster_size=10,min_samples=10,leaf), a fragmenting configuration with no early rejection rules.",
            "outlier_explanation": "Restrictive density settings, leaf selection and low-neighbor UMAP yielded many small islands; short/partial metadata, language separation and true low-density themes were not separately characterized.",
        },
        "observed_previous": {"documents": len(docs), "topics_excluding_outliers": sum(row.get("topic_id") != "-1" for row in topics), "outliers": outliers, "outlier_percentage": round(100*outliers/max(len(docs),1),4), "ambiguous_documents": ambiguous, "heterogeneity_statuses": dict(__import__("collections").Counter(row.get("status","") for row in heterogeneity)), "language_flagged_topics": sum(row.get("potentially_language_driven","").casefold()=="true" for row in language), "stability_missing_rows": sum(not row.get("stability") for row in stability)},
    }
    target=root/"reports"/"pipeline_audit.json"; target.parent.mkdir(parents=True,exist_ok=True); target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report
