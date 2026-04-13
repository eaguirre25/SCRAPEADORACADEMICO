#!/usr/bin/env python3
"""
generate_dashboard.py
Genera el dashboard interactivo HTML desde los CSVs del repo.
Se ejecuta diariamente después del scraper.
"""

import os
import json
import csv
from pathlib import Path
from datetime import date
from collections import Counter
import re

DATA_DIR   = Path("data")
OUTPUT_DIR = Path("docs")  # GitHub Pages sirve desde /docs
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Leer datos ────────────────────────────────────────────────────────────────

def leer_csv(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

records  = leer_csv(DATA_DIR / "master_records.csv")
topicos  = leer_csv(Path("output") / "tabla_topicos.csv")

# ── Cuadrante 1: Nube de palabras ────────────────────────────────────────────

# Extraer keywords de todos los registros
todas_keywords = []
stopwords_nube = {
    "school","education","educational","leadership","management","learning",
    "teachers","teacher","students","student","principal","principals",
    "gestión","educación","educativa","escolar","escuela","liderazgo",
    "dirección","docentes","docente","estudiantes","aprendizaje"
}

for r in records:
    kws = r.get("keywords", "") or ""
    for kw in kws.split(";"):
        kw = kw.strip().lower()
        if kw and len(kw) > 3 and kw not in stopwords_nube:
            todas_keywords.append(kw)

conteo_kw = Counter(todas_keywords).most_common(80)
wordcloud_data = [{"text": w, "size": c} for w, c in conteo_kw if c >= 2]

# ── Cuadrante 2: Tópicos STM ─────────────────────────────────────────────────

PALETA = [
    "#E63946","#F4A261","#2A9D8F","#457B9D","#A8DADC",
    "#E9C46A","#264653","#F77F00","#6A4C93","#1982C4",
    "#8AC926","#FF595E","#FFCA3A","#6A4C93","#1982C4",
    "#52B788","#D62828","#023E8A","#F3722C","#90BE6D",
]

topicos_data = []
for i, t in enumerate(topicos[:20]):
    topicos_data.append({
        "id":           t.get("topico", str(i+1)),
        "prevalencia":  float(t.get("prevalencia", 0)),
        "frex":         t.get("frex_top10", "").split(", ")[:7],
        "color":        t.get("color", PALETA[i % len(PALETA)])
    })

# ── Cuadrante 3: Mapa por países ─────────────────────────────────────────────

paises_raw = []
for r in records:
    paises = r.get("author_countries", "") or ""
    for p in paises.split(";"):
        p = p.strip()
        if p:
            paises_raw.append(p)

conteo_paises = Counter(paises_raw)

# Coordenadas aproximadas por país (ISO 3166-1 alpha-2 → [lat, lon])
coords_paises = {
    "AR": [-34.6, -58.4], "MX": [19.4, -99.1], "CO": [4.7, -74.1],
    "CL": [-33.5, -70.6], "PE": [-12.0, -77.0], "BR": [-15.8, -47.9],
    "ES": [40.4, -3.7],   "US": [38.9, -77.0],  "GB": [51.5, -0.1],
    "AU": [-35.3, 149.1], "CA": [45.4, -75.7],  "NZ": [-41.3, 174.8],
    "ZA": [-25.7, 28.2],  "NG": [9.1, 7.4],     "KE": [-1.3, 36.8],
    "GH": [5.6, -0.2],    "ID": [-6.2, 106.8],  "MY": [3.1, 101.7],
    "PH": [14.6, 121.0],  "CN": [39.9, 116.4],  "IN": [28.6, 77.2],
    "TR": [39.9, 32.9],   "PK": [33.7, 73.1],   "FI": [60.2, 24.9],
    "NO": [59.9, 10.7],   "SE": [59.3, 18.1],   "DK": [55.7, 12.6],
    "DE": [52.5, 13.4],   "FR": [48.9, 2.3],    "IT": [41.9, 12.5],
    "NL": [52.4, 4.9],    "PT": [38.7, -9.1],   "VE": [10.5, -66.9],
    "EC": [-0.2, -78.5],  "BO": [-16.5, -68.1], "UY": [-34.9, -56.2],
    "PY": [-25.3, -57.6], "CR": [9.9, -84.1],   "PA": [8.9, -79.5],
    "GT": [14.6, -90.5],  "HN": [14.1, -87.2],  "SV": [13.7, -89.2],
    "NI": [12.1, -86.3],  "DO": [18.5, -69.9],  "CU": [23.1, -82.4],
}

mapa_data = []
for codigo, cantidad in conteo_paises.most_common(50):
    if codigo in coords_paises:
        lat, lon = coords_paises[codigo]
        mapa_data.append({
            "pais":     codigo,
            "cantidad": cantidad,
            "lat":      lat,
            "lon":      lon,
            "radio":    max(5, min(40, cantidad * 2))
        })

# ── Cuadrante 4: Últimos 15 artículos ────────────────────────────────────────

def safe_int(v, default=0):
    try:
        return int(v)
    except:
        return default

ultimos = sorted(
    [r for r in records if r.get("title")],
    key=lambda r: (safe_int(r.get("publication_year", 0)),
                   r.get("publication_date", "")),
    reverse=True
)[:15]

articulos_data = []
for r in ultimos:
    kws = (r.get("keywords") or "").split(";")
    kws = [k.strip() for k in kws if k.strip()][:5]
    doi  = r.get("doi", "")
    url  = r.get("url") or (f"https://doi.org/{doi}" if doi else "#")
    autores = (r.get("authors") or "").split(";")
    autores = "; ".join(a.strip() for a in autores[:3])
    if len((r.get("authors") or "").split(";")) > 3:
        autores += " et al."
    articulos_data.append({
        "titulo":  r.get("title", "Sin título"),
        "autores": autores,
        "revista": r.get("origin", ""),
        "anio":    r.get("publication_year", ""),
        "url":     url,
        "keywords": kws,
    })

# ── Estadísticas generales ────────────────────────────────────────────────────

total   = len(records)
anios   = [safe_int(r.get("publication_year", 0)) for r in records if r.get("publication_year")]
anio_min = min(anios) if anios else 2020
anio_max = max(anios) if anios else 2026
paises_unicos = len(conteo_paises)

# ── Generar HTML del dashboard ───────────────────────────────────────────────

wc_json      = json.dumps(wordcloud_data,  ensure_ascii=False)
topicos_json = json.dumps(topicos_data,    ensure_ascii=False)
mapa_json    = json.dumps(mapa_data,       ensure_ascii=False)
arts_json    = json.dumps(articulos_data,  ensure_ascii=False)

html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard – Dirección Escolar</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  :root{{
    --bg:#0D1117;--surface:#161B22;--border:#21262D;
    --text:#C9D1D9;--muted:#8B949E;--accent:#58A6FF;--dim:#484F58
  }}
  body{{font-family:"Segoe UI",system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}}
  header{{background:var(--surface);border-bottom:1px solid var(--border);padding:16px 24px;display:flex;align-items:center;justify-content:space-between}}
  header h1{{font-size:1.2em;color:#E6EDF3;font-weight:600}}
  header h1 span{{color:var(--accent)}}
  .stamp{{font-size:.75em;color:var(--dim)}}
  .kpis{{display:flex;gap:12px;padding:16px 24px;background:var(--surface);border-bottom:1px solid var(--border)}}
  .kpi{{text-align:center;flex:1}}
  .kpi-n{{font-size:1.8em;font-weight:700;color:var(--accent)}}
  .kpi-l{{font-size:.72em;color:var(--muted)}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:auto auto;gap:12px;padding:16px 24px;max-width:1600px;margin:0 auto}}
  .card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden;display:flex;flex-direction:column}}
  .card-header{{padding:12px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px}}
  .card-header h2{{font-size:.9em;font-weight:600;color:#E6EDF3;text-transform:uppercase;letter-spacing:.05em}}
  .badge{{background:var(--accent);color:#0D1117;border-radius:20px;padding:2px 8px;font-size:.7em;font-weight:700}}
  .card-body{{flex:1;padding:16px;overflow:auto}}

  /* Wordcloud */
  #wc-svg{{width:100%;height:320px}}

  /* Tópicos */
  .topic-bar{{margin-bottom:10px}}
  .topic-label{{display:flex;justify-content:space-between;align-items:center;margin-bottom:3px}}
  .topic-name{{font-size:.8em;font-weight:600}}
  .topic-pct{{font-size:.75em;color:var(--muted)}}
  .bar-track{{background:#1E2A38;border-radius:4px;height:8px;overflow:hidden}}
  .bar-fill{{height:100%;border-radius:4px;transition:width .4s}}
  .topic-words{{font-size:.72em;color:var(--muted);margin-top:2px;line-height:1.4}}

  /* Mapa */
  #map{{height:340px;border-radius:6px}}
  .leaflet-container{{background:#0D1117}}

  /* Artículos */
  .art-item{{border-bottom:1px solid var(--border);padding:10px 0;cursor:pointer;transition:background .15s}}
  .art-item:hover{{background:#1a2030}}
  .art-item:last-child{{border-bottom:none}}
  .art-title{{font-size:.85em;font-weight:600;color:var(--accent);text-decoration:none;line-height:1.3}}
  .art-title:hover{{text-decoration:underline}}
  .art-meta{{font-size:.75em;color:var(--muted);margin-top:3px}}
  .art-kws{{margin-top:5px;display:flex;flex-wrap:wrap;gap:4px}}
  .kw-tag{{background:#1E2A38;color:var(--muted);border-radius:4px;padding:2px 7px;font-size:.7em}}

  footer{{text-align:center;padding:20px;color:var(--dim);font-size:.75em;border-top:1px solid var(--border)}}
  @media(max-width:900px){{.grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>

<header>
  <h1>Dashboard · <span>Dirección y Gestión Escolar</span></h1>
  <span class="stamp">Actualizado: {date.today().strftime('%d/%m/%Y')} · Literatura 2020–{anio_max}</span>
</header>

<div class="kpis">
  <div class="kpi"><div class="kpi-n">{total:,}</div><div class="kpi-l">Publicaciones</div></div>
  <div class="kpi"><div class="kpi-n">{len(topicos_data)}</div><div class="kpi-l">Tópicos STM</div></div>
  <div class="kpi"><div class="kpi-n">{paises_unicos}</div><div class="kpi-l">Países</div></div>
  <div class="kpi"><div class="kpi-n">{anio_min}–{anio_max}</div><div class="kpi-l">Período</div></div>
</div>

<div class="grid">

  <!-- Cuadrante 1: Nube de palabras -->
  <div class="card">
    <div class="card-header">
      <h2>Nube de palabras</h2>
      <span class="badge">Keywords del corpus</span>
    </div>
    <div class="card-body" style="padding:8px">
      <svg id="wc-svg"></svg>
    </div>
  </div>

  <!-- Cuadrante 2: Tópicos STM -->
  <div class="card">
    <div class="card-header">
      <h2>Tópicos emergentes</h2>
      <span class="badge">STM inductivo</span>
    </div>
    <div class="card-body" id="topicos-container"></div>
  </div>

  <!-- Cuadrante 3: Mapa -->
  <div class="card">
    <div class="card-header">
      <h2>Distribución geográfica</h2>
      <span class="badge">Por país de publicación</span>
    </div>
    <div class="card-body" style="padding:8px">
      <div id="map"></div>
    </div>
  </div>

  <!-- Cuadrante 4: Últimos artículos -->
  <div class="card">
    <div class="card-header">
      <h2>Publicaciones recientes</h2>
      <span class="badge">Últimas 15</span>
    </div>
    <div class="card-body" id="articulos-container"></div>
  </div>

</div>

<footer>
  Datos: OpenAlex API · Análisis: STM (R) · Actualización diaria automática via GitHub Actions
</footer>

<script>
// ── Datos ─────────────────────────────────────────────────────────────────────
const WC_DATA      = {wc_json};
const TOPICOS_DATA = {topicos_json};
const MAPA_DATA    = {mapa_json};
const ARTS_DATA    = {arts_json};

// ── 1. Wordcloud con D3 ───────────────────────────────────────────────────────
(function() {{
  const svg    = d3.select("#wc-svg");
  const W      = document.getElementById("wc-svg").clientWidth || 600;
  const H      = 320;
  svg.attr("viewBox", `0 0 ${{W}} ${{H}}`);

  const maxCount = d3.max(WC_DATA, d => d.size);
  const scale    = d3.scaleLinear().domain([1, maxCount]).range([12, 48]);

  const colors = ["#E63946","#F4A261","#2A9D8F","#457B9D","#E9C46A",
                  "#8AC926","#F77F00","#6A4C93","#1982C4","#52B788",
                  "#FF595E","#FFCA3A","#D62828","#F3722C","#90BE6D"];

  const placed = [];
  const words  = WC_DATA.slice(0, 60);

  words.forEach((d, i) => {{
    const fs   = scale(d.size);
    const color = colors[i % colors.length];
    let x, y, tries = 0, ok = false;

    while (tries < 200 && !ok) {{
      x = Math.random() * (W - 120) + 60;
      y = Math.random() * (H - 40)  + 20;
      const w = d.text.length * fs * 0.55;
      const h = fs * 1.2;
      ok = placed.every(p =>
        Math.abs(x - p.x) > (w + p.w) / 2 + 4 ||
        Math.abs(y - p.y) > (h + p.h) / 2 + 4
      );
      tries++;
    }}

    if (ok) {{
      const w = d.text.length * fs * 0.55;
      const h = fs * 1.2;
      placed.push({{ x, y, w, h }});
      svg.append("text")
        .attr("x", x).attr("y", y)
        .attr("text-anchor", "middle")
        .attr("dominant-baseline", "middle")
        .attr("fill", color)
        .attr("font-size", fs)
        .attr("font-family", "Segoe UI, sans-serif")
        .attr("font-weight", d.size > maxCount * 0.5 ? "700" : "400")
        .attr("opacity", 0.85)
        .text(d.text)
        .append("title").text(`${{d.text}} (${{d.size}})`);
    }}
  }});
}})();

// ── 2. Tópicos STM ────────────────────────────────────────────────────────────
(function() {{
  const container = document.getElementById("topicos-container");
  const maxPrev   = Math.max(...TOPICOS_DATA.map(t => t.prevalencia));

  TOPICOS_DATA.forEach(t => {{
    const div = document.createElement("div");
    div.className = "topic-bar";
    div.innerHTML = `
      <div class="topic-label">
        <span class="topic-name" style="color:${{t.color}}">T${{t.id}}</span>
        <span class="topic-pct">${{t.prevalencia.toFixed(1)}}%</span>
      </div>
      <div class="bar-track">
        <div class="bar-fill" style="width:${{(t.prevalencia/maxPrev*100).toFixed(1)}}%;background:${{t.color}}"></div>
      </div>
      <div class="topic-words">${{t.frex.join(" · ")}}</div>
    `;
    container.appendChild(div);
  }});
}})();

// ── 3. Mapa Leaflet ───────────────────────────────────────────────────────────
(function() {{
  const map = L.map("map", {{
    center: [10, 10], zoom: 1.5,
    zoomControl: true, scrollWheelZoom: false
  }});

  L.tileLayer("https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png", {{
    attribution: "© CartoDB",
    subdomains: "abcd", maxZoom: 10
  }}).addTo(map);

  const maxQ = Math.max(...MAPA_DATA.map(d => d.cantidad));

  MAPA_DATA.forEach(d => {{
    const color = d3.interpolateViridis(d.cantidad / maxQ);
    L.circleMarker([d.lat, d.lon], {{
      radius:      Math.max(5, Math.sqrt(d.cantidad) * 3),
      fillColor:   color,
      color:       "#fff",
      weight:      0.5,
      opacity:     0.9,
      fillOpacity: 0.75
    }})
    .addTo(map)
    .bindPopup(`<strong>${{d.pais}}</strong><br>${{d.cantidad}} publicaciones`);
  }});
}})();

// ── 4. Artículos recientes ────────────────────────────────────────────────────
(function() {{
  const container = document.getElementById("articulos-container");

  ARTS_DATA.forEach(a => {{
    const div  = document.createElement("div");
    div.className = "art-item";
    const kwHTML = a.keywords.map(k =>
      `<span class="kw-tag">${{k}}</span>`
    ).join("");
    div.innerHTML = `
      <a class="art-title" href="${{a.url}}" target="_blank" rel="noopener">${{a.titulo}}</a>
      <div class="art-meta">${{a.autores || "—"}} · ${{a.revista || "—"}} · ${{a.anio || "—"}}</div>
      ${{kwHTML ? `<div class="art-kws">${{kwHTML}}</div>` : ""}}
    `;
    container.appendChild(div);
  }});
}})();
</script>
</body>
</html>"""

output_path = OUTPUT_DIR / "index.html"
output_path.write_text(html, encoding="utf-8")
print(f"Dashboard generado: {output_path}")
print(f"  Publicaciones: {total}")
print(f"  Tópicos: {len(topicos_data)}")
print(f"  Países en mapa: {len(mapa_data)}")
print(f"  Artículos recientes: {len(articulos_data)}")
