#!/usr/bin/env python3
"""
generate_dashboard_three_columns.py

Genera un dashboard HTML de tres columnas a partir de data/master_records.csv.
El objetivo es que GitHub Pages muestre siempre todos los registros scrapeados,
incluidos CONICET Digital y otros repositorios, sin depender de archivos STM.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List


DATA_DIR = Path("data")
OUT_DIR = Path("docs")
MASTER_CSV = DATA_DIR / "master_records.csv"
OUT_HTML = OUT_DIR / "index.html"
NOJEKYLL = OUT_DIR / ".nojekyll"


def s(value: Any) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        print(f"No existe {path}. Se genera un dashboard vacío.")
        return []
    csv.field_size_limit(10_000_000)
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def normalize_key(value: Any) -> str:
    text = s(value).casefold()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def infer_source(row: Dict[str, Any]) -> str:
    source = s(row.get("source"))
    if source:
        return source

    url = s(row.get("url")).lower()
    origin = s(row.get("origin")).lower()
    openalex_id = s(row.get("openalex_id"))

    if "ri.conicet" in url or "conicet" in origin:
        return "CONICET Digital"
    if "repositorio.unsam" in url or "unsam" in origin:
        return "RIAA-UNSAM"
    if "sedici.unlp.edu.ar" in url or "sedici" in origin:
        return "SEDICI-UNLP"
    if openalex_id or "doi.org" in url or "dx.doi.org" in url:
        return "OpenAlex"
    return "Repositorio / Otro"


def infer_origin(row: Dict[str, Any]) -> str:
    origin = s(row.get("origin"))
    return origin or infer_source(row)


def short_authors(value: Any, limit: int = 3) -> str:
    authors = [a.strip() for a in s(value).split(";") if a.strip()]
    if not authors:
        return ""
    shown = "; ".join(authors[:limit])
    return shown + (" et al." if len(authors) > limit else "")


def split_keywords(value: Any, limit: int = 6) -> List[str]:
    raw = re.split(r"[;|,]", s(value))
    clean: List[str] = []
    seen = set()
    for item in raw:
        item = re.sub(r"\s+", " ", item).strip()
        key = normalize_key(item)
        if len(key) < 3 or key in seen:
            continue
        seen.add(key)
        clean.append(item)
        if len(clean) >= limit:
            break
    return clean


def build_url(row: Dict[str, Any]) -> str:
    url = s(row.get("url"))
    doi = s(row.get("doi"))
    if url:
        return url
    if doi:
        return f"https://doi.org/{doi}"
    return ""


def prepare_records(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    prepared: List[Dict[str, Any]] = []
    seen = set()

    for idx, row in enumerate(rows, start=1):
        title = s(row.get("title"))
        if not title:
            continue

        doi = s(row.get("doi"))
        record_id = s(row.get("record_id")) or doi or f"row-{idx}"
        source = infer_source(row)
        origin = infer_origin(row)
        year = s(row.get("publication_year"))
        url = build_url(row)

        dedup_key = normalize_key(doi or f"{title}::{year}::{origin}")
        if dedup_key and dedup_key in seen:
            continue
        seen.add(dedup_key)

        prepared.append(
            {
                "id": record_id,
                "title": title,
                "authors": short_authors(row.get("authors")),
                "authors_full": s(row.get("authors")),
                "origin": origin,
                "source": source,
                "year": year,
                "date": s(row.get("publication_date")),
                "doi": doi,
                "url": url,
                "keywords": split_keywords(row.get("keywords")),
                "abstract": s(row.get("abstract"))[:900],
                "search_term": s(row.get("search_term")),
                "document_type": s(row.get("document_type")),
                "pdf_url": s(row.get("pdf_url")),
                "first_seen_date": s(row.get("first_seen_date")),
            }
        )

    prepared.sort(key=lambda r: (safe_int(r["year"]), r["title"].casefold()), reverse=True)
    return prepared


def top_counts(records: List[Dict[str, Any]], field: str, limit: int | None = None) -> List[Dict[str, Any]]:
    counts = Counter(s(r.get(field)) or "Sin dato" for r in records)
    items = counts.most_common(limit)
    return [{"name": name, "count": count} for name, count in items]


def keyword_counts(records: List[Dict[str, Any]], limit: int = 40) -> List[Dict[str, Any]]:
    stop = {
        "school", "schools", "education", "educational", "management", "leadership",
        "gestión", "gestion", "escolar", "escuela", "educación", "educacion",
        "dirección", "direccion", "educativa", "educativo", "study", "research",
        "analysis", "article", "public", "policy", "política", "politica",
    }
    counter: Counter[str] = Counter()
    display: Dict[str, str] = {}
    for rec in records:
        for kw in rec.get("keywords", []):
            key = normalize_key(kw)
            if key and key not in stop:
                counter[key] += 1
                display.setdefault(key, kw)
    return [{"name": display[k], "count": c} for k, c in counter.most_common(limit)]


def build_payload(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    years = [safe_int(r["year"]) for r in records if safe_int(r["year"])]
    conicet_total = sum(1 for r in records if "conicet" in normalize_key(r.get("source")))
    return {
        "generated": date.today().strftime("%d/%m/%Y"),
        "records": records,
        "stats": {
            "total": len(records),
            "sources": len({r["source"] for r in records}),
            "origins": len({r["origin"] for r in records}),
            "conicet_total": conicet_total,
            "year_min": min(years) if years else "",
            "year_max": max(years) if years else "",
        },
        "sources": top_counts(records, "source"),
        "origins": top_counts(records, "origin", 300),
        "years": top_counts(records, "year"),
        "keywords": keyword_counts(records),
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Dashboard · Dirección escolar</title>
<style>
*{box-sizing:border-box}
:root{
  --bg:#090d16;--panel:#111827;--panel2:#0f172a;--line:#233047;
  --text:#e5e7eb;--muted:#94a3b8;--accent:#60a5fa;--accent2:#c084fc;
  --good:#5eead4;--warn:#fbbf24;--chip:#1e293b;--hover:#172554
}
body{margin:0;background:radial-gradient(circle at top left,#13203a 0,#090d16 45%,#05070c 100%);color:var(--text);font-family:Inter,Segoe UI,system-ui,sans-serif;min-height:100vh}
header{position:sticky;top:0;z-index:20;background:rgba(5,7,12,.92);backdrop-filter:blur(10px);border-bottom:1px solid var(--line);padding:14px 20px;display:flex;justify-content:space-between;gap:20px;align-items:center}
h1{font-size:1.15rem;margin:0;font-weight:900;letter-spacing:.02em;text-shadow:0 0 14px rgba(96,165,250,.75)}
.subtitle{font-size:.78rem;color:var(--muted);margin-top:3px}
.subtitle a{color:var(--accent);text-decoration:none}
.updated{font-size:.75rem;color:var(--muted);text-align:right}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;padding:14px 20px}
.kpi{background:linear-gradient(180deg,rgba(17,24,39,.96),rgba(15,23,42,.96));border:1px solid var(--line);border-radius:14px;padding:12px}
.kpi .n{font-size:1.45rem;font-weight:900;color:var(--accent)}
.kpi .l{font-size:.72rem;color:var(--muted);margin-top:2px}
.layout{display:grid;grid-template-columns:280px minmax(0,1fr) 340px;gap:14px;padding:0 20px 20px;height:calc(100vh - 142px);min-height:620px}
.panel{background:rgba(17,24,39,.94);border:1px solid var(--line);border-radius:16px;overflow:hidden;min-height:0}
.panel h2{font-size:.75rem;letter-spacing:.08em;text-transform:uppercase;color:#cbd5e1;margin:0;padding:12px 14px;border-bottom:1px solid var(--line);background:rgba(15,23,42,.92)}
.panel-body{padding:12px;overflow:auto;height:calc(100% - 43px)}
label{display:block;font-size:.72rem;color:var(--muted);margin:12px 0 6px}
input,select{width:100%;background:#0b1220;color:var(--text);border:1px solid var(--line);border-radius:10px;padding:9px 10px;outline:none}
input:focus,select:focus{border-color:var(--accent)}
button{background:#1e293b;color:var(--text);border:1px solid var(--line);border-radius:10px;padding:8px 10px;cursor:pointer}
button:hover{border-color:var(--accent);color:#bfdbfe}
button:disabled{opacity:.35;cursor:not-allowed}
.small{font-size:.72rem;color:var(--muted);line-height:1.45}
.source-row,.origin-row{margin:8px 0;padding:8px;border:1px solid rgba(35,48,71,.8);border-radius:12px;background:rgba(15,23,42,.7);cursor:pointer}
.source-row:hover,.origin-row:hover{background:rgba(23,37,84,.8)}
.row-top{display:flex;justify-content:space-between;gap:8px;font-size:.78rem}
.bar{height:5px;background:#0b1220;border-radius:99px;margin-top:7px;overflow:hidden}
.fill{height:100%;background:linear-gradient(90deg,var(--accent),var(--accent2))}
.main-head{display:flex;gap:10px;align-items:center;padding:12px;border-bottom:1px solid var(--line);background:rgba(15,23,42,.92)}
.main-head input{flex:1}
#count{white-space:nowrap;font-size:.78rem;color:var(--muted)}
#cards{height:calc(100% - 98px);overflow:auto;padding:12px}
.card{border:1px solid rgba(35,48,71,.85);background:linear-gradient(180deg,rgba(15,23,42,.94),rgba(12,18,31,.94));border-radius:14px;padding:12px;margin-bottom:10px}
.card a{color:#93c5fd;text-decoration:none;font-weight:800;line-height:1.35}
.card a:hover{text-decoration:underline}
.meta{font-size:.76rem;color:var(--muted);margin-top:6px;line-height:1.4}
.tags{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}
.tag{font-size:.68rem;color:#c4b5fd;background:rgba(88,28,135,.35);border:1px solid rgba(168,85,247,.35);border-radius:999px;padding:2px 7px}
.source-chip{color:#99f6e4;background:rgba(13,148,136,.18);border-color:rgba(45,212,191,.35)}
.pager{height:44px;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 12px;border-top:1px solid var(--line);background:rgba(15,23,42,.92)}
#pageinfo{font-size:.76rem;color:var(--muted)}
.keyword-cloud{display:flex;flex-wrap:wrap;gap:6px}
.kw{font-size:.72rem;border:1px solid rgba(96,165,250,.35);background:rgba(30,64,175,.2);border-radius:999px;padding:4px 8px;cursor:pointer}
.kw:hover{background:rgba(30,64,175,.45)}
.origin-list{max-height:270px;overflow:auto;margin-top:8px}
.empty{padding:30px;text-align:center;color:var(--muted)}
.notice{border:1px solid rgba(251,191,36,.35);background:rgba(120,53,15,.18);border-radius:12px;padding:10px;font-size:.73rem;color:#fde68a;margin-top:10px}
@media(max-width:1050px){
  .layout{grid-template-columns:1fr;height:auto}
  .panel{min-height:360px}
  .kpis{grid-template-columns:repeat(2,1fr)}
  header{position:static;display:block}
  .updated{text-align:left;margin-top:6px}
}
</style>
</head>
<body>
<header>
  <div>
    <h1>Dashboard · Dirección escolar</h1>
    <div class="subtitle">versión beta desarrollada por <a href="mailto:aguirre.elias.gonzalo@gmail.com">Elias Aguirre</a></div>
  </div>
  <div class="updated">Actualizado: <span id="generated"></span><br><span id="period"></span></div>
</header>

<section class="kpis">
  <div class="kpi"><div class="n" id="k_total">0</div><div class="l">publicaciones</div></div>
  <div class="kpi"><div class="n" id="k_sources">0</div><div class="l">fuentes</div></div>
  <div class="kpi"><div class="n" id="k_origins">0</div><div class="l">revistas / orígenes</div></div>
  <div class="kpi"><div class="n" id="k_conicet">0</div><div class="l">registros CONICET</div></div>
  <div class="kpi"><div class="n" id="k_period">—</div><div class="l">período</div></div>
</section>

<main class="layout">
  <aside class="panel">
    <h2>Filtros y control</h2>
    <div class="panel-body">
      <label for="sourceFilter">Fuente</label>
      <select id="sourceFilter"></select>

      <label for="yearFilter">Año</label>
      <select id="yearFilter"></select>

      <label for="sortFilter">Orden</label>
      <select id="sortFilter">
        <option value="year_desc">Más recientes primero</option>
        <option value="year_asc">Más antiguos primero</option>
        <option value="title_asc">Título A-Z</option>
        <option value="source_asc">Fuente A-Z</option>
      </select>

      <div class="notice">
        Este tablero se genera directamente desde <strong>data/master_records.csv</strong>. Si el CSV cambia, el workflow vuelve a crear esta página y actualiza el contador.
      </div>

      <label>Fuentes detectadas</label>
      <div id="sourceBars"></div>
    </div>
  </aside>

  <section class="panel">
    <div class="main-head">
      <input id="search" type="search" placeholder="Buscar por título, autor, revista, fuente, palabra clave o DOI...">
      <span id="count">0 resultados</span>
    </div>
    <div id="cards"></div>
    <div class="pager">
      <button id="prevBtn">← Anterior</button>
      <span id="pageinfo"></span>
      <button id="nextBtn">Siguiente →</button>
    </div>
  </section>

  <aside class="panel">
    <h2>Mapa de revistas y temas</h2>
    <div class="panel-body">
      <div class="small">
        Las revistas y repositorios se listan como orígenes. Al hacer clic se filtra la columna central.
      </div>

      <label>Palabras clave frecuentes</label>
      <div class="keyword-cloud" id="keywordCloud"></div>

      <label>Revistas / orígenes scrapeados</label>
      <input id="originSearch" type="search" placeholder="Filtrar origen...">
      <div class="origin-list" id="originList"></div>
    </div>
  </aside>
</main>

<script>
const DATA = __PAYLOAD__;
const state = {q:"", source:"", year:"", origin:"", kw:"", sort:"year_desc", page:1, pageSize:30};

const $ = id => document.getElementById(id);
const norm = v => String(v || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"");
const esc = v => String(v || "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
const fmt = n => Number(n || 0).toLocaleString("es-AR");

function init(){
  $("generated").textContent = DATA.generated;
  $("period").textContent = DATA.stats.year_min ? `${DATA.stats.year_min}–${DATA.stats.year_max}` : "sin período";
  $("k_total").textContent = fmt(DATA.stats.total);
  $("k_sources").textContent = fmt(DATA.stats.sources);
  $("k_origins").textContent = fmt(DATA.stats.origins);
  $("k_conicet").textContent = fmt(DATA.stats.conicet_total);
  $("k_period").textContent = DATA.stats.year_min ? `${DATA.stats.year_min}–${DATA.stats.year_max}` : "—";

  fillSelect("sourceFilter", DATA.sources.map(x=>x.name), "Todas las fuentes");
  const years = [...new Set(DATA.records.map(r=>r.year).filter(Boolean))].sort((a,b)=>Number(b)-Number(a));
  fillSelect("yearFilter", years, "Todos los años");

  renderSourceBars();
  renderKeywordCloud();
  renderOrigins();
  bind();
  render();
}

function fillSelect(id, values, first){
  const el = $(id);
  el.innerHTML = `<option value="">${esc(first)}</option>` + values.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join("");
}

function bind(){
  $("search").addEventListener("input", e => {state.q=e.target.value; state.page=1; render();});
  $("sourceFilter").addEventListener("change", e => {state.source=e.target.value; state.page=1; render();});
  $("yearFilter").addEventListener("change", e => {state.year=e.target.value; state.page=1; render();});
  $("sortFilter").addEventListener("change", e => {state.sort=e.target.value; state.page=1; render();});
  $("originSearch").addEventListener("input", renderOrigins);
  $("prevBtn").addEventListener("click", () => {state.page=Math.max(1,state.page-1); render();});
  $("nextBtn").addEventListener("click", () => {state.page += 1; render();});
}

function renderSourceBars(){
  const max = Math.max(1, ...DATA.sources.map(x=>x.count));
  $("sourceBars").innerHTML = DATA.sources.map(x => `
    <div class="source-row" onclick="filterSource('${esc(x.name)}')">
      <div class="row-top"><strong>${esc(x.name)}</strong><span>${fmt(x.count)}</span></div>
      <div class="bar"><div class="fill" style="width:${Math.max(3, x.count/max*100)}%"></div></div>
    </div>`).join("");
}

function renderKeywordCloud(){
  $("keywordCloud").innerHTML = DATA.keywords.map(k => `<button class="kw" onclick="filterKeyword('${esc(k.name)}')">${esc(k.name)} · ${fmt(k.count)}</button>`).join("");
}

function renderOrigins(){
  const q = norm($("originSearch").value);
  const items = DATA.origins.filter(x => !q || norm(x.name).includes(q));
  const max = Math.max(1, ...DATA.origins.map(x=>x.count));
  $("originList").innerHTML = items.map(x => `
    <div class="origin-row" onclick="filterOrigin('${esc(x.name)}')">
      <div class="row-top"><span>${esc(x.name)}</span><span>${fmt(x.count)}</span></div>
      <div class="bar"><div class="fill" style="width:${Math.max(3, x.count/max*100)}%"></div></div>
    </div>`).join("");
}

function filterSource(v){ state.source=v; $("sourceFilter").value=v; state.page=1; render(); }
function filterOrigin(v){ state.origin = state.origin === v ? "" : v; state.page=1; render(); }
function filterKeyword(v){ state.kw = state.kw === v ? "" : v; state.page=1; render(); }

function getFiltered(){
  const q = norm(state.q);
  const kw = norm(state.kw);
  let rows = DATA.records.filter(r => {
    if(state.source && r.source !== state.source) return false;
    if(state.year && r.year !== state.year) return false;
    if(state.origin && r.origin !== state.origin) return false;
    if(kw && !r.keywords.some(k => norm(k).includes(kw))) return false;
    if(!q) return true;
    const hay = [r.title,r.authors_full,r.authors,r.origin,r.source,r.year,r.doi,r.search_term,r.document_type,...(r.keywords||[])].join(" ");
    return norm(hay).includes(q);
  });

  rows = rows.slice();
  if(state.sort === "year_asc") rows.sort((a,b)=>(Number(a.year)||0)-(Number(b.year)||0));
  if(state.sort === "title_asc") rows.sort((a,b)=>a.title.localeCompare(b.title));
  if(state.sort === "source_asc") rows.sort((a,b)=>(a.source+a.title).localeCompare(b.source+b.title));
  if(state.sort === "year_desc") rows.sort((a,b)=>(Number(b.year)||0)-(Number(a.year)||0) || a.title.localeCompare(b.title));
  return rows;
}

function render(){
  const rows = getFiltered();
  const pages = Math.max(1, Math.ceil(rows.length/state.pageSize));
  state.page = Math.min(state.page, pages);
  const start = (state.page-1)*state.pageSize;
  const pageRows = rows.slice(start, start+state.pageSize);

  $("count").textContent = `${fmt(rows.length)} resultados`;
  $("cards").innerHTML = pageRows.length ? pageRows.map(card).join("") : `<div class="empty">Sin resultados para esta búsqueda.</div>`;
  $("pageinfo").textContent = `Página ${state.page} de ${pages}`;
  $("prevBtn").disabled = state.page <= 1;
  $("nextBtn").disabled = state.page >= pages;
}

function card(r){
  const title = esc(r.title);
  const href = r.url ? esc(r.url) : "#";
  const link = r.url ? `<a href="${href}" target="_blank" rel="noopener">${title}</a>` : `<strong>${title}</strong>`;
  const tags = [`<span class="tag source-chip">${esc(r.source || "Sin fuente")}</span>`]
    .concat((r.keywords||[]).map(k=>`<span class="tag">${esc(k)}</span>`)).join("");
  const abstract = r.abstract ? `<div class="meta">${esc(r.abstract)}</div>` : "";
  return `
    <article class="card">
      ${link}
      <div class="meta">${esc(r.authors || "Autoría sin dato")} · ${esc(r.origin || "Origen sin dato")} · ${esc(r.year || "s/f")}</div>
      ${abstract}
      <div class="tags">${tags}</div>
    </article>`;
}

init();
</script>
</body>
</html>
"""


def write_dashboard() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = prepare_records(read_csv(MASTER_CSV))
    payload = build_payload(records)
    html = HTML_TEMPLATE.replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False))
    OUT_HTML.write_text(html, encoding="utf-8")
    NOJEKYLL.write_text("", encoding="utf-8")
    print(f"Dashboard generado: {OUT_HTML} ({len(records)} registros)")


if __name__ == "__main__":
    write_dashboard()
