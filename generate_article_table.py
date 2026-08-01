#!/usr/bin/env python3
"""Genera una vista de trabajo para buscar y revisar articulos validados."""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path("data")
OUT_DIR = Path("docs")
OUT_DIR.mkdir(exist_ok=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    csv.field_size_limit(20_000_000)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def s(value: object) -> str:
    return str(value or "").strip()


def normalize_search_text(value: object) -> str:
    """Normaliza texto igual que el buscador del navegador."""
    decomposed = unicodedata.normalize("NFKD", s(value).lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def search_tokens(value: object) -> set[str]:
    """Extrae palabras indexables; omite números y tokens OCR desmesurados."""
    normalized = normalize_search_text(value)
    return {
        token
        for token in re.findall(r"[a-z0-9]{2,40}", normalized)
        if any("a" <= char <= "z" for char in token)
    }


def build_fulltext_index(
    articles: list[dict[str, str]], corpus: list[dict[str, str]]
) -> tuple[dict[str, list[int]], int]:
    """Crea un índice palabra -> artículos sin duplicar el cuerpo en el HTML."""
    article_by_doi = {
        s(article.get("doi")).lower(): index
        for index, article in enumerate(articles)
        if s(article.get("doi"))
    }
    postings: dict[str, set[int]] = defaultdict(set)
    indexed_documents: set[int] = set()

    for row in corpus:
        text = s(row.get("texto"))
        article_index = article_by_doi.get(s(row.get("doi")).lower())
        if article_index is None or not text:
            continue
        indexed_documents.add(article_index)
        for token in search_tokens(text):
            postings[token].add(article_index)

    compact_index = {
        token: sorted(article_indexes)
        for token, article_indexes in sorted(postings.items())
    }
    return compact_index, len(indexed_documents)


def main() -> None:
    records = read_csv(DATA_DIR / "master_records.csv")
    corpus = read_csv(DATA_DIR / "corpus.csv")
    doc_topics = read_csv(Path("output") / "document_topics.csv")

    corpus_by_doi = {s(row.get("doi")).lower(): row for row in corpus if s(row.get("doi"))}
    topic_by_doi = {s(row.get("doi")).lower(): row for row in doc_topics if s(row.get("doi"))}

    articles: list[dict[str, str]] = []
    for row in records:
        doi = s(row.get("doi"))
        doi_key = doi.lower()
        corpus_row = corpus_by_doi.get(doi_key, {})
        topic_row = topic_by_doi.get(doi_key, {})
        full_text = s(corpus_row.get("texto"))
        articles.append(
            {
                "record_id": s(row.get("record_id")),
                "first_seen_date": s(row.get("first_seen_date")),
                "source": s(row.get("source")),
                "origin": s(row.get("origin")),
                "document_type": s(row.get("document_type")),
                "authors": s(row.get("authors")),
                "title": s(row.get("title")),
                "abstract": s(row.get("abstract")),
                "keywords": s(row.get("keywords")),
                "publication_year": s(row.get("publication_year")),
                "publication_date": s(row.get("publication_date")),
                "doi": doi,
                "url": s(row.get("url")),
                "pdf_url": s(row.get("pdf_url")),
                "relevance_status": s(row.get("relevance_status")),
                "relevance_score": s(row.get("relevance_score")),
                "relevance_reason": s(row.get("relevance_reason")),
                "relevance_evidence": s(row.get("relevance_evidence")),
                "second_review_status": s(row.get("second_review_status")),
                "second_review_reason": s(row.get("second_review_reason")),
                "corpus_status": s(corpus_row.get("status")) or ("con texto" if full_text else "sin texto"),
                "corpus_pages": s(corpus_row.get("paginas")),
                "topic": s(topic_row.get("topico")),
                "topic_weight": s(topic_row.get("proporcion")),
                "text_excerpt": full_text[:1200],
            }
        )

    articles.sort(
        key=lambda item: (
            item["first_seen_date"],
            item["publication_date"],
            item["publication_year"],
            item["title"],
        ),
        reverse=True,
    )

    fulltext_index, indexed_documents = build_fulltext_index(articles, corpus)
    fulltext_meta = {"documents": indexed_documents, "terms": len(fulltext_index)}
    index_javascript = (
        "window.FULLTEXT_SEARCH_INDEX="
        + json.dumps(fulltext_index, ensure_ascii=False, separators=(",", ":"))
        + ";\nwindow.FULLTEXT_SEARCH_META="
        + json.dumps(fulltext_meta, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )

    data_json = json.dumps(articles, ensure_ascii=False)
    total = len(articles)

    html = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Articulos | SCRAPEADORACADEMICO</title>
<style>
:root{{--bg:#0d1117;--panel:#161b22;--line:#30363d;--text:#e6edf3;--muted:#8b949e;--blue:#58a6ff;--green:#3fb950;--yellow:#d29922}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font-family:Segoe UI,Arial,sans-serif;font-size:14px}}
header{{position:sticky;top:0;z-index:5;background:#0d1117;border-bottom:1px solid var(--line);padding:14px 18px}}
.top{{display:flex;align-items:center;gap:12px;justify-content:space-between}} h1{{margin:0;font-size:1.25rem;letter-spacing:.02em}} a{{color:var(--blue);text-decoration:none}} a:hover{{text-decoration:underline}}
.tools{{display:grid;grid-template-columns:minmax(220px,1.7fr) repeat(4,minmax(120px,.6fr));gap:8px;margin-top:12px}}
input,select,button{{background:#0d1117;border:1px solid var(--line);color:var(--text);border-radius:6px;padding:8px 10px;font:inherit}} input:focus,select:focus{{outline:none;border-color:var(--blue)}} button{{cursor:pointer}} button.primary{{background:#1f6feb;border-color:#1f6feb}}
.meta{{color:var(--muted);font-size:.86rem}} main{{display:grid;grid-template-columns:minmax(0,1fr) 390px;gap:12px;padding:12px 18px}}
.table-wrap{{border:1px solid var(--line);background:var(--panel);height:calc(100vh - 142px);overflow:auto;border-radius:8px}}
table{{border-collapse:collapse;width:100%;min-width:1180px}} th,td{{border-bottom:1px solid #242b35;padding:9px 10px;vertical-align:top;text-align:left}} th{{position:sticky;top:0;background:#111820;color:#c9d1d9;font-size:.78rem;text-transform:uppercase}} tr{{cursor:pointer}} tr:hover td,tr.active td{{background:#1c2530}}
.title{{font-weight:650;color:#fff}} .small{{color:var(--muted);font-size:.82rem;margin-top:3px;line-height:1.35}} .pill{{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:2px 7px;margin:2px;color:#c9d1d9;font-size:.78rem}} .ok{{color:var(--green)}} .warn{{color:var(--yellow)}}
.text-hit{{display:inline-block;margin-top:5px;border:1px solid #1f6feb;border-radius:999px;padding:2px 7px;color:#79c0ff;font-size:.75rem}}
mark{{background:#ffd33d;color:#111827;border-radius:3px;padding:0 2px;box-shadow:0 0 0 1px rgba(255,211,61,.2)}}
aside{{border:1px solid var(--line);background:var(--panel);border-radius:8px;height:calc(100vh - 142px);overflow:auto;padding:14px}} aside h2{{font-size:1rem;margin:0 0 8px}} .field{{border-top:1px solid #242b35;padding:10px 0}} .label{{color:var(--muted);font-size:.74rem;text-transform:uppercase;margin-bottom:4px}} .value{{white-space:pre-wrap;line-height:1.42}} .actions{{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 4px}} .pager{{display:flex;align-items:center;gap:8px;margin-top:10px}} .pager span{{color:var(--muted)}}
@media(max-width:980px){{.tools{{grid-template-columns:1fr 1fr}} main{{grid-template-columns:1fr}} aside{{height:auto}} .table-wrap{{height:62vh}}}}
</style>
</head>
<body>
<header>
  <div class="top">
    <div>
      <h1>Articulos compilados</h1>
      <div class="meta">SCRAPEADORACADEMICO · __TOTAL__ registros validados · texto completo indexado en __INDEXED__ artículos</div>
    </div>
    <a href="index.html">Volver al dashboard</a>
  </div>
  <div class="tools">
    <input id="q" placeholder="Buscar en título, autor, resumen, palabras clave o texto completo..." aria-label="Buscar también dentro del texto extraído de los PDF" autofocus>
    <select id="source"><option value="">Todas las fuentes</option></select>
    <select id="year"><option value="">Todos los años</option></select>
    <select id="corpus"><option value="">Corpus: todos</option><option value="con texto">Con texto</option><option value="sin texto">Sin texto</option></select>
    <select id="sort"><option value="recent">Más recientes</option><option value="year_desc">Año desc.</option><option value="score_desc">Pertinencia</option><option value="title">Título</option></select>
  </div>
</header>
<main>
  <section>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Titulo</th><th>Autores</th><th>Año</th><th>Fuente</th><th>Pertinencia</th><th>Corpus</th><th>Tópico</th></tr></thead>
        <tbody id="rows"></tbody>
      </table>
    </div>
    <div class="pager">
      <button id="prev">Anterior</button><span id="page"></span><button id="next">Siguiente</button>
    </div>
  </section>
  <aside id="detail"><h2>Seleccioná un artículo</h2><div class="meta">El detalle aparece acá para revisar la ficha completa sin salir de la tabla.</div></aside>
</main>
<script src="fulltext_search_index.js"></script>
<script>
const ARTICLES = __DATA__;
const FULLTEXT_INDEX = window.FULLTEXT_SEARCH_INDEX || {{}};
const FULLTEXT_META = window.FULLTEXT_SEARCH_META || {{documents:0,terms:0}};
const PAGE_SIZE = 100;
let filtered = [...ARTICLES], page = 0, selected = null, fullTextOnlyMatches = new Set();
const $ = id => document.getElementById(id);
function norm(v){{return (v||"").toString().toLowerCase().normalize("NFD").replace(/[\\u0300-\\u036f]/g,"")}}
function queryTokens(v){{return [...new Set(norm(v).match(/[a-z0-9]{{2,40}}/g)||[])].filter(token=>/[a-z]/.test(token))}}
function fullTextMatches(q){{const tokens=queryTokens(q); if(!tokens.length)return new Set(); let matches=null; for(const token of tokens){{if(!Object.prototype.hasOwnProperty.call(FULLTEXT_INDEX,token))return new Set(); const posting=new Set(FULLTEXT_INDEX[token]); matches=matches===null?posting:new Set([...matches].filter(index=>posting.has(index))); if(!matches.size)return matches;}} return matches||new Set();}}
function metadataText(a){{return norm([a.title,a.authors,a.abstract,a.keywords,a.doi,a.source,a.origin,a.publication_year,a.relevance_reason,a.relevance_evidence].join(" "))}}
function accentPattern(token){{const accents={{a:"[aáàäâã]",e:"[eéèëê]",i:"[iíìïî]",o:"[oóòöôõ]",u:"[uúùüû]",n:"[nñ]",c:"[cç]"}}; return [...token].map(char=>accents[char]||char).join("")}}
function highlightHtml(value){{const text=(value||"").toString(), tokens=queryTokens($("q").value).sort((a,b)=>b.length-a.length); if(!tokens.length)return escapeHtml(text); const expression=new RegExp(`(${{tokens.map(accentPattern).join("|")}})`,"giu"); return text.split(expression).map((part,index)=>index%2?`<mark>${{escapeHtml(part)}}</mark>`:escapeHtml(part)).join("")}}
function unique(key){{return [...new Set(ARTICLES.map(a=>a[key]).filter(Boolean))].sort((a,b)=>a.localeCompare(b))}}
function fillSelect(id,key){{for(const v of unique(key)){{const o=document.createElement("option");o.value=v;o.textContent=v;$(id).appendChild(o)}}}}
fillSelect("source","source"); fillSelect("year","publication_year");
function corpusLabel(a){{return a.text_excerpt ? "con texto" : "sin texto"}}
function sortRows(rows){{const mode=$("sort").value; rows.sort((a,b)=>{{if(mode==="year_desc")return (b.publication_year||"").localeCompare(a.publication_year||""); if(mode==="score_desc")return (+b.relevance_score||0)-(+a.relevance_score||0); if(mode==="title")return a.title.localeCompare(b.title); return ((b.first_seen_date+b.publication_date+b.title).localeCompare(a.first_seen_date+a.publication_date+a.title));}})}}
function applyFilters(){{const rawQuery=$("q").value, q=norm(rawQuery), src=$("source").value, yr=$("year").value, corp=$("corpus").value, textMatches=fullTextMatches(rawQuery); fullTextOnlyMatches=new Set(); filtered=ARTICLES.filter((a,index)=>{{if(src&&a.source!==src)return false; if(yr&&a.publication_year!==yr)return false; if(corp&&corpusLabel(a)!==corp)return false; if(!q)return true; const metadataMatch=metadataText(a).includes(q); const textMatch=textMatches.has(index); if(textMatch&&!metadataMatch)fullTextOnlyMatches.add(a.record_id); return metadataMatch||textMatch;}}); sortRows(filtered); page=0; render();}}
function render(){{const tbody=$("rows"); tbody.innerHTML=""; const start=page*PAGE_SIZE; const rows=filtered.slice(start,start+PAGE_SIZE); for(const a of rows){{const tr=document.createElement("tr"); if(selected===a.record_id)tr.className="active"; const hit=fullTextOnlyMatches.has(a.record_id)?`<div class="text-hit">Coincidencia en texto completo: <mark>${escapeHtml($("q").value.trim())}</mark></div>`:""; tr.innerHTML=`<td><div class="title">${highlightHtml(a.title||"Sin titulo")}</div><div class="small">${highlightHtml((a.abstract||"").slice(0,180))}</div>${hit}</td><td>${highlightHtml(shortAuthors(a.authors))}</td><td>${highlightHtml(a.publication_year||"")}</td><td>${highlightHtml(a.source||"")}</td><td>${escapeHtml(a.relevance_score||"")}<div class="small">${highlightHtml(a.relevance_reason||"")}</div></td><td class="${a.text_excerpt?'ok':'warn'}">${corpusLabel(a)}</td><td>${highlightHtml(a.topic||"")}</td>`; tr.onclick=()=>showDetail(a); tbody.appendChild(tr);}} $("page").textContent=`${filtered.length.toLocaleString()} resultados · página ${page+1} de ${Math.max(1,Math.ceil(filtered.length/PAGE_SIZE))}`; $("prev").disabled=page===0; $("next").disabled=(page+1)*PAGE_SIZE>=filtered.length;}}
function showDetail(a){{selected=a.record_id; $("detail").innerHTML=`<h2>${escapeHtml(a.title||"Sin titulo")}</h2><div class="actions">${a.url?`<a class="pill" target="_blank" rel="noopener" href="${escapeAttr(a.url)}">Abrir fuente</a>`:""}${a.pdf_url?`<a class="pill" target="_blank" rel="noopener" href="${escapeAttr(a.pdf_url)}">Abrir PDF</a>`:""}${a.doi?`<a class="pill" target="_blank" rel="noopener" href="https://doi.org/${escapeAttr(a.doi)}">DOI</a>`:""}</div>${field("Autores",a.authors)}${field("Año / fecha",`${a.publication_year||""} ${a.publication_date||""}`)}${field("Fuente / origen",`${a.source||""} · ${a.origin||""}`)}${field("Resumen",a.abstract)}${field("Palabras clave",a.keywords)}${field("Pertinencia",`${a.relevance_status||""} · score ${a.relevance_score||""}\\n${a.relevance_reason||""}\\n${a.relevance_evidence||""}`)}${field("Corpus",`${corpusLabel(a)} · paginas ${a.corpus_pages||""}\\n${a.text_excerpt||""}`)}${field("Tópico STM",`${a.topic||""} ${a.topic_weight||""}`)}${field("Identificadores",`record_id: ${a.record_id||""}\\nDOI: ${a.doi||""}`)}`; render();}}
function field(label,value){{return value?`<div class="field"><div class="label">${label}</div><div class="value">${highlightHtml(value)}</div></div>`:""}}
function shortAuthors(v){{const parts=(v||"").split(";").map(x=>x.trim()).filter(Boolean); return parts.length>3?parts.slice(0,3).join("; ")+" et al.":parts.join("; ")}}
function escapeHtml(v){{return (v||"").toString().replace(/[&<>"']/g,m=>({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[m]))}}
function escapeAttr(v){{return escapeHtml(v).replace(/"/g,"&quot;")}}
$("q").oninput=applyFilters; $("source").onchange=applyFilters; $("year").onchange=applyFilters; $("corpus").onchange=applyFilters; $("sort").onchange=applyFilters;
$("prev").onclick=()=>{{if(page>0){{page--;render()}}}}; $("next").onclick=()=>{{if((page+1)*PAGE_SIZE<filtered.length){{page++;render()}}}};
applyFilters();
</script>
</body>
</html>"""
    # The template keeps doubled braces so CSS and JavaScript can be edited
    # safely alongside template-literal expressions. Convert them before
    # injecting article JSON; otherwise the generated page contains invalid
    # CSS and JavaScript (for example, `function render(){{ ... }}`).
    html = html.replace("{{", "{").replace("}}", "}")
    html = (
        html.replace("__TOTAL__", f"{total:,}")
        .replace("__INDEXED__", f"{indexed_documents:,}")
        .replace("__DATA__", data_json)
    )

    (OUT_DIR / "articulos.html").write_text(html, encoding="utf-8")
    (OUT_DIR / "fulltext_search_index.js").write_text(index_javascript, encoding="utf-8")
    print(
        "Vista de articulos generada: docs/articulos.html "
        f"({total:,} registros; {indexed_documents:,} con texto completo indexado)"
    )


if __name__ == "__main__":
    main()
