#!/usr/bin/env python3
"""Generate a standalone semantic laboratory page for the academic scraper."""
from __future__ import annotations

import csv
import html
import itertools
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)
OUT = DOCS / "laboratorio.html"

PALETTE = ["#58A6FF", "#2A9D8F", "#F4A261", "#E76F51", "#A78BFA", "#F9C74F", "#43AA8B", "#F94144", "#90BE6D", "#577590"]


def read_csv(path: Path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def clean(value):
    return " ".join(str(value or "").split())


def num(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def split_keywords(value):
    raw = clean(value).replace("|", ";")
    return [x.strip().lower() for x in raw.split(";") if len(x.strip()) > 3][:15]


def build_document_network(records, max_nodes=320, max_edges=1600):
    docs = []
    keyword_index = defaultdict(list)
    for idx, r in enumerate(records):
        title = clean(r.get("title"))
        kws = split_keywords(r.get("keywords"))
        if not title or not kws:
            continue
        node_id = len(docs)
        docs.append({
            "id": node_id,
            "label": title[:88],
            "title": title,
            "authors": clean(r.get("authors")),
            "year": clean(r.get("publication_year")),
            "source": clean(r.get("origin") or r.get("source")),
            "url": clean(r.get("url")) or (f"https://doi.org/{clean(r.get('doi'))}" if clean(r.get("doi")) else ""),
            "keywords": kws,
            "kind": "document",
        })
        for kw in set(kws):
            keyword_index[kw].append(node_id)

    weights = defaultdict(int)
    for kw, ids in keyword_index.items():
        if 2 <= len(ids) <= 35:
            for a, b in itertools.combinations(ids, 2):
                weights[(min(a, b), max(a, b))] += 1
    edges = sorted(((a, b, w) for (a, b), w in weights.items() if w >= 2), key=lambda x: -x[2])[:max_edges]
    degree = defaultdict(int)
    for a, b, w in edges:
        degree[a] += w
        degree[b] += w
    keep = set(i for i, _ in sorted(degree.items(), key=lambda kv: -kv[1])[:max_nodes])
    kept_docs = [d for d in docs if d["id"] in keep]
    remap = {d["id"]: i for i, d in enumerate(kept_docs)}
    for i, d in enumerate(kept_docs):
        d["id"] = i
        d["degree"] = degree[next(k for k, v in remap.items() if v == i)] if remap else 1
        d["color"] = PALETTE[i % len(PALETTE)]
    kept_edges = [{"source": remap[a], "target": remap[b], "weight": w, "relation": "keywords_compartidas"} for a, b, w in edges if a in remap and b in remap]
    return {"nodes": kept_docs, "edges": kept_edges, "description": "Artículos conectados por dos o más palabras clave compartidas. Esta vista es independiente de STM."}


def build_bertopic_network():
    pref = ROOT / "output/topic_models/bertopic/metadata_multilingual/preferred_solution"
    topics = [r for r in read_csv(pref / "topics.csv") if clean(r.get("topic_id")) not in {"", "-1"}]
    similarity = read_csv(pref / "topic_similarity.csv")
    labels = read_csv(ROOT / "output/topic_models/validation/topic_llm_labels.csv")
    llm = {clean(r.get("topic_id")): r for r in labels}
    nodes = []
    ids = {}
    for i, r in enumerate(topics):
        tid = clean(r.get("topic_id"))
        ids[tid] = i
        l = llm.get(tid, {})
        label = clean(l.get("researcher_label") or l.get("conceptual_label") or l.get("descriptive_label") or r.get("automatic_label") or f"Tópico {tid}")
        nodes.append({
            "id": i, "topic_id": tid, "label": label, "title": label,
            "automatic_label": clean(r.get("automatic_label")),
            "size": clean(r.get("document_count")), "prevalence": clean(r.get("prevalence")),
            "kind": "bertopic", "degree": 1, "color": PALETTE[i % len(PALETTE)],
            "llm_status": clean(l.get("llm_status")), "definition": clean(l.get("definition")),
        })
    edges = []
    for r in similarity:
        a, b = clean(r.get("topic_a")), clean(r.get("topic_b"))
        sim = num(r.get("ctfidf_similarity") or r.get("similarity"))
        if a in ids and b in ids and sim >= 0.08:
            edges.append({"source": ids[a], "target": ids[b], "weight": sim * 10, "similarity": sim, "relation": "similitud_bertopic"})
            nodes[ids[a]]["degree"] += 1
            nodes[ids[b]]["degree"] += 1
    return {"nodes": nodes, "edges": edges, "description": "Macrotemas BERTopic conectados por similitud entre sus representaciones c-TF-IDF. Etiquetas LLM o humanas se muestran sin modificar los clusters."}


def build_alignment_network():
    rows = read_csv(ROOT / "output/topic_models/comparison/stm_bertopic_alignment.csv") or read_csv(ROOT / "output/topic_models/comparison/topic_alignment.csv")
    nodes, edges, ids = [], [], {}
    def node(kind, tid):
        key = f"{kind}:{tid}"
        if key not in ids:
            ids[key] = len(nodes)
            nodes.append({"id": ids[key], "label": f"{kind} {tid}", "title": f"{kind} {tid}", "kind": kind.lower(), "degree": 1, "color": "#58A6FF" if kind == "BERTopic" else "#F4A261"})
        return ids[key]
    for r in rows:
        s = clean(r.get("stm_topic")); b = clean(r.get("bertopic_topic"))
        score = num(r.get("combined_alignment") or r.get("combined_similarity"))
        if not s or not b or score <= 0:
            continue
        a = node("STM", s); c = node("BERTopic", b)
        edges.append({"source": a, "target": c, "weight": max(1, score * 8), "similarity": score, "relation": clean(r.get("relationship") or "alineamiento")})
        nodes[a]["degree"] += 1; nodes[c]["degree"] += 1
    return {"nodes": nodes, "edges": edges, "description": "Vista comparativa de correspondencias STM–BERTopic. Sirve para observar convergencias y diferencias entre métodos, no para fusionarlos."}


def label_rows():
    rows = read_csv(ROOT / "output/topic_models/validation/topic_llm_labels.csv")
    if not rows:
        return '<div class="empty">Todavía no hay etiquetas LLM. Configure <code>OPENAI_API_KEY</code> y ejecute el flujo del laboratorio.</div>'
    out = []
    for r in rows:
        preferred = clean(r.get("researcher_label") or r.get("conceptual_label") or r.get("descriptive_label"))
        out.append(f'''<tr><td>T{html.escape(clean(r.get("topic_id")))}</td><td>{html.escape(clean(r.get("automatic_label")))}</td><td><strong>{html.escape(preferred)}</strong><div class="mini">Descriptiva: {html.escape(clean(r.get("descriptive_label")))}<br>Breve: {html.escape(clean(r.get("short_label")))}</div></td><td>{html.escape(clean(r.get("confidence")))}</td><td>{html.escape(clean(r.get("llm_status")))}</td><td>{html.escape(clean(r.get("researcher_status")) or "pendiente")}</td></tr>''')
    return ''.join(out)


def main():
    records = read_csv(ROOT / "data/master_records.csv")
    networks = {
        "documents": build_document_network(records),
        "bertopic": build_bertopic_network(),
        "alignment": build_alignment_network(),
    }
    payload = json.dumps(networks, ensure_ascii=False)
    labels = label_rows()
    page = f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Laboratorio temático</title><script src="https://cdn.jsdelivr.net/npm/d3@7"></script><style>
:root{{--bg:#0d1117;--panel:#161b22;--border:#30363d;--text:#c9d1d9;--muted:#8b949e;--accent:#58a6ff;--good:#2a9d8f}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}}header{{padding:20px 24px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;gap:20px}}h1,h2{{margin:0;color:#f0f6fc}}a{{color:var(--accent)}}.wrap{{padding:18px 24px;max-width:1500px;margin:auto}}.guide{{background:#10233b;border:1px solid #1f6feb;border-radius:10px;padding:14px 16px;margin-bottom:16px}}.guide summary{{cursor:pointer;font-weight:700;color:#79c0ff}}.guide ol{{margin-bottom:6px}}.note{{color:var(--muted);font-size:.9em}}.tabs{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}}button,select{{background:var(--panel);color:var(--text);border:1px solid var(--border);border-radius:7px;padding:8px 11px}}button{{cursor:pointer}}button.active{{border-color:var(--accent);color:#fff;background:#13233a}}.panel{{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px;margin-bottom:16px}}.toolbar{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px}}#network{{width:100%;height:620px;background:#0b1016;border-radius:8px}}.legend{{color:var(--muted);font-size:.86em;margin:7px 0 0}}table{{width:100%;border-collapse:collapse;font-size:.88em}}th,td{{padding:8px;border-bottom:1px solid var(--border);vertical-align:top;text-align:left}}th{{color:#f0f6fc;position:sticky;top:0;background:var(--panel)}}.tablewrap{{max-height:540px;overflow:auto}}.mini{{font-size:.8em;color:var(--muted);margin-top:4px}}.empty{{padding:20px;color:var(--muted)}}.tooltip{{position:fixed;pointer-events:none;opacity:0;background:#010409;border:1px solid var(--border);border-radius:6px;padding:8px;max-width:360px;z-index:5}}.status{{font-size:.85em;color:var(--muted)}}
</style></head><body><header><div><h1>Laboratorio temático y red semántica</h1><div class="note">SCRAPEADORACADEMICO · explorar → comparar → revisar evidencia → validar</div></div><div><a href="index.html">← Dashboard</a> · <a href="biblioteca.html">Lecturas</a></div></header><main class="wrap">
<details class="guide" open><summary>¿Cómo usar este laboratorio?</summary><ol><li>Elegí una vista de red según la pregunta: artículos, BERTopic o comparación STM–BERTopic.</li><li>Explorá relaciones y ajustá el umbral para reducir conexiones débiles.</li><li>Revisá las etiquetas: descriptor algorítmico, propuesta LLM y etiqueta validada por investigador se conservan por separado.</li><li>Volvé siempre a los documentos y a la evidencia antes de interpretar un tópico como hallazgo sustantivo.</li><li>Usá la Biblioteca para guardar y fichar los textos relevantes.</li></ol><div class="note"><strong>Criterio de uso:</strong> algoritmo detecta patrones → LLM propone una interpretación → investigador valida → el texto fundamenta.</div></details>
<section class="panel"><div class="toolbar"><h2 style="margin-right:auto">Red semántica multimétodo</h2><select id="network-select"><option value="documents">Artículos · palabras clave compartidas</option><option value="bertopic">Macrotemas · BERTopic</option><option value="alignment">Comparar · STM ↔ BERTopic</option></select><label>Umbral <input id="threshold" type="range" min="0" max="100" value="10"></label><span id="count" class="status"></span></div><div id="description" class="legend"></div><svg id="network"></svg></section>
<section class="panel"><div class="toolbar"><h2 style="margin-right:auto">Etiquetado asistido por LLM</h2><span class="status">Las propuestas LLM no sustituyen la validación humana.</span></div><div class="tablewrap"><table><thead><tr><th>ID</th><th>Descriptor algorítmico</th><th>Etiqueta preferida / LLM</th><th>Confianza</th><th>Estado LLM</th><th>Validación humana</th></tr></thead><tbody>{labels}</tbody></table></div></section>
<section class="panel"><h2>Lecturas y evidencia</h2><p>La revisión sustantiva continúa en la <a href="biblioteca.html">Biblioteca</a>. La intención es que cada tópico o relación pueda desembocar en lectura, fichaje y comprobación documental.</p></section>
</main><div id="tip" class="tooltip"></div><script>
const NETWORKS={payload}; const svg=d3.select('#network'); const tip=document.getElementById('tip'); const sel=document.getElementById('network-select'); const threshold=document.getElementById('threshold');
function render(){{svg.selectAll('*').remove(); const data=JSON.parse(JSON.stringify(NETWORKS[sel.value])); const W=document.getElementById('network').clientWidth||1000,H=620; svg.attr('viewBox',`0 0 ${{W}} ${{H}}`); const raw=+threshold.value/100; const maxW=Math.max(1,...data.edges.map(e=>+e.weight||0)); const edges=data.edges.filter(e=>(+e.weight||0)/maxW>=raw); const used=new Set(edges.flatMap(e=>[+e.source,+e.target])); const nodes=data.nodes.filter(n=>used.has(+n.id)||data.nodes.length<60); const byOld=new Map(nodes.map((n,i)=>[+n.id,i])); nodes.forEach((n,i)=>n.id=i); const filtered=edges.filter(e=>byOld.has(+e.source)&&byOld.has(+e.target)).map(e=>({{...e,source:byOld.get(+e.source),target:byOld.get(+e.target)}})); document.getElementById('description').textContent=data.description; document.getElementById('count').textContent=`${{nodes.length}} nodos · ${{filtered.length}} conexiones`; const g=svg.append('g'); svg.call(d3.zoom().scaleExtent([.15,8]).on('zoom',ev=>g.attr('transform',ev.transform))); const sim=d3.forceSimulation(nodes).force('link',d3.forceLink(filtered).id((d,i)=>i).distance(65).strength(.35)).force('charge',d3.forceManyBody().strength(-95)).force('center',d3.forceCenter(W/2,H/2)).force('collision',d3.forceCollide(10)); const link=g.append('g').selectAll('line').data(filtered).join('line').attr('stroke','#30363d').attr('stroke-opacity',.55).attr('stroke-width',d=>Math.max(.7,Math.min(4,+d.weight||1))); const node=g.append('g').selectAll('circle').data(nodes).join('circle').attr('r',d=>5+Math.min(8,Math.sqrt(+d.degree||1))).attr('fill',d=>d.color||'#58a6ff').attr('stroke','#0d1117').attr('stroke-width',1.2).style('cursor','pointer').on('mouseover',(ev,d)=>{{tip.style.opacity=1;tip.innerHTML=`<strong>${{d.title||d.label}}</strong><br>${{d.authors||''}} ${{d.year||''}}<br>${{d.definition||d.automatic_label||''}}`;}}).on('mousemove',ev=>{{tip.style.left=(ev.clientX+12)+'px';tip.style.top=(ev.clientY+12)+'px';}}).on('mouseout',()=>tip.style.opacity=0).on('click',(ev,d)=>{{if(d.url)window.open(d.url,'_blank')}}).call(d3.drag().on('start',(e,d)=>{{if(!e.active)sim.alphaTarget(.3).restart();d.fx=d.x;d.fy=d.y}}).on('drag',(e,d)=>{{d.fx=e.x;d.fy=e.y}}).on('end',(e,d)=>{{if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null}})); sim.on('tick',()=>{{link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);node.attr('cx',d=>d.x).attr('cy',d=>d.y)}})}}
sel.addEventListener('change',render);threshold.addEventListener('input',render);render();
</script></body></html>'''
    OUT.write_text(page, encoding="utf-8")
    print(f"Laboratorio generado -> {OUT}")


if __name__ == "__main__":
    main()
