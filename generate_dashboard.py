#!/usr/bin/env python3
"""
generate_dashboard.py
Dashboard interactivo con:
1. Red de similitud semántica estilo Connected Papers (D3 force-directed)
2. Tópicos STM clickeables con lista de artículos del tópico
3. Lista completa paginada (50/página) con buscador por título/autor
"""

import csv, json, re, itertools, html as html_lib
from pathlib import Path
from datetime import date
from collections import Counter, defaultdict

DATA_DIR = Path("data")
OUT_DIR  = Path("docs")
OUT_DIR.mkdir(exist_ok=True)

PALETA = [
    "#E63946","#F4A261","#2A9D8F","#457B9D","#A8DADC",
    "#E9C46A","#264653","#F77F00","#6A4C93","#1982C4",
    "#8AC926","#FF595E","#FFCA3A","#7B2D8B","#0077B6",
    "#52B788","#D62828","#023E8A","#F3722C","#90BE6D",
    "#43AA8B","#577590","#F9C74F","#F8961E","#277DA1",
    "#C77DFF","#FF6B6B","#4ECDC4","#FFE66D","#A8E6CF"
]

def read_csv(path):
    p = Path(path)
    if not p.exists():
        return []
    csv.field_size_limit(10_000_000)
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def s(v):
    return str(v or "").strip()

def safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default

def safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def infer_source(row):
    source = s(row.get("source", ""))
    if source:
        return source
    url = s(row.get("url", "")).lower()
    origin = s(row.get("origin", "")).lower()
    openalex_id = s(row.get("openalex_id", ""))
    if "ri.conicet" in url or "conicet" in origin:
        return "CONICET Digital"
    if "repositorio.unsam" in url or "unsam" in origin:
        return "RIAA-UNSAM"
    if "sedici.unlp.edu.ar" in url or "sedici" in origin:
        return "SEDICI-UNLP"
    if openalex_id or "doi.org" in url or "dx.doi.org" in url:
        return "OpenAlex"
    return "Repositorio / Otro"


def infer_origin(row):
    origin = s(row.get("origin", ""))
    return origin or infer_source(row)

# ── Cargar datos ──────────────────────────────────────────────────────────────

records    = read_csv("data/master_records.csv")
corpus     = read_csv("data/corpus.csv")
topicos    = read_csv("output/tabla_topicos.csv")
doc_topics = read_csv("output/document_topics.csv")
MODEL_VIEWS = [
    ("principal", "bertopic-macros", "BERTopic multilingüe · 14 macrotemas", "BERTopic", "output/topic_models/bertopic/metadata_multilingual/preferred_solution/topics.csv"),
    ("principal", "bertopic-subtopics", "BERTopic multilingüe · subtópicos", "BERTopic", "output/topic_models/bertopic/metadata_multilingual/preferred_solution/subtopics.csv"),
    ("comparative", "stm-es", "STM metadatos · español", "STM", "output/topic_models/stm/metadata_es_corrected/topics.csv"),
    ("comparative", "stm-en", "STM metadatos · inglés", "STM", "output/topic_models/stm/metadata_en_corrected/topics.csv"),
    ("comparative", "stm-pt", "STM metadatos · portugués · exploratorio", "STM", "output/topic_models/stm/metadata_pt_corrected/topics.csv"),
    ("historical", "legacy-stm", "STM anterior · texto completo · archivado", "STM", "output/topic_models/stm/topics.csv"),
]
topic_alignment = read_csv("output/topic_models/comparison/stm_bertopic_alignment.csv")
if not topic_alignment:
    topic_alignment = read_csv("output/topic_models/comparison/topic_alignment.csv")

print(f"Records: {len(records)} | Corpus: {len(corpus)} | Topicos: {len(topicos)} | Doc-topics: {len(doc_topics)}")

# ── Colores por tópico ────────────────────────────────────────────────────────

topic_colors = {}
for i, t in enumerate(sorted(topicos, key=lambda row: safe_int(s(row.get("topico")), 10_000))):
    tid = s(t.get("topico", str(i + 1)))
    # Use a deterministic dashboard palette. The STM export may carry a
    # placeholder color shared by every topic, which would make the network
    # visually indistinguishable even when topic assignments are different.
    color = PALETA[i % len(PALETA)]
    topic_colors[tid] = color
    t["color"] = color

# ── DOI → tópico dominante ───────────────────────────────────────────────────

doi_to_topic = {}
for d in doc_topics:
    doi = s(d.get("doi", ""))
    tid = s(d.get("topico_dominante", ""))
    if doi and tid:
        doi_to_topic[doi] = tid

# ── DOI → registro completo ───────────────────────────────────────────────────

doi_to_record = {}
for r in records:
    doi = s(r.get("doi", ""))
    if doi:
        doi_to_record[doi] = r

# ── Tópico → lista de artículos ──────────────────────────────────────────────

topic_papers = defaultdict(list)

for cp in corpus:
    doi = s(cp.get("doi", ""))
    tid = doi_to_topic.get(doi, "")
    if not tid:
        continue
    rec    = doi_to_record.get(doi, cp)
    titulo = s(rec.get("title", "") or cp.get("titulo", ""))
    if not titulo:
        continue
    autores   = s(rec.get("authors", "") or cp.get("autores", ""))
    auth_list = [a.strip() for a in autores.split(";") if a.strip()]
    auth_short = "; ".join(auth_list[:3]) + (" et al." if len(auth_list) > 3 else "")
    url = s(rec.get("url", "") or cp.get("url", ""))
    if not url and doi:
        url = f"https://doi.org/{doi}"
    topic_papers[tid].append({
        "titulo":  titulo,
        "autores": auth_short,
        "revista": s(rec.get("origin", "") or cp.get("revista", "")),
        "anio":    s(rec.get("publication_year", "") or cp.get("anio", "")),
        "url":     url,
    })

# ── Red de similitud semántica ────────────────────────────────────────────────

KW_STOPS = {
    "school","education","educational","leadership","management","learning",
    "teachers","teacher","students","student","principal","principals",
    "gestion","educacion","educativa","escolar","escuela","liderazgo",
    "direccion","docentes","docente","estudiantes","aprendizaje",
    "academic","research","study","analysis","university","policy",
    "national","international","social","public","system","systems"
}

# Cada vista del selector de modelado necesita su propia asignacion
# documento -> topico y su propia tabla de topicos. Antes el grafo se construia
# una sola vez con la STM historica y cambiar de modelo solo movia las
# tarjetas; ahora se precalcula una red por vista.
BERTOPIC_ROOT = "output/topic_models/bertopic/metadata_multilingual/preferred_solution"
NETWORK_SOURCES = {
    "bertopic-macros": {
        "documents": f"{BERTOPIC_ROOT}/document_topics.csv",
        "document_topic_field": "topic_id",
        "topics": f"{BERTOPIC_ROOT}/topics.csv",
        "topic_id_field": "topic_id",
        "similarity": f"{BERTOPIC_ROOT}/topic_similarity.csv",
        "label_model": "BERTopic-METADATA-MULTILINGUAL",
    },
    "bertopic-subtopics": {
        "documents": f"{BERTOPIC_ROOT}/document_topic_hierarchy.csv",
        "document_topic_field": "subtopic_id",
        "topics": f"{BERTOPIC_ROOT}/subtopics.csv",
        "topic_id_field": "subtopic_id",
        "parent_field": "parent_topic_id",
    },
    "stm-es": {
        "documents": "output/topic_models/stm/metadata_es_corrected/document_topics.csv",
        "document_topic_field": "topic_id",
        "topics": "output/topic_models/stm/metadata_es_corrected/topics.csv",
        "topic_id_field": "topic_id",
    },
    "stm-en": {
        "documents": "output/topic_models/stm/metadata_en_corrected/document_topics.csv",
        "document_topic_field": "topic_id",
        "topics": "output/topic_models/stm/metadata_en_corrected/topics.csv",
        "topic_id_field": "topic_id",
    },
    "stm-pt": {
        "documents": "output/topic_models/stm/metadata_pt_corrected/document_topics.csv",
        "document_topic_field": "topic_id",
        "topics": "output/topic_models/stm/metadata_pt_corrected/topics.csv",
        "topic_id_field": "topic_id",
    },
    "legacy-stm": {
        "documents": "output/topic_models/stm/document_topics.csv",
        "document_topic_field": "topic_id",
        "topics": "output/topic_models/stm/topics.csv",
        "topic_id_field": "topic_id",
    },
}

MAX_NODES = 400
MAX_EDGES = 2500
MAX_TOPIC_EDGES = 150
MIN_SHARED_KEYWORDS = 2
SPARSE_NETWORK_NODES = 150
MIN_SEMANTIC_SIMILARITY = 0.35
MIN_COASSIGNMENT = 0.15
MIN_WORD_OVERLAP = 0.03


def _row_doi(row):
    """Las salidas de modelado traen `doi` o un `document_id` con prefijo."""
    doi = s(row.get("doi"))
    if doi:
        return doi.lower()
    document_id = s(row.get("document_id"))
    if document_id.lower().startswith("doi:"):
        return document_id[4:].strip().lower()
    return ""


def _topic_id(value):
    """Los subtopicos se exportan como float ("0.0") y los topicos como int."""
    value = s(value)
    return value[:-2] if value.endswith(".0") else value


def load_document_topics(config):
    assignments = {}
    for row in read_csv(config["documents"]):
        doi = _row_doi(row)
        topic_id = _topic_id(row.get(config["document_topic_field"]))
        if doi and topic_id and topic_id != "-1":
            assignments[doi] = topic_id
    return assignments


# Etiquetas humanas propuestas: los topics.csv traen el descriptor automatico
# ("leadership · style"), ilegible en una leyenda de colores.
PROPOSED_LABELS = defaultdict(dict)
for row in read_csv("config/topic_labels.csv"):
    label = s(row.get("human_label"))
    if label:
        PROPOSED_LABELS[s(row.get("model"))][_topic_id(row.get("topic_id"))] = label


def topic_display_label(row, overrides=None):
    return (
        (overrides or {}).get(_topic_id(row.get("topic_id")), "")
        or s(row.get("human_label"))
        or s(row.get("automatic_label"))
        or s(row.get("descriptor_automatic"))
        or s(row.get("topic_label"))
        or "Sin descriptor"
    )


def load_topic_table(config):
    overrides = PROPOSED_LABELS.get(config.get("label_model", ""), {})
    topics = []
    for row in read_csv(config["topics"]):
        topic_id = _topic_id(row.get(config["topic_id_field"]))
        if not topic_id or topic_id == "-1":
            continue
        raw_words = s(row.get("top_words") or row.get("descriptor_automatic"))
        topics.append({
            "id": topic_id,
            "label": topic_display_label(row, overrides),
            "size": safe_int(row.get("document_count") or row.get("subtopic_size"), 0),
            "prevalence": safe_float(row.get("prevalence"), 0.0),
            "parent": _topic_id(row.get(config.get("parent_field") or "")),
            "words": [w.strip().lower() for w in raw_words.replace("·", "|").split("|") if w.strip()],
        })
    return topics


def topic_palette(topics):
    ordered = sorted(topics, key=lambda topic: safe_float(topic["id"], 1e9))
    return {topic["id"]: PALETA[i % len(PALETA)] for i, topic in enumerate(ordered)}


# Pool de documentos: titulo, autoria y keywords con las que se tejen aristas.
paper_pool = {}
for row in records:
    doi = s(row.get("doi", "")).lower()
    title = s(row.get("title", ""))
    if not doi or not title:
        continue
    kws_raw = s(row.get("keywords", ""))
    authors = [a.strip() for a in s(row.get("authors", "")).split(";") if a.strip()]
    paper_pool[doi] = {
        "title": title[:70] + ("..." if len(title) > 70 else ""),
        "authors": "; ".join(authors[:2]) + (" et al." if len(authors) > 2 else ""),
        "year": s(row.get("publication_year", "")),
        "url": s(row.get("url", "")) or f"https://doi.org/{doi}",
        "kws": [
            k.strip().lower() for k in kws_raw.split(";")
            if k.strip() and len(k.strip()) > 3 and k.strip().lower() not in KW_STOPS
        ][:12],
    }

corpus_dois = {s(cp.get("doi", "")).lower() for cp in corpus if s(cp.get("doi", ""))}
BASE_UNIVERSES = {
    "master": ("todos los registros validados", set(paper_pool)),
    "corpus": ("documentos con texto completo", corpus_dois & set(paper_pool)),
}


def _weave(papers, min_shared):
    """Teje la red exigiendo `min_shared` keywords en comun por arista."""
    kw_index = defaultdict(list)
    for i, paper in enumerate(papers):
        for kw in paper["kws"]:
            kw_index[kw].append(i)

    edge_weights = defaultdict(int)
    for paper_ids in kw_index.values():
        if 2 <= len(paper_ids) <= 40:
            for a, b in itertools.combinations(paper_ids, 2):
                edge_weights[(a, b)] += 1

    strong_edges = sorted(
        ((a, b, w) for (a, b), w in edge_weights.items() if w >= min_shared),
        key=lambda edge: -edge[2],
    )[:MAX_EDGES]

    connected = sorted({node for a, b, _ in strong_edges for node in (a, b)})
    old_to_new = {old: new for new, old in enumerate(connected)}
    nodes = [dict(papers[i], degree=0) for i in connected]
    for a, b, _ in strong_edges:
        nodes[old_to_new[a]]["degree"] += 1
        nodes[old_to_new[b]]["degree"] += 1

    if len(nodes) > MAX_NODES:
        keep = sorted(sorted(range(len(nodes)), key=lambda i: -nodes[i]["degree"])[:MAX_NODES])
        remap = {old: new for new, old in enumerate(keep)}
        kept = set(keep)
        nodes = [nodes[i] for i in keep]
        edges = [
            {"source": remap[old_to_new[a]], "target": remap[old_to_new[b]], "weight": w}
            for a, b, w in strong_edges
            if old_to_new[a] in kept and old_to_new[b] in kept
        ]
    else:
        edges = [
            {"source": old_to_new[a], "target": old_to_new[b], "weight": w}
            for a, b, w in strong_edges
        ]
    # Las keywords ya cumplieron su funcion y abultarian el HTML.
    for node in nodes:
        node.pop("kws", None)
    return nodes, edges


def build_keyword_network(base_dois, assignments, colors, labels):
    """Red documental: nodos = articulos, aristas = keywords compartidas."""
    papers = []
    for doi in sorted(base_dois):
        info = paper_pool[doi]
        topic_id = assignments.get(doi)
        if not topic_id or not info["kws"]:
            continue
        papers.append({
            **info,
            "topic": topic_id,
            "topic_label": labels.get(topic_id, ""),
            "color": colors.get(topic_id, "#484F58"),
        })

    nodes, edges = _weave(papers, MIN_SHARED_KEYWORDS)
    # Los modelos con pocos documentos asignados no llegan a dos keywords
    # compartidas y quedarian con un grafo casi vacio; ahi se afloja el umbral.
    if len(nodes) < SPARSE_NETWORK_NODES and len(papers) > len(nodes):
        relaxed_nodes, relaxed_edges = _weave(papers, 1)
        if len(relaxed_nodes) > len(nodes):
            nodes, edges = relaxed_nodes, relaxed_edges
    return nodes, edges


def build_topic_network(topics, colors, assignments, config):
    """Red de topicos: nodos = topicos, aristas = similitud entre ellos."""
    counts = Counter(assignments.values())
    index = {topic["id"]: i for i, topic in enumerate(topics)}
    nodes = [{
        "id": topic["id"],
        "label": topic["label"],
        "size": topic["size"] or counts.get(topic["id"], 0),
        "prevalence": topic["prevalence"],
        "color": colors.get(topic["id"], "#484F58"),
        "words": topic["words"][:8],
    } for topic in topics]

    raw_edges = []
    threshold = MIN_WORD_OVERLAP
    if config.get("similarity"):
        # BERTopic exporta la similitud c-TF-IDF entre clusters.
        threshold = MIN_SEMANTIC_SIMILARITY
        for row in read_csv(config["similarity"]):
            a, b = _topic_id(row.get("topic_a")), _topic_id(row.get("topic_b"))
            weight = safe_float(row.get("ctfidf_similarity"))
            if a in index and b in index and weight > 0:
                raw_edges.append((index[a], index[b], weight))
    elif config.get("parent_field"):
        # Los subtopicos no tienen matriz de similitud: se conectan los que
        # cuelgan del mismo macrotema.
        by_parent = defaultdict(list)
        for topic in topics:
            by_parent[topic["parent"]].append(topic["id"])
        for members in by_parent.values():
            for a, b in itertools.combinations(members, 2):
                raw_edges.append((index[a], index[b], 1.0))
    else:
        # Las STM no exportan matriz de similitud y sus top_words son casi
        # disjuntas por construccion, asi que Jaccard deja el grafo vacio. Si
        # se vinculan por el segundo topico de cada documento: dos topicos se
        # tocan cuando comparten documentos fronterizos.
        pair_counts = Counter()
        for row in read_csv(config["documents"]):
            first = _topic_id(row.get(config["document_topic_field"]))
            second = _topic_id(row.get("second_topic_id"))
            if first in index and second in index and first != second:
                pair_counts[tuple(sorted((index[first], index[second])))] += 1
        if pair_counts:
            strongest = max(pair_counts.values())
            raw_edges = [(a, b, count / strongest) for (a, b), count in pair_counts.items()]
            threshold = MIN_COASSIGNMENT
        else:
            for a, b in itertools.combinations(topics, 2):
                words_a, words_b = set(a["words"]), set(b["words"])
                if not words_a or not words_b:
                    continue
                weight = len(words_a & words_b) / len(words_a | words_b)
                if weight > 0:
                    raw_edges.append((index[a["id"]], index[b["id"]], weight))

    raw_edges.sort(key=lambda edge: -edge[2])
    selected = [edge for edge in raw_edges if edge[2] >= threshold]
    # Un umbral fijo deja sin aristas a los modelos de vocabulario disperso; se
    # completa con los pares mas fuertes hasta tener un grafo legible.
    if len(selected) < len(nodes):
        selected = raw_edges[:len(nodes)]
    selected = selected[:MAX_TOPIC_EDGES]
    return nodes, [{"source": a, "target": b, "weight": round(w, 3)} for a, b, w in selected]


networks = {}
for _, model_key, model_label, model_kind, _ in MODEL_VIEWS:
    config = NETWORK_SOURCES.get(model_key)
    if not config:
        continue
    assignments = load_document_topics(config)
    topics = load_topic_table(config)
    if not assignments or not topics:
        continue
    colors = topic_palette(topics)
    labels = {topic["id"]: topic["label"] for topic in topics}

    # Base adaptativa: se elige el universo documental que mas asignaciones de
    # este modelo llega a representar en la red.
    base_key, base_label, base_dois, best_cover = "", "", set(), -1
    for candidate_key, (candidate_label, candidate_dois) in BASE_UNIVERSES.items():
        cover = sum(1 for doi in candidate_dois if doi in assignments and paper_pool[doi]["kws"])
        if cover > best_cover:
            base_key, base_label, base_dois, best_cover = (
                candidate_key, candidate_label, candidate_dois, cover
            )

    doc_nodes, doc_edges = build_keyword_network(base_dois, assignments, colors, labels)
    topic_nodes, topic_edges = build_topic_network(topics, colors, assignments, config)
    networks[model_key] = {
        "label": model_label,
        "kind": model_kind,
        "base": base_label,
        "assigned": best_cover,
        "documents": {"nodes": doc_nodes, "edges": doc_edges},
        "topics": {"nodes": topic_nodes, "edges": topic_edges},
    }
    print(
        f"Red {model_key}: {len(doc_nodes)} nodos / {len(doc_edges)} aristas "
        f"(base {base_key}, {best_cover} asignados) - "
        f"{len(topic_nodes)} topicos / {len(topic_edges)} enlaces"
    )

DEFAULT_NETWORK = "bertopic-macros" if "bertopic-macros" in networks else next(iter(networks), "")
nodes = networks.get(DEFAULT_NETWORK, {}).get("documents", {}).get("nodes", [])
edges = networks.get(DEFAULT_NETWORK, {}).get("documents", {}).get("edges", [])

# ── Lista completa de artículos ───────────────────────────────────────────────

all_articles = []
for r in records:
    title = s(r.get("title", ""))
    if not title:
        continue
    doi  = s(r.get("doi", ""))
    url  = s(r.get("url", ""))
    if not url and doi:
        url = f"https://doi.org/{doi}"
    autores   = s(r.get("authors", ""))
    auth_list = [a.strip() for a in autores.split(";") if a.strip()]
    auth_short = "; ".join(auth_list[:3]) + (" et al." if len(auth_list) > 3 else "")
    kws_raw = s(r.get("keywords", ""))
    kws = [k.strip() for k in kws_raw.split(";") if k.strip()][:5]
    resumen = s(r.get("abstract", ""))
    fuente = infer_source(r)
    revista = infer_origin(r)
    search_text = " ".join([title, autores, revista, fuente, s(r.get("publication_year", "")), kws_raw, resumen])
    all_articles.append({
        "titulo":  title,
        "autores": auth_short,
        "revista": revista,
        "fuente": fuente,
        "anio":    s(r.get("publication_year", "")),
        "url":     url,
        "kws":     kws,
        "resumen": resumen[:450],
        "search":  search_text,
    })

all_articles.sort(key=lambda x: safe_int(x["anio"], 0), reverse=True)

# ── Estadísticas ──────────────────────────────────────────────────────────────

total  = len(records)
anios  = [safe_int(r.get("publication_year", 0)) for r in records if r.get("publication_year")]
anio_min = min(anios) if anios else 2020
anio_max = max(anios) if anios else 2026

# ── JSON ──────────────────────────────────────────────────────────────────────

networks_json = json.dumps(networks, ensure_ascii=False, separators=(",", ":"))
arts_json    = json.dumps(all_articles, ensure_ascii=False)
topicos_json = json.dumps([{
    "id":          s(t.get("topico", "")),
    "prevalencia": float(t.get("prevalencia", 0) or 0),
    "frex":        s(t.get("frex_top10", "")).split(", ")[:8],
    "color":       t.get("color", PALETA[i % len(PALETA)]),
    "papers":      topic_papers.get(s(t.get("topico", "")), [])
} for i, t in enumerate(topicos)], ensure_ascii=False)

n_nodes = len(nodes)
n_edges = len(edges)
n_arts  = len(all_articles)
n_tops  = len(topicos)
n_macros_preferred = sum(row.get("topic_id") != "-1" for row in read_csv("output/topic_models/bertopic/metadata_multilingual/preferred_solution/topics.csv"))
evaluation_topics = read_csv("output/topic_models/evaluation/topic_metrics.csv")
language_diagnostics = read_csv("output/topic_models/evaluation/language_dependence.csv")
heterogeneity_diagnostics = read_csv("output/topic_models/evaluation/heterogeneity.csv")
model_runs = read_csv("output/topic_models/evaluation/model_runs.csv")
evaluation_by_topic = {(s(row.get("model")), s(row.get("topic_id"))): row for row in evaluation_topics}
language_by_topic = {(s(row.get("model")), s(row.get("topic_id"))): row for row in language_diagnostics}
heterogeneity_by_topic = {(s(row.get("model")), s(row.get("topic_id"))): row for row in heterogeneity_diagnostics}
preferred_run = next((row for row in model_runs if s(row.get("is_preferred_model")).lower() == "true"), {})
annual_coverage = read_csv("output/topic_models/corpus/annual_coverage.csv")
low_coverage_years = [s(row.get("year")) for row in annual_coverage if float(row.get("fulltext_coverage_in_year") or 0) < 0.5]
preferred_root = Path("output/topic_models/bertopic/metadata_multilingual/preferred_solution")
topic_label_proposals = read_csv("output/topic_models/validation/topic_label_proposals.csv")
topic_label_proposal_by_id = {s(row.get("topic_id")): row for row in topic_label_proposals}
outlier_rows = read_csv(preferred_root / "outlier_analysis.csv")
outlier_causes = defaultdict(int)
for row in outlier_rows:
    outlier_causes[s(row.get("reason_category")) or "unknown"] += 1
effective_config = {}
effective_path = preferred_root / "effective_configuration.json"
if effective_path.exists():
    effective_config = json.loads(effective_path.read_text(encoding="utf-8"))
outlier_summary = " · ".join(f"{key}: {value}" for key, value in sorted(outlier_causes.items(), key=lambda item: -item[1]))
config_summary = (
    f"Embeddings: {effective_config.get('embedding_model_name', 'pendiente')} · "
    f"dimensión {effective_config.get('embedding_dimension', '—')} · "
    f"n-gramas {effective_config.get('vectorizer_parameters', {}).get('ngram_range', '—')} · "
    f"UMAP {effective_config.get('umap_parameters', {})} · "
    f"HDBSCAN {effective_config.get('hdbscan_parameters', {})} · semilla {effective_config.get('seed', 42)}"
)

def topic_cards(rows, model):
    if not rows:
        return '<p class="tm-empty">Todavia no hay resultados para este modelo.</p>'
    cards = []
    for row in rows:
        topic_id = s(row.get("topic_id") or row.get("subtopic_id") or row.get("macro_topic_id"))
        proposal = topic_label_proposal_by_id.get(topic_id, {}) if model == "BERTopic" else {}
        algorithmic_label = s(row.get("automatic_label") or row.get("descriptor_automatic")) or f"Tópico {topic_id}"
        proposed_label = s(proposal.get("proposed_human_label"))
        validated_label = s(row.get("human_label")) if s(row.get("label_status")).lower() in {"validated", "human_validated", "approved"} else ""
        label = validated_label or proposed_label or algorithmic_label
        measure = "prevalencia STM" if model == "STM" else "proporción del cluster"
        label_status = s(row.get("label_status")) or "pending"
        selection_status = s(row.get("selection_status") or row.get("model_status")) or "exploratory"
        count = safe_int(row.get("document_count") or row.get("subtopic_size") or row.get("macro_topic_size"), 0)
        diagnostic_key = (s(row.get("model")), s(row.get("topic_id")))
        evaluation = evaluation_by_topic.get(diagnostic_key, {})
        language_diagnostic = language_by_topic.get(diagnostic_key, {})
        heterogeneity = heterogeneity_by_topic.get(diagnostic_key, {})
        alerts = []
        if label_status.lower() not in {"validated", "human_validated", "approved"}:
            alerts.append("Etiqueta humana provisional. Validación documental pendiente.")
        if count and count < 15:
            alerts.append("tópico pequeño")
        if selection_status.lower() not in {"validated", "metrics_complete"}:
            alerts.append(f"modelo {selection_status}")
        if s(row.get("stability")) == "" and model == "STM":
            alerts.append("estabilidad no calculada")
        if s(language_diagnostic.get("classification")) == "language_concentrated_candidate":
            alerts.append(f"posible dependencia del idioma {s(language_diagnostic.get('dominant_language'))}")
        if safe_float(heterogeneity.get("borderline_document_share"), 0) > 0.25:
            alerts.append("alta proporción de documentos fronterizos")
        if safe_int(heterogeneity.get("negative_silhouette_document_count"), 0) > 0:
            alerts.append("contiene documentos con silueta negativa")
        if heterogeneity and s(heterogeneity.get("coherence_status")) != "computed":
            alerts.append("coherencia no calculada")
        if heterogeneity and s(heterogeneity.get("country_status")) != "computed":
            alerts.append("metadatos territoriales insuficientes")
        if safe_float(heterogeneity.get("contamination_share"), 0) > 0:
            alerts.append("posibles candidatos de contaminación")
        if s(heterogeneity.get("status")) not in {"", "coherent_candidate"}:
            alerts.append(f"heterogeneidad: {s(heterogeneity.get('status'))}")
        alert_html = f'<div class="tm-alert">⚠ {html_lib.escape(" · ".join(alerts))}</div>' if alerts else ""
        interpretation_html = ""
        if proposal:
            coherence_text = s(heterogeneity.get("coherence_cv")) or "No disponible por cobertura insuficiente"
            country_text = (
                f"{s(heterogeneity.get('dominant_country'))} ({100*safe_float(heterogeneity.get('dominant_country_share_known'),0):.1f}%)"
                if s(heterogeneity.get("country_status")) == "computed" else
                "Metadatos insuficientes para evaluar concentración territorial"
            )
            source_text = (
                f"{s(heterogeneity.get('dominant_source'))} · entropía {s(heterogeneity.get('source_entropy'))}"
                if s(heterogeneity.get("source_status")) == "computed" else
                "Proveedor conocido, pero sin categorías suficientes para calcular entropía"
            )
            contamination_text = (
                f"{100*safe_float(heterogeneity.get('contamination_share'),0):.1f}% · {s(heterogeneity.get('contamination_status'))}"
                if s(heterogeneity.get("relevance_metadata_coverage")) else "Evidencia insuficiente"
            )
            interpretation_html = (
                '<details class="tm-details"><summary>Ver interpretación y evidencia</summary>'
                f'<div><strong>ID algorítmico:</strong> T{html_lib.escape(topic_id)}</div>'
                f'<div><strong>Descriptor automático:</strong> {html_lib.escape(algorithmic_label)}</div>'
                f'<div><strong>Etiqueta humana propuesta:</strong> {html_lib.escape(proposed_label)}</div>'
                f'<div><strong>Definición:</strong> {html_lib.escape(s(proposal.get("short_definition")))}</div>'
                f'<div><strong>Confianza:</strong> {html_lib.escape(s(proposal.get("interpretive_confidence")))} · '
                f'<strong>acción:</strong> {html_lib.escape(s(proposal.get("proposed_action")))}</div>'
                f'<div><strong>Justificación:</strong> {html_lib.escape(s(proposal.get("rationale")))}</div>'
                f'<div><strong>Próximos tópicos:</strong> {html_lib.escape(s(proposal.get("related_topics")))}</div>'
                f'<div><strong>Revisión:</strong> {html_lib.escape(s(proposal.get("reviewed_unique_documents")))} documentos únicos; '
                f'{html_lib.escape(s(proposal.get("provisional_doubtful_reviews")))} casos priorizados como dudosos.</div>'
                f'<div><strong>Heterogeneidad:</strong> silueta media {html_lib.escape(s(heterogeneity.get("silhouette_mean")) or "No disponible")} · '
                f'negativas {100*safe_float(heterogeneity.get("silhouette_negative_share"),0):.1f}% · '
                f'fronterizos {100*safe_float(heterogeneity.get("borderline_document_share"),0):.1f}% · '
                f'baja confianza {100*safe_float(heterogeneity.get("low_confidence_document_share"),0):.1f}% · '
                f'c_v {html_lib.escape(coherence_text)} · estado {html_lib.escape(s(heterogeneity.get("status")))}.</div>'
                f'<div><strong>Territorio:</strong> {html_lib.escape(country_text)}.</div>'
                f'<div><strong>Procedencia bibliográfica:</strong> {html_lib.escape(source_text)}.</div>'
                f'<div><strong>Contaminación:</strong> {html_lib.escape(contamination_text)}. Pendiente de revisión humana.</div></details>'
            )
        cards.append(
            '<article class="tm-card">'
            f'<div class="tm-title">{html_lib.escape(label)}</div>'
            f'<div class="tm-meta"><strong>ID:</strong> T{html_lib.escape(topic_id)} · <strong>descriptor automático:</strong> {html_lib.escape(algorithmic_label)}</div>'
            f'<div class="tm-meta">{html_lib.escape(measure)}: {html_lib.escape(s(row.get("prevalence")))}% · '
            f'{count} documentos · validación: {html_lib.escape(label_status)}</div>'
            f'{alert_html}'
            f'<div class="tm-words">{html_lib.escape(s(row.get("top_words")))}</div>'
            f'<div class="tm-reps">{html_lib.escape(s(row.get("representative_titles")))}</div>{interpretation_html}</article>'
        )
    return "".join(cards)

alignment_rows = sorted(topic_alignment, key=lambda row: float(row.get("combined_alignment") or row.get("combined_similarity") or 0), reverse=True)[:20]
alignment_html = "".join(
    f'<tr><td>STM {html_lib.escape(s(row.get("stm_topic")))}</td><td>BERTopic {html_lib.escape(s(row.get("bertopic_topic")))}</td>'
    f'<td>{html_lib.escape(s(row.get("relationship") or row.get("alignment_status")))}</td><td>{html_lib.escape(s(row.get("combined_alignment") or row.get("combined_similarity")))}</td></tr>'
    for row in alignment_rows
) or '<tr><td colspan="4">Ejecute ambos modelos y la comparacion para completar esta vista.</td></tr>'
available_models = []
for group, key, label, kind, path in MODEL_VIEWS:
    model_rows = read_csv(path)
    if key == "bertopic-macros":
        model_rows = [row for row in model_rows if s(row.get("topic_id")) != "-1"]
    available_models.append((group, key, label, kind, model_rows))
first_model = "bertopic-macros"
group_labels = {"principal": "Modelo principal", "comparative": "Modelos comparativos", "historical": "Históricos"}
model_options = "".join(
    f'<optgroup label="{group_labels[group]}">' + "".join(
        f'<option value="{key}"{" selected" if key == first_model else ""}>{html_lib.escape(label)}{" · sin ejecutar" if not rows else ""}</option>'
        for item_group, key, label, _, rows in available_models if item_group == group and rows
    ) + '</optgroup>' for group in ("principal", "comparative", "historical")
) + '<optgroup label="Comparación"><option value="comparison">Comparación STM–BERTopic</option></optgroup>'
model_panes = "".join(
    f'<div class="tm-pane" id="tm-{key}"{"" if key == first_model else " hidden"}>{topic_cards(rows, kind)}</div>'
    for _, key, _, kind, rows in available_models if rows
)
hybrid_section = f'''<section class="tm-section" id="modelado-tematico">
  <div class="tm-head"><div><h2>Modelado temático</h2><p><strong>BERTopic multilingüe · solución preferida provisional · 14 macrotemas · validación humana pendiente.</strong> Las STM son comparativas y los históricos aparecen separados.</p></div>
  <select id="tm-select" onchange="showTopicModel(this.value)">{model_options}</select></div>
  <div class="tm-method"><strong>Outliers conservados:</strong> {len(outlier_rows)} ({(100*len(outlier_rows)/2182 if outlier_rows else 0):.2f}%). Causas provisionales: {html_lib.escape(outlier_summary or "pendiente")}.</div>
  <div class="tm-method"><strong>Configuración efectiva:</strong> {html_lib.escape(config_summary)}. Se muestran por separado el ID algorítmico, el descriptor automático y la etiqueta humana propuesta. Ninguna propuesta equivale a validación especializada.</div>
  {model_panes}
  <div class="tm-pane" id="tm-comparison" hidden><table><thead><tr><th>Topico STM</th><th>Topico BERTopic</th><th>Relacion</th><th>Similitud combinada</th></tr></thead><tbody>{alignment_html}</tbody></table></div>
  <div class="tm-method">Estado exploratorio: la selección computacional y las etiquetas son provisionales hasta completar estabilidad, intrusión y revisión humana. Semilla: 42 · período 2020–2026 · 2026 es incompleto. La prevalencia STM es una mezcla documental; el tamaño BERTopic es una asignación de cluster. Cobertura full text inferior al 50% en: {html_lib.escape(", ".join(low_coverage_years) or "ningún año")}.</div>
</section>'''

# ── HTML ──────────────────────────────────────────────────────────────────────

html = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Dashboard - Direccion Escolar</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0D1117;--surface:#161B22;--border:#21262D;
  --text:#C9D1D9;--muted:#8B949E;--accent:#58A6FF;--dim:#484F58;--hover:#1F2937
}
body{font-family:"Segoe UI",system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
header{background:#070b14;border-bottom:1px solid #1a2a4a;padding:14px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
@keyframes neon-pulse{0%{text-shadow:0 0 5px #58a6ff,0 0 10px #58a6ff,0 0 20px #58a6ff,0 0 40px #1d6fd8}100%{text-shadow:0 0 8px #7bbfff,0 0 16px #7bbfff,0 0 32px #58a6ff,0 0 64px #1d6fd8,0 0 90px #1d6fd8}}
.neon-title{font-size:1.25em;font-weight:900;letter-spacing:.05em;color:#fff;text-shadow:0 0 5px #58a6ff,0 0 10px #58a6ff,0 0 20px #58a6ff,0 0 40px #1d6fd8;animation:neon-pulse 2.5s ease-in-out infinite alternate;white-space:nowrap}
.neon-title .nt-accent{color:#a8d4ff;text-shadow:0 0 5px #a8d4ff,0 0 12px #58a6ff,0 0 26px #58a6ff,0 0 50px #1d6fd8}
.neon-sub{font-size:.68em;color:#8B949E;margin-top:2px;letter-spacing:.01em}
.neon-sub a{color:#58A6FF;text-decoration:none}
.neon-sub a:hover{text-decoration:underline}
.header-left{display:flex;flex-direction:column}
.stamp{font-size:.7em;color:var(--dim)}.kpis{display:flex;background:var(--surface);border-bottom:1px solid var(--border)}
.kpi{flex:1;text-align:center;padding:10px 8px;border-right:1px solid var(--border)}
.kpi:last-child{border-right:none}
.kpi-n{font-size:1.5em;font-weight:700;color:var(--accent)}
.kpi-l{font-size:.68em;color:var(--muted);margin-top:2px}
.main-grid{display:grid;grid-template-columns:1fr 360px;height:calc(55vh);overflow:hidden;border-bottom:1px solid var(--border)}
.net-panel{display:flex;flex-direction:column;border-right:1px solid var(--border)}
.panel-head{padding:8px 14px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
.panel-head h2{font-size:.78em;font-weight:600;color:#E6EDF3;text-transform:uppercase;letter-spacing:.06em}
.badge{background:var(--accent);color:#0D1117;border-radius:20px;padding:2px 8px;font-size:.65em;font-weight:700}
#net-svg{flex:1;width:100%;cursor:grab;min-height:0}
#net-svg:active{cursor:grabbing}
.net-controls{display:flex;align-items:center;gap:8px}
#net-view{background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:3px 8px;font-size:.72em}
#net-view:focus{outline:none;border-color:var(--accent)}
.net-legend{flex-shrink:0;max-height:62px;overflow-y:auto;padding:6px 12px;border-top:1px solid var(--border);display:flex;flex-wrap:wrap;gap:4px 10px;background:var(--surface)}
.net-legend span{font-size:.66em;color:var(--muted);display:inline-flex;align-items:center;gap:4px;white-space:nowrap}
.net-legend i{width:8px;height:8px;border-radius:50%;display:inline-block;flex-shrink:0}
.net-empty{padding:14px;font-size:.75em;color:var(--muted)}
.tooltip{position:fixed;background:#1a2030;border:1px solid var(--border);border-radius:8px;padding:10px 14px;font-size:.76em;pointer-events:none;opacity:0;transition:opacity .15s;max-width:260px;z-index:300;line-height:1.5}
.topics-panel{display:flex;flex-direction:column;overflow:hidden}
.topics-scroll{flex:1;overflow-y:auto;padding:10px}
.topic-item{margin-bottom:8px;padding:9px 11px;border-radius:8px;border:1px solid var(--border);border-left-width:3px;cursor:pointer;transition:all .2s;background:var(--surface)}
.topic-item:hover{background:var(--hover);transform:translateX(2px)}
.topic-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
.t-name{font-size:.8em;font-weight:700}
.t-meta{font-size:.68em;color:var(--muted)}
.bar-track{background:#1E2A38;border-radius:3px;height:5px}
.bar-fill{height:100%;border-radius:3px}
.t-frex{font-size:.68em;color:var(--muted);margin-top:4px;line-height:1.4}
.t-hint{font-size:.62em;color:var(--dim);margin-top:3px}
.arts-section{display:flex;flex-direction:column;height:45vh;overflow:hidden}
.arts-head{padding:10px 20px;display:flex;align-items:center;gap:14px;border-bottom:1px solid var(--border);background:var(--surface);flex-shrink:0}
.arts-head h2{font-size:.78em;font-weight:600;color:#E6EDF3;text-transform:uppercase;letter-spacing:.06em;white-space:nowrap}
.search{flex:1;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:6px 12px;color:var(--text);font-size:.82em;outline:none}
.search:focus{border-color:var(--accent)}
.search::placeholder{color:var(--dim)}
.table-wrap{flex:1;overflow-y:auto;overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.78em}
thead th{background:var(--surface);color:var(--muted);padding:7px 12px;text-align:left;font-size:.7em;text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid var(--border);position:sticky;top:0;z-index:10}
tbody td{padding:7px 12px;border-bottom:1px solid #161B22;vertical-align:top}
tbody tr:hover td{background:var(--hover)}
.alink{color:var(--accent);text-decoration:none;font-weight:500;line-height:1.3;display:block}
.alink:hover{text-decoration:underline}
.ameta{color:var(--muted);font-size:.7em;margin-top:1px}
.kws{display:flex;flex-wrap:wrap;gap:3px;margin-top:3px}
.kt{background:#1E2A38;color:var(--muted);border-radius:3px;padding:1px 5px;font-size:.65em}
.pager{display:flex;align-items:center;gap:8px;padding:8px 20px;border-top:1px solid var(--border);background:var(--surface);flex-shrink:0}
.pager button{background:var(--hover);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:4px 11px;cursor:pointer;font-size:.76em;transition:all .15s}
.pager button:hover{border-color:var(--accent);color:var(--accent)}
.pager button:disabled{opacity:.3;cursor:not-allowed}
.pager .pinfo{font-size:.74em;color:var(--muted);flex:1;text-align:center}
.no-res{padding:20px;text-align:center;color:var(--muted);font-size:.82em;display:none}
.modal-ov{position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:500;display:none;align-items:center;justify-content:center}
.modal-ov.open{display:flex}
.modal{background:var(--surface);border:1px solid var(--border);border-radius:12px;width:90%;max-width:780px;max-height:80vh;display:flex;flex-direction:column;overflow:hidden}
.modal-h{padding:14px 18px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}
.modal-h h3{font-size:.95em;color:#E6EDF3}
.mcls{background:none;border:none;color:var(--muted);font-size:1.4em;cursor:pointer;line-height:1}
.mcls:hover{color:#E6EDF3}
.mfrex{padding:8px 18px;border-bottom:1px solid var(--border);font-size:.75em;color:var(--muted)}
.mbody{overflow-y:auto;padding:10px 18px}
.mpaper{padding:8px 0;border-bottom:1px solid var(--border)}
.mpaper:last-child{border-bottom:none}
.mpaper a{color:var(--accent);text-decoration:none;font-size:.83em;font-weight:500;line-height:1.4;display:block}
.mpaper a:hover{text-decoration:underline}
.mpmeta{font-size:.72em;color:var(--muted);margin-top:2px}
.mcount{font-size:.72em;color:var(--dim);padding:7px 18px;border-top:1px solid var(--border);text-align:right}
.tm-section{padding:20px;border-bottom:1px solid var(--border);background:#0b1018}.tm-head{display:flex;justify-content:space-between;align-items:center;gap:14px;margin-bottom:12px}.tm-head h2{font-size:1em;color:#E6EDF3}.tm-head p,.tm-method{font-size:.76em;color:var(--muted);margin-top:4px}.tm-head select{max-width:420px;background:var(--surface);color:var(--text);border:1px solid var(--border);padding:7px 12px;border-radius:6px}.tm-pane{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:9px;max-height:520px;overflow:auto}.tm-pane[hidden]{display:none}.tm-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px}.tm-title{font-size:.83em;font-weight:700;color:#E6EDF3}.tm-meta,.tm-words,.tm-reps,.tm-alert{font-size:.69em;color:var(--muted);line-height:1.45;margin-top:5px}.tm-reps{color:var(--dim)}.tm-alert{color:#f6c177;background:#2b2214;border-left:2px solid #f6c177;padding:4px 6px}.tm-details{font-size:.69em;color:var(--muted);line-height:1.5;margin-top:8px;border-top:1px solid var(--border);padding-top:7px}.tm-details summary{cursor:pointer;color:var(--accent);font-weight:700}.tm-details div{margin-top:4px}.tm-method{border-left:3px solid var(--accent);padding:8px 10px;margin-top:12px;background:var(--surface)}.tm-empty{font-size:.8em;color:var(--muted)}
@media(max-width:900px){.main-grid{grid-template-columns:1fr}.topics-panel{display:none}}
</style>
</head>
<body>

<header>
  <div class="header-left">
    <div class="neon-title">Dashboard &middot; <span class="nt-accent">Direccion y Gestion Escolar</span></div>
    <div class="neon-sub">version beta &middot; desarrollada por <a href="mailto:aguirre.elias.gonzalo@gmail.com">Elias Aguirre</a> &middot; <a href="articulos.html">Trabajar con tabla de articulos</a></div>
  </div>
  <span class="stamp">Actualizado: """ + date.today().strftime('%d/%m/%Y') + f""" &middot; {anio_min}&ndash;{anio_max}</span>
</header>

<div class="kpis">
  <div class="kpi"><div class="kpi-n">{total:,}</div><div class="kpi-l">Publicaciones</div></div>
  <div class="kpi"><div class="kpi-n">{n_macros_preferred}</div><div class="kpi-l">Macrotemas BERTopic</div></div>
  <div class="kpi"><div class="kpi-n">{n_nodes}</div><div class="kpi-l">Nodos en red</div></div>
  <div class="kpi"><div class="kpi-n">{n_edges}</div><div class="kpi-l">Conexiones</div></div>
  <div class="kpi"><div class="kpi-n">{anio_min}&ndash;{anio_max}</div><div class="kpi-l">Periodo</div></div>
</div>

""" + hybrid_section + """

<div class="main-grid">
  <div class="net-panel">
    <div class="panel-head">
      <h2 id="net-title">Red temática</h2>
      <div class="net-controls">
        <select id="net-view" onchange="setNetworkView(this.value)">
          <option value="documents">Red de documentos</option>
          <option value="topics">Red de tópicos</option>
        </select>
        <span class="badge" id="net-badge">&nbsp;</span>
      </div>
    </div>
    <svg id="net-svg"></svg>
    <div class="net-legend" id="net-legend"></div>
  </div>
  <div class="topics-panel">
    <div class="panel-head">
      <h2>Tópicos STM históricos</h2>
      <span class="badge">Clic para ver articulos</span>
    </div>
    <div class="topics-scroll" id="topics-container"></div>
  </div>
</div>

<div class="arts-section" id="articulos">
  <div class="arts-head">
    <h2>Todos los articulos</h2>
    <input type="text" class="search" id="search-input" placeholder="Buscar por titulo, autor, resumen, palabras clave, revista, fuente o anio..." oninput="onSearch()">
    <span class="badge" id="count-badge">{n_arts:,} articulos</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th style="width:36%">Titulo</th>
          <th style="width:18%">Autores</th>
          <th style="width:16%">Revista / origen</th>
          <th style="width:12%">Fuente</th>
          <th style="width:4%">Ano</th>
          <th style="width:14%">Palabras clave</th>
        </tr>
      </thead>
      <tbody id="arts-tbody"></tbody>
    </table>
    <div class="no-res" id="no-res">Sin resultados para esta busqueda.</div>
  </div>
  <div class="pager">
    <button onclick="prevPage()" id="btn-prev" disabled>&#8592; Anterior</button>
    <span class="pinfo" id="pinfo"></span>
    <button onclick="nextPage()" id="btn-next">Siguiente &#8594;</button>
  </div>
</div>

<div class="tooltip" id="tooltip"></div>

<div class="modal-ov" id="modal-ov" onclick="closeMod(event)">
  <div class="modal">
    <div class="modal-h">
      <h3 id="mod-title"></h3>
      <button class="mcls" onclick="closeMod()">&#215;</button>
    </div>
    <div class="mfrex" id="mod-frex"></div>
    <div class="mbody" id="mod-body"></div>
    <div class="mcount" id="mod-count"></div>
  </div>
</div>

<script>
const NETWORKS = """ + networks_json + """;
const TOPICOS = """ + topicos_json + """;
const ARTS    = """ + arts_json + """;
const PG = 50;

// ── Redes por modelo ──────────────────────────────────────────────────────────
// El selector de modelado y el de vista comparten un mismo estado: al cambiar
// cualquiera de los dos se vuelve a dibujar el grafo con los datos del modelo
// elegido, en lugar de mostrar siempre la STM histórica.
let currentModel = """ + json.dumps(DEFAULT_NETWORK) + """;
let currentView  = "documents";
let netSim = null;

function showTopicModel(name){
  document.querySelectorAll(".tm-pane").forEach(pane => pane.hidden = pane.id !== "tm-"+name);
  if(NETWORKS[name]) currentModel = name;
  renderNetwork(!NETWORKS[name]);
}

function setNetworkView(view){ currentView = view; renderNetwork(false); }

function renderNetwork(isComparison){
  const svgEl  = document.getElementById("net-svg");
  const legend = document.getElementById("net-legend");
  const title  = document.getElementById("net-title");
  const badge  = document.getElementById("net-badge");
  const tip    = document.getElementById("tooltip");

  if(netSim){ netSim.stop(); netSim = null; }
  d3.select("#net-svg").selectAll("*").remove();
  tip.style.opacity = "0";

  const model = NETWORKS[currentModel];
  if(!model){ legend.innerHTML = ""; badge.textContent = "Sin red disponible"; return; }

  const isTopics = currentView === "topics";
  const view = model[currentView] || {nodes:[], edges:[]};
  title.textContent = (isTopics ? "Red de tópicos · " : "Red de documentos · ") + model.label;
  badge.textContent = isComparison
    ? "La comparación no tiene red propia · se mantiene " + model.label
    : (isTopics
        ? `${view.nodes.length} tópicos · ${view.edges.length} enlaces`
        : `${view.nodes.length} nodos · ${view.edges.length} aristas · base: ${model.base}`);

  // En la vista documental el color no se explica solo: la leyenda traduce
  // cada color al tópico del modelo activo.
  legend.innerHTML = isTopics ? "" : model.topics.nodes
    .map(t=>`<span><i style="background:${t.color}"></i>T${t.id} ${t.label}</span>`).join("");

  const W = svgEl.clientWidth || 800;
  const H = svgEl.clientHeight || 400;
  const svg = d3.select("#net-svg").attr("width",W).attr("height",H);

  if(!view.nodes.length){
    svg.append("text").attr("x",W/2).attr("y",H/2).attr("text-anchor","middle")
       .attr("fill","#8B949E").attr("font-size",13)
       .text("Este modelo no tiene documentos suficientes para tejer una red.");
    return;
  }

  const g = svg.append("g");
  svg.call(d3.zoom().scaleExtent([0.15,10]).on("zoom", e => g.attr("transform", e.transform)));

  // Se clona: la simulación escribe x/y sobre los objetos y volveríamos a
  // dibujar posiciones viejas al regresar a un modelo ya visitado.
  const nodes = view.nodes.map(n=>Object.assign({},n));
  const links = view.edges.map(e=>Object.assign({},e));
  const maxWeight = Math.max(1, ...nodes.map(n=>(isTopics ? n.size : n.degree)||1));

  netSim = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id((_,i)=>i)
      .distance(isTopics ? d=>130-70*d.weight : d=>55-d.weight*3)
      .strength(isTopics ? 0.35 : 0.5))
    .force("charge", d3.forceManyBody().strength(isTopics ? -430 : -70))
    .force("center", d3.forceCenter(W/2, H/2))
    .force("collision", d3.forceCollide(isTopics ? 36 : 9));

  const link = g.append("g").selectAll("line").data(links).enter().append("line")
    .attr("stroke","#1E2A38")
    .attr("stroke-width", d=>isTopics ? Math.max(0.6, d.weight*3) : Math.min(3, d.weight*0.4))
    .attr("stroke-opacity",0.5);

  const node = g.append("g").selectAll("circle").data(nodes).enter().append("circle")
    .attr("r", d=>isTopics ? 9+Math.sqrt((d.size||1)/maxWeight)*24 : 4+((d.degree||0)/maxWeight)*9)
    .attr("fill", d=>d.color||"#484F58")
    .attr("stroke","#0D1117").attr("stroke-width",1).attr("opacity",0.87)
    .style("cursor", isTopics ? "default" : "pointer")
    .on("mouseover",(ev,d)=>{
      tip.style.opacity="1";
      tip.innerHTML = isTopics
        ? `<strong>T${d.id} &middot; ${d.label}</strong><br><span style="color:#8B949E">${d.size} documentos${d.prevalence?` &middot; ${d.prevalence.toFixed(1)}%`:""}</span><br><span style="color:#58A6FF">${(d.words||[]).join(" &middot; ")}</span>`
        : `<strong>${d.title}</strong><br><span style="color:#8B949E">${d.authors}</span><br><span style="color:#58A6FF">${d.year}</span>${d.topic?`<br>T${d.topic} ${d.topic_label||""}`:""}`;
    })
    .on("mousemove",ev=>{ tip.style.left=(ev.clientX+14)+"px"; tip.style.top=(ev.clientY-10)+"px"; })
    .on("mouseout",()=>{ tip.style.opacity="0"; })
    .on("click",(_,d)=>{ if(!isTopics && d.url) window.open(d.url,"_blank"); })
    .call(d3.drag()
      .on("start",(e,d)=>{ if(!e.active) netSim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; })
      .on("drag", (e,d)=>{ d.fx=e.x; d.fy=e.y; })
      .on("end",  (e,d)=>{ if(!e.active) netSim.alphaTarget(0); d.fx=null; d.fy=null; }));

  const caption = isTopics
    ? g.append("g").selectAll("text").data(nodes).enter().append("text")
        .text(d=>"T"+d.id).attr("font-size",10).attr("font-weight",700)
        .attr("fill","#0D1117").attr("text-anchor","middle").attr("pointer-events","none")
    : null;

  netSim.on("tick",()=>{
    link.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y)
        .attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
    node.attr("cx",d=>d.x).attr("cy",d=>d.y);
    if(caption) caption.attr("x",d=>d.x).attr("y",d=>d.y+3);
  });
}

renderNetwork(false);

// ── Topicos ───────────────────────────────────────────────────────────────────
(function(){
  const con = document.getElementById("topics-container");
  const mx  = Math.max(...TOPICOS.map(t=>t.prevalencia));
  TOPICOS.forEach(t=>{
    const d = document.createElement("div");
    d.className = "topic-item";
    d.style.borderLeftColor = t.color;
    d.innerHTML = `
      <div class="topic-row">
        <span class="t-name" style="color:${t.color}">T${t.id}</span>
        <span class="t-meta">${t.prevalencia.toFixed(1)}% &middot; ${t.papers.length} arts.</span>
      </div>
      <div class="bar-track"><div class="bar-fill" style="width:${(t.prevalencia/mx*100).toFixed(1)}%;background:${t.color}"></div></div>
      <div class="t-frex">${t.frex.join(" &middot; ")}</div>
      <div class="t-hint">&#9654; Clic para ver articulos</div>`;
    d.addEventListener("click",()=>openMod(t));
    con.appendChild(d);
  });
})();

function openMod(t){
  document.getElementById("mod-title").textContent = `Topico ${t.id} &middot; ${t.prevalencia.toFixed(1)}% del corpus`;
  document.getElementById("mod-frex").textContent  = "FREX: " + t.frex.join(" · ");
  document.getElementById("mod-count").textContent = t.papers.length + " articulos en este topico";
  const b = document.getElementById("mod-body");
  b.innerHTML = "";
  if(!t.papers.length){
    b.innerHTML='<p style="color:var(--muted);padding:16px">Sin articulos asignados aun.</p>';
  } else {
    t.papers.forEach(p=>{
      const dv=document.createElement("div");
      dv.className="mpaper";
      dv.innerHTML=`<a href="${p.url||"#"}" target="_blank" rel="noopener">${p.titulo}</a>
        <div class="mpmeta">${p.autores||"—"} &middot; ${p.revista||"—"} &middot; ${p.anio||"—"}</div>`;
      b.appendChild(dv);
    });
  }
  document.getElementById("modal-ov").classList.add("open");
}

function closeMod(ev){
  if(!ev||ev.target===document.getElementById("modal-ov"))
    document.getElementById("modal-ov").classList.remove("open");
}
document.addEventListener("keydown",e=>{ if(e.key==="Escape") closeMod(); });

// ── Articulos paginados ────────────────────────────────────────────────────────
let curPage=0, filtered=ARTS;

function onSearch(){
  const q=document.getElementById("search-input").value.toLowerCase().trim();
  filtered = q ? ARTS.filter(a=>(a.search||"").toLowerCase().includes(q)) : ARTS;
  curPage=0;
  render();
}

function render(){
  const tbody = document.getElementById("arts-tbody");
  const noRes = document.getElementById("no-res");
  const st    = curPage*PG;
  const page  = filtered.slice(st, st+PG);
  const tot   = filtered.length;
  const pages = Math.ceil(tot/PG)||1;

  document.getElementById("count-badge").textContent = tot.toLocaleString()+" articulo"+(tot!==1?"s":"");
  document.getElementById("pinfo").textContent = tot>0 ? `Pagina ${curPage+1} de ${pages} (${tot.toLocaleString()} resultados)` : "0 resultados";
  document.getElementById("btn-prev").disabled = curPage===0;
  document.getElementById("btn-next").disabled = curPage>=pages-1;

  tbody.innerHTML="";
  noRes.style.display = tot===0?"block":"none";

  page.forEach(a=>{
    const tr=document.createElement("tr");
    const kws=(a.kws||[]).map(k=>`<span class="kt">${k}</span>`).join("");
    const resumen=a.resumen ? `<div class="ameta">${a.resumen}</div>` : "";
    tr.innerHTML=`
      <td><a class="alink" href="${a.url||"#"}" target="_blank" rel="noopener">${a.titulo}</a>${resumen}</td>
      <td><span class="ameta">${a.autores||"—"}</span></td>
      <td><span class="ameta">${a.revista||"—"}</span></td>
      <td><span class="ameta">${a.fuente||"—"}</span></td>
      <td><span class="ameta">${a.anio||"—"}</span></td>
      <td><div class="kws">${kws}</div></td>`;
    tbody.appendChild(tr);
  });
}

function focusArticleSearch(){
  if(window.location.hash !== "#articulos") return;
  const section = document.getElementById("articulos");
  const input = document.getElementById("search-input");
  if(section) section.scrollIntoView({block:"start"});
  if(input) setTimeout(()=>input.focus(), 250);
}

function prevPage(){ if(curPage>0){ curPage--; render(); } }
function nextPage(){ if(curPage<Math.ceil(filtered.length/PG)-1){ curPage++; render(); } }

render();
focusArticleSearch();
</script>
</body>
</html>"""

(OUT_DIR / "index.html").write_text(html, encoding="utf-8")
print(f"Dashboard generado: docs/index.html")
print(f"  Red: {n_nodes} nodos - {n_edges} aristas")
print(f"  Topicos: {n_tops}")
print(f"  Articulos: {n_arts:,}")
