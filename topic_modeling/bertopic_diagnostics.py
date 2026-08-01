from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .bertopic_search import _cluster_terms
from .corpus_builder import write_csv


def ambiguity_flag(row: dict[str, Any], config: dict[str, Any]) -> bool:
    if int(row.get("topic_id", -1)) < 0:
        return False
    cfg = config["bertopic"].get("ambiguity", {})
    margin = float(row.get("assignment_margin") or 0)
    membership = float(row.get("hdbscan_membership_strength") or 0)
    local = float(row.get("local_consistency") or 0)
    centroid = float(row.get("nearest_centroid_similarity") or 0)
    outlier_score = float(row.get("outlier_score") or 0)
    contextual_low_margin = margin < float(cfg.get("margin_below", 0.08)) and (
        membership < float(cfg.get("membership_context_below", 0.80)) or
        local < float(cfg.get("local_consistency_below", 0.60))
    )
    return bool(contextual_low_margin or membership < float(cfg.get("membership_below", 0.35)) or
                centroid < float(cfg.get("centroid_similarity_below", 0.35)) or
                outlier_score > float(cfg.get("outlier_score_above", 0.80)))


def classify_heterogeneity(*, documents: int, minimum_size: int, contamination_status: str,
                           language_status: str, dominant_source_share: float,
                           silhouette_mean: float, semantic_dispersion: float,
                           borderline_share: float) -> str:
    if documents < minimum_size: return "too_small"
    if contamination_status == "contaminated_candidate": return "contaminated_candidate"
    if language_status == "language_driven_candidate": return "language_driven_candidate"
    if dominant_source_share > 0.85: return "source_driven_candidate"
    if silhouette_mean < 0 or semantic_dispersion > 0.45 or borderline_share > 0.45: return "heterogeneous_candidate"
    if semantic_dispersion > 0.30 or borderline_share > 0.25: return "broad_but_interpretable"
    return "coherent_candidate"


def _entropy(values: list[str]) -> float:
    counts = Counter(value or "unknown" for value in values); total = sum(counts.values())
    return -sum((count / total) * math.log(count / total) for count in counts.values()) if total else 0.0


def _mean_pairwise_distance(matrix) -> float:
    import numpy as np
    if len(matrix) < 2: return 0.0
    centroid = np.asarray(matrix).mean(axis=0); centroid /= max(float(np.linalg.norm(centroid)), 1e-12)
    return float(np.mean(1 - np.clip(np.asarray(matrix) @ centroid, -1, 1)))


def export_topic_diagnostics(out: Path, documents: list[dict[str, Any]], rows: list[dict[str, Any]], embeddings, title_embeddings, abstract_embeddings, topic_terms: dict[int, list[str]], config: dict[str, Any]) -> None:
    import numpy as np
    from sklearn.metrics import normalized_mutual_info_score
    from sklearn.neighbors import NearestNeighbors

    labels = np.asarray([int(row["topic_id"]) for row in rows]); embeddings = np.asarray(embeddings)
    languages = [row.get("language") or "und" for row in rows]
    valid = labels >= 0
    global_language_mi = float(normalized_mutual_info_score(np.asarray(languages)[valid], labels[valid])) if valid.any() else 0.0
    global_sources = Counter(doc.get("source") or "unknown" for doc in documents)
    neighbor_idx = NearestNeighbors(n_neighbors=min(11, len(rows)), metric="cosine").fit(embeddings).kneighbors(return_distance=False)
    language_rows=[]; heterogeneity=[]; contamination=[]
    domain_scores = [float(doc.get("relevance_score") or 0) for doc in documents]
    for topic_id in sorted(int(x) for x in set(labels) if int(x) >= 0):
        indexes=np.where(labels==topic_id)[0]; topic_rows=[rows[int(i)] for i in indexes]; topic_docs=[documents[int(i)] for i in indexes]
        lang=[languages[int(i)] for i in indexes]; counts=Counter(lang); dominant_language, dominant_count=max(counts.items(),key=lambda x:x[1])
        source=[doc.get("source") or "unknown" for doc in topic_docs]; country=[doc.get("country") or "unknown" for doc in topic_docs]
        cross=[]
        for i in indexes:
            local=[j for j in neighbor_idx[int(i)] if j!=i][:10]
            cross.append(sum(languages[int(j)]!=languages[int(i)] for j in local)/max(len(local),1))
        language_centroids={}
        for language in counts:
            matrix=embeddings[[int(i) for i in indexes if languages[int(i)]==language]]
            centroid=matrix.mean(axis=0); centroid/=max(float(np.linalg.norm(centroid)),1e-12); language_centroids[language]=centroid
        cross_centroid=[]
        keys=sorted(language_centroids)
        for pos,left in enumerate(keys):
            for right in keys[pos+1:]: cross_centroid.append(float(language_centroids[left]@language_centroids[right]))
        dom_share=dominant_count/len(indexes); lang_entropy=_entropy(lang); source_entropy=_entropy(source); country_entropy=_entropy(country)
        dominant_source, dominant_source_count = Counter(source).most_common(1)[0]
        dominant_source_share=dominant_source_count/len(source); dominant_country_share=max(Counter(country).values())/len(country)
        global_source_share=global_sources[dominant_source]/len(documents)
        semantic_cross=float(np.mean(cross)) if cross else 0.0; centroid_cross=float(np.mean(cross_centroid)) if cross_centroid else 0.0
        if len(counts)>1 and dom_share<0.80: classification="multilingual_topic"
        elif dominant_country_share>0.80 and Counter(country).most_common(1)[0][0]!="unknown": classification="geographically_specific"
        elif dom_share>0.85 and semantic_cross<0.05 and centroid_cross<0.55: classification="language_driven_candidate"
        elif dom_share>0.80: classification="language_concentrated_but_thematic"
        else: classification="insufficient_evidence"
        language_rows.append({
            "model":rows[0]["model"],"corpus":rows[0]["corpus"],"topic_id":topic_id,
            "topic_language_distribution":str(dict(counts)),"dominant_language":dominant_language,"dominant_language_share":round(dom_share,6),
            "language_entropy":round(lang_entropy,6),"language_mutual_information":round(global_language_mi,6),
            "topic_vs_language_residual":round(dom_share-(Counter(languages)[dominant_language]/len(languages)),6),
            "cross_language_nearest_neighbors":round(semantic_cross,6),"cross_language_centroid_similarity":round(centroid_cross,6),
            "dominant_source_share":round(dominant_source_share,6),"dominant_country_share":round(dominant_country_share,6),
            "classification":classification,"review_status":"pending_human_review",
        })
        relevant=sum(doc.get("relevance_status")=="included" for doc in topic_docs)/len(topic_docs)
        borderline=sum(doc.get("relevance_status") in {"borderline","manual_review"} for doc in topic_docs)/len(topic_docs)
        excluded=sum(doc.get("relevance_status")=="excluded" for doc in topic_docs)/len(topic_docs)
        # `relevance_score` is a rule score, not a cosine.  Bound its exported
        # proxy to [0, 1] so it cannot masquerade as an impossible similarity.
        scores=np.clip([domain_scores[int(i)] for i in indexes], 0.0, 1.0)
        terms=set(topic_terms.get(topic_id,[])); contam_terms=sorted(terms & {"hospital","patient","clinical","nursing","tax","accounting","mineral","suicide","pmid","scielo","redalyc"})
        contamination_status="domain_relevant"
        if excluded>0.20 or relevant<0.55: contamination_status="contaminated_candidate"
        elif borderline>0.20 or contam_terms: contamination_status="mixed_relevance"
        contamination.append({"topic_id":topic_id,"included_document_share":round(relevant,6),"borderline_document_share":round(borderline,6),"excluded_candidate_share":round(excluded,6),"domain_similarity_mean":round(float(np.mean(scores)),6),"domain_similarity_min":round(float(np.min(scores)),6),"contamination_terms":" | ".join(contam_terms),"representative_contaminating_documents":" | ".join(doc.get("title","") for doc in topic_docs if doc.get("relevance_status")!="included")[:4000],"status":contamination_status,"review_status":"pending_human_review"})
        sil=[float(row["silhouette"]) for row in topic_rows if row.get("silhouette")!=""]
        membership=[float(row.get("hdbscan_membership_strength") or 0) for row in topic_rows]
        borderline_share=sum(bool(row.get("is_ambiguous")) for row in topic_rows)/len(topic_rows)
        low_share=sum(value<0.35 for value in membership)/len(membership)
        compact=_mean_pairwise_distance(embeddings[indexes]); title_disp=_mean_pairwise_distance(np.asarray(title_embeddings)[indexes]); abstract_disp=_mean_pairwise_distance(np.asarray(abstract_embeddings)[indexes])
        source_driven_signal = dominant_source_share if dominant_source_share - global_source_share > 0.15 else 0.0
        status=classify_heterogeneity(documents=len(indexes),minimum_size=int(config["bertopic"].get("min_topic_size",35)),contamination_status=contamination_status,language_status=classification,dominant_source_share=source_driven_signal,silhouette_mean=float(np.mean(sil)) if sil else -1,semantic_dispersion=compact,borderline_share=borderline_share)
        heterogeneity.append({"model":rows[0]["model"],"corpus":rows[0]["corpus"],"topic_id":topic_id,"documents":len(indexes),"embedding_compactness":round(1-compact,6),"silhouette_mean":round(float(np.mean(sil)),6) if sil else "","silhouette_min":round(float(np.min(sil)),6) if sil else "","title_semantic_dispersion":round(title_disp,6),"abstract_semantic_dispersion":round(abstract_disp,6),"ctfidf_coherence_cv":"","ctfidf_coherence_npmi":"","topic_diversity":round(len(terms)/max(sum(len(v) for v in topic_terms.values()),1),6),"language_entropy":round(lang_entropy,6),"dominant_language_share":round(dom_share,6),"source_entropy":round(source_entropy,6),"country_entropy":round(country_entropy,6),"contamination_share":round(max(excluded,borderline),6),"borderline_document_share":round(borderline_share,6),"low_confidence_share":round(low_share,6),"status":status,"review_status":"pending_human_review"})
    write_csv(out/"language_dependence.csv",language_rows); write_csv(out/"language_alignment_report.csv",language_rows); write_csv(out/"contamination_report.csv",contamination); write_csv(out/"heterogeneity.csv",heterogeneity)


def export_outlier_analysis(out: Path, documents: list[dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    results=[]
    for doc,row in zip(documents,rows,strict=True):
        if int(row["topic_id"])!=-1: continue
        length=int(float(doc.get("text_characters") or len(doc.get("text_for_modeling", ""))))
        similarity=float(row.get("nearest_centroid_similarity") or 0); margin=float(row.get("assignment_margin") or 0); score=float(row.get("outlier_score") or 0)
        if length<200 or not doc.get("abstract_text"): reason="short_or_incomplete_text"
        elif doc.get("relevance_status")!="included": reason="contamination_candidate"
        elif similarity>=0.55 and margin<0.08: reason="borderline_between_topics"
        elif similarity>=0.55: reason="representation_failure"
        elif score<0.55: reason="small_valid_theme"
        elif score>=0.85: reason="true_noise"
        else: reason="unknown"
        results.append({"document_id":row["document_id"],"language":row.get("language",""),"year":row.get("year",""),"source":row.get("source",""),"text_length":length,"has_abstract":bool(doc.get("abstract_text")),"relevance_status":doc.get("relevance_status",""),"hdbscan_outlier_score":row.get("outlier_score",""),"nearest_topic":row.get("nearest_topic",""),"nearest_topic_similarity":row.get("nearest_centroid_similarity",""),"second_nearest_topic":row.get("second_nearest_topic",""),"similarity_margin":row.get("assignment_margin",""),"reason_category":reason,"original_topic":-1,"suggested_topic":row.get("suggested_topic",""),"reassignment_method":row.get("reassignment_method",""),"reassignment_confidence":row.get("reassignment_confidence",""),"accepted_reassignment":False})
    write_csv(out/"outlier_analysis.csv",results)


def build_document_hierarchy(out: Path, documents: list[dict[str, Any]], rows: list[dict[str, Any]], embeddings, topic_rows: list[dict[str, Any]], config: dict[str, Any]) -> None:
    import numpy as np
    from hdbscan import HDBSCAN
    from umap import UMAP

    labels=np.asarray([int(row["topic_id"]) for row in rows]); embeddings=np.asarray(embeddings); threshold=int(config["bertopic"]["macro_search"]["subcluster_minimum_documents"]); seed=int(config["project"]["seed"])
    topic_by_id={int(row["topic_id"]):row for row in topic_rows}; macro=[]; sub=[]; hierarchy=[]; assignments=[]
    sublabels_by_index={}
    for topic_id in sorted(x for x in set(labels) if x>=0):
        indexes=np.where(labels==topic_id)[0]; topic=topic_by_id[topic_id]
        macro.append({"macro_topic_id":topic_id,"descriptor_automatic":topic.get("label_automatic",""),"human_label":topic.get("label_human",""),"macro_topic_size":len(indexes),"validation_status":"pending_human_review"})
        if len(indexes)>=threshold:
            reduced=UMAP(n_neighbors=min(15,len(indexes)-1),n_components=min(5,len(indexes)-2),min_dist=0.05,metric="cosine",random_state=seed,low_memory=True).fit_transform(embeddings[indexes])
            min_size=max(10,min(20,len(indexes)//4)); local=HDBSCAN(min_cluster_size=min_size,min_samples=5,metric="euclidean",cluster_selection_method="eom").fit_predict(reduced)
            local_terms=_cluster_terms([documents[int(i)].get("text_for_vectorizer") or documents[int(i)].get("text_for_modeling","") for i in indexes],local,config)
            for local_id in sorted(x for x in set(local) if x>=0):
                key=f"{topic_id}.{local_id}"; count=int(np.sum(local==local_id)); sub.append({"macro_topic_id":topic_id,"subtopic_id":key,"parent_topic_id":topic_id,"hierarchy_level":2,"macro_topic_size":len(indexes),"subtopic_size":count,"descriptor_automatic":" · ".join(local_terms.get(int(local_id),[])[:5]),"human_label":"","validation_status":"pending_human_review"}); hierarchy.append({"parent_topic_id":topic_id,"subtopic_id":key,"relationship":"subcluster","decision_status":"provisional_computational"})
            for position,index in enumerate(indexes): sublabels_by_index[int(index)]="" if int(local[position])<0 else f"{topic_id}.{int(local[position])}"
    for index,row in enumerate(rows): assignments.append({"document_id":row["document_id"],"original_topic":row["original_topic"],"macro_topic_id":"" if int(row["topic_id"])<0 else row["topic_id"],"subtopic_id":sublabels_by_index.get(index,""),"parent_topic_id":"" if int(row["topic_id"])<0 else row["topic_id"],"hierarchy_level":0 if int(row["topic_id"])<0 else (2 if sublabels_by_index.get(index) else 1),"is_outlier":int(row["topic_id"])<0,"merge_proposal":"","human_decision":"pending"})
    write_csv(out/"macro_topics.csv",macro); write_csv(out/"subtopics.csv",sub); write_csv(out/"topic_hierarchy.csv",hierarchy,["parent_topic_id","subtopic_id","relationship","decision_status"]); write_csv(out/"document_topic_hierarchy.csv",assignments)


def export_review_sets(out: Path, rows: list[dict[str, Any]], per_set: int, seed: int) -> None:
    rng=random.Random(seed); groups=defaultdict(list)
    for row in rows:
        if int(row["topic_id"])>=0: groups[int(row["topic_id"])].append(row)
    central=[]; borderline=[]; low=[]; random_rows=[]
    for topic_id,docs in groups.items():
        central.extend(sorted(docs,key=lambda r:float(r.get("distance_to_centroid") or 1e9))[:per_set])
        borderline.extend(sorted(docs,key=lambda r:float(r.get("assignment_margin") or 0))[:per_set])
        low.extend(sorted(docs,key=lambda r:float(r.get("hdbscan_membership_strength") or 0))[:per_set])
        random_rows.extend(rng.sample(docs,min(per_set,len(docs))))
    for name,data in (("central_documents.csv",central),("borderline_documents.csv",borderline),("low_confidence_documents.csv",low),("random_documents.csv",random_rows)): write_csv(out/name,data)
