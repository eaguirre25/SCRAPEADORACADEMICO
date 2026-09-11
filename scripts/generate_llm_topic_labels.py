#!/usr/bin/env python3
"""Generate auditable LLM-assisted labels for the preferred BERTopic solution.

The LLM never changes cluster membership. It receives topic terms plus a small,
traceable sample of representative documents and returns three label variants.
Researcher validation remains a separate field and has precedence in the UI.
"""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFERRED = ROOT / "output/topic_models/bertopic/metadata_multilingual/preferred_solution"
VALIDATION = ROOT / "output/topic_models/validation"
OUT = VALIDATION / "topic_llm_labels.csv"
MODEL = os.getenv("OPENAI_LABEL_MODEL", "gpt-5")


def read_csv(path: Path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def clean(value):
    return " ".join(str(value or "").split())


def f(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def representative_evidence(topic_id: int, docs: list[dict], metadata: dict[str, dict], limit: int = 6):
    ranked = sorted(
        [d for d in docs if int(d.get("topic_id", -999)) == topic_id],
        key=lambda r: (f(r.get("distance_to_centroid"), 999), -f(r.get("topic_probability"), 0)),
    )[:limit]
    evidence = []
    for row in ranked:
        meta = metadata.get(row.get("document_id", ""), {})
        evidence.append({
            "document_id": row.get("document_id", ""),
            "title": clean(meta.get("title") or row.get("title")),
            "abstract": clean(meta.get("abstract"))[:1200],
            "year": clean(meta.get("year")),
            "language": clean(meta.get("language")),
            "source": clean(meta.get("source")),
        })
    return evidence


def call_llm(topic_id: int, automatic_label: str, terms: list[str], evidence: list[dict]):
    from openai import OpenAI

    client = OpenAI()
    prompt = {
        "task": "Etiquetar un tópico de literatura académica para investigación social y educativa.",
        "rules": [
            "No inventes un alcance que no esté respaldado por la evidencia.",
            "Distingue una etiqueta descriptiva, una conceptual y una breve.",
            "La etiqueta conceptual debe nombrar el problema o relación sustantiva, no solo repetir palabras frecuentes.",
            "Indica incertidumbre cuando los documentos sean heterogéneos.",
            "Devuelve solamente JSON válido con las claves solicitadas.",
        ],
        "topic_id": topic_id,
        "automatic_label": automatic_label,
        "top_terms": terms,
        "representative_documents": evidence,
        "output_schema": {
            "descriptive_label": "string",
            "conceptual_label": "string",
            "short_label": "string",
            "definition": "string",
            "confidence": "alta|media|baja",
            "rationale": "string",
            "evidence_note": "string",
        },
    }
    response = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": "Sos un asistente de análisis textual académico. Priorizá trazabilidad, prudencia interpretativa y precisión conceptual."},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
    )
    text = response.output_text.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    return json.loads(text)


def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY no configurada: se omite el etiquetado LLM sin alterar resultados existentes.")
        return

    topics = [r for r in read_csv(PREFERRED / "topics.csv") if int(r.get("topic_id", -1)) >= 0]
    doc_topics = read_csv(PREFERRED / "document_topics.csv")
    metadata_rows = read_csv(ROOT / "output/topic_models/corpus/modeling_corpus_metadata.csv")
    metadata = {r.get("document_id", ""): r for r in metadata_rows}
    words = defaultdict(list)
    for r in read_csv(PREFERRED / "topic_words.csv"):
        try:
            tid = int(r.get("topic_id", -1))
        except Exception:
            continue
        if tid >= 0:
            words[tid].append(r.get("term", ""))

    existing = {r.get("topic_id", ""): r for r in read_csv(OUT)}
    validation = {r.get("topic_id", ""): r for r in read_csv(VALIDATION / "topic_validation.csv")}
    rows = []

    for topic in topics:
        tid = int(topic["topic_id"])
        key = str(tid)
        evidence = representative_evidence(tid, doc_topics, metadata)
        try:
            result = call_llm(tid, clean(topic.get("automatic_label")), words[tid][:18], evidence)
            status = "llm_proposed_pending_human_validation"
            error = ""
        except Exception as exc:
            previous = existing.get(key, {})
            result = {
                "descriptive_label": previous.get("descriptive_label", ""),
                "conceptual_label": previous.get("conceptual_label", ""),
                "short_label": previous.get("short_label", ""),
                "definition": previous.get("definition", ""),
                "confidence": previous.get("confidence", ""),
                "rationale": previous.get("rationale", ""),
                "evidence_note": previous.get("evidence_note", ""),
            }
            status = "llm_error_previous_value_preserved" if previous else "llm_error"
            error = clean(exc)[:500]

        human = validation.get(key, {})
        rows.append({
            "topic_id": key,
            "automatic_label": clean(topic.get("automatic_label")),
            "descriptive_label": clean(result.get("descriptive_label")),
            "conceptual_label": clean(result.get("conceptual_label")),
            "short_label": clean(result.get("short_label")),
            "definition": clean(result.get("definition")),
            "confidence": clean(result.get("confidence")),
            "rationale": clean(result.get("rationale")),
            "evidence_note": clean(result.get("evidence_note")),
            "evidence_document_ids": " | ".join(e.get("document_id", "") for e in evidence),
            "researcher_label": clean(human.get("human_label") or human.get("validated_label")),
            "researcher_status": clean(human.get("status") or human.get("label_status")),
            "llm_status": status,
            "model": MODEL,
            "error": error,
        })

    VALIDATION.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Etiquetas LLM: {len(rows)} tópicos -> {OUT}")


if __name__ == "__main__":
    main()
