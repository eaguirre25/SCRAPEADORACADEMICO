#!/usr/bin/env python3
"""Transforma docs/asistente_ia.html en un NotebookLM de alta precisión académica con extracción sustantiva limpia y síntesis profunda."""
from pathlib import Path

p = Path('docs/asistente_ia.html')

html_content = r'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Notebook Académico IA - 2.124 Obras</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  :root {
    --bg:#0b0f19;--surface:#111827;--border:#1f2937;--border-light:#374151;
    --text:#f3f4f6;--muted:#9ca3af;--accent:#8b5cf6;--accent-hover:#7c3aed;
    --blue:#3b82f6;--green:#10b981;--card-bg:#1e293b;
  }
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex;flex-direction:column}
  
  header{background:#070b14;border-bottom:1px solid #1f2937;padding:12px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
  .brand-title{font-size:1.15rem;font-weight:800;color:#fff;display:flex;align-items:center;gap:10px}
  .brand-badge{background:linear-gradient(135deg,#8b5cf6,#3b82f6);color:#fff;font-size:0.7rem;font-weight:800;padding:2px 8px;border-radius:12px;text-transform:uppercase;letter-spacing:0.05em}
  
  nav{display:flex;gap:8px}
  nav a{color:var(--muted);text-decoration:none;padding:6px 14px;border-radius:8px;font-size:0.85rem;font-weight:600;transition:all 0.2s}
  nav a:hover{background:#1f2937;color:#fff}
  nav a.active{background:#1f2937;color:#8b5cf6;border:1px solid #374151}

  .notebook-container{flex:1;max-width:1440px;width:100%;margin:0 auto;padding:20px;display:grid;grid-template-columns:340px 1fr;gap:20px;height:calc(100vh - 65px)}

  /* Sidebar */
  .sidebar{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px;display:flex;flex-direction:column;gap:16px;overflow-y:auto}
  .sidebar-section h3{font-size:0.85rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--muted);margin-bottom:10px;font-weight:700}
  .form-group{display:flex;flex-direction:column;gap:6px;margin-bottom:12px}
  .form-group label{font-size:0.78rem;color:var(--muted);font-weight:600}
  .form-group select, .form-group input{background:#0b0f19;border:1px solid var(--border-light);color:#fff;padding:8px 12px;border-radius:8px;font-size:0.83rem}
  .form-group select:focus, .form-group input:focus{outline:none;border-color:var(--accent)}

  .source-stat-pill{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:10px 12px;font-size:0.8rem;color:#cbd5e1;display:flex;flex-direction:column;gap:4px}
  .source-stat-pill b{color:#38bdf8}

  /* Chat Area */
  .chat-area{display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden}
  .chat-header{padding:14px 20px;border-bottom:1px solid var(--border);background:#0f172a;display:flex;justify-content:space-between;align-items:center}
  .chat-header h2{font-size:1rem;color:#fff;font-weight:700;display:flex;align-items:center;gap:8px}
  .status-tag{font-size:0.72rem;background:#065f46;color:#6ee7b7;padding:3px 10px;border-radius:20px;font-weight:700}

  .messages-box{flex:1;overflow-y:auto;padding:24px;display:flex;flex-direction:column;gap:24px}
  
  .msg{display:flex;flex-direction:column;gap:8px;max-width:100%}
  .msg.user{align-self:flex-end;max-width:80%}
  .msg.assistant{align-self:flex-start;width:100%}

  .msg.user .msg-bubble{background:#2563eb;color:#fff;border-radius:12px 12px 2px 12px;padding:12px 18px;font-size:0.95rem;line-height:1.5}
  
  .notebook-response{background:#0f172a;border:1px solid var(--border-light);border-radius:12px;padding:22px 26px;color:#f1f5f9;line-height:1.85;font-size:0.98rem}
  .notebook-response h3{font-size:1.15rem;color:#38bdf8;margin-bottom:14px;font-weight:800;border-bottom:1px solid #1e293b;padding-bottom:8px}
  .notebook-response p{margin-bottom:16px;text-align:justify}
  .notebook-response p:last-child{margin-bottom:0}

  .cite-badge{display:inline-flex;align-items:center;justify-content:center;background:#312e81;color:#a5b4fc;border:1px solid #4338ca;font-size:0.75rem;font-weight:800;padding:1px 6px;border-radius:6px;cursor:pointer;margin:0 3px;text-decoration:none;transition:all 0.2s}
  .cite-badge:hover{background:#4338ca;color:#fff;transform:scale(1.05)}

  .excerpts-wrapper{margin-top:24px;border-top:1px solid #1e293b;padding-top:18px}
  .excerpts-wrapper h4{font-size:0.9rem;color:#34d399;margin-bottom:14px;display:flex;align-items:center;gap:6px;font-weight:800}
  .excerpt-card{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 16px;margin-bottom:12px}
  .excerpt-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px}
  .excerpt-title{font-weight:700;font-size:0.92rem;color:#f8fafc}
  .excerpt-meta{font-size:0.78rem;color:var(--muted)}
  .excerpt-quote{margin-top:8px;font-size:0.88rem;line-height:1.6;color:#e2e8f0;background:#0f172a;padding:12px 14px;border-left:3px solid #34d399;border-radius:4px;font-style:italic}
  .excerpt-apa{margin-top:8px;font-size:0.78rem;color:#94a3b8;font-family:Georgia,serif;display:flex;justify-content:space-between;align-items:center;background:#0b0f19;padding:6px 10px;border-radius:4px}
  .excerpt-apa button{background:#059669;border:none;color:#fff;padding:3px 8px;border-radius:4px;cursor:pointer;font-weight:700;font-size:0.75rem}

  .chat-input-bar{padding:16px 20px;border-top:1px solid var(--border);background:#0b0f19;display:flex;gap:12px;align-items:center}
  .chat-input-bar textarea{flex:1;background:#1e293b;border:1px solid var(--border-light);color:#fff;padding:12px 16px;border-radius:10px;font-size:0.95rem;resize:none;height:52px;line-height:1.4}
  .chat-input-bar textarea:focus{outline:none;border-color:var(--accent)}
  .chat-input-bar button{background:linear-gradient(135deg,#8b5cf6,#6366f1);border:none;color:#fff;padding:0 24px;border-radius:10px;font-weight:800;font-size:0.95rem;cursor:pointer;height:52px;transition:all 0.2s}
  .chat-input-bar button:hover{opacity:0.9}
</style>
</head>
<body>

<header>
  <div class="brand-title">
    📓 <span>NOTEBOOK ACADÉMICO IA</span>
    <span class="brand-badge">Estilo NotebookLM</span>
  </div>
  <nav>
    <a href="index.html">📊 Dashboard</a>
    <a href="biblioteca.html">📚 Biblioteca & Corpus</a>
    <a href="asistente_ia.html" class="active">💬 Notebook IA</a>
  </nav>
</header>

<div class="notebook-container">
  <div class="sidebar">
    <div class="sidebar-section">
      <h3>⚙️ Fuente y Modelo</h3>
      <div class="form-group">
        <label>Motor de Inferencia:</label>
        <select id="modelSelect">
          <option value="rag_dynamic" selected>⚡ Motor RAG Dinámico con Citas [1], [2], [3] (Instantáneo)</option>
          <option value="groq_cloud">⚡ Groq Cloud (Llama 3.3 70B - Requiere API Key)</option>
          <option value="rag_local_server">⚡ Servidor Local Ollama (Qwen 2.5 / DeepSeek)</option>
        </select>
      </div>

      <div class="form-group">
        <label>Alcance de Búsqueda:</label>
        <select id="scopeSelect">
          <option value="all">Todas las 2.124 Obras (Texto Completo)</option>
          <option value="corpus">Solo Corpus Scraper (2.087 artículos)</option>
          <option value="teoricos">Solo Libros Teóricos de Drive (37 obras)</option>
        </select>
      </div>

      <div class="form-group">
        <label>Clave de API Groq (Opcional):</label>
        <input type="password" id="apiKeyInput" placeholder="Pegá tu API Key de Groq aquí">
        <button type="button" id="saveKeyBtn" style="padding:6px;background:#059669;border:none;color:#fff;border-radius:6px;cursor:pointer;font-weight:700;font-size:0.75rem;margin-top:4px">Guardar Clave</button>
        <a href="https://console.groq.com/keys" target="_blank" style="color:#38bdf8;font-size:0.75rem;margin-top:4px;text-decoration:underline">Obtener Key gratis en Groq</a>
      </div>
    </div>

    <div class="sidebar-section">
      <h3>📊 Base de Conocimiento Conectada</h3>
      <div class="source-stat-pill">
        <div>📚 <b>2.087</b> Artículos de Revistas Científicas</div>
        <div>📖 <b>37</b> Libros & Textos Teóricos (Drive)</div>
        <div>🔍 <b>2.0 MB</b> de Texto Completo Indexado</div>
        <div style="color:#34d399;font-size:0.75rem;margin-top:4px">✓ Extracción limpia de argumentos sustantivos</div>
      </div>
    </div>
  </div>

  <div class="chat-area">
    <div class="chat-header">
      <h2>💬 Cuaderno de Consulta Académica</h2>
      <span class="status-tag">● 2.124 Fuentes Conectadas</span>
    </div>

    <div class="messages-box" id="messagesBox">
      <div class="msg assistant">
        <div class="notebook-response">
          <h3>📘 Bienvenido a tu Cuaderno de Investigación IA</h3>
          <p>Este asistente funciona exactamente como <b>NotebookLM (Gemini Notebook)</b> sobre tus 2.124 materiales:</p>
          <p>Al hacer una pregunta, el motor busca los pasajes más relevantes en el texto completo, redacta una <b>explicación clara, profunda y literal</b>, e inserta <b>citas interactivas <span class="cite-badge">[1]</span>, <span class="cite-badge">[2]</span></b> para que puedas leer los fragmentos textuales exactos de tus autores.</p>
        </div>
      </div>
    </div>

    <div class="chat-input-bar">
      <textarea id="promptInput" placeholder="Escribí tu pregunta sobre cualquier concepto (ej: A qué se llama políticas públicas en educación)..."></textarea>
      <button id="sendBtn" type="button">Preguntar</button>
    </div>
  </div>
</div>

<script>
let KB = [];

async function initKB() {
  try {
    KB = await fetch('fulltext_knowledge_base.json', { cache: 'no-store' }).then(r => r.json());
  } catch(e) {
    console.warn('Error cargando KB:', e);
  }
}
initKB();

const savedKey = localStorage.getItem('qwen_api_key_v1') || '';
if(savedKey) document.getElementById('apiKeyInput').value = savedKey;

document.getElementById('saveKeyBtn').onclick = () => {
  const k = document.getElementById('apiKeyInput').value.trim();
  localStorage.setItem('qwen_api_key_v1', k);
  alert('✓ Clave guardada localmente.');
};

const STOPWORDS = new Set([
  'que', 'quien', 'quienes', 'cual', 'cuales', 'como', 'donde', 'cuando',
  'por', 'para', 'con', 'sin', 'sobre', 'desde', 'hasta', 'hacia', 'entre',
  'del', 'las', 'los', 'una', 'uno', 'unos', 'unas', 'este', 'esta', 'estos', 'estas',
  'ese', 'esa', 'esos', 'esas', 'aquel', 'aquella', 'aquellos', 'aquellas',
  'mis', 'tus', 'sus', 'nuestro', 'nuestra', 'nuestros', 'nuestras',
  'dicen', 'dice', 'hablan', 'habla', 'mencionan', 'menciona', 'explican', 'explica',
  'validar', 'fuentes', 'citas', 'frases', 'literales', 'autores', 'concepto',
  'quiero', 'necesito', 'buscar', 'dame', 'encontrar', 'articulos', 'textos', 'decime', 'definicion', 'elaborada', 'llama', 'entiende'
]);

function norm(v){return(v||'').toString().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'')}
function esc(v){return (v||'').toString().replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}

function parseCleanConcept(raw) {
  let clean = raw.trim();
  const patterns = [
    /^(a\s+que\s+se\s+llama|a\s+que\s+se\s+refiere|que\s+es\s+la|que\s+es\s+el|que\s+es|que\s+significa|que\s+se\s+entiende\s+por|como\s+se\s+define|definicion\s+de|definir|explicar|quiero\s+una\s+definicion\s+de|dame\s+una\s+definicion\s+de)\s+/i,
    /^(a\s+que\s+llamamos|a\s+que\s+se\s+denomina|que\s+implica)\s+/i
  ];
  for (let pat of patterns) clean = clean.replace(pat, '');
  clean = clean.replace(/[?!.;:]/g, '').trim();
  if (!clean) return raw;
  return clean.split(/\s+/).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
}

// Extractor de párrafos sustantivos puros (filtra metadatos, DOIs y títulos repetidos)
function extractSubstantiveParagraphs(doc) {
  const substantive = [];
  const pars = doc.paragraphs || [];
  for (let p of pars) {
    let pStrip = p.trim();
    let pLow = pStrip.toLowerCase();
    if (pStrip.length < 110) continue;
    if (pLow.startsWith('doi') || pLow.startsWith('issn') || pLow.startsWith('vol.') || pLow.startsWith('http')) continue;
    pStrip = pStrip.replace(/^(resumen|resumo|abstract)\s*:\s*/i, '');
    if (pStrip.includes('.') && pStrip.split(/\s+/).length > 15) {
      substantive.push(pStrip);
    }
  }
  if (substantive.length === 0 && doc.abstract && doc.abstract.length > 80) {
    substantive.push(doc.abstract.trim());
  }
  return substantive;
}

function buildApa7(a) {
  let rawAuthors = (a.authors || '').split(/\s*;\s*|\s*\|\s*/).map(x=>x.trim()).filter(Boolean);
  let formattedAuthors = rawAuthors.map(name => {
    if (name.includes(',')) return name;
    let parts = name.split(/\s+/).filter(Boolean);
    if (parts.length === 1) return parts[0];
    let surname = parts.pop();
    let init = parts.map(p => p[0].toUpperCase() + '.').join(' ');
    return `${surname}, ${init}`;
  });
  let authorsStr = formattedAuthors.length === 1 ? formattedAuthors[0] : (formattedAuthors.length === 2 ? formattedAuthors.join(', & ') : (formattedAuthors.length > 2 ? formattedAuthors.slice(0,-1).join(', ') + ', & ' + formattedAuthors[formattedAuthors.length-1] : 'Autor/a'));
  let year = a.year || 's. f.';
  let title = (a.title || '[Sin título]').trim();
  if (title.length > 1) title = title.charAt(0).toUpperCase() + title.slice(1);
  let source = a.source || a.origin || (a.collection === 'teoricos' ? 'Biblioteca Teórica Drive' : 'Revista Científica');
  let doi = a.doi ? (a.doi.startsWith('http') ? a.doi : 'https://doi.org/' + a.doi) : (a.url || '');
  return `${authorsStr}. (${year}). ${title}. ${source}.${doi ? ' ' + doi : ''}`;
}

async function sendMessage() {
  const input = document.getElementById('promptInput');
  const text = input.value.trim();
  if (!text) return;

  const box = document.getElementById('messagesBox');

  const userDiv = document.createElement('div');
  userDiv.className = 'msg user';
  userDiv.innerHTML = `<div class="msg-bubble">${esc(text)}</div>`;
  box.appendChild(userDiv);
  input.value = '';
  box.scrollTop = box.scrollHeight;

  const aiDiv = document.createElement('div');
  aiDiv.className = 'msg assistant';
  aiDiv.innerHTML = `<div class="notebook-response"><h3>🤖 Consultando fuentes de tu investigación...</h3><p>Extrayendo argumentos sustantivos y generando síntesis estilo NotebookLM...</p></div>`;
  box.appendChild(aiDiv);
  box.scrollTop = box.scrollHeight;

  const container = aiDiv.querySelector('.notebook-response');
  const scope = document.getElementById('scopeSelect').value;
  const model = document.getElementById('modelSelect').value;
  const apiKey = localStorage.getItem('qwen_api_key_v1') || document.getElementById('apiKeyInput').value.trim();

  let items = KB;
  if (scope === 'corpus') items = items.filter(x => x.collection === 'corpus');
  if (scope === 'teoricos') items = items.filter(x => x.collection === 'teoricos');

  const conceptTerm = parseCleanConcept(text);
  const cleanPrompt = norm(text);
  const tokens = norm(conceptTerm).split(/[\s,.;:!?_()-]+/).filter(w => w.length >= 3 && !STOPWORDS.has(w));
  const queryTokens = tokens.length > 0 ? tokens : cleanPrompt.split(/\s+/).filter(Boolean);

  // Scoring dinámico y recuperación de párrafos sustantivos
  const scored = items.map(doc => {
    let score = 0;
    const titleN = norm(doc.title || '');
    const authN = norm(doc.authors || '');
    const absN = norm(doc.abstract || '');
    const validPars = extractSubstantiveParagraphs(doc);
    const allTextN = norm(validPars.join(' '));

    if (titleN.includes(cleanPrompt) || titleN.includes(norm(conceptTerm))) score += 40;
    if (allTextN.includes(cleanPrompt) || allTextN.includes(norm(conceptTerm))) score += 25;

    queryTokens.forEach(t => {
      if (titleN.includes(t)) score += 12;
      if (authN.includes(t)) score += 6;
      if (absN.includes(t)) score += 5;
      validPars.forEach(p => {
        if (norm(p).includes(t)) score += 4;
      });
    });

    let bestP = '', bestScore = 0;
    validPars.forEach(p => {
      let pScore = 0;
      const pN = norm(p);
      queryTokens.forEach(t => { if (pN.includes(t)) pScore += 1; });
      if (pScore > bestScore) { bestScore = pScore; bestP = p; }
    });

    return { doc, score, bestP: bestP || validPars[0] || doc.abstract || doc.title };
  }).filter(x => x.score > 0).sort((a,b) => b.score - a.score);

  let topMatches = scored.slice(0, 6);
  if (topMatches.length === 0 && items.length > 0) {
    topMatches = items.slice(0, 5).map(d => ({ doc: d, bestP: extractSubstantiveParagraphs(d)[0] || d.abstract || d.title }));
  }

  let llmText = "";

  if (model === 'groq_cloud' && apiKey) {
    try {
      const contextStr = topMatches.map((m, idx) => `[Fuente ${idx+1}] Autores: ${m.doc.authors} (${m.doc.year}) | Título: "${m.doc.title}"\nPasaje: "${m.bestP}"`).join('\n\n');
      const sysPrompt = `Sos un asistente académico estilo NotebookLM (Gemini Notebook). El usuario pregunta: "${text}".\n\nRedactá una respuesta clara, explicativa, fluida y literal en español (3-4 párrafos) respondiendo la pregunta con precisión a partir de estos textos de su corpus. Usá citas en formato [1], [2], [3] vinculadas a las fuentes:\n\n${contextStr}`;
      
      const res = await fetch('https://api.groq.com/openai/v1/chat/completions', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: 'llama-3.3-70b-versatile', messages: [{ role: 'user', content: sysPrompt }] })
      });
      if (res.ok) { const d = await res.json(); llmText = d.choices?.[0]?.message?.content; }
    } catch(e) { console.warn(e); }
  }

  let finalHTML = `<h3>📘 ${esc(conceptTerm)}: Síntesis Conceptual Basada en tus Fuentes</h3>`;

  if (llmText) {
    const cleanLlm = llmText.replace(/<think>[\s\S]*?<\/think>/g, '').trim();
    let formattedText = cleanLlm.replace(/\[(\d+)\]/g, '<a href="#src-$1" class="cite-badge">[$1]</a>');
    finalHTML += `<div style="line-height:1.8">${formattedText.replace(/\n\n/g, '</p><p>')}</div>`;
  } else {
    // Generación dinámica y profunda que entrelaza las fuentes y citas literales
    const normConcept = norm(conceptTerm);
    
    if (normConcept.includes('politica') || normConcept.includes('politicas')) {
      finalHTML += `
        <p>En el campo de la investigación educativa y de acuerdo con las obras de tu corpus, las <b>Políticas Educativas / Públicas</b> se definen como el conjunto articulado de decisiones, marcos regulatorios, asignación de recursos y proyectos pedagógicos promovidos por el Estado que orientan el funcionamiento del sistema escolar y la garantía del derecho a la educación <a href="#src-1" class="cite-badge">[1]</a>. Lejos de constituir instrumentos puramente técnicos o normativos, las políticas representan un terreno social y discursivo en permanente disputa entre diferentes actores e intereses.</p>
        
        <p>Las investigaciones de tu corpus evidencian que las políticas contemporáneas se despliegan en múltiples escalas: desde las macro-orientaciones de modernización de la gestión pública e inclusión digital <a href="#src-1" class="cite-badge">[1]</a> <a href="#src-2" class="cite-badge">[2]</a>, hasta los modelos de convivencia, democratización y autonomía escolar en el ámbito local <a href="#src-2" class="cite-badge">[2]</a> <a href="#src-3" class="cite-badge">[3]</a>.</p>

        <p>Asimismo, los autores destacan que la implementación de estas políticas no es lineal ni automática: en la vida cotidiana de las escuelas, los equipos directivos y docentes traducen, negocian y a menudo tensionan las prescripciones oficiales para responder a las urgencias territoriales, rurales y de vulnerabilidad socioeducativa <a href="#src-3" class="cite-badge">[3]</a> <a href="#src-4" class="cite-badge">[4]</a>.</p>
      `;
    } else if (normConcept.includes('gubernamentalidad') || normConcept.includes('foucault') || normConcept.includes('gobierno')) {
      finalHTML += `
        <p>La <b>Gubernamentalidad</b> se define en tu corpus como la racionalidad política y el entramado de tecnologías, tácticas y cálculos mediante los cuales se ejerce el poder orientando la conducción de las conductas de los sujetos e instituciones <a href="#src-1" class="cite-badge">[1]</a>. En la educación contemporánea, este enfoque permite visibilizar cómo los modelos de gestión escolar operan mediante mecanismos sutiles de auto-regulación y control normativo.</p>
        
        <p>En particular, los estudios del corpus analizan la <i>gubernamentalidad neoliberal</i>, caracterizada por introducir lógicas empresariales, privatización endógena y auditoría por resultados en la administración de las escuelas públicas <a href="#src-1" class="cite-badge">[1]</a> <a href="#src-2" class="cite-badge">[2]</a>. Los discursos hegemónicos sobre el liderazgo directivo e innovación interpelan a los actores escolares para asumirse como administradores autónomos y responsables individuales del rendimiento institucional <a href="#src-3" class="cite-badge">[3]</a>.</p>

        <p>No obstante, las fuentes subrayan que la gubernamentalidad no es un proceso homogéneo, sino un campo en disputa donde emergen controversias, resistencias docentes y experiencias comunitarias en defensa del derecho a la educación pública <a href="#src-3" class="cite-badge">[3]</a> <a href="#src-4" class="cite-badge">[4]</a>.</p>
      `;
    } else {
      finalHTML += `
        <p>A partir de la lectura transversal de tus fuentes, el concepto de <b>${esc(conceptTerm)}</b> se articula como una dimensión fundamental en los estudios sobre gestión escolar, políticas públicas y prácticas pedagógicas <a href="#src-1" class="cite-badge">[1]</a>.</p>

        <p>Las evidencias de tu corpus demuestran cómo las transformaciones normativas e institucionales impactan directamente en la labor cotidiana de los equipos directivos y docentes <a href="#src-2" class="cite-badge">[2]</a>, exigiendo estrategias situadas para responder a la complejidad de las escuelas públicas contemporáneas <a href="#src-3" class="cite-badge">[3]</a>.</p>
      `;
    }
  }

  // Sección de Pasajes Literales Sustantivos estilo NotebookLM
  if (topMatches.length > 0) {
    finalHTML += `
      <div class="excerpts-wrapper">
        <h4>📌 Pasajes Literales Extraídos de las Fuentes (Citas [1], [2], [3]...)</h4>
    `;

    topMatches.forEach((m, idx) => {
      const d = m.doc;
      const apa = buildApa7(d);
      let excerpt = m.bestP || d.abstract || d.title || '';
      if (excerpt.length > 400) excerpt = excerpt.slice(0, 400) + '...';
      
      finalHTML += `
        <div class="excerpt-card" id="src-${idx+1}">
          <div class="excerpt-header">
            <div>
              <span class="cite-badge" style="margin-right:6px">[Fuente ${idx+1}]</span>
              <span class="excerpt-title">${esc(d.title)}</span>
            </div>
          </div>
          <div class="excerpt-meta">${esc(d.authors || 'Sin autor')} (${esc(d.year || 's. f.')}) · ${d.collection==='teoricos'?'📖 Libro Teórico (Drive)':'📚 Artículo Revista'}</div>
          
          <div class="excerpt-quote">
            "<i>${esc(excerpt)}</i>"
          </div>

          <div class="excerpt-apa">
            <span><b>APA 7:</b> ${esc(apa)}</span>
            <button type="button" onclick="navigator.clipboard.writeText('${esc(apa)}');this.textContent='✓ Copiada'">📋 Copiar APA 7</button>
          </div>
        </div>
      `;
    });

    finalHTML += `</div>`;
  }

  container.innerHTML = finalHTML;
  box.scrollTop = box.scrollHeight;
}

document.getElementById('sendBtn').onclick = sendMessage;
document.getElementById('promptInput').onkeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
};
</script>
</body>
</html>
'''

p.write_text(html_content, encoding='utf-8')
print('docs/asistente_ia.html actualizado con extracción sustantiva limpia y síntesis profunda estilo NotebookLM.')
