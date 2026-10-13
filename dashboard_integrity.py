"""Version-bound topic evidence and a compact publication audit."""
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from publication_identity import canonical_url, same_publication_url
from topic_modeling.identifiers import normalize_doi, normalize_text


def model_fingerprint(topics, documents):
    # Bind topic IDs to their actual partition, not just to corpus membership.
    payload = {
        "topics": sorted((str(r.get("topic_id", r.get("subtopic_id", ""))),
                          r.get("automatic_label", r.get("descriptor_automatic", ""))) for r in topics),
        "documents": sorted((str(r.get("document_id", "")), str(r.get("topic_id", "")),
                             str(r.get("subtopic_id", ""))) for r in documents),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def proposal_matches(proposal, topic, fingerprint=""):
    if not proposal:
        return False
    bound = str(proposal.get("model_fingerprint", ""))
    if bound:
        return bound == fingerprint
    # Legacy proposals have no fingerprint. Their descriptor and population
    # must both match; a corpus hash alone does not identify the fitted model.
    old = normalize_text(proposal.get("descriptor_automatic"))
    current = normalize_text(topic.get("automatic_label") or topic.get("descriptor_automatic"))
    return bool(old and old == current and
                str(proposal.get("document_count", "")) == str(topic.get("document_count", "")))


def publication_audit(records):
    groups = {k: defaultdict(list) for k in ("doi", "record_id", "url", "title")}
    for row in records:
        for field, key in (("doi", normalize_doi(row.get("doi"))),
                           ("record_id", str(row.get("record_id") or "").strip()),
                           ("url", canonical_url(row.get("url"))),
                           ("title", normalize_text(row.get("title")))):
            if key:
                groups[field][key].append(row)
    url_pairs = []
    for url, rows in groups["url"].items():
        for pos, left in enumerate(rows):
            for right in rows[pos + 1:]:
                if same_publication_url(left, right):
                    url_pairs.append({"url": url, "record_ids": [left.get("record_id"), right.get("record_id")]})
    duplicates = {field: sum(len(rows) - 1 for rows in groups[field].values())
                  for field in ("doi", "record_id")}
    return {"records": len(records), "duplicate_identifiers": duplicates,
            "duplicate_publication_urls": url_pairs,
            "homonymous_title_groups": sum(len(rows) > 1 for rows in groups["title"].values()),
            "missing_titles": sum(not str(r.get("title") or "").strip() for r in records),
            "missing_years": sum(not str(r.get("publication_year") or "").strip() for r in records)}
