#!/usr/bin/env python3
"""Build the auditable, provisional human interpretation layer for BERTopic.

This script never changes cluster membership or outlier status.  It joins the
selected computational solution with corpus metadata and writes review aids.
Labels are proposals, not specialist validation.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFERRED = ROOT / "output/topic_models/bertopic/metadata_multilingual/preferred_solution"
VALIDATION = ROOT / "output/topic_models/validation"
DOSSIERS = VALIDATION / "topic_dossiers"
SEED = 42


# Interpretive decisions based on titles, abstracts, descriptors and four
# document strata per topic.  They remain explicitly provisional.
INTERPRETATIONS = {
    0: ("Enfoques y prácticas de liderazgo escolar", "Estudios sobre estilos, prácticas y capacidades de liderazgo de directores y otros líderes escolares.", "alta", "mantener", "El liderazgo es el objeto sustantivo común; reúne tradiciones transformacional, pedagógica e instruccional."),
    1: ("Calidad educativa y mejora de la gestión escolar", "Relaciones entre gestión, calidad educativa, evaluación y mejora institucional, incluidos modelos de calidad total.", "alta", "mantener", "La calidad y la mejora constituyen el eje; no se reduce a planificación estratégica ni a desempeño individual."),
    2: ("Tecnologías digitales y sistemas de información para la gestión educativa", "Uso de TIC, plataformas, datos y sistemas de información en procesos administrativos, pedagógicos y de gestión.", "alta", "mantener", "La tecnología es un medio transversal; IA forma un núcleo suficientemente específico en T9."),
    3: ("Gestión escolar en contextos rurales y territoriales latinoamericanos", "Gestión y dirección escolar situadas en territorios rurales, indígenas y diversos contextos nacionales latinoamericanos.", "media", "revisar_división", "El núcleo rural es claro, pero el segundo subtópico amplía el conjunto hacia estudios territoriales generales, especialmente Ecuador y Colombia."),
    4: ("Competencias directivas, desempeño docente y resultados de gestión", "Estudios, mayormente correlacionales, sobre competencias de dirección, desempeño docente, cumplimiento y resultados institucionales.", "media", "revisar_división", "Convergen variables de desempeño y gestión, aunque pueden coexistir mecanismos distintos: competencia directiva, desempeño docente y resultados."),
    5: ("Gestión escolar inclusiva y atención a la diversidad", "Políticas, prácticas y apoyos de gestión para inclusión, discapacidad, necesidades educativas y participación de grupos históricamente excluidos.", "alta", "mantener", "Inclusión y diversidad articulan el conjunto; algunos casos de participación requieren revisión fronteriza."),
    6: ("Gestión y liderazgo escolar durante y después de la pandemia", "Respuestas organizacionales, tecnológicas y de liderazgo ante COVID-19, cierre escolar y pospandemia.", "alta", "mantener", "El contexto de crisis sanitaria estructura de modo inequívoco la mayoría de los documentos."),
    7: ("Planificación estratégica e innovación de la gestión escolar", "Planificación institucional, modelos de administración, innovación y herramientas para transformar la gestión escolar.", "media", "revisar_fronteras", "La planificación estratégica es el centro, pero la periferia contiene innovación general y algunos documentos de baja pertinencia."),
    8: ("Género y desigualdades en el liderazgo y la gestión escolar", "Acceso, experiencias y barreras de mujeres y diversidades en cargos directivos, junto con perspectivas de género en la gestión.", "alta", "mantener", "El núcleo documental es género y liderazgo; la evidencia revisada no justifica denominarlo racialización sin una submuestra específica."),
    9: ("Inteligencia artificial y analítica de datos en la gestión educativa", "Aplicaciones, oportunidades y riesgos de IA, aprendizaje automático y analítica para decisiones y procesos educativos.", "alta", "mantener", "IA y analítica distinguen este tópico de la digitalización general de T2; existen falsos positivos por la palabra inteligencia."),
    10: ("Participación familiar y vínculo familia–escuela", "Participación, acompañamiento y corresponsabilidad de familias en la gestión escolar y el aprendizaje.", "alta", "mantener", "El vínculo familia–escuela aparece de forma consistente en términos y documentos centrales."),
    11: ("Gestión de internados y escuelas islámicas", "Modelos de gestión, liderazgo, valores y formación del carácter en pesantren e internados islámicos, principalmente de Indonesia.", "alta", "mantener_con_alerta_geográfica", "Es temáticamente coherente, pero muy concentrado por tradición institucional, país e idioma."),
    12: ("Políticas, normativas e historia del gobierno escolar en Argentina y América Latina", "Estudios de regulación, gobierno, dirección y organización escolar con énfasis histórico y subnacional argentino, más comparaciones latinoamericanas.", "media", "mantener_con_alerta_geográfica", "Argentina, Buenos Aires y Córdoba dominan, pero el tópico incluye Chile, Brasil, Uruguay y Perú; no debe etiquetarse como exclusivamente argentino."),
    13: ("Bienestar, satisfacción y desempeño laboral del personal educativo", "Relaciones entre gestión, satisfacción, motivación, estrés, bienestar y desempeño de docentes y personal escolar.", "alta", "mantener", "Las variables laborales y de bienestar forman un eje consistente, aunque desempeño puede solaparse con T4."),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def f(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clean(value: str | None) -> str:
    return " ".join((value or "").split())


def fmt_terms(items, limit=15) -> str:
    return " | ".join(str(item[0] if isinstance(item, list) else item) for item in items[:limit])


def sample_review_rows(documents, corpus, topic_id: int):
    """Review four evidence strata; for clusters <40 include every document."""
    ranked = {
        "central": sorted(documents, key=lambda r: (f(r.get("distance_to_centroid"), 9), -f(r.get("topic_probability"))))[:10],
        "borderline": sorted(documents, key=lambda r: f(r.get("assignment_margin"), 9))[:10],
        "low_confidence": sorted(documents, key=lambda r: f(r.get("topic_probability")))[:10],
    }
    rng = random.Random(SEED + topic_id)
    shuffled = list(documents)
    rng.shuffle(shuffled)
    ranked["random"] = shuffled[:10]
    if len(documents) < 40:
        already = {r["document_id"] for values in ranked.values() for r in values}
        ranked["random"].extend(r for r in documents if r["document_id"] not in already)

    out = []
    seen = set()
    for stratum, values in ranked.items():
        for doc in values:
            key = (stratum, doc["document_id"])
            if key in seen:
                continue
            seen.add(key)
            meta = corpus.get(doc["document_id"], {})
            prob = f(doc.get("topic_probability"))
            margin = f(doc.get("assignment_margin"))
            if stratum == "central" and prob >= 0.65:
                relevance, reason = "claro", "Alta pertenencia y cercanía al centro; confirmar mediante lectura experta."
            elif stratum in {"borderline", "low_confidence"} or margin < 0.03 or prob < 0.25:
                relevance, reason = "dudoso", "Caso fronterizo o de baja confianza; revisar el resumen frente al segundo tópico."
            else:
                relevance, reason = "probable", "Compatible con el descriptor, pendiente de codificación humana independiente."
            out.append({
                "topic_id": topic_id, "sample_type": stratum, "document_id": doc["document_id"],
                "title": clean(meta.get("title") or doc.get("title")), "authors": clean(meta.get("authors")),
                "year": meta.get("year", ""), "source": meta.get("source", ""), "language": meta.get("language", ""),
                "country": "", "abstract": clean(meta.get("abstract")),
                "topic_probability": doc.get("topic_probability", ""), "distance_to_centroid": doc.get("distance_to_centroid", ""),
                "assignment_margin": doc.get("assignment_margin", ""), "second_topic_id": doc.get("second_nearest_topic", ""),
                "provisional_fit": relevance, "review_reason": reason,
                "human_decision": "", "human_notes": "",
            })
    return out


def main() -> None:
    VALIDATION.mkdir(parents=True, exist_ok=True)
    DOSSIERS.mkdir(parents=True, exist_ok=True)
    topics = {int(r["topic_id"]): r for r in read_csv(PREFERRED / "topics.csv") if int(r["topic_id"]) >= 0}
    documents = read_csv(PREFERRED / "document_topics.csv")
    corpus_rows = read_csv(ROOT / "output/topic_models/corpus/modeling_corpus_metadata.csv")
    corpus = {r["document_id"]: r for r in corpus_rows}
    by_topic = defaultdict(list)
    for row in documents:
        by_topic[int(row["topic_id"])].append(row)
    assert set(topics) == set(range(14)), "Expected selected macrotopics T0–T13"
    assert len(documents) == len(corpus_rows) == 2182
    assert sum(len(by_topic[t]) for t in range(14)) == 1340
    assert len(by_topic[-1]) == 842

    model_json = json.loads((PREFERRED / "model/topics.json").read_text(encoding="utf-8"))
    keybert = model_json.get("topic_aspects", {}).get("KeyBERT", {})
    words = defaultdict(list)
    for row in read_csv(PREFERRED / "topic_words.csv"):
        tid = int(row["topic_id"])
        if tid >= 0:
            words[tid].append((row["term"], f(row["weight"])))
    subtopics = defaultdict(list)
    for row in read_csv(PREFERRED / "subtopics.csv"):
        subtopics[int(row["macro_topic_id"])].append(row)
    similarity = read_csv(PREFERRED / "topic_similarity.csv")

    proposals = []
    all_reviews = []
    for tid in range(14):
        label, definition, confidence, action, rationale = INTERPRETATIONS[tid]
        docs = by_topic[tid]
        langs = Counter(corpus[d["document_id"]].get("language", "unknown") for d in docs)
        sources = Counter(corpus[d["document_id"]].get("source", "unknown") for d in docs)
        years = Counter(corpus[d["document_id"]].get("year", "unknown") for d in docs)
        nearest = sorted(
            (r for r in similarity if int(r["topic_a"]) == tid or int(r["topic_b"]) == tid),
            key=lambda r: f(r["ctfidf_similarity"]), reverse=True,
        )[:3]
        related = " | ".join(
            f"T{r['topic_b'] if int(r['topic_a']) == tid else r['topic_a']} ({f(r['ctfidf_similarity']):.3f})" for r in nearest
        )
        reviews = sample_review_rows(docs, corpus, tid)
        all_reviews.extend(reviews)
        unclear = sum(1 for r in reviews if r["provisional_fit"] == "dudoso")
        proposals.append({
            "topic_id": tid, "automatic_label": topics[tid]["automatic_label"], "proposed_human_label": label,
            "short_definition": definition, "interpretive_confidence": confidence, "proposed_action": action,
            "rationale": rationale, "document_count": len(docs), "prevalence": topics[tid]["prevalence"],
            "dominant_languages": " | ".join(f"{k}:{v}" for k, v in langs.most_common()),
            "dominant_sources": " | ".join(f"{k}:{v}" for k, v in sources.most_common()),
            "year_distribution": " | ".join(f"{k}:{v}" for k, v in sorted(years.items())),
            "related_topics": related, "reviewed_unique_documents": len({r['document_id'] for r in reviews}),
            "provisional_doubtful_reviews": unclear, "label_status": "proposed_pending_documentary_validation",
            "reviewer": "Codex-assisted substantive review", "review_date": "2026-07-31",
        })

        central = sorted(docs, key=lambda r: (f(r.get("distance_to_centroid"), 9), -f(r.get("topic_probability"))))[:10]
        borderline = sorted(docs, key=lambda r: f(r.get("assignment_margin"), 9))[:10]
        subsection = "\n".join(
            f"- **{s['subtopic_id']}** ({s['subtopic_size']} docs): {s['descriptor_automatic']}" for s in subtopics[tid]
        ) or "- El algoritmo no produjo subtópicos estables para este macrotópico."
        evidence = lambda ds: "\n".join(
            f"- {clean(corpus[d['document_id']].get('title'))} — {corpus[d['document_id']].get('year','s/f')}, {corpus[d['document_id']].get('language','')}, {corpus[d['document_id']].get('source','')}"
            for d in ds
        )
        dossier = f"""# T{tid} · {label}

> Etiqueta humana provisional. Validación documental pendiente. No modifica la asignación algorítmica.

## Ficha

- Identificador algorítmico: T{tid}
- Descriptor automático: {topics[tid]['automatic_label']}
- Tamaño: {len(docs)} documentos ({topics[tid]['prevalence']}% del corpus)
- Confianza interpretativa: {confidence}
- Acción propuesta: {action}
- Idiomas: {', '.join(f'{k}={v}' for k,v in langs.most_common())}
- Fuentes: {', '.join(f'{k}={v}' for k,v in sources.most_common())}

## Interpretación provisional

**Definición:** {definition}

**Justificación:** {rationale}

**Tópicos semánticamente próximos:** {related or 'sin dato'}.

## Evidencia léxica

- c-TF-IDF (hasta 15 exportados): {fmt_terms(words[tid], 15)}
- KeyBERT (hasta 15; el modelo exportó {len(keybert.get(str(tid), []))}): {fmt_terms(keybert.get(str(tid), []), 15)}
- N-gramas destacados: {topics[tid]['top_ngrams']}

## Estructura interna

{subsection}

## Diez documentos centrales

{evidence(central)}

## Diez documentos fronterizos

{evidence(borderline)}

## Nota de validación

Se revisaron {len({r['document_id'] for r in reviews})} documentos únicos en estratos central, fronterizo, baja confianza y aleatorio. Las clasificaciones automáticas `claro/probable/dudoso` son ayudas de priorización y no respuestas humanas. Consulte `topic_document_review.csv` para codificar `human_decision` y `human_notes`.
"""
        (DOSSIERS / f"T{tid:02d}.md").write_text(dossier, encoding="utf-8")

    write_csv(VALIDATION / "topic_label_proposals.csv", proposals)
    write_csv(VALIDATION / "topic_document_review.csv", all_reviews)

    merge_rows = []
    for a, b, recommendation, rationale in [
        (1, 7, "no_fusionar_por_ahora", "T1 se organiza por calidad/mejora; T7 por planificación e innovación. Revisar fronteras antes de cualquier fusión."),
        (2, 9, "no_fusionar;_relación_jerárquica", "T9 es un núcleo específico de IA/analítica dentro del campo digital más amplio de T2."),
        (4, 13, "no_fusionar_por_ahora", "Comparten desempeño, pero T4 estudia competencias/resultados de gestión y T13 condiciones laborales y bienestar."),
        (0, 4, "revisar_solapamiento", "Liderazgo y competencia directiva se solapan; mantener mientras los documentos de T4 se distingan por diseños de desempeño."),
    ]:
        sim = next((f(r["ctfidf_similarity"]) for r in similarity if {int(r["topic_a"]), int(r["topic_b"])} == {a, b}), None)
        merge_rows.append({"topic_a": a, "topic_b": b, "ctfidf_similarity": sim, "recommendation": recommendation, "rationale": rationale, "human_decision": "", "human_notes": ""})
    write_csv(VALIDATION / "topic_merge_proposals.csv", merge_rows)

    split_rows = [
        {"topic_id": 3, "candidate_dimensions": "rural/indígena | gestión territorial latinoamericana", "recommendation": "revisar", "rationale": INTERPRETATIONS[3][4], "human_decision": "", "human_notes": ""},
        {"topic_id": 4, "candidate_dimensions": "competencias directivas | desempeño docente | resultados institucionales", "recommendation": "revisar", "rationale": INTERPRETATIONS[4][4], "human_decision": "", "human_notes": ""},
        {"topic_id": 8, "candidate_dimensions": "mujeres en dirección | perspectiva de género/ESI", "recommendation": "mantener_y_monitorear", "rationale": "La evidencia disponible sostiene un paraguas de género; dividir sólo si una codificación completa muestra dos comunidades coherentes.", "human_decision": "", "human_notes": ""},
        {"topic_id": 12, "candidate_dimensions": "política contemporánea | historia de gobierno escolar | Argentina | comparación latinoamericana", "recommendation": "revisar", "rationale": INTERPRETATIONS[12][4], "human_decision": "", "human_notes": ""},
    ]
    write_csv(VALIDATION / "topic_split_proposals.csv", split_rows)

    # Intrusion tests: reproducible randomized candidates, deliberately unanswered.
    rng = random.Random(SEED)
    word_intrusion = []
    all_terms = {t: [x[0] for x in words[t][:15]] for t in range(14)}
    for t in range(14):
        for trial in range(1, 4):
            intruder_topic = rng.choice([x for x in range(14) if x != t])
            intruder = rng.choice(all_terms[intruder_topic])
            candidates = all_terms[t][(trial - 1) * 4: trial * 4] + [intruder]
            rng.shuffle(candidates)
            word_intrusion.append({"topic_id": t, "trial_id": trial, "candidate_words": " | ".join(candidates), "intruder_word": intruder, "intruder_source_topic": intruder_topic, "human_selected_word": "", "human_correct": "", "human_notes": ""})
    write_csv(VALIDATION / "word_intrusion.csv", word_intrusion)

    intrusion = []
    for t in range(14):
        candidates = sorted(by_topic[t], key=lambda r: f(r.get("topic_probability")), reverse=True)[:15]
        for doc in candidates:
            intruder_t = rng.choice([x for x in range(14) if x != t])
            intrusion.append({"topic_id": t, "document_id": doc["document_id"], "title": corpus[doc["document_id"]].get("title", ""), "correct_label": INTERPRETATIONS[t][0], "intruder_topic_id": intruder_t, "intruder_label": INTERPRETATIONS[intruder_t][0], "candidate_order": "intruder|correct" if rng.random() < .5 else "correct|intruder", "human_selected_topic": "", "human_correct": "", "human_notes": ""})
    write_csv(VALIDATION / "topic_intrusion.csv", intrusion)

    # Stratified outlier audit. A row can carry multiple strata, avoiding duplication.
    outliers = by_topic[-1]
    chosen = {}
    def take(name, rows, n=20):
        for row in rows[:n]:
            chosen.setdefault(row["document_id"], {"row": row, "strata": []})["strata"].append(name)
    take("nearest_single_topic", sorted(outliers, key=lambda r: f(r.get("assignment_margin")), reverse=True))
    take("between_two_topics", sorted(outliers, key=lambda r: f(r.get("assignment_margin"))))
    take("low_similarity", sorted(outliers, key=lambda r: f(r.get("nearest_centroid_similarity"))))
    for lang in sorted({corpus[r["document_id"]].get("language", "unknown") for r in outliers}):
        pool = [r for r in outliers if corpus[r["document_id"]].get("language", "unknown") == lang]
        rng.shuffle(pool); take(f"language:{lang}", pool)
    for source, _ in Counter(corpus[r["document_id"]].get("source", "unknown") for r in outliers).most_common(2):
        pool = [r for r in outliers if corpus[r["document_id"]].get("source", "unknown") == source]
        rng.shuffle(pool); take(f"source:{source}", pool)
    for year in sorted({corpus[r["document_id"]].get("year", "unknown") for r in outliers}):
        pool = [r for r in outliers if corpus[r["document_id"]].get("year", "unknown") == year]
        rng.shuffle(pool); take(f"year:{year}", pool)
    outlier_review = []
    for doc_id, item in chosen.items():
        row, meta = item["row"], corpus[doc_id]
        outlier_review.append({"document_id": doc_id, "sample_strata": " | ".join(item["strata"]), "title": meta.get("title", ""), "abstract": clean(meta.get("abstract")), "year": meta.get("year", ""), "source": meta.get("source", ""), "language": meta.get("language", ""), "nearest_topic": row.get("nearest_topic", ""), "nearest_similarity": row.get("nearest_centroid_similarity", ""), "second_topic": row.get("second_nearest_topic", ""), "second_similarity": row.get("second_nearest_centroid_similarity", ""), "assignment_margin": row.get("assignment_margin", ""), "human_decision": "", "human_notes": ""})
    write_csv(VALIDATION / "outlier_review_sample.csv", outlier_review)

    # Preserve any actually validated labels; proposals never silently replace them.
    labels_path = ROOT / "config/topic_labels.csv"
    existing = read_csv(labels_path) if labels_path.exists() else []
    validated = {(r.get("model"), r.get("topic_id")): r for r in existing if r.get("label_status") in {"validated", "human_validated", "approved"}}
    config_rows = []
    for p in proposals:
        key = ("BERTopic-METADATA-MULTILINGUAL", str(p["topic_id"]))
        config_rows.append(validated.get(key, {"model": key[0], "topic_id": key[1], "human_label": p["proposed_human_label"], "label_status": "proposed_pending_documentary_validation", "label_notes": p["rationale"]}))
    write_csv(labels_path, config_rows, ["model", "topic_id", "human_label", "label_status", "label_notes"])

    digest = hashlib.sha256((PREFERRED / "document_topics.csv").read_bytes()).hexdigest()[:12]
    summary = f"""# Resumen de validación sustantiva provisional

Generado el 2026-07-31 sobre la solución BERTopic seleccionada (`document_topics.csv` SHA-256 `{digest}…`).

## Alcance

- Corpus: 2.182 publicaciones; 1.340 asignadas a T0–T13 y 842 outliers conservados.
- Se propusieron 14 etiquetas humanas provisionales; **ninguna está validada por especialistas**.
- Se prepararon {len(all_reviews)} filas de revisión ({len({r['document_id'] for r in all_reviews})} documentos únicos), 42 pruebas de intrusión léxica, {len(intrusion)} pruebas de intrusión temática y {len(outlier_review)} outliers estratificados.
- No se modificaron embeddings, UMAP, HDBSCAN, asignaciones, outliers ni hiperparámetros.

## Decisiones interpretativas prioritarias

1. Mantener separados T1 (calidad/mejora) y T7 (planificación/innovación), revisando sus fronteras.
2. Mantener separados T2 (digitalización/TIC) y T9 (IA/analítica), tratándolos como relacionados jerárquicamente.
3. Revisar posibles divisiones en T3, T4 y T12; no ejecutarlas sin codificación humana.
4. Etiquetar T8 como género y desigualdades; la muestra revisada no sustenta todavía agregar “raza” al nombre.
5. Conservar alertas geográficas en T11 y T12.

## Cómo completar la validación

Dos revisores deben completar los campos `human_*` sin mirar la respuesta del otro. Luego se calcula acuerdo (porcentaje y kappa/alpha según escala), se resuelven discrepancias y sólo entonces se cambia `label_status` a `validated`. Las columnas `provisional_fit` y las propuestas de fusión/división son ayudas para priorizar, no verdad de terreno.
"""
    (VALIDATION / "validation_summary.md").write_text(summary, encoding="utf-8")
    print(f"Wrote validation layer: {len(proposals)} topics, {len(all_reviews)} review rows, {len(outlier_review)} outliers")


if __name__ == "__main__":
    main()
