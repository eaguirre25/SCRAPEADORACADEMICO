"""Build docs/matriz-data.json combining curated reading-matrix rows and
automatically extracted analytical rows from all scraped texts.

Sources:
1. data/matriz_analisis_textos.xlsx (curated qualitative reading matrix)
2. data/master_records.csv + data/corpus.csv.gz + docs/textos/*.txt
"""

from __future__ import annotations

import csv
import glob
import gzip
import json
import re
import sys
import unicodedata
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apa_citation import build_citation, plain_text  # noqa: E402

csv.field_size_limit(150_000_000)

CANONICAL_COLUMNS = [
    {"key": "seccion", "label": "Sección / Capítulo"},
    {"key": "apa", "label": "Cita en norma APA"},
    {"key": "tema", "label": "Tema principal"},
    {"key": "conceptos", "label": "Conceptos clave (y su uso)"},
    {"key": "categorias", "label": "Categorías analíticas"},
    {"key": "metodologia", "label": "Metodología"},
    {"key": "problema", "label": "Construcción del problema"},
    {"key": "epistemologia", "label": "Ubicación epistemológica"},
    {"key": "contexto", "label": "Contexto de estudio"},
    {"key": "muestra", "label": "Muestra y alcance empírico"},
    {"key": "aportes_dir", "label": "Potenciales aportes a dirección escolar"},
    {"key": "implicaciones", "label": "Implicaciones prácticas y políticas"},
    {"key": "hallazgos", "label": "Principales hallazgos y conclusiones"},
    {"key": "citas", "label": "Citas literales clave"},
    {"key": "discusion", "label": "Discusión (diálogo/crítica)"},
    {"key": "limitaciones", "label": "Limitaciones reconocidas"},
    {"key": "futura", "label": "Propuestas de investigación futura"},
    {"key": "palabras_clave", "label": "Palabras clave"},
    {"key": "aportes_estudio", "label": "Aportes al estudio de la dirección escolar"},
]

# Compiled multilingual extraction patterns (ES / EN / PT)
RE_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑÜ\"«(])")

PATTERNS = {
    "conceptos": re.compile(
        r"\b(concepto|marco teórico|marco conceptual|enfoque|modelo|noción|se entiende por|"
        r"definid[oa] como|theoretical framework|conceptual|defined as|refers to|liderazgo|"
        r"gestión escolar|autonomía|sensemaking|gubernamentalidad|performatividad|micropolítica)\b",
        re.I,
    ),
    "categorias": re.compile(
        r"\b(categorías?|dimensiones?|ejes? de análisis|tipología|tipos de|niveles de|"
        r"factores?|variables?|themes?|categories|dimensions?|typology|pillars?)\b",
        re.I,
    ),
    "metodologia": re.compile(
        r"\b(metodolog[íi]a|m[eé]todo|cualitativ[oa]|cuantitativ[oa]|enfoque mixto|"
        r"estudio de caso|etnograf[íi]a|entrevistas?|encuestas?|cuestionarios?|"
        r"revisi[oó]n sistem[aá]tica|an[aá]lisis documental|an[aá]lisis del discurso|"
        r"qualitative|quantitative|mixed methods?|case study|systematic review|"
        r"interviews?|survey|grounded theory|ethnograph|abordagem|metodologia)\b",
        re.I,
    ),
    "problema": re.compile(
        r"\b(problema de investigaci[oó]n|problem[aá]tica|brecha|tensi[oó]n|desaf[íi]o|"
        r"objetivo|prop[oó]sito|pregunta de investigaci[oó]n|se propone analizar|"
        r"busca comprender|research question|this study examines|aims to|purpose of|"
        r"addresses the gap|investiga-se|objetiva)\b",
        re.I,
    ),
    "epistemologia": re.compile(
        r"\b(epistemol[oó]g|paradigma|postestructural|foucault|bourdieu|critico|cr[íi]tic[oa]|"
        r"fenomenolog|hermen[eé]ut|interpretativ|constructiv|positivis|sociocr[íi]tic|"
        r"decolonial|teor[íi]a fundamentada|critical theory|pragmat|ontology|ontol[oó]g)\b",
        re.I,
    ),
    "contexto": re.compile(
        r"\b(contexto|escuela secundaria|educaci[oó]n media|escuela primaria|escuelas? p[uú]blicas?|"
        r"escuelas? privadas?|rural|urbana|argentina|chile|m[eé]xico|colombia|brasil|espa[ñn]a|"
        r"per[uú]|uruguay|ecuador|estados unidos|australia|reino unido|secondary school|"
        r"high school|primary school|public school|setting|context|sistema educativo)\b",
        re.I,
    ),
    "muestra": re.compile(
        r"\b(muestra|participantes?|informantes?|entrevistad[oa]s|encuestad[oa]s|"
        r"n\s*=\s*\d+|\d+\s+(?:directores?|rectores?|docentes?|profesores?|escuelas?|establecimientos?|principals?|teachers?|schools?)|"
        r"sample|participants?|respondents?)\b",
        re.I,
    ),
    "aportes_dir": re.compile(
        r"\b(direcci[oó]n escolar|gesti[oó]n escolar|liderazgo escolar|directivos?|"
        r"equipo directivo|rectores?|school leadership|school management|principals?|"
        r"headteachers?|aporta|contribuye|contributes to)\b",
        re.I,
    ),
    "implicaciones": re.compile(
        r"\b(implicaciones?|pol[íi]ticas? p[uú]blicas?|pol[íi]ticas? educativas?|"
        r"formaci[oó]n de directores|capacitaci[oó]n|recomendaciones?|pr[aá]ctica educativa|"
        r"policy implications?|practical implications?|recommendations?|professional development)\b",
        re.I,
    ),
    "hallazgos": re.compile(
        r"\b(hallazgos?|resultados?|conclusiones?|se encontr[oó]|evidencia|demuestra|"
        r"muestra que|revela|concluye|findings?|results?|conclusions?|we found|"
        r"results show|demonstrates?|conclui-se|achados)\b",
        re.I,
    ),
    "discusion": re.compile(
        r"\b(discusi[oó]n|debate|cr[íi]tica|en di[aá]logo con|a diferencia de|"
        r"sin embargo|no obstante|cuestiona|discussion|critique|in contrast to|however|"
        r"nevertheless|tension)\b",
        re.I,
    ),
    "limitaciones": re.compile(
        r"\b(limitaciones?|limitaci[oó]n|sesgo|no permite generalizar|"
        r"limitations?|limitation|caveat|scope constraints?)\b",
        re.I,
    ),
    "futura": re.compile(
        r"\b(futuras? investigaciones?|investigaci[oó]n futura|l[íi]neas? futuras?|"
        r"futuros? estudios?|queda abierto|future research|further research|future studies)\b",
        re.I,
    ),
}


def normalize_header(raw: str) -> str | None:
    """Map a raw Excel header label to a canonical column key."""
    s = re.sub(r"^\d+\.\s*", "", raw.strip()).lower()
    if not s or s.isdigit():
        return None
    if s.startswith(("capítulo", "sección", "texto", "clase")):
        return "seccion"
    if "cita en norma apa" in s:
        return "apa"
    if s == "tema principal":
        return "tema"
    if s.startswith("conceptos clave"):
        return "conceptos"
    if s.startswith("categorías analíticas") or s.startswith("categorias analiticas"):
        return "categorias"
    if s.startswith("metodología") or s.startswith("metodologia"):
        return "metodologia"
    if "construcción del problema" in s or "construccion del problema" in s:
        return "problema"
    if "epistemológica" in s or "epistemologica" in s:
        return "epistemologia"
    if s == "contexto de estudio":
        return "contexto"
    if s.startswith("muestra y alcance"):
        return "muestra"
    if s == "aportes al estudio de la dirección escolar":
        return "aportes_estudio"
    if "aportes" in s:
        return "aportes_dir"
    if s.startswith("implicaciones"):
        return "implicaciones"
    if "hallazgos" in s:
        return "hallazgos"
    if s.startswith("citas literales"):
        return "citas"
    if s.startswith("discusión") or s.startswith("discusion"):
        return "discusion"
    if s.startswith("limitaciones"):
        return "limitaciones"
    if "investigación futura" in s or "investigacion futura" in s:
        return "futura"
    if s.startswith("palabras clave"):
        return "palabras_clave"
    return None


def norm_title(t: str) -> str:
    """Normalize a title for deduplication between Excel and scraped records."""
    s = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", s.lower())[:90]


def parse_matriz_xlsx(xlsx_path: Path) -> list[dict[str, str]]:
    """Parse all curated rows from the Excel workbook using dynamic section headers."""
    if not xlsx_path.exists():
        return []
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb[wb.sheetnames[0]]

    col_map: dict[int, str] = {}
    rows: list[dict[str, str]] = []

    for r in range(1, ws.max_row + 1):
        vals = [str(ws.cell(r, c).value or "").strip() for c in range(1, ws.max_column + 1)]
        if any("Cita en norma APA" in v for v in vals):
            col_map = {}
            for idx, v in enumerate(vals):
                if not v:
                    continue
                key = normalize_header(v)
                if key:
                    col_map[idx] = key
            continue

        if not col_map:
            continue

        record: dict[str, str] = {col["key"]: "" for col in CANONICAL_COLUMNS}
        for idx, key in col_map.items():
            if idx < len(vals) and vals[idx]:
                record[key] = (record[key] + "\n" + vals[idx]) if record[key] else vals[idx]

        if not record["seccion"] and len(vals) > 1 and vals[1] and not vals[1].isdigit() and record["apa"]:
            record["seccion"] = vals[1]

        non_empty = sum(1 for v in record.values() if v)
        if not record["apa"] and non_empty < 2:
            continue
        if not record["apa"] and not record["tema"] and not record["conceptos"]:
            continue

        if not record["seccion"]:
            record["seccion"] = "Matriz curada"
        rows.append(record)

    return rows


def clean_text(txt: str) -> str:
    """Collapse excessive whitespace and hyphenation artifacts."""
    txt = re.sub(r"-\s*\n\s*", "", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def split_sentences(text: str, max_chars: int = 24000) -> list[str]:
    """Split text into clean sentences within a bounded window."""
    if not text:
        return []
    sample = clean_text(text[:max_chars])
    sents = RE_SENTENCE_SPLIT.split(sample)
    return [s.strip() for s in sents if 35 <= len(s.strip()) <= 520]


def pick_matching_sentences(
    sentences: list[str], pattern: re.Pattern[str], limit: int = 2, max_len: int = 480
) -> str:
    """Pick top matching sentences for a given analytical dimension."""
    hits: list[str] = []
    seen: set[str] = set()
    for s in sentences:
        if pattern.search(s):
            key = s[:60].lower()
            if key not in seen:
                seen.add(key)
                hits.append(s)
                if len(hits) >= limit:
                    break
    out = " ".join(hits)
    return (out[: max_len - 1] + "…") if len(out) > max_len else out


def extract_quotes(full_txt: str, sentences: list[str]) -> str:
    """Extract 1-2 verbatim quotes or high-signal excerpts from the full text."""
    # Prefer actual quoted passages inside full text
    quoted = re.findall(r"[«\"“]([^»\"”]{50,260})[»\"”]", full_txt[:30000])
    clean_q = []
    for q in quoted:
        cq = clean_text(q)
        if len(cq) >= 50 and "http" not in cq.lower():
            clean_q.append(f'"{cq}"')
        if len(clean_q) >= 2:
            break
    if clean_q:
        return " | ".join(clean_q)

    # Fallback: take analytical sentences from the middle/body of the text
    if len(sentences) >= 4:
        mid = sentences[len(sentences) // 3 : len(sentences) // 3 + 2]
        return " | ".join(f'"{s[:240]}"' for s in mid)
    if sentences:
        return f'"{sentences[0][:240]}"'
    return ""


def norm_doi(d: str) -> str:
    """Normalize a DOI by stripping URL prefixes and lowercasing."""
    s = (d or "").strip().lower()
    s = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", s)
    s = re.sub(r"^doi:\s*", "", s)
    return s.rstrip(".")


def load_fulltext_index() -> dict[str, str]:
    """Load extracted full text keyed by normalized DOI and filename."""
    corpus_texts: dict[str, str] = {}
    corpus_gz = ROOT / "data" / "corpus.csv.gz"
    if corpus_gz.exists():
        with gzip.open(corpus_gz, "rt", encoding="utf-8-sig", errors="replace") as f:
            for r in csv.DictReader(f):
                txt = (r.get("texto") or "").strip()
                if not txt:
                    continue
                doi = norm_doi(r.get("doi") or "")
                fn = (r.get("filename") or "").strip()
                if doi:
                    corpus_texts[doi] = txt
                if fn:
                    corpus_texts[fn] = txt

    for tf in glob.glob(str(ROOT / "docs" / "textos" / "*.txt")):
        fname = Path(tf).name
        if fname not in corpus_texts:
            try:
                content = Path(tf).read_text(encoding="utf-8", errors="replace").strip()
                if content:
                    corpus_texts[fname] = content
            except Exception:
                pass
    return corpus_texts


def build_scraped_row(rec: dict[str, str], full_txt: str) -> dict[str, str]:
    """Extract the 19 canonical analytical fields from a scraped record + full text."""
    title = (rec.get("title") or "").strip()
    abstract = (rec.get("abstract") or "").strip()
    keywords = (rec.get("keywords") or "").strip()
    search_term = (rec.get("search_term") or "").strip()
    origin = (rec.get("origin") or rec.get("source") or "").strip()
    year = (rec.get("publication_year") or "").strip()
    doc_type = (rec.get("document_type") or "").strip()
    rel_ev = (rec.get("relevance_evidence") or "").strip()

    has_full = bool(full_txt and len(full_txt) > max(len(abstract) + 100, 300))
    source_text = full_txt if has_full else abstract
    sentences = split_sentences(source_text)
    abs_sentences = split_sentences(abstract, max_chars=4000)

    cit = build_citation(rec)
    apa = plain_text(cit)
    if rec.get("doi"):
        apa = f"{apa} https://doi.org/{rec['doi'].strip()}"
    elif rec.get("url"):
        apa = f"{apa} {rec['url'].strip()}"

    lead = abs_sentences[0] if abs_sentences else (sentences[0] if sentences else "")
    tema = f"{title}. {lead}".strip() if lead else title
    if len(tema) > 460:
        tema = tema[:459] + "…"

    conceptos_sent = pick_matching_sentences(sentences, PATTERNS["conceptos"], limit=2, max_len=420)
    if keywords and conceptos_sent:
        conceptos = f"Ejes: {keywords}. {conceptos_sent}"
    else:
        conceptos = conceptos_sent or keywords or search_term

    aportes_dir = pick_matching_sentences(sentences, PATTERNS["aportes_dir"], limit=2, max_len=420)
    if not aportes_dir and rel_ev:
        aportes_dir = rel_ev[:420]

    aportes_est = []
    if origin:
        aportes_est.append(f"Fuente: {origin}" + (f" ({year})" if year else ""))
    if doc_type:
        aportes_est.append(f"Tipo: {doc_type}")
    if search_term:
        aportes_est.append(f"Línea de búsqueda: {search_term}")
    if rel_ev:
        aportes_est.append(rel_ev[:240])

    return {
        "seccion": "Corpus completo (PDF)" if has_full else "Corpus (resumen/metadatos)",
        "apa": apa,
        "tema": tema,
        "conceptos": conceptos[:480],
        "categorias": pick_matching_sentences(sentences, PATTERNS["categorias"]),
        "metodologia": pick_matching_sentences(sentences, PATTERNS["metodologia"]),
        "problema": pick_matching_sentences(abs_sentences + sentences, PATTERNS["problema"]),
        "epistemologia": pick_matching_sentences(sentences, PATTERNS["epistemologia"]),
        "contexto": pick_matching_sentences(sentences, PATTERNS["contexto"]),
        "muestra": pick_matching_sentences(sentences, PATTERNS["muestra"]),
        "aportes_dir": aportes_dir,
        "implicaciones": pick_matching_sentences(sentences, PATTERNS["implicaciones"]),
        "hallazgos": pick_matching_sentences(sentences, PATTERNS["hallazgos"]),
        "citas": extract_quotes(source_text, sentences),
        "discusion": pick_matching_sentences(sentences, PATTERNS["discusion"]),
        "limitaciones": pick_matching_sentences(sentences, PATTERNS["limitaciones"]),
        "futura": pick_matching_sentences(sentences, PATTERNS["futura"]),
        "palabras_clave": keywords or search_term,
        "aportes_estudio": " · ".join(aportes_est),
    }


def main() -> int:
    xlsx_path = ROOT / "data" / "matriz_analisis_textos.xlsx"
    master_path = ROOT / "data" / "master_records.csv"
    out_path = ROOT / "docs" / "matriz-data.json"

    curated_rows = parse_matriz_xlsx(xlsx_path)

    # Index curated DOIs and normalized titles to avoid duplicating manual entries
    seen_dois: set[str] = set()
    seen_titles: set[str] = set()
    for row in curated_rows:
        apa = row.get("apa", "")
        m_doi = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", apa)
        if m_doi:
            seen_dois.add(m_doi.group(0).lower().rstrip("."))
        # Also index normalized APA snippet for title overlap check
        seen_titles.add(norm_title(row.get("tema", "")))
        nt_apa = norm_title(apa)
        if nt_apa:
            seen_titles.add(nt_apa)

    corpus_texts = load_fulltext_index()

    scraped_rows: list[dict[str, str]] = []
    fulltext_hits = 0
    if master_path.exists():
        with master_path.open(encoding="utf-8-sig", errors="replace") as f:
            for rec in csv.DictReader(f):
                doi = norm_doi(rec.get("doi") or "")
                title = (rec.get("title") or "").strip()
                nt = norm_title(title)
                if doi and doi in seen_dois:
                    continue
                if nt and any(nt in st for st in seen_titles if len(nt) > 25):
                    continue

                fn = (rec.get("filename") or "").strip()
                full_txt = corpus_texts.get(doi) or corpus_texts.get(fn) or ""
                if not full_txt and doi:
                    # Also check sanitized DOI filename (e.g. 10.1007_s10833.pdf or .txt)
                    doi_fn = doi.replace("/", "_")
                    full_txt = corpus_texts.get(doi_fn + ".pdf") or corpus_texts.get(doi_fn + ".txt") or ""
                if full_txt:
                    fulltext_hits += 1
                scraped_rows.append(build_scraped_row(rec, full_txt))

    # Put full-text PDF rows first after curated rows, then metadata/abstract rows
    scraped_rows.sort(
        key=lambda r: (0 if r["seccion"] == "Corpus completo (PDF)" else 1)
    )
    all_rows = curated_rows + scraped_rows

    payload = {
        "title": "Matriz de Análisis de Textos",
        "total": len(all_rows),
        "curated_count": len(curated_rows),
        "fulltext_scraped_count": fulltext_hits,
        "scraped_total_count": len(scraped_rows),
        "columns": CANONICAL_COLUMNS,
        "rows": all_rows,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(
        f"Wrote {len(all_rows)} rows ({len(curated_rows)} curated + {len(scraped_rows)} scraped, "
        f"{fulltext_hits} with full PDF text) to {out_path} ({size_mb:.2f} MB)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
