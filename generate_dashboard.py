#!/usr/bin/env python3
"""
generate_dashboard.py
Dashboard interactivo con:
1. Red de similitud semántica estilo Connected Papers (D3 force-directed)
2. Tópicos STM clickeables con lista de artículos del tópico
3. Lista completa paginada (50/página) con buscador por título/autor
"""

import csv, json, re, itertools
from pathlib import Path
from datetime import date
from collections import defaultdict

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

# ── Cargar datos ──────────────────────────────────────────────────────────────

records    = read_csv("data/master_records.csv")
corpus     = read_csv("data/corpus.csv")
topicos    = read_csv("output/tabla_topicos.csv")
doc_topics = read_csv("output/document_topics.csv")

print(f"Records: {len(records)} | Corpus: {len(corpus)} | Topicos: {len(topicos)} | Doc-topics: {len(doc_topics)}")

# ── Colores por tópico ────────────────────────────────────────────────────────

topic_colors = {}
for i, t in enumerate(topicos):
    tid = s(t.get("topico", str(i + 1)))
    topic_colors[tid] = s(t.get("color", PALETA[i % len(PALETA)]))

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

network_papers = []
for i, cp in enumerate(corpus):
    doi   = s(cp.get("doi", ""))
    rec   = doi_to_record.get(doi, cp)
    title = s(rec.get("title", "") or cp.get("titulo", ""))
    if not title:
        continue
    kws_raw = s(rec.get("keywords", "") or cp.get("keywords", ""))
    kws = [k.strip().lower() for k in kws_raw.split(";")
           if k.strip() and len(k.strip()) > 3 and k.strip().lower() not in KW_STOPS]
    url = s(rec.get("url", "") or cp.get("url", ""))
    if not url and doi:
        url = f"https://doi.org/{doi}"
    tid   = doi_to_topic.get(doi, "")
    color = topic_colors.get(tid, "#484F58")
    autores   = s(rec.get("authors", "") or cp.get("autores", ""))
    auth_list = [a.strip() for a in autores.split(";") if a.strip()]
    auth_short = "; ".join(auth_list[:2]) + (" et al." if len(auth_list) > 2 else "")
    network_papers.append({
        "idx":     i,
        "title":   title[:70] + ("..." if len(title) > 70 else ""),
        "authors": auth_short,
        "year":    s(rec.get("publication_year", "") or cp.get("anio", "")),
        "url":     url,
        "topic":   tid,
        "color":   color,
        "kws":     kws[:12],
        "degree":  0
    })

# Construir índice keyword → papers
kw_index = defaultdict(list)
for i, p in enumerate(network_papers):
    for kw in p["kws"]:
        kw_index[kw].append(i)

# Contar keywords compartidas
edge_weights = defaultdict(int)
for kw, paper_ids in kw_index.items():
    if 2 <= len(paper_ids) <= 40:
        for a, b in itertools.combinations(paper_ids, 2):
            edge_weights[(min(a, b), max(a, b))] += 1

# Filtrar aristas fuertes
strong_edges = sorted(
    [(a, b, w) for (a, b), w in edge_weights.items() if w >= 2],
    key=lambda x: -x[2]
)[:2500]

connected = set()
for a, b, _ in strong_edges:
    connected.add(a)
    connected.add(b)

old_to_new = {old: new for new, old in enumerate(sorted(connected))}
nodes = [network_papers[i] for i in sorted(connected)]

for a, b, _ in strong_edges:
    if a in old_to_new and b in old_to_new:
        nodes[old_to_new[a]]["degree"] += 1
        nodes[old_to_new[b]]["degree"] += 1

MAX_NODES = 400
if len(nodes) > MAX_NODES:
    top_idx = sorted(range(len(nodes)), key=lambda i: -nodes[i]["degree"])[:MAX_NODES]
    keep    = set(top_idx)
    remap   = {old: new for new, old in enumerate(sorted(keep))}
    nodes   = [nodes[i] for i in sorted(keep)]
    strong_edges = [
        (remap[old_to_new[a]], remap[old_to_new[b]], w)
        for a, b, w in strong_edges
        if old_to_new.get(a) in keep and old_to_new.get(b) in keep
    ]
    edges = [{"source": a, "target": b, "weight": w} for a, b, w in strong_edges]
else:
    edges = [{"source": old_to_new[a], "target": old_to_new[b], "weight": w}
             for a, b, w in strong_edges if a in old_to_new and b in old_to_new]

print(f"Red: {len(nodes)} nodos, {len(edges)} aristas")

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
    all_articles.append({
        "titulo":  title,
        "autores": auth_short,
        "revista": s(r.get("origin", "")),
        "anio":    s(r.get("publication_year", "")),
        "url":     url,
        "kws":     kws,
    })

all_articles.sort(key=lambda x: safe_int(x["anio"], 0), reverse=True)

# ── Estadísticas ──────────────────────────────────────────────────────────────

total  = len(records)
anios  = [safe_int(r.get("publication_year", 0)) for r in records if r.get("publication_year")]
anio_min = min(anios) if anios else 2020
anio_max = max(anios) if anios else 2026

# ── JSON ──────────────────────────────────────────────────────────────────────

nodes_json   = json.dumps(nodes, ensure_ascii=False)
edges_json   = json.dumps(edges, ensure_ascii=False)
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
header{background:var(--surface);border-bottom:1px solid var(--border);padding:12px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
header h1{font-size:1.1em;color:#E6EDF3;font-weight:700}
header h1 span{color:var(--accent)}
.stamp{font-size:.72em;color:var(--dim)}
.kpis{display:flex;background:var(--surface);border-bottom:1px solid var(--border)}
.kpi{flex:1;text-align:center;padding:10px 8px;border-right:1px solid var(--border)}
.kpi:last-child{border-right:none}
.kpi-n{font-size:1.5em;font-weight:700;color:var(--accent)}
.kpi-l{font-size:.68em;color:var(--muted);margin-top:2px}
.main-grid{display:grid;grid-template-columns:1fr 360px;height:calc(55vh);overflow:hidden;border-bottom:1px solid var(--border)}
.net-panel{display:flex;flex-direction:column;border-right:1px solid var(--border)}
.panel-head{padding:8px 14px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
.panel-head h2{font-size:.78em;font-weight:600;color:#E6EDF3;text-transform:uppercase;letter-spacing:.06em}
.badge{background:var(--accent);color:#0D1117;border-radius:20px;padding:2px 8px;font-size:.65em;font-weight:700}
#net-svg{flex:1;width:100%;cursor:grab}
#net-svg:active{cursor:grabbing}
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
@media(max-width:900px){.main-grid{grid-template-columns:1fr}.topics-panel{display:none}}
</style>
</head>
<body>

<header>
  <h1>Dashboard &middot; <span>Direccion y Gestion Escolar</span></h1>
  <span class="stamp">Actualizado: """ + date.today().strftime('%d/%m/%Y') + f""" &middot; {anio_min}&ndash;{anio_max}</span>
</header>

<div class="kpis">
  <div class="kpi"><div class="kpi-n">{total:,}</div><div class="kpi-l">Publicaciones</div></div>
  <div class="kpi"><div class="kpi-n">{n_tops}</div><div class="kpi-l">Topicos STM</div></div>
  <div class="kpi"><div class="kpi-n">{n_nodes}</div><div class="kpi-l">Nodos en red</div></div>
  <div class="kpi"><div class="kpi-n">{n_edges}</div><div class="kpi-l">Conexiones</div></div>
  <div class="kpi"><div class="kpi-n">{anio_min}&ndash;{anio_max}</div><div class="kpi-l">Periodo</div></div>
</div>

<div class="main-grid">
  <div class="net-panel">
    <div class="panel-head">
      <h2>Red de similitud semantica</h2>
      <span class="badge">Keywords compartidas · color = topico STM</span>
    </div>
    <svg id="net-svg"></svg>
  </div>
  <div class="topics-panel">
    <div class="panel-head">
      <h2>Topicos emergentes</h2>
      <span class="badge">Clic para ver articulos</span>
    </div>
    <div class="topics-scroll" id="topics-container"></div>
  </div>
</div>

<div class="arts-section">
  <div class="arts-head">
    <h2>Todos los articulos</h2>
    <input type="text" class="search" id="search-input" placeholder="Buscar por titulo o autor..." oninput="onSearch()">
    <span class="badge" id="count-badge">{n_arts:,} articulos</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th style="width:42%">Titulo</th>
          <th style="width:20%">Autores</th>
          <th style="width:16%">Revista</th>
          <th style="width:4%">Ano</th>
          <th style="width:18%">Palabras clave</th>
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
const NODES   = """ + nodes_json + """;
const EDGES   = """ + edges_json + """;
const TOPICOS = """ + topicos_json + """;
const ARTS    = """ + arts_json + """;
const PG = 50;

// ── Red D3 ────────────────────────────────────────────────────────────────────
(function(){
  const svgEl = document.getElementById("net-svg");
  const W = svgEl.clientWidth || 800;
  const H = svgEl.clientHeight || 400;
  const svg = d3.select("#net-svg").attr("width",W).attr("height",H);
  const g   = svg.append("g");
  const tip = document.getElementById("tooltip");

  svg.call(d3.zoom().scaleExtent([0.15,10]).on("zoom", e => g.attr("transform", e.transform)));

  const maxDeg = Math.max(1,...NODES.map(n=>n.degree||1));

  const sim = d3.forceSimulation(NODES)
    .force("link", d3.forceLink(EDGES).id((_,i)=>i).distance(d=>55-d.weight*3).strength(0.5))
    .force("charge", d3.forceManyBody().strength(-70))
    .force("center", d3.forceCenter(W/2, H/2))
    .force("collision", d3.forceCollide(9));

  const link = g.append("g").selectAll("line").data(EDGES).enter().append("line")
    .attr("stroke","#1E2A38").attr("stroke-width",d=>Math.min(3,d.weight*0.4)).attr("stroke-opacity",0.5);

  const node = g.append("g").selectAll("circle").data(NODES).enter().append("circle")
    .attr("r", d=>4+(d.degree/maxDeg)*9)
    .attr("fill", d=>d.color||"#484F58")
    .attr("stroke","#0D1117").attr("stroke-width",1).attr("opacity",0.87)
    .style("cursor","pointer")
    .on("mouseover",(ev,d)=>{
      tip.style.opacity="1";
      tip.innerHTML=`<strong>${d.title}</strong><br><span style="color:#8B949E">${d.authors}</span><br><span style="color:#58A6FF">${d.year}</span>${d.topic?` &middot; T${d.topic}`:""}`;
    })
    .on("mousemove",ev=>{ tip.style.left=(ev.clientX+14)+"px"; tip.style.top=(ev.clientY-10)+"px"; })
    .on("mouseout",()=>{ tip.style.opacity="0"; })
    .on("click",(_,d)=>{ if(d.url) window.open(d.url,"_blank"); })
    .call(d3.drag()
      .on("start",(e,d)=>{ if(!e.active) sim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; })
      .on("drag", (e,d)=>{ d.fx=e.x; d.fy=e.y; })
      .on("end",  (e,d)=>{ if(!e.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }));

  sim.on("tick",()=>{
    link.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y)
        .attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
    node.attr("cx",d=>d.x).attr("cy",d=>d.y);
  });
})();

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
  filtered = q ? ARTS.filter(a=>(a.titulo||"").toLowerCase().includes(q)||(a.autores||"").toLowerCase().includes(q)) : ARTS;
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
    tr.innerHTML=`
      <td><a class="alink" href="${a.url||"#"}" target="_blank" rel="noopener">${a.titulo}</a></td>
      <td><span class="ameta">${a.autores||"—"}</span></td>
      <td><span class="ameta">${a.revista||"—"}</span></td>
      <td><span class="ameta">${a.anio||"—"}</span></td>
      <td><div class="kws">${kws}</div></td>`;
    tbody.appendChild(tr);
  });
}

function prevPage(){ if(curPage>0){ curPage--; render(); } }
function nextPage(){ if(curPage<Math.ceil(filtered.length/PG)-1){ curPage++; render(); } }

render();
</script>
</body>
</html>"""

(OUT_DIR / "index.html").write_text(html, encoding="utf-8")
print(f"Dashboard generado: docs/index.html")
print(f"  Red: {n_nodes} nodos - {n_edges} aristas")
print(f"  Topicos: {n_tops}")
print(f"  Articulos: {n_arts:,}")
