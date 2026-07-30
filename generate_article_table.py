#!/usr/bin/env python3
"""Genera una vista de trabajo para buscar y revisar articulos validados."""
from __future__ import annotations

import csv
import json
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
aside{{border:1px solid var(--line);background:var(--panel);border-radius:8px;height:calc(100vh - 142px);overflow:auto;padding:14px}} aside h2{{font-size:1rem;margin:0 0 8px}} .field{{border-top:1px solid #242b35;padding:10px 0}} .label{{color:var(--muted);font-size:.74rem;text-transform:uppercase;margin-bottom:4px}} .value{{white-space:pre-wrap;line-height:1.42}} .actions{{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 4px}} .pager{{display:flex;align-items:center;gap:8px;margin-top:10px}} .pager span{{color:var(--muted)}}
@media(max-width:980px){{.tools{{grid-template-columns:1fr 1fr}} main{{grid-template-columns:1fr}} aside{{height:auto}} .table-wrap{{height:62vh}}}}
</style>
</head>
<body>
<header>
  <div class="top">
    <div>
      <h1>Articulos compilados</h1>
      <div class="meta">SCRAPEADORACADEMICO · __TOTAL__ registros validados</div>
    </div>
    <a href="index.html">Volver al dashboard</a>
  </div>
  <div class="tools">
    <input id="q" placeholder="Buscar en titulo, autor, resumen, palabras clave, DOI, fuente..." autofocus>
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
<script>
const ARTICLES = __DATA__;
const PAGE_SIZE = 100;
let filtered = [...ARTICLES], page = 0, selected = null;
const $ = id => document.getElementById(id);
function norm(v){{return (v||"").toString().toLowerCase().normalize("NFD").replace(/[\\u0300-\\u036f]/g,"")}}
function unique(key){{return [...new Set(ARTICLES.map(a=>a[key]).filter(Boolean))].sort((a,b)=>a.localeCompare(b))}}
function fillSelect(id,key){{for(const v of unique(key)){{const o=document.createElement("option");o.value=v;o.textContent=v;$(id).appendChild(o)}}}}
fillSelect("source","source"); fillSelect("year","publication_year");
function corpusLabel(a){{return a.text_excerpt ? "con texto" : "sin texto"}}
function sortRows(rows){{const mode=$("sort").value; rows.sort((a,b)=>{{if(mode==="year_desc")return (b.publication_year||"").localeCompare(a.publication_year||""); if(mode==="score_desc")return (+b.relevance_score||0)-(+a.relevance_score||0); if(mode==="title")return a.title.localeCompare(b.title); return ((b.first_seen_date+b.publication_date+b.title).localeCompare(a.first_seen_date+a.publication_date+a.title));}})}}
function applyFilters(){{const q=norm($("q").value), src=$("source").value, yr=$("year").value, corp=$("corpus").value; filtered=ARTICLES.filter(a=>{{if(src&&a.source!==src)return false; if(yr&&a.publication_year!==yr)return false; if(corp&&corpusLabel(a)!==corp)return false; if(!q)return true; return norm(Object.values(a).join(" ")).includes(q);}}); sortRows(filtered); page=0; render();}}
function render(){{const tbody=$("rows"); tbody.innerHTML=""; const start=page*PAGE_SIZE; const rows=filtered.slice(start,start+PAGE_SIZE); for(const a of rows){{const tr=document.createElement("tr"); if(selected===a.record_id)tr.className="active"; tr.innerHTML=`<td><div class="title">${escapeHtml(a.title||"Sin titulo")}</div><div class="small">${escapeHtml((a.abstract||"").slice(0,180))}</div></td><td>${escapeHtml(shortAuthors(a.authors))}</td><td>${escapeHtml(a.publication_year||"")}</td><td>${escapeHtml(a.source||"")}</td><td>${escapeHtml(a.relevance_score||"")}<div class="small">${escapeHtml(a.relevance_reason||"")}</div></td><td class="${a.text_excerpt?'ok':'warn'}">${corpusLabel(a)}</td><td>${escapeHtml(a.topic||"")}</td>`; tr.onclick=()=>showDetail(a); tbody.appendChild(tr);}} $("page").textContent=`${filtered.length.toLocaleString()} resultados · página ${page+1} de ${Math.max(1,Math.ceil(filtered.length/PAGE_SIZE))}`; $("prev").disabled=page===0; $("next").disabled=(page+1)*PAGE_SIZE>=filtered.length;}}
function showDetail(a){{selected=a.record_id; $("detail").innerHTML=`<h2>${escapeHtml(a.title||"Sin titulo")}</h2><div class="actions">${a.url?`<a class="pill" target="_blank" rel="noopener" href="${escapeAttr(a.url)}">Abrir fuente</a>`:""}${a.pdf_url?`<a class="pill" target="_blank" rel="noopener" href="${escapeAttr(a.pdf_url)}">Abrir PDF</a>`:""}${a.doi?`<a class="pill" target="_blank" rel="noopener" href="https://doi.org/${escapeAttr(a.doi)}">DOI</a>`:""}</div>${field("Autores",a.authors)}${field("Año / fecha",`${a.publication_year||""} ${a.publication_date||""}`)}${field("Fuente / origen",`${a.source||""} · ${a.origin||""}`)}${field("Resumen",a.abstract)}${field("Palabras clave",a.keywords)}${field("Pertinencia",`${a.relevance_status||""} · score ${a.relevance_score||""}\\n${a.relevance_reason||""}\\n${a.relevance_evidence||""}`)}${field("Corpus",`${corpusLabel(a)} · paginas ${a.corpus_pages||""}\\n${a.text_excerpt||""}`)}${field("Tópico STM",`${a.topic||""} ${a.topic_weight||""}`)}${field("Identificadores",`record_id: ${a.record_id||""}\\nDOI: ${a.doi||""}`)}`; render();}}
function field(label,value){{return value?`<div class="field"><div class="label">${label}</div><div class="value">${escapeHtml(value)}</div></div>`:""}}
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
    html = html.replace("__TOTAL__", f"{total:,}").replace("__DATA__", data_json)

    (OUT_DIR / "articulos.html").write_text(html, encoding="utf-8")
    print(f"Vista de articulos generada: docs/articulos.html ({total:,} registros)")


if __name__ == "__main__":
    main()
