#!/usr/bin/env python3
"""
generate_dashboard.py
Dashboard interactivo con:
1. Red de similitud semántica estilo Connected Papers (D3 force-directed)
2. Tópicos STM clickeables con lista de artículos del tópico
3. Lista completa paginada (50/página) con buscador por título/autor
"""

import csv, gzip, json, re, itertools, shutil, html as html_lib
from pathlib import Path
from datetime import date
from collections import Counter, defaultdict
from apa_citation import build_citation, detect_language, format_author
from topic_modeling.identifiers import normalize_doi, stable_document_id
from keyword_network import build_network, read_rules, topic_agreement, DEFAULT_PROFILE, clean_keywords
from dashboard_integrity import model_fingerprint, proposal_matches

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
    opener = (lambda: gzip.open(p, "rt", encoding="utf-8-sig", newline="")) if p.suffix == ".gz" else (lambda: open(p, encoding="utf-8-sig"))
    with opener() as f:
        return list(csv.DictReader(f))

def s(v):
    return str(v or "").strip()

def clean_title(v):
    txt = s(v)
    txt = re.sub(r"</?(?:b|i|em|strong|sub|sup|span|p)\b[^>]*>", "", txt, flags=re.I)
    return re.sub(r"\s+", " ", txt).strip()

def fmt_es(n):
    return f"{int(n):,}".replace(",", ".")

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

N_MACROS = sum(row.get("topic_id") not in ("-1", "", None) for row in read_csv("output/topic_models/bertopic/metadata_multilingual/preferred_solution/topics.csv"))
records    = read_csv("data/master_records.csv")
corpus     = read_csv("data/corpus.csv.gz")
topicos    = read_csv("output/tabla_topicos.csv")
doc_topics = read_csv("output/document_topics.csv")
MODEL_VIEWS = [
    ("principal", "bertopic-macros", f"BERTopic multilingüe · {N_MACROS} macrotemas", "BERTopic", "output/topic_models/bertopic/metadata_multilingual/preferred_solution/topics.csv"),
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
    titulo = clean_title(rec.get("title", "") or cp.get("titulo", ""))
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

MIN_SEMANTIC_SIMILARITY = 0.35
MIN_COASSIGNMENT = 0.15
MIN_WORD_OVERLAP = 0.03


def _row_doi(row):
    """Las salidas de modelado traen `doi` o un `document_id` con prefijo."""
    doi = s(row.get("doi"))
    if doi:
        return normalize_doi(doi)
    document_id = s(row.get("document_id"))
    if document_id.lower().startswith("doi:"):
        return normalize_doi(document_id)
    return ""


def _topic_id(value):
    """Los subtopicos se exportan como float ("0.0") y los topicos como int."""
    value = s(value)
    return value[:-2] if value.endswith(".0") else value


def match_paper(row):
    doi = _row_doi(row)
    if doi and doi in paper_keys_by_doi:
        return paper_keys_by_doi[doi]
    for field in ("publication_document_id", "document_id"):
        key = s(row.get(field))
        if key in paper_pool:
            return key
        if key in paper_keys_by_model_id:
            return paper_keys_by_model_id[key]
    document = model_document_metadata.get(s(row.get("document_id")), row)
    matches = paper_keys_by_title.get(s(document.get("title")).casefold(), [])
    return matches[0] if len(matches) == 1 else None


def load_document_topics(config):
    assignments = {}
    for row in read_csv(config["documents"]):
        key = match_paper(row)
        topic_id = _topic_id(row.get(config["document_topic_field"]))
        if key and topic_id:
            assignments[key] = topic_id
    return assignments


# Etiquetas humanas propuestas: los topics.csv traen el descriptor automatico
# ("leadership · style"), ilegible en una leyenda de colores.
# Cada etiqueta queda atada al corpus del modelo para el que se escribió
# (model_corpus_hash). Si el modelo se reajusta con otro corpus, sus tópicos
# cambian y la etiqueta vieja no se aplica: se muestra el descriptor automático.
PREFERRED_CONFIG = Path("output/topic_models/bertopic/metadata_multilingual/preferred_solution/effective_configuration.json")
CURRENT_MODEL_HASH = json.loads(PREFERRED_CONFIG.read_text(encoding="utf-8")).get("corpus_hash", "") if PREFERRED_CONFIG.exists() else ""
PROPOSED_LABELS = defaultdict(dict)
STALE_LABELS = 0
current_topics = {_topic_id(r.get("topic_id")): r for r in read_csv(f"{BERTOPIC_ROOT}/topics.csv")}
for row in read_csv("config/topic_labels.csv"):
    label = s(row.get("human_label"))
    bound = s(row.get("model_corpus_hash"))
    if label and bound and bound != CURRENT_MODEL_HASH:
        STALE_LABELS += 1
        continue
    if label and not proposal_matches(row, current_topics.get(_topic_id(row.get("topic_id")), {})):
        continue
    if label:
        PROPOSED_LABELS[s(row.get("model"))][_topic_id(row.get("topic_id"))] = label
if STALE_LABELS:
    print(f"Etiquetas de otra versión del modelo no aplicadas: {STALE_LABELS} (revisar config/topic_labels.csv)")


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


# Pool de documentos: la red léxica se calcula una sola vez para todos los modelos.
keyword_rules = read_rules()
keyword_ids, keyword_cleaned, keyword_variants, keyword_audit = build_network(records, keyword_rules)
paper_pool = {}
paper_keys_by_doi = {}
paper_keys_by_model_id = {}
model_document_metadata = {s(row.get("document_id")): row for row in read_csv(f"{BERTOPIC_ROOT}/document_topics.csv")}
paper_keys_by_title = defaultdict(list)
for row_index, row in enumerate(records):
    doi = normalize_doi(row.get("doi"))
    title = clean_title(row.get("title", ""))
    paper_key = s(row.get("record_id")) or f"record-{row_index}"
    paper_keys_by_model_id.setdefault(stable_document_id(row), paper_key)
    if doi:
        paper_keys_by_doi.setdefault(doi, paper_key)
    if title:
        paper_keys_by_title[title.casefold()].append(paper_key)
    kws_raw = s(row.get("keywords", ""))
    authors = [a.strip() for a in s(row.get("authors", "")).split(";") if a.strip()]
    language = detect_language(row)
    surnames = [format_author(author, language).split(",", 1)[0] for author in authors]
    short_author = (surnames[0] + " et al." if len(surnames) > 2 else " & ".join(surnames)) or "Sin autor"
    citation = build_citation(row, language)
    paper_pool[paper_key] = {
        "id": paper_key,
        "title": title or "Registro sin título",
        "short_citation": f"{short_author}, {s(row.get('publication_year')) or 's. f.'}",
        "reference": citation.text,
        "reference_missing": citation.missing,
        "authors": "; ".join(authors[:2]) + (" et al." if len(authors) > 2 else ""),
        "year": s(row.get("publication_year", "")),
        "url": s(row.get("url", "")) or (f"https://doi.org/{doi}" if doi else ""),
        "kws": keyword_cleaned[paper_key]["keywords"],
        "keywords": keyword_cleaned[paper_key]["keywords"],
        "keyword_original": [k.strip() for k in kws_raw.split(";") if k.strip()],
        "keyword_excluded": keyword_cleaned[paper_key]["excluded"],
        "keyword_provenance": keyword_cleaned[paper_key]["provenance"],
    }

duplicate_aliases = read_csv("data/duplicate_records.csv")
for alias in duplicate_aliases:
    target = s(alias.get("duplicate_of"))
    if target not in paper_pool:
        continue
    paper_keys_by_model_id[stable_document_id(alias)] = target
    paper_keys_by_model_id[s(alias.get("record_id"))] = target
    paper_keys_by_title[s(alias.get("title")).casefold()].append(target)

BASE_UNIVERSES = {"master": ("corpus completo de registros", set(paper_pool))}


def _weave(papers):
    edges = keyword_variants[DEFAULT_PROFILE]
    nodes = [{k: v for k, v in paper.items() if k not in {"kws", "keywords", "keyword_original", "keyword_excluded", "keyword_provenance", "title", "authors", "year", "url", "short_citation", "reference", "reference_missing"}} for paper in papers]
    for node in nodes:
        node["degree"] = 0
    for edge in edges:
        nodes[edge["source"]]["degree"] += 1
        nodes[edge["target"]]["degree"] += 1
    return nodes, edges


def build_keyword_network(base_dois, assignments, colors, labels):
    papers = []
    for key in sorted(base_dois):
        info = paper_pool[key]
        topic_id = assignments.get(key)
        state = "outlier" if topic_id == "-1" else "assigned" if topic_id is not None else "not_modeled"
        papers.append({**info, "topic": topic_id if state == "assigned" else "",
            "topic_label": labels.get(topic_id, "Sin grupo asignado" if state == "outlier" else "Sin asignación vinculada a este modelo"),
            "assignment_status": state, "color": colors.get(topic_id, "#72879e")})
    return _weave(papers)


def build_topic_network(topics, colors, assignments, config):
    """Red de topicos: nodos = topicos, aristas = similitud entre ellos."""
    counts = Counter(topic for topic in assignments.values() if topic != "-1")
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

    base_key = "master"
    base_label = "corpus completo de registros"
    base_dois = set(paper_pool)
    best_cover = sum(topic != "-1" for topic in assignments.values())
    doc_nodes, doc_edges = build_keyword_network(base_dois, assignments, colors, labels)
    topic_nodes, topic_edges = build_topic_network(topics, colors, assignments, config)
    keyword_audit.setdefault("topic_comparison", {})[model_key] = {profile: topic_agreement(keyword_ids, edges, assignments) for profile, edges in keyword_variants.items()}
    networks[model_key] = {
        "label": model_label,
        "fingerprint": model_fingerprint(read_csv(config["topics"]), read_csv(config["documents"])),
        "kind": model_kind,
        "base": base_label,
        "assigned": best_cover,
        "modeled": len(read_csv(config["documents"])),
        "unlinked": sum(match_paper(row) is None for row in read_csv(config["documents"])),
        "outliers": sum(topic == "-1" for topic in assignments.values()),
        "not_modeled": len(paper_pool) - len(assignments),
        "documents": {"nodes": doc_nodes, "edges": doc_edges},
        "topics": {"nodes": topic_nodes, "edges": topic_edges},
    }
    print(
        f"Red {model_key}: {len(doc_nodes)} nodos / {len(doc_edges)} aristas "
        f"(base {base_key}, {best_cover} asignados) - "
        f"{len(topic_nodes)} topicos / {len(topic_edges)} enlaces"
    )

legacy_index = defaultdict(list)
for i, key in enumerate(keyword_ids):
    original = [t.strip().lower() for t in paper_pool[key]["keyword_original"] if len(t.strip()) > 3 and t.strip().lower() not in KW_STOPS][:12]
    for term in set(original):
        legacy_index[term].append(i)
legacy_counts = Counter()
for members in legacy_index.values():
    if 2 <= len(members) <= 40:
        legacy_counts.update(itertools.combinations(members, 2))
legacy_edges = [pair for pair, count in legacy_counts.items() if count >= 2]
legacy_connected = set(i for pair in legacy_edges for i in pair)
keyword_audit["legacy"] = {"label": "Criterio anterior de coincidencias exactas", "edges": len(legacy_edges), "connected_records": len(legacy_connected), "isolated_records": len(keyword_ids)-len(legacy_connected), "keyword_limit": 12, "max_document_frequency": 40, "min_shared": 2}
keyword_audit["generated_on"] = date.today().isoformat()
keyword_audit["selection_reason"] = "La configuración intermedia 0,20 es un punto de comparación exploratorio entre 0,10 y 0,30; no fue optimizada por apariencia ni validada como solución estadística. Las alternativas quedan disponibles."
keyword_audit["sources"] = [
 {"apa": "van Eck, N. J., & Waltman, L. (2010). Software survey: VOSviewer, a computer program for bibliometric mapping. Scientometrics, 84, 523–538.", "url": "https://doi.org/10.1007/s11192-009-0146-3"},
 {"apa": "van Eck, N. J., & Waltman, L. (2023). VOSviewer manual (version 1.6.20).", "url": "https://www.vosviewer.com/documentation/Manual_VOSviewer_1.6.20.pdf"},
 {"apa": "OpenAlex. (s. f.). Keywords. OpenAlex Help Center. Consulta: 3 de octubre de 2026.", "url": "https://help.openalex.org/data/keywords/"}]
shutil.copyfile("config/keyword_thesaurus.csv", OUT_DIR / "keyword-thesaurus.csv")
(OUT_DIR / "keyword-network-audit.json").write_text(json.dumps(keyword_audit, ensure_ascii=False, indent=2), encoding="utf-8")
# Store links once as compact arrays. All model views refer to the same lexical graph.
vocabulary = sorted({term for edges in keyword_variants.values() for e in edges for term in e["shared_keywords"]})
term_index = {term: i for i, term in enumerate(vocabulary)}
pool = {}; variant_indexes = {}
for profile, edges in keyword_variants.items():
    indexes = []
    for edge in edges:
        pair = (edge["source"], edge["target"])
        if pair not in pool:
            pool[pair] = {"index": len(pool), "edge": edge}
        indexes.append(pool[pair]["index"])
    variant_indexes[profile] = indexes
# Cada perfil de semejanza se publica en su propio JSON y se descarga solo al elegirlo:
# el perfil por defecto pesa unos MB; los exploratorios, decenas.
KEYWORD_DATA_DIR = OUT_DIR / "data"
KEYWORD_DATA_DIR.mkdir(exist_ok=True)
for profile, edges in keyword_variants.items():
    rows = [[e["source"], e["target"], e["jaccard"] if profile == "jaccard_control" else e["weight"], [term_index[t] for t in e["shared_keywords"]]] for e in edges]
    (KEYWORD_DATA_DIR / f"keyword-edges-{profile}.json").write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
keyword_payload = {"default_profile": DEFAULT_PROFILE, "profiles": keyword_audit["profiles"], "terms": vocabulary}
(OUT_DIR / "keyword-network-data.js").write_text("window.KeywordNetworkData = " + json.dumps(keyword_payload, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")

review_models = {}
for model_key, config in NETWORK_SOURCES.items():
    if model_key not in networks:
        continue
    member_groups = defaultdict(list)
    for row in read_csv(config["documents"]):
        topic_id = _topic_id(row.get(config["document_topic_field"]))
        if not topic_id or topic_id == "-1":
            continue
        key = match_paper(row)
        member = {"id": key or s(row.get("document_id")),
            "ambiguous": s(row.get("is_ambiguous")).lower() == "true",
            "silhouette": row.get("silhouette", ""),
            "membership": row.get("hdbscan_membership_strength", ""),
            "topic_probability": row.get("topic_probability", "")}
        if key is None:
            row = model_document_metadata.get(s(row.get("document_id")), row)
            member["paper"] = {"title": s(row.get("title")) or "Sin título", "year": s(row.get("year")),
                "authors": "Autoría no disponible", "url": f"https://doi.org/{_row_doi(row)}" if _row_doi(row) else ""}
        if not any(existing["id"] == member["id"] for existing in member_groups[topic_id]):
            member_groups[topic_id].append(member)
    review_models[model_key] = {"topics": member_groups}
(OUT_DIR / "topic-review-data.json").write_text(json.dumps({"models": review_models}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

DEFAULT_NETWORK = "bertopic-macros" if "bertopic-macros" in networks else next(iter(networks), "")
nodes = networks.get(DEFAULT_NETWORK, {}).get("documents", {}).get("nodes", [])
edges = networks.get(DEFAULT_NETWORK, {}).get("documents", {}).get("edges", [])

# ── Lista completa de artículos ───────────────────────────────────────────────

all_articles = []
for r in records:
    title = clean_title(r.get("title", ""))
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
    kws = clean_keywords(kws_raw, keyword_rules)[0][:5]
    resumen = s(r.get("abstract", ""))
    fuente = infer_source(r)
    revista = infer_origin(r)
    aliases = [a for a in duplicate_aliases if s(a.get("duplicate_of")) == s(r.get("record_id"))]
    variant_text = " ".join(s(a.get("title")) + " " + s(a.get("authors")) for a in aliases)
    # El navegador arma el texto buscable completo con titulo, autores, revista, fuente, año y resumen;
    # aquí solo se guarda lo que no aparece en esos campos (palabras clave originales y títulos duplicados).
    search_text = " ".join([kws_raw, variant_text]).strip()
    all_articles.append({
        "titulo":    title,
        "autores":   auth_short,
        "revista":   revista,
        "fuente":    fuente,
        "anio":      s(r.get("publication_year", "")),
        "fecha_pub": s(r.get("publication_date", "")),
        "tipo":      s(r.get("document_type", "")),
        "termino":   s(r.get("search_term", "")),
        "doi":       doi,
        "url":       url,
        "oa":        "Sí" if str(r.get("is_oa", "")).strip().lower() in {"true", "1", "yes", "sí", "si"} else "No",
        "pdf":       s(r.get("pdf_url", "")),
        "kws":       kws,
        "resumen":   resumen[:450],
        "fecha_reg": s(r.get("first_seen_date", "")),
        "score":     s(r.get("relevance_score", "")),
        "search":    search_text,
    })

all_articles.sort(key=lambda x: safe_int(x["anio"], 0), reverse=True)

# ── Estadísticas ──────────────────────────────────────────────────────────────

drive_manifest = read_csv("data/drive_manifest.csv")
drive_pdf_count = len({r.get("drive_file_id") for r in drive_manifest if r.get("drive_file_id")})
total  = len(records)
anios  = [safe_int(r.get("publication_year", 0)) for r in records if r.get("publication_year")]
anio_min = min(anios) if anios else 2020
anio_max = max(anios) if anios else 2026

# ── JSON ──────────────────────────────────────────────────────────────────────

# Los nodos documentales de cada modelo y la tabla de papers pesan varios MB:
# se publican como JSON aparte y el navegador los pide solo cuando los necesita.
DATA_SUBDIR = OUT_DIR / "data"
DATA_SUBDIR.mkdir(exist_ok=True)
network_export = {}
for key, net in networks.items():
    nodes_json = json.dumps(net["documents"]["nodes"], ensure_ascii=False, separators=(",", ":"))
    (DATA_SUBDIR / f"network-{key}.json").write_text(nodes_json, encoding="utf-8")
    network_export[key] = {**net, "documents": {"nodes": [], "edges": []}}
networks_json = json.dumps(network_export, ensure_ascii=False, separators=(",", ":"))
PAPER_DETAIL_KEYS = ("reference", "reference_missing", "keyword_original", "keyword_excluded", "keyword_provenance")
papers_light = {key: {k: v for k, v in paper.items() if k != "kws" and k not in PAPER_DETAIL_KEYS} for key, paper in paper_pool.items()}
papers_detail = {key: {k: paper[k] for k in PAPER_DETAIL_KEYS if k in paper} for key, paper in paper_pool.items()}
(DATA_SUBDIR / "papers.json").write_text(json.dumps(papers_light, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
(DATA_SUBDIR / "papers-detail.json").write_text(json.dumps(papers_detail, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
papers_json = "{}"
arts_json    = json.dumps(all_articles, ensure_ascii=False, separators=(",", ":"))
(OUT_DIR / "dashboard-articles.js").write_text("window.StellarArticles = " + arts_json + ";\n", encoding="utf-8")
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
topic_label_proposal_by_id = {s(row.get("topic_id")): row for row in topic_label_proposals
    if proposal_matches(row, current_topics.get(s(row.get("topic_id")), {}), networks.get("bertopic-macros", {}).get("fingerprint", ""))}
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

def topic_cards(rows, model, model_key):
    if not rows:
        return '<p class="tm-empty">Todavia no hay resultados para este modelo.</p>'
    cards = []
    for row in rows:
        topic_id = _topic_id(row.get("topic_id") or row.get("subtopic_id") or row.get("macro_topic_id"))
        proposal = topic_label_proposal_by_id.get(topic_id, {}) if model_key == "bertopic-macros" else {}
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
        if model_key == "bertopic-macros" and not proposal:
            evaluation = {}
            language_diagnostic = {}
            heterogeneity = {}
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
            f'<article class="tm-card" role="button" tabindex="0" data-model="{html_lib.escape(model_key)}" data-topic="{html_lib.escape(topic_id)}" data-original-label="{html_lib.escape(label)}" aria-label="Revisar tema {html_lib.escape(label)}">'
            f'<div class="tm-title">{html_lib.escape(label)}</div>'
            f'<div class="tm-meta"><strong>ID:</strong> T{html_lib.escape(topic_id)} · <strong>descriptor automático:</strong> {html_lib.escape(algorithmic_label)}</div>'
            f'<div class="tm-meta">{html_lib.escape(measure)}: {html_lib.escape(s(row.get("prevalence")))}% · '
            f'{count} documentos</div>'
            '<div class="tm-open">Revisar los documentos del tema →</div>'
            f'<div class="tm-words">{html_lib.escape(s(row.get("top_words")))}</div>'
            f'<template class="tm-evidence">{alert_html}{interpretation_html}<p><strong>Estado del modelo:</strong> {html_lib.escape(selection_status)}. <strong>Etiqueta original:</strong> {html_lib.escape(label_status)}.</p></template></article>'
        )
    return "".join(cards)

alignment_rows = sorted(topic_alignment, key=lambda row: float(row.get("combined_alignment") or row.get("combined_similarity") or 0), reverse=True)[:20]
alignment_html = "".join(
    f'<tr><td>{html_lib.escape(s(row.get("stm_model")))} · {html_lib.escape(s(row.get("language")))} · T{html_lib.escape(s(row.get("stm_topic")))}</td><td>BERTopic T{html_lib.escape(s(row.get("bertopic_topic")))}</td>'
    f'<td>{html_lib.escape(s(row.get("relationship") or row.get("alignment_status")))}</td><td>{html_lib.escape(s(row.get("combined_alignment") or row.get("combined_similarity")))}</td></tr>'
    for row in alignment_rows if s(row.get("bertopic_topic")) != "-1"
) or '<tr><td colspan="4">Ejecute ambos modelos y la comparacion para completar esta vista.</td></tr>'
available_models = []
for group, key, label, kind, path in MODEL_VIEWS:
    model_rows = read_csv(path)
    if key == "bertopic-macros":
        model_rows = [row for row in model_rows if s(row.get("topic_id")) != "-1"]
    available_models.append((group, key, label, kind, model_rows))
first_model = "bertopic-macros"
stm_stability_warning = (
    "En STM, las réplicas de estabilidad actuales no convergieron: la selección de temas requiere revisión."
    if any("nonconverged" in s(row.get("selection_status") or row.get("model_status"))
           for _, _, _, kind, rows in available_models if kind == "STM" for row in rows)
    else "La convergencia y la estabilidad deben revisarse antes de interpretar la selección de temas."
)
group_labels = {"principal": "Modelo principal", "comparative": "Modelos comparativos", "historical": "Históricos"}
model_options = "".join(
    f'<optgroup label="{group_labels[group]}">' + "".join(
        f'<option value="{key}"{" selected" if key == first_model else ""}>{html_lib.escape(label)}{" · sin ejecutar" if not rows else ""}</option>'
        for item_group, key, label, _, rows in available_models if item_group == group and rows
    ) + '</optgroup>' for group in ("principal", "comparative", "historical")
) + '<optgroup label="Comparación"><option value="comparison">Comparación STM–BERTopic</option></optgroup>'
model_panes = "".join(
    f'<div class="tm-pane" id="tm-{key}"{"" if key == first_model else " hidden"}>{topic_cards(rows, kind, key)}</div>'
    for _, key, _, kind, rows in available_models if rows
)
hybrid_section = f'''<section class="tm-section" id="modelado-tematico">
  <div class="tm-head"><div><h2>Modelado temático</h2><p class="tm-lead"><strong>Elegí un modelo y abrí un tema para revisar sus documentos.</strong> El selector cambia los temas y colorea la red.</p><p>Resultados exploratorios: la validación humana está pendiente.</p>
  <details class="tm-notes"><summary>Cómo leer estos resultados</summary><p>Los modelos principales y comparativos se estimaron sobre metadatos bibliográficos; no representan un análisis del texto completo de todos los PDF. {stm_stability_warning} BERTopic mantiene los documentos sin tema fuera de la comparación temática.</p></details></div>
  <select id="tm-select" aria-label="Modelo temático" onchange="showTopicModel(this.value)">{model_options}</select></div>
  {model_panes}
  <div class="tm-pane" id="tm-comparison" hidden><table><thead><tr><th scope="col">Tópico STM</th><th scope="col">Tópico BERTopic</th><th scope="col">Relación</th><th scope="col">Similitud combinada</th></tr></thead><tbody>{alignment_html}</tbody></table></div>
  <div class="tm-review-tools"><button type="button" id="topic-export">Exportar revisiones</button><label>Importar revisiones <input type="file" id="topic-import" accept="application/json,.json"></label><span id="topic-review-status" role="status">Las decisiones se guardan en este navegador.</span></div>
</section>'''

# ── HTML ──────────────────────────────────────────────────────────────────────

html = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Dashboard · Dirección y Gestión Escolar</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<script src="stellar-network.js"></script>
<script src="keyword-method.js" defer></script>
<script src="topic-review.js" defer></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0D1117;--surface:#161B22;--border:#21262D;
  --text:#C9D1D9;--muted:#8B949E;--accent:#58A6FF;--dim:#7F8A96;--hover:#1F2937
}
body{font-family:"Segoe UI",system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
header{background:#070b14;border-bottom:1px solid #1a2a4a;padding:14px 24px;display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;position:sticky;top:0;z-index:100}
@keyframes neon-pulse{0%{text-shadow:0 0 5px #58a6ff,0 0 10px #58a6ff,0 0 20px #58a6ff,0 0 40px #1d6fd8}100%{text-shadow:0 0 8px #7bbfff,0 0 16px #7bbfff,0 0 32px #58a6ff,0 0 64px #1d6fd8,0 0 90px #1d6fd8}}
.neon-title{font-size:clamp(1.05em,1.8vw,1.25em);font-weight:900;letter-spacing:.05em;color:#fff;text-shadow:0 0 5px #58a6ff,0 0 10px #58a6ff,0 0 20px #58a6ff,0 0 40px #1d6fd8;animation:neon-pulse 2.5s ease-in-out infinite alternate}
.neon-title .nt-accent{color:#a8d4ff;text-shadow:0 0 5px #a8d4ff,0 0 12px #58a6ff,0 0 26px #58a6ff,0 0 50px #1d6fd8}
.neon-sub{font-size:.68em;color:#8B949E;margin-top:2px;letter-spacing:.01em}
.neon-sub a{color:#58A6FF;text-decoration:none}
.neon-sub a:hover{text-decoration:underline}
.header-left{display:flex;flex-direction:column;min-width:0}
.stamp{font-size:.7em;color:var(--dim)}.kpis{display:flex;background:var(--surface);border-bottom:1px solid var(--border)}
.kpi{flex:1;text-align:center;padding:10px 8px;border-right:1px solid var(--border)}
.kpi:last-child{border-right:none}
.kpi-n{font-size:1.5em;font-weight:700;color:var(--accent)}
.kpi-l{font-size:.68em;color:var(--muted);margin-top:2px}
.main-grid{display:grid;grid-template-columns:1fr 360px;height:calc(62vh);min-height:460px;overflow:hidden;border-bottom:1px solid var(--border)}
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
.arts-section{display:flex;flex-direction:column;height:52vh;min-height:420px;overflow:hidden;background:var(--bg)}
.arts-section:fullscreen,.arts-section.is-fullscreen{position:fixed;inset:0;width:100vw;height:100vh;z-index:900;background:var(--bg)}
.arts-head{padding:10px 20px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;border-bottom:1px solid var(--border);background:var(--surface);flex-shrink:0}
.arts-head h2{font-size:.78em;font-weight:600;color:#E6EDF3;text-transform:uppercase;letter-spacing:.06em;white-space:nowrap}
.search{flex:1;min-width:220px;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:6px 12px;color:var(--text);font-size:.82em;outline:none}
.search:focus{border-color:var(--accent)}
.search::placeholder{color:var(--dim)}
.arts-tools{display:flex;align-items:center;gap:8px;flex-wrap:wrap;position:relative}
.arts-btn,.arts-select{background:#10243a;border:1px solid #355575;color:#dceaff;border-radius:6px;padding:5px 10px;font-size:.76em;cursor:pointer;white-space:nowrap}
.arts-btn:hover,.arts-select:hover{background:#193957;border-color:var(--accent)}
.arts-btn.active{background:#1f6feb;border-color:#58a6ff;color:#fff}
.col-picker{position:absolute;right:0;top:calc(100% + 6px);width:min(360px,90vw);max-height:65vh;overflow:auto;background:#0d1726;border:1px solid #385e82;border-radius:10px;padding:12px;box-shadow:0 14px 40px rgba(0,0,0,.78);z-index:250}
.col-picker[hidden]{display:none}
.col-picker-head{display:flex;justify-content:space-between;align-items:center;gap:8px;padding-bottom:8px;margin-bottom:8px;border-bottom:1px solid var(--border);font-size:.78em;color:#e6edf3;font-weight:600}
.col-picker-actions{display:flex;gap:6px}
.col-picker-actions button{background:#162436;border:1px solid #304963;color:#a8d4ff;border-radius:5px;padding:3px 8px;font-size:.85em;cursor:pointer}
.col-picker-actions button:hover{border-color:var(--accent);color:#fff}
.col-picker-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px 10px}
.col-picker-item{display:flex;align-items:center;gap:7px;font-size:.76em;color:var(--text);cursor:pointer;padding:3px 4px;border-radius:5px}
.col-picker-item:hover{background:#182433}
.col-picker-item input{accent-color:var(--accent);cursor:pointer}
.table-wrap{flex:1;overflow-y:auto;overflow-x:auto}
table{width:max-content;min-width:100%;border-collapse:collapse;font-size:.78em}
thead th{background:var(--surface);color:var(--muted);padding:7px 12px;text-align:left;font-size:.7em;text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid var(--border);position:sticky;top:0;z-index:10;white-space:nowrap;cursor:pointer;user-select:none}
thead th:hover{color:#e6edf3}
thead th .sort-ind{margin-left:4px;color:var(--accent);font-size:.9em}
tbody td{padding:7px 12px;border-bottom:1px solid #161B22;vertical-align:top;max-width:340px}
tbody td.col-titulo{min-width:290px;max-width:420px}
tbody td.col-resumen{min-width:260px;max-width:380px}
tbody td.col-autores{min-width:170px}
tbody td.col-revista,tbody td.col-termino{min-width:150px}
tbody td.col-doi,tbody td.col-pdf,tbody td.col-url{max-width:210px;word-break:break-all}
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
/* ── Accesibilidad y legibilidad ───────────────────────────────────────────── */
.skip-link{position:absolute;left:12px;top:-64px;z-index:1000;background:#fff;color:#0d1117;padding:10px 16px;border-radius:8px;font-weight:700;text-decoration:none}
.skip-link:focus{top:10px}
.sr-only{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}
a:focus-visible,button:focus-visible,select:focus-visible,input:focus-visible,textarea:focus-visible,summary:focus-visible,[tabindex]:focus-visible{outline:2px solid #a8d4ff;outline-offset:2px}
.search:focus,#net-view:focus{outline:2px solid #a8d4ff;outline-offset:1px}
main:focus{outline:none}
.neon-sub{font-size:.78em}.stamp{font-size:.78em}.kpi-l{font-size:.78em}.badge{font-size:.75em}
#net-view,#net-profile{font-size:.8em}.net-legend span{font-size:.75em;padding:4px 8px}
.t-name{display:inline-flex;align-items:center;gap:6px;color:#E6EDF3}.t-dot{width:10px;height:10px;border-radius:50%;display:inline-block;box-shadow:0 0 6px currentColor}
.t-meta,.t-frex{font-size:.78em}.t-hint{font-size:.75em;color:var(--muted)}
table{font-size:.82em}.ameta{font-size:.92em}.kt{font-size:.9em;padding:2px 6px}thead th{font-size:.92em}.alink{padding:4px 0}
.search{font-size:.9em}.pager button{font-size:.85em;padding:6px 14px}.pager .pinfo{font-size:.82em}
.tooltip{font-size:.82em}.mfrex,.mcount,.mpmeta{font-size:.78em}
.tm-head p,.tm-method,.tm-meta,.tm-words,.tm-reps,.tm-alert,.tm-details{font-size:.78em}.tm-title{font-size:.9em}
.tm-open{font-size:12px;font-weight:700;color:var(--accent);margin-top:6px}
.tm-lead{font-size:.86em;color:var(--text);margin-top:4px}
.tm-notes{margin-top:8px;font-size:1em;color:var(--muted)}.tm-notes summary{font-size:.8em;cursor:pointer;color:var(--accent);font-weight:700}.tm-notes p{margin-top:6px;line-height:1.5}
.kpi-l abbr{text-decoration:underline dotted;cursor:help}
button,select{min-height:28px}
.net-method,.net-method p,.net-method summary,#keyword-audit-open{font-size:12px}
.topic-item:focus-visible,.tm-card:focus-visible{outline-offset:-2px}
@media(pointer:coarse){button,select,.pager button,.stellar-tools button,.net-legend span{min-height:44px}.stellar-tools button{min-width:44px}.net-legend span{padding:10px 10px}.topic-item,.tm-card{min-height:44px}.mcls{min-width:44px;min-height:44px}}
</style>
<link rel="stylesheet" href="stellar-network.css">
<link rel="stylesheet" href="topic-review.css">
</head>
<body>
<a class="skip-link" href="#contenido">Saltar al contenido</a>

<header>
  <div class="header-left">
    <h1 class="neon-title">Dashboard &middot; <span class="nt-accent">Dirección y Gestión Escolar</span></h1>
    <div class="neon-sub">Versión beta &middot; desarrollada por <a href="mailto:aguirre.elias.gonzalo@gmail.com">Elias Aguirre</a> &middot; <a href="articulos.html">Trabajar con la tabla de artículos</a></div>
  </div>
  <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap"><a class="argentina-link" href="argentina.html" style="color:#d5edff;border:1px solid #4072a0;border-radius:22px;padding:10px 16px;text-decoration:none;background:#10233c">✦ Argentina · BERTopic 2020–2026 ↗</a><span class="stamp">Actualizado: """ + date.today().strftime('%d/%m/%Y') + f""" &middot; {anio_min}&ndash;{anio_max}</span></div>
</header>

<main id="contenido" tabindex="-1">
<div class="kpis" role="group" aria-label="Resumen del corpus">
  <div class="kpi"><div class="kpi-n">{fmt_es(total)}</div><div class="kpi-l">Publicaciones en catálogo</div></div>
  <div class="kpi"><div class="kpi-n" id="kpi-topics">{fmt_es(n_macros_preferred)}</div><div class="kpi-l">Temas del modelo</div></div>
  <div class="kpi" title="Cada documento es un nodo de la red."><div class="kpi-n" id="kpi-nodes">{fmt_es(n_nodes)}</div><div class="kpi-l">Documentos en la red</div></div>
  <div class="kpi" title="Dos documentos se enlazan si comparten palabras clave."><div class="kpi-n" id="kpi-edges">{fmt_es(n_edges)}</div><div class="kpi-l">Enlaces por palabras clave</div></div>
  <div class="kpi"><div class="kpi-n">{fmt_es(drive_pdf_count)}</div><div class="kpi-l">PDF en Drive</div></div>
  <div class="kpi"><div class="kpi-n">{anio_min}&ndash;{anio_max}</div><div class="kpi-l">Periodo</div></div>
</div>

<div class="main-grid">
  <div class="net-panel">
    <div class="panel-head">
      <h2 id="net-title">Red temática</h2>
      <div class="net-controls">
        <select id="net-model" aria-label="Modelo temático que colorea la red" onchange="syncModelSelect(this.value)"></select>
        <select id="net-view" aria-label="Vista de la red" onchange="setNetworkView(this.value)">
          <option value="documents">Red de documentos</option>
          <option value="topics">Red de tópicos</option>
        </select>
        <select id="net-profile" aria-label="Criterio de semejanza" onchange="setKeywordProfile(this.value)"></select>
        <button type="button" id="keyword-audit-open">Método y comparación</button>
        <span class="badge" id="net-badge">&nbsp;</span>
      </div>
    </div>
    <div class="stellar-stage" id="stellar-stage">
      <svg id="net-svg" aria-label="Red temática interactiva" aria-describedby="net-summary"></svg>
      <p id="net-summary" class="sr-only" aria-live="polite"></p>
      <div class="stellar-tools" aria-label="Controles de la red">
        <button type="button" id="net-zoom-in" aria-label="Acercar">+</button>
        <button type="button" id="net-zoom-out" aria-label="Alejar">−</button>
        <button type="button" id="net-fit">Encuadrar</button>
        <button type="button" id="net-fullscreen" onclick="toggleNetFullscreen()" title="Pantalla completa">⛶</button>
        <input type="search" id="net-search" class="stellar-search" placeholder="Localizar nodo en la red…" aria-label="Localizar nodo en la red" oninput="onNetSearch(this.value)">
      </div>
      <div class="stellar-hint">Arrastrá un nodo · Doble clic enfoca su vecindario · Flechas para recorrer, + − 0 para zoom · Leyenda: aislar constelación</div>
      <aside id="net-detail" class="stellar-detail" aria-label="Ficha del nodo" hidden>
        <button type="button" id="net-detail-close" aria-label="Cerrar ficha">×</button>
        <div id="net-detail-body" aria-live="polite"></div>
      </aside>
    </div>
    <div class="net-legend" id="net-legend"></div>
    <details class="net-method"><summary>Cómo se construye esta red</summary><p id="net-method-text"></p><p>La ubicación resulta de una simulación de fuerzas. Las distancias en pantalla no son una escala de semejanza semántica. Las formas regulares aparecen cuando muchos nodos tienen enlaces y tamaños similares.</p></details>
  </div>
  <div class="topics-panel">
    <div class="panel-head">
      <h2>Tópicos STM históricos</h2>
      <span class="badge">Elegí un tópico</span>
    </div>
    <div class="topics-scroll" id="topics-container"></div>
  </div>
</div>

""" + hybrid_section + """

<div class="arts-section" id="articulos">
  <div class="arts-head">
    <h2>Tabla en vivo del catálogo</h2>
    <input type="text" class="search" id="search-input" placeholder="Buscar por título, autor, resumen, palabras clave, DOI, revista, fuente o año…" aria-label="Buscar en el catálogo de artículos" oninput="onSearch()">
    <div class="arts-tools">
      <select class="arts-select" id="filter-source" aria-label="Filtrar por fuente" onchange="onSearch()"><option value="">Todas las fuentes</option></select>
      <select class="arts-select" id="filter-year" aria-label="Filtrar por año" onchange="onSearch()"><option value="">Todos los años</option></select>
      <select class="arts-select" id="filter-oa" aria-label="Filtrar por acceso abierto" onchange="onSearch()"><option value="">Acceso abierto: todos</option><option value="Sí">Solo acceso abierto</option><option value="No">Sin acceso abierto</option></select>
      <button type="button" class="arts-btn" id="btn-cols" aria-expanded="false" aria-controls="col-picker" onclick="toggleColPicker()">⚙ Columnas (<span id="col-count">16/16</span>)</button>
      <button type="button" class="arts-btn" id="btn-export-csv" onclick="exportVisibleCsv()" title="Descargar las filas filtradas y columnas visibles en CSV">⬇ CSV</button>
      <button type="button" class="arts-btn" id="btn-arts-fullscreen" onclick="toggleArtsFullscreen()" title="Ver tabla en pantalla completa">⛶ Pantalla completa</button>
      <div class="col-picker" id="col-picker" role="dialog" aria-label="Selector de columnas visibles" hidden>
        <div class="col-picker-head">
          <span>Columnas visibles (solo lectura)</span>
          <div class="col-picker-actions">
            <button type="button" onclick="setAllCols(true)">Todas</button>
            <button type="button" onclick="setCompactCols()">Compacta</button>
          </div>
        </div>
        <div class="col-picker-grid" id="col-picker-grid"></div>
      </div>
    </div>
    <span class="badge" id="count-badge" role="status">Cargando…</span>
  </div>
  <div class="table-wrap">
    <table id="arts-table">
      <caption class="sr-only">Catálogo completo interactivo de artículos</caption>
      <thead>
        <tr id="arts-thead-row"></tr>
      </thead>
      <tbody id="arts-tbody"></tbody>
    </table>
    <div class="no-res" id="no-res">Sin resultados para esta búsqueda.</div>
  </div>
  <div class="pager">
    <button type="button" onclick="prevPage()" id="btn-prev" disabled>&#8592; Anterior</button>
    <span class="pinfo" id="pinfo" role="status"></span>
    <button type="button" onclick="nextPage()" id="btn-next">Siguiente &#8594;</button>
  </div>
</div>

</main>

<div class="tooltip" id="tooltip" role="tooltip"></div>

<div class="modal-ov" id="modal-ov" onclick="closeMod(event)">
  <div class="modal" role="dialog" aria-modal="true" aria-labelledby="mod-title">
    <div class="modal-h">
      <h3 id="mod-title"></h3>
      <button type="button" class="mcls" id="mod-close" aria-label="Cerrar" onclick="closeMod()">&#215;</button>
    </div>
    <div class="mfrex" id="mod-frex"></div>
    <div class="mbody" id="mod-body"></div>
    <div class="mcount" id="mod-count"></div>
  </div>
</div>

<script>
const NETWORKS = """ + networks_json + """;
window.StellarPapers = {};
const TOPICOS = """ + topicos_json + """;
let ARTS = [];
const PG = 50;
let KEYWORD_DATA = null;
let currentProfile = null;
const keywordCache = {};

// ── Carga diferida de datos pesados ──────────────────────────────────────────
function loadJSON(url){return fetch(url).then(r=>{if(!r.ok)throw Error(url+" HTTP "+r.status);return r.json();});}
function loadScript(src){return new Promise((ok,fail)=>{const el=document.createElement("script");el.src=src;el.onload=ok;el.onerror=()=>fail(Error(src));document.head.appendChild(el);});}
let papersPromise=null, keywordPromise=null, articlesPromise=null;
const networkPromises={};
window.ensurePapers=()=>papersPromise||(papersPromise=loadJSON("data/papers.json").then(p=>{window.StellarPapers=p;return p;}).catch(e=>{papersPromise=null;throw e;}));
function ensureKeywords(){
  return keywordPromise||(keywordPromise=loadScript("keyword-network-data.js").then(()=>{
    KEYWORD_DATA=window.KeywordNetworkData;
    currentProfile=KEYWORD_DATA.default_profile;
    for(const [id,p] of Object.entries(KEYWORD_DATA.profiles)){profileSelect.appendChild(new Option(p.label,id));}
    profileSelect.value=currentProfile;
  }).catch(e=>{keywordPromise=null;throw e;}));
}
const keywordEdgePromises={};
function ensureKeywordEdges(profile){
  if(keywordCache[profile]) return Promise.resolve();
  return keywordEdgePromises[profile]||(keywordEdgePromises[profile]=loadJSON("data/keyword-edges-"+profile+".json").then(rows=>{
    keywordCache[profile]=rows.map(e=>({source:e[0],target:e[1],weight:e[2],shared_count:e[3].length,shared_keywords:e[3].map(i=>KEYWORD_DATA.terms[i])}));
  }).catch(e=>{delete keywordEdgePromises[profile];throw e;}));
}
let detailPromise=null;
window.ensurePaperDetails=()=>detailPromise||(detailPromise=loadJSON("data/papers-detail.json").then(d=>{window.StellarPaperDetails=d;return d;}).catch(e=>{detailPromise=null;throw e;}));
function ensureNetwork(name){
  const net=NETWORKS[name];
  if(!net||net.documents.nodes.length) return Promise.resolve();
  return networkPromises[name]||(networkPromises[name]=loadJSON("data/network-"+name+".json").then(nodes=>{
    net.documents.nodes=nodes;
    if(window.applyTopicReviews) window.applyTopicReviews();
  }).catch(e=>{delete networkPromises[name];throw e;}));
}
function ensureArticles(){
  return articlesPromise||(articlesPromise=loadScript("dashboard-articles.js").then(()=>{
    ARTS=window.StellarArticles||[];
    for(const a of ARTS) a.search=[a.titulo,a.autores,a.revista,a.fuente,a.anio,a.doi,a.tipo,a.termino,a.resumen,a.search].join(" ").toLowerCase();
    populateTableFilters();
    applyTableFilters();
  }).catch(e=>{articlesPromise=null;throw e;}));
}
function whenNear(el,fn,margin){
  if(!el) return;
  let done=false;
  const run=()=>{if(done)return;done=true;fn();};
  if(!("IntersectionObserver" in window)){run();return;}
  const io=new IntersectionObserver(es=>{if(es.some(e=>e.isIntersecting)){io.disconnect();run();}},{rootMargin:margin||"800px"});
  io.observe(el);
  // Respaldo: pestañas en segundo plano o navegadores que no notifican la intersección.
  const fallback=()=>setTimeout(()=>{io.disconnect();run();},2500);
  if(document.readyState==="complete") fallback(); else window.addEventListener("load",fallback,{once:true});
}
const profileSelect = document.getElementById('net-profile');
function keywordEdges(profile){ return keywordCache[profile] || []; }
function setKeywordProfile(profile){if(!KEYWORD_DATA||!KEYWORD_DATA.profiles[profile])return;currentProfile=profile;renderNetwork(false);}

// ── Redes por modelo ──────────────────────────────────────────────────────────
// El selector de modelado y el de vista comparten un mismo estado: al cambiar
// cualquiera de los dos se vuelve a dibujar el grafo con los datos del modelo
// elegido, en lugar de mostrar siempre la STM histórica.
let currentModel = """ + json.dumps(DEFAULT_NETWORK) + """;
let currentView  = "documents";
let netSim = null;

function syncModelSelect(name){
  const main = document.getElementById("tm-select");
  if(main){ main.value = name; }
  showTopicModel(name);
}
(function(){
  const main = document.getElementById("tm-select"), mirror = document.getElementById("net-model");
  if(!main || !mirror) return;
  mirror.innerHTML = main.innerHTML;
  mirror.value = main.value;
  main.addEventListener("change", () => { mirror.value = main.value; });
})();
function showTopicModel(name){
  document.querySelectorAll(".tm-pane").forEach(pane => pane.hidden = pane.id !== "tm-"+name);
  if(NETWORKS[name]) currentModel = name;
  renderNetwork(!NETWORKS[name]);
}

function setNetworkView(view){ currentView = view; renderNetwork(false); }

let netRenderToken=0;
async function renderNetwork(isComparison){
  const token=++netRenderToken;
  const model=NETWORKS[currentModel];
  if(!KEYWORD_DATA||!papersPromise||(model&&!model.documents.nodes.length)){
    document.getElementById("net-badge").textContent="Cargando red…";
  }
  try{
    await ensureKeywords();
    await Promise.all([ensureKeywordEdges(currentProfile),ensurePapers(),ensureNetwork(currentModel)]);
  }catch(err){
    document.getElementById("net-badge").textContent="No se pudo cargar la red. Reintentá recargando la página.";
    console.error(err);return;
  }
  if(token!==netRenderToken) return;
  for(const net of Object.values(NETWORKS)) if(net.documents.nodes.length) net.documents.edges = keywordEdges(currentProfile);
  renderNetworkNow(isComparison);
}
function renderNetworkNow(isComparison){
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
  const baseView = model[currentView] || {nodes:[], edges:[]};
  const edges = isTopics ? baseView.edges : keywordEdges(currentProfile);
  const degrees = new Array(baseView.nodes.length).fill(0);
  if(!isTopics) for(const e of edges){degrees[e.source]++;degrees[e.target]++;}
  const view = isTopics ? baseView : {nodes:baseView.nodes.map((n,i)=>({...n,degree:degrees[i]})),edges};
  profileSelect.disabled = isTopics;
  document.getElementById("kpi-topics").textContent = model.topics.nodes.length.toLocaleString("es-AR");
  document.getElementById("kpi-nodes").textContent = view.nodes.length.toLocaleString("es-AR");
  document.getElementById("kpi-edges").textContent = view.edges.length.toLocaleString("es-AR");
  document.getElementById("net-method-text").textContent = isTopics
    ? (model.kind === "STM" ? "Nodos: temas. Tamaño: cantidad de documentos con ese tema predominante. Enlaces: coasignación como primer y segundo tema; se conservan los pares más fuertes según el criterio del modelo." : currentModel === "bertopic-subtopics" ? "Nodos: subtópicos. Tamaño: cantidad de documentos. Enlaces: pertenencia al mismo macrotema." : "Nodos: macrotemas. Tamaño: cantidad de documentos. Enlaces: similitud c-TF-IDF entre sus vocabularios; se aplica un umbral y se completan los pares más fuertes cuando la red queda escasa.")
    : `Corpus completo: ${view.nodes.length} registros, incluidos los aislados. ${model.assigned} con tema asignado; ${model.outliers} sin grupo asignado; ${model.not_modeled} sin asignación vinculada a este modelo. Su exportación contiene ${model.modeled} filas; ${model.unlinked} no pudieron vincularse a un registro maestro. Enlaces: al menos dos etiquetas normalizadas compartidas y semejanza ${KEYWORD_DATA.profiles[currentProfile].threshold.toFixed(2)} o mayor (${currentProfile === "jaccard_control" ? "Jaccard simple" : "Jaccard ponderado por IDF"}). Se consideran todas las etiquetas retenidas, sin límite de frecuencia. Diccionario de equivalencias y exclusiones propuesto, pendiente de revisión. Origen histórico de las etiquetas sin trazabilidad exacta. Consultá Método y comparación. Tamaño: número de conexiones en esta red. Gris: sin tema asignado. Sin recorte de 400 nodos.`;
  title.textContent = (isTopics ? "Red de tópicos · " : "Red de documentos · ") + model.label;
  const summary = document.getElementById("net-summary");
  if(summary) summary.textContent = (isTopics
      ? `Red de ${view.nodes.length} tópicos del modelo ${model.label}.`
      : `Red de ${view.nodes.length.toLocaleString("es-AR")} documentos y ${view.edges.length.toLocaleString("es-AR")} enlaces por palabras clave, coloreada con el modelo ${model.label}.`)
    + " Con el foco en la red, usá las flechas para pasar de un nodo al más cercano, Enter para abrir su ficha y más, menos o cero para el zoom."
    + " La misma información está disponible como texto en las tarjetas de tema y en la tabla de artículos.";
  badge.textContent = isComparison
    ? "La comparación no tiene red propia · se mantiene " + model.label
    : (isTopics
        ? `${view.nodes.length} tópicos · ${view.edges.length} enlaces`
        : `${view.nodes.length} registros · ${view.edges.length} enlaces · ${model.assigned} con tema`);

  // En la vista documental el color no se explica solo: la leyenda traduce
  // cada color al tópico del modelo activo y permite aislar su constelación.
  legend.innerHTML = isTopics ? "" : model.topics.nodes
    .map(t=>`<span data-legend-topic="${t.id}" onclick="toggleLegendTopic('${t.id}', this)" title="Clic para enfocar esta constelación temática"><i style="background:${t.color};box-shadow:0 0 6px ${t.color}"></i>T${t.id} ${String(t.label).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}</span>`).join("") + '<span><i style="background:#72879e"></i>Sin tema asignado / sin asignación vinculada</span>';

  netSim = StellarNetwork.render({svgEl, model, view, isTopics, tip});
}

function toggleLegendTopic(topicId, el){
  if(!netSim || !netSim.focusTopic) return;
  const activeTopic = netSim.focusTopic(topicId);
  document.querySelectorAll("#net-legend span[data-legend-topic]").forEach(sp=>{
    sp.classList.toggle("active", sp.dataset.legendTopic === activeTopic);
  });
}

function onNetSearch(val){
  if(netSim && netSim.searchNodes) netSim.searchNodes(val);
}

function toggleNetFullscreen(){
  const st = document.getElementById("stellar-stage");
  if(!st) return;
  if(!document.fullscreenElement) st.requestFullscreen?.();
  else document.exitFullscreen?.();
}

whenNear(document.getElementById("stellar-stage")||document.getElementById("net-svg"),()=>renderNetwork(false),"600px");

// ── Topicos ───────────────────────────────────────────────────────────────────
(function(){
  const con = document.getElementById("topics-container");
  const mx  = Math.max(...TOPICOS.map(t=>t.prevalencia));
  TOPICOS.forEach(t=>{
    const d = document.createElement("div");
    d.className = "topic-item";
    d.style.borderLeftColor = t.color;
    d.tabIndex = 0;
    d.setAttribute("role", "button");
    d.setAttribute("aria-label", `Tópico ${t.id}: ${t.papers.length} artículos. Abrir lista`);
    const row = document.createElement("div");
    row.className = "topic-row";
    const name = document.createElement("span");
    name.className = "t-name";
    const dot = document.createElement("i");
    dot.className = "t-dot"; dot.style.background = t.color; dot.style.color = t.color; dot.setAttribute("aria-hidden", "true");
    name.append(dot, document.createTextNode("T" + t.id));
    const meta = document.createElement("span");
    meta.className = "t-meta";
    meta.textContent = `${t.prevalencia.toFixed(1)}% · ${t.papers.length} artículos`;
    row.append(name, meta);
    const track = document.createElement("div");
    track.className = "bar-track";
    const fill = document.createElement("div");
    fill.className = "bar-fill"; fill.style.width = (t.prevalencia/mx*100).toFixed(1) + "%"; fill.style.background = t.color;
    track.appendChild(fill);
    const frex = document.createElement("div");
    frex.className = "t-frex"; frex.textContent = t.frex.join(" · ");
    const hint = document.createElement("div");
    hint.className = "t-hint"; hint.textContent = `Ver los ${t.papers.length} artículos del tópico →`;
    d.append(row, track, frex, hint);
    d.addEventListener("click", () => openMod(t, d));
    d.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openMod(t, d); } });
    con.appendChild(d);
  });
})();

let modReturnFocus = null;
function safeUrl(u){
  try { const x = new URL(u, location.href); return ["https:", "http:"].includes(x.protocol) ? x.href : ""; } catch(_) { return ""; }
}
function openMod(t, opener){
  modReturnFocus = opener || document.activeElement;
  document.getElementById("mod-title").textContent = `Tópico ${t.id} · ${t.prevalencia.toFixed(1)}% del corpus`;
  document.getElementById("mod-frex").textContent  = "FREX: " + t.frex.join(" · ");
  document.getElementById("mod-count").textContent = t.papers.length + " artículos en este tópico";
  const b = document.getElementById("mod-body");
  b.replaceChildren();
  if(!t.papers.length){
    const empty = document.createElement("p");
    empty.style.cssText = "color:var(--muted);padding:16px";
    empty.textContent = "Todavía no hay artículos asignados a este tópico.";
    b.appendChild(empty);
  } else {
    t.papers.forEach(p=>{
      const dv = document.createElement("div");
      dv.className = "mpaper";
      const a = document.createElement("a");
      const href = safeUrl(p.url);
      if(href){ a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer"; }
      a.textContent = p.titulo || "Sin título";
      const meta = document.createElement("div");
      meta.className = "mpmeta";
      meta.textContent = `${p.autores||"—"} · ${p.revista||"—"} · ${p.anio||"—"}`;
      dv.append(a, meta);
      b.appendChild(dv);
    });
  }
  document.getElementById("modal-ov").classList.add("open");
  document.getElementById("mod-close").focus();
}

function closeMod(ev){
  const ov = document.getElementById("modal-ov");
  if(!ov.classList.contains("open")) return;
  if(!ev||ev.target===ov){
    ov.classList.remove("open");
    if(modReturnFocus && modReturnFocus.focus) modReturnFocus.focus();
    modReturnFocus = null;
  }
}
document.addEventListener("keydown",e=>{ if(e.key==="Escape") closeMod(); });

// ── Tabla interactiva en vivo (solo lectura, con selector de columnas y pantalla completa) ──
const TABLE_COLS = [
  {key:"titulo", label:"Título", visible:true, compact:true},
  {key:"anio", label:"Año", visible:true, compact:true},
  {key:"fecha_pub", label:"Fecha pub.", visible:true, compact:false},
  {key:"autores", label:"Autores", visible:true, compact:true},
  {key:"revista", label:"Revista / origen", visible:true, compact:true},
  {key:"fuente", label:"Fuente", visible:true, compact:true},
  {key:"tipo", label:"Tipo", visible:true, compact:false},
  {key:"termino", label:"Término búsqueda", visible:true, compact:false},
  {key:"doi", label:"DOI", visible:true, compact:false},
  {key:"url", label:"URL", visible:true, compact:false},
  {key:"oa", label:"Acceso abierto", visible:true, compact:false},
  {key:"pdf", label:"PDF URL", visible:true, compact:false},
  {key:"resumen", label:"Abstract / resumen", visible:true, compact:false},
  {key:"kws", label:"Palabras clave", visible:true, compact:true},
  {key:"fecha_reg", label:"Fecha registro", visible:true, compact:false},
  {key:"score", label:"Pertinencia", visible:true, compact:false}
];
let curPage=0, filtered=ARTS, sortCol=null, sortDir=1;
function articlesLoading(){document.getElementById("pinfo").textContent="Cargando artículos…";document.getElementById("count-badge").textContent="Cargando…";}
function escHtml(v){return String(v||"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));}

function populateTableFilters(){
  const srcSel=document.getElementById("filter-source"), yrSel=document.getElementById("filter-year");
  if(srcSel && srcSel.options.length<=1){
    const srcs=[...new Set(ARTS.map(a=>a.fuente).filter(Boolean))].sort();
    for(const s of srcs) srcSel.add(new Option(s,s));
  }
  if(yrSel && yrSel.options.length<=1){
    const yrs=[...new Set(ARTS.map(a=>a.anio).filter(Boolean))].sort((a,b)=>b.localeCompare(a));
    for(const y of yrs) yrSel.add(new Option(y,y));
  }
}

function buildColPicker(){
  const grid=document.getElementById("col-picker-grid");
  if(!grid) return;
  grid.innerHTML="";
  TABLE_COLS.forEach((col, idx)=>{
    const lab=document.createElement("label");
    lab.className="col-picker-item";
    const cb=document.createElement("input");
    cb.type="checkbox";
    cb.checked=col.visible;
    cb.onchange=()=>{
      col.visible=cb.checked;
      if(TABLE_COLS.every(c=>!c.visible)){ col.visible=true; cb.checked=true; }
      updateColCount();
      renderTableHeader();
      render();
    };
    const span=document.createElement("span");
    span.textContent=col.label;
    lab.append(cb, span);
    grid.appendChild(lab);
  });
  updateColCount();
}

function updateColCount(){
  const n=TABLE_COLS.filter(c=>c.visible).length;
  const el=document.getElementById("col-count");
  if(el) el.textContent=n+"/"+TABLE_COLS.length;
}

function toggleColPicker(){
  const p=document.getElementById("col-picker"), b=document.getElementById("btn-cols");
  if(!p) return;
  p.hidden=!p.hidden;
  if(b){ b.setAttribute("aria-expanded", String(!p.hidden)); b.classList.toggle("active", !p.hidden); }
}

function setAllCols(val){
  TABLE_COLS.forEach(c=>c.visible=val);
  buildColPicker();
  renderTableHeader();
  render();
}

function setCompactCols(){
  TABLE_COLS.forEach(c=>c.visible=!!c.compact);
  buildColPicker();
  renderTableHeader();
  render();
}

document.addEventListener("click", ev=>{
  const p=document.getElementById("col-picker"), b=document.getElementById("btn-cols");
  if(p && !p.hidden && !p.contains(ev.target) && ev.target!==b && !b?.contains(ev.target)){
    p.hidden=true;
    if(b){ b.setAttribute("aria-expanded","false"); b.classList.remove("active"); }
  }
});

function renderTableHeader(){
  const tr=document.getElementById("arts-thead-row");
  if(!tr) return;
  tr.innerHTML="";
  TABLE_COLS.filter(c=>c.visible).forEach(c=>{
    const th=document.createElement("th");
    th.scope="col";
    th.title="Clic para ordenar por "+c.label;
    const ind=sortCol===c.key ? (sortDir===1?" ▲":" ▼") : "";
    th.innerHTML=escHtml(c.label)+(ind?`<span class="sort-ind">${ind}</span>`:"");
    th.onclick=()=>{
      if(sortCol===c.key) sortDir*=-1;
      else { sortCol=c.key; sortDir=(c.key==="anio"||c.key==="score"||c.key==="fecha_pub"||c.key==="fecha_reg")?-1:1; }
      applyTableFilters();
    };
    tr.appendChild(th);
  });
}

function applyTableFilters(){
  const q=(document.getElementById("search-input")?.value||"").toLowerCase().trim();
  const src=document.getElementById("filter-source")?.value||"";
  const yr=document.getElementById("filter-year")?.value||"";
  const oa=document.getElementById("filter-oa")?.value||"";
  filtered=ARTS.filter(a=>{
    if(src && a.fuente!==src) return false;
    if(yr && a.anio!==yr) return false;
    if(oa && a.oa!==oa) return false;
    if(q && !(a.search||"").includes(q)) return false;
    return true;
  });
  if(sortCol){
    filtered=[...filtered].sort((a,b)=>{
      if(sortCol==="anio"||sortCol==="score"){
        return ((Number(a[sortCol])||0)-(Number(b[sortCol])||0))*sortDir;
      }
      const va=Array.isArray(a[sortCol])?a[sortCol].join(" "):String(a[sortCol]||"");
      const vb=Array.isArray(b[sortCol])?b[sortCol].join(" "):String(b[sortCol]||"");
      return va.localeCompare(vb,"es")*sortDir;
    });
  }
  curPage=0;
  renderTableHeader();
  render();
}

function onSearch(){
  if(!articlesPromise){ensureArticles();return;}
  applyTableFilters();
}

function formatCell(a, key){
  const v=a[key];
  if(key==="titulo"){
    const href=safeUrl(a.url);
    return href ? `<a class="alink" href="${escHtml(href)}" target="_blank" rel="noopener">${escHtml(v)}</a>` : `<strong>${escHtml(v)}</strong>`;
  }
  if(key==="kws"){
    return `<div class="kws">${(v||[]).map(k=>`<span class="kt">${escHtml(k)}</span>`).join("")}</div>`;
  }
  if(key==="doi" && v){
    const doiHref=`https://doi.org/${encodeURIComponent(v)}`;
    return `<a class="alink" href="${doiHref}" target="_blank" rel="noopener">${escHtml(v)}</a>`;
  }
  if((key==="url"||key==="pdf") && v){
    const href=safeUrl(v);
    if(href) return `<a class="alink" href="${escHtml(href)}" target="_blank" rel="noopener">${key==="pdf"?"Abrir PDF ↗":"Enlace ↗"}</a>`;
  }
  if(key==="oa"){
    const ok=v==="Sí";
    return `<span class="kt" style="color:${ok?"#7ee787":"#8b949e"};border:1px solid ${ok?"#238636":"#30363d"}">${escHtml(v||"No")}</span>`;
  }
  return `<span class="ameta">${escHtml(v||"—")}</span>`;
}

function render(){
  const tbody = document.getElementById("arts-tbody");
  const noRes = document.getElementById("no-res");
  const st    = curPage*PG;
  const page  = filtered.slice(st, st+PG);
  const tot   = filtered.length;
  const pages = Math.ceil(tot/PG)||1;

  document.getElementById("count-badge").textContent = tot.toLocaleString("es-AR")+" artículo"+(tot!==1?"s":"");
  document.getElementById("pinfo").textContent = tot>0 ? `Página ${curPage+1} de ${pages} (${tot.toLocaleString("es-AR")} resultados)` : "0 resultados";
  document.getElementById("btn-prev").disabled = curPage===0;
  document.getElementById("btn-next").disabled = curPage>=pages-1;

  tbody.innerHTML="";
  noRes.style.display = tot===0?"block":"none";

  const visCols=TABLE_COLS.filter(c=>c.visible);
  page.forEach(a=>{
    const tr=document.createElement("tr");
    tr.innerHTML=visCols.map(c=>`<td class="col-${c.key}">${formatCell(a,c.key)}</td>`).join("");
    tbody.appendChild(tr);
  });
}

function exportVisibleCsv(){
  if(!filtered.length) return;
  const visCols=TABLE_COLS.filter(c=>c.visible);
  const csvEsc=v=>`"${String(v||"").replace(/"/g,'""')}"`;
  const lines=[visCols.map(c=>csvEsc(c.label)).join(",")];
  for(const a of filtered){
    lines.push(visCols.map(c=>csvEsc(Array.isArray(a[c.key])?a[c.key].join("; "):a[c.key])).join(","));
  }
  const blob=new Blob(["\\ufeff"+lines.join("\\n")],{type:"text/csv;charset=utf-8;"});
  const url=URL.createObjectURL(blob), link=document.createElement("a");
  link.href=url; link.download="catalogo_scrapeador_"+new Date().toISOString().slice(0,10)+".csv";
  link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function toggleArtsFullscreen(){
  const sec=document.getElementById("articulos"), btn=document.getElementById("btn-arts-fullscreen");
  if(!sec) return;
  const isFull=document.fullscreenElement===sec || sec.classList.contains("is-fullscreen");
  if(!isFull){
    if(sec.requestFullscreen) sec.requestFullscreen().catch(()=>sec.classList.add("is-fullscreen"));
    else sec.classList.add("is-fullscreen");
    if(btn){ btn.textContent="✕ Salir de pantalla completa"; btn.classList.add("active"); }
  }else{
    if(document.fullscreenElement===sec) document.exitFullscreen?.();
    sec.classList.remove("is-fullscreen");
    if(btn){ btn.textContent="⛶ Pantalla completa"; btn.classList.remove("active"); }
  }
}
document.addEventListener("fullscreenchange",()=>{
  const sec=document.getElementById("articulos"), btn=document.getElementById("btn-arts-fullscreen");
  if(!sec||!btn) return;
  const active=document.fullscreenElement===sec || sec.classList.contains("is-fullscreen");
  btn.textContent=active?"✕ Salir de pantalla completa":"⛶ Pantalla completa";
  btn.classList.toggle("active",active);
});
document.addEventListener("keydown",e=>{
  if(e.key==="Escape"){
    const sec=document.getElementById("articulos");
    if(sec && sec.classList.contains("is-fullscreen")) toggleArtsFullscreen();
  }
});

buildColPicker();
renderTableHeader();

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
articlesLoading();
const idleLoad=()=>setTimeout(()=>ensureArticles(),1200);
if(document.readyState==="complete") idleLoad(); else window.addEventListener("load",idleLoad,{once:true});
document.getElementById("search-input").addEventListener("focus",()=>ensureArticles(),{once:true});
focusArticleSearch();
</script>
</body>
</html>"""

(OUT_DIR / "index.html").write_text(html, encoding="utf-8")
print(f"Dashboard generado: docs/index.html")
print(f"  Red: {n_nodes} nodos - {n_edges} aristas")
print(f"  Topicos: {n_tops}")
print(f"  Articulos: {n_arts:,}")
