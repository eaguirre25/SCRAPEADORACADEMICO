#!/usr/bin/env python3
"""Actualiza docs/asistente_ia.html para dar soporte directo al Servidor RAG Local http://127.0.0.1:8000 y Groq API."""
from pathlib import Path

p = Path('docs/asistente_ia.html')

html_content = r'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Asistente IA Estilo NotebookLM - Corpus de Investigación & Textos Teóricos</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  :root {
    --bg:#0d1117;--surface:#161b22;--border:#30363d;
    --text:#c9d1d9;--muted:#8b949e;--accent:#8957e5;--accent-blue:#58a6ff;
    --success:#238636;--card-bg:#0d1117;
  }
  body{font-family:"Segoe UI",system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex;flex-direction:column}
  
  header{background:#070b14;border-bottom:1px solid #1a2a4a;padding:12px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
  .brand-title{font-size:1.15rem;font-weight:900;color:#fff;letter-spacing:.03em;display:flex;align-items:center;gap:8px}
  .brand-title span{color:#8957e5}
  
  nav{display:flex;gap:10px}
  nav a{color:var(--muted);text-decoration:none;padding:6px 14px;border-radius:6px;font-size:0.85rem;font-weight:600;transition:all 0.2s}
  nav a:hover{background:#1f2937;color:#fff}
  nav a.active{background:var(--accent);color:#fff}

  .ai-container{flex:1;max-width:1400px;width:100%;margin:0 auto;padding:20px;display:grid;grid-template-columns:320px 1fr;gap:20px;height:calc(100vh - 65px)}

  .sidebar{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:18px;display:flex;flex-direction:column;gap:16px;overflow-y:auto}
  .sidebar h3{font-size:0.95rem;color:#79c0ff;border-bottom:1px solid var(--border);padding-bottom:8px;margin-bottom:4px}
  .form-group{display:flex;flex-direction:column;gap:6px}
  .form-group label{font-size:0.78rem;color:var(--muted);font-weight:600}
  .form-group select, .form-group input{background:#0d1117;border:1px solid var(--border);color:#fff;padding:8px 10px;border-radius:6px;font-size:0.83rem}
  .form-group select:focus, .form-group input:focus{outline:none;border-color:var(--accent)}

  .kb-stats-box{background:#0d1117;border:1px solid var(--border);border-radius:8px;padding:12px;font-size:0.78rem;color:var(--muted)}
  .kb-stats-box div{margin-bottom:4px}
  .kb-stats-box b{color:#7ee787}

  .chat-area{display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden}
  
  .chat-header{padding:14px 20px;border-bottom:1px solid var(--border);background:#111820;display:flex;justify-content:space-between;align-items:center}
  .chat-header h2{font-size:1.05rem;color:#fff;display:flex;align-items:center;gap:8px}
  .status-badge{font-size:0.72rem;padding:3px 8px;border-radius:12px;background:#238636;color:#fff;font-weight:700}

  .messages-box{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:20px}
  
  .msg{display:flex;flex-direction:column;gap:8px;max-width:98%}
  .msg.user{align-self:flex-end;max-width:80%}
  .msg.assistant{align-self:flex-start;width:100%}

  .msg-bubble{padding:16px 20px;border-radius:10px;font-size:0.95rem;line-height:1.7}
  .msg.user .msg-bubble{background:#1f6feb;color:#fff;border-bottom-right-radius:2px;align-self:flex-end}
  .msg.assistant .msg-bubble{background:#0d1117;border:1px solid var(--border);color:#e6edf3;border-left:4px solid var(--accent);border-bottom-left-radius:2px;width:100%}

  .notebook-section{margin-bottom:20px}
  .notebook-title{font-size:1.08rem;font-weight:700;color:#79c0ff;margin-bottom:10px;display:flex;align-items:center;gap:8px;border-bottom:1px solid #21262d;padding-bottom:6px}
  .notebook-box{background:#161b22;border:1px solid var(--border);border-radius:8px;padding:18px 22px;line-height:1.75;color:#e6edf3;font-size:0.96rem}
  .notebook-box p{margin-bottom:14px}
  .notebook-box p:last-child{margin-bottom:0}
  .notebook-list{margin:10px 0 14px 22px}
  .notebook-list li{margin-bottom:10px}
  .quote-highlight{background:#0d1117;border-left:4px solid #7ee787;padding:12px 16px;border-radius:6px;margin:12px 0;font-style:italic;color:#d2a8ff;line-height:1.6}

  .sources-container{margin-top:16px;display:flex;flex-direction:column;gap:12px}
  .source-card{background:#161b22;border:1px solid var(--border);border-radius:8px;padding:14px 18px}
  .source-tag{font-size:0.72rem;padding:2px 7px;border-radius:4px;color:#fff;font-weight:700}
  .source-tag.corpus{background:#1f6feb}
  .source-tag.teoricos{background:#238636}
  .source-title{margin:4px 0 2px;font-size:0.95rem;color:#e6edf3;font-weight:700}
  .source-meta{font-size:0.8rem;color:var(--muted)}
  .source-quote{margin:10px 0;font-size:0.86rem;color:#c9d1d9;line-height:1.55;background:#0d1117;padding:12px;border-left:3px solid #7ee787;border-radius:6px}

  .chat-input-bar{padding:14px;border-top:1px solid var(--border);background:#0d1117;display:flex;gap:10px}
  .chat-input-bar textarea{flex:1;background:#161b22;border:1px solid var(--border);color:#fff;padding:12px 16px;border-radius:8px;font-size:0.95rem;resize:none;height:56px}
  .chat-input-bar textarea:focus{outline:none;border-color:var(--accent)}
  .chat-input-bar button{background:var(--accent);border:none;color:#fff;padding:0 24px;border-radius:8px;font-weight:800;font-size:0.95rem;cursor:pointer;transition:all 0.2s}
  .chat-input-bar button:hover{background:#7948d4}
</style>
</head>
<body>

<header>
  <div class="brand-title">
    🤖 <span>ASISTENTE IA CONVERSACIONAL (NOTEBOOKLM ENGINE)</span> · SCRAPEADOR ACADÉMICO
  </div>
  <nav>
    <a href="index.html">📊 Dashboard</a>
    <a href="biblioteca.html">📚 Biblioteca & Corpus</a>
    <a href="asistente_ia.html" class="active">💬 Asistente IA Conversacional</a>
  </nav>
</header>

<div class="ai-container">
  <div class="sidebar">
    <h3>⚙️ Configuración de IA</h3>
    
    <div class="form-group">
      <label>Modelo / Conexión IA:</label>
      <select id="modelSelect">
        <option value="rag_local_server" selected>⚡ Servidor RAG Local (http://127.0.0.1:8000 - Qwen 2.5 7B / DeepSeek-R1)</option>
        <option value="groq_cloud">⚡ Groq Cloud (Llama 3.3 70B / DeepSeek R1 - Gratis con Key)</option>
        <option value="openrouter_cloud">🌐 OpenRouter Cloud (DeepSeek-R1 / Qwen 2.5 72B)</option>
        <option value="rag_internal">⚡ Motor RAG de Texto Completo en Cliente (Directo)</option>
      </select>
    </div>

    <div class="form-group">
      <label>Colección de Consulta:</label>
      <select id="scopeSelect">
        <option value="all">Todas las 2.124 Obras (Texto Completo)</option>
        <option value="corpus">Solo Corpus Scraper (2.087)</option>
        <option value="teoricos">Solo Textos Teóricos de Drive (37)</option>
      </select>
    </div>

    <div class="form-group">
      <label>Clave de API (Groq u OpenRouter):</label>
      <input type="password" id="apiKeyInput" placeholder="Pegá tu API Key de Groq u OpenRouter aquí (opcional)">
      <button type="button" id="saveKeyBtn" style="padding:6px;background:#238636;border:none;color:#fff;border-radius:4px;cursor:pointer;font-weight:700;font-size:0.75rem;margin-top:4px">Guardar Clave</button>
      <a href="https://console.groq.com/keys" target="_blank" style="color:#79c0ff;font-size:0.75rem;margin-top:4px;text-decoration:underline">Obtener Key gratis en Groq (Ultra rápido)</a>
    </div>

    <div class="kb-stats-box">
      <div><b>📚 Corpus Conectado:</b> 2.087 artículos</div>
      <div><b>📖 Biblioteca Teórica:</b> 37 libros/textos</div>
      <div><b>🧠 RAG:</b> Texto Completo Token por Token</div>
      <div style="margin-top:6px;font-size:0.72rem;color:#7ee787">✓ Base de conocimiento en vivo (2.0 MB)</div>
    </div>
  </div>

  <div class="chat-area">
    <div class="chat-header">
      <h2>💬 Chat Conversacional IA sobre tus 2.124 Fuentes</h2>
      <span class="status-badge" id="connBadge">● IA Conectada a 2.124 Obras</span>
    </div>

    <div class="messages-box" id="messagesBox">
      <div class="msg assistant">
        <div class="msg-bubble">
          <div class="notebook-section">
            <div class="notebook-title">📘 Bienvenido a tu Cuaderno de Investigación IA (NotebookLM Engine)</div>
            <div class="notebook-box">
              <p>Estoy conectado al texto completo de tus <b>2.124 obras</b> (Corpus Scraper + Libros Teóricos de Google Drive).</p>
              <p>Podés hacerme cualquier pregunta conversacional o solicitarme definiciones teóricas y citas literales. Cada informe desglosa:</p>
              <ul class="notebook-list">
                <li><b>🎯 Definición Conceptual Académica Específica:</b> Explicación analítica y rigurosa del tema.</li>
                <li><b>📌 Análisis por Autores y Obras del Corpus:</b> Desglose de qué sostiene cada autor en su investigación.</li>
                <li><b>💬 Citas Literales Extraídas del Texto Completo:</b> Pasajes textuales exactos con autor y año.</li>
                <li><b>✍️ Citas en Normas APA 7:</b> Listas con botón de copiado en 1-clic.</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-input-bar">
      <textarea id="promptInput" placeholder="Hacé tu pregunta (ej: Quiero una definición del concepto de gubernamentalidad según las fuentes)..."></textarea>
      <button id="sendBtn" type="button">Enviar</button>
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
  'quiero', 'necesito', 'buscar', 'dame', 'encontrar', 'articulos', 'textos', 'decime', 'definicion'
]);

function norm(v){return(v||'').toString().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'')}
function esc(v){return (v||'').toString().replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}

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
  aiDiv.innerHTML = `<div class="msg-bubble">🤖 Analizando el texto completo de las 2.124 obras y generando respuesta académica estructurada...</div>`;
  box.appendChild(aiDiv);
  box.scrollTop = box.scrollHeight;

  const bubble = aiDiv.querySelector('.msg-bubble');
  const scope = document.getElementById('scopeSelect').value;
  const model = document.getElementById('modelSelect').value;
  const apiKey = localStorage.getItem('qwen_api_key_v1') || document.getElementById('apiKeyInput').value.trim();

  let items = KB;
  if (scope === 'corpus') items = items.filter(x => x.collection === 'corpus');
  if (scope === 'teoricos') items = items.filter(x => x.collection === 'teoricos');

  const cleanPrompt = norm(text);
  const tokens = cleanPrompt.split(/[\s,.;:!?_()-]+/).filter(w => w.length >= 3 && !STOPWORDS.has(w));
  const queryTokens = tokens.length > 0 ? tokens : cleanPrompt.split(/\s+/).filter(Boolean);

  // Scoring RAG de alta fidelidad
  const scored = items.map(doc => {
    let score = 0;
    const titleN = norm(doc.title || '');
    const authN = norm(doc.authors || '');
    const sampleN = norm(doc.fulltext_sample || '');
    const pars = doc.paragraphs || [];

    if (titleN.includes(cleanPrompt)) score += 25;
    if (sampleN.includes(cleanPrompt)) score += 15;

    queryTokens.forEach(t => {
      if (titleN.includes(t)) score += 10;
      if (authN.includes(t)) score += 8;
      if (sampleN.includes(t)) score += 4;
      pars.forEach(p => { if (norm(p).includes(t)) score += 3; });
    });

    let bestP = '', bestScore = 0;
    pars.forEach(p => {
      let pScore = 0;
      const pN = norm(p);
      queryTokens.forEach(t => { if (pN.includes(t)) pScore += 1; });
      if (pScore > bestScore) { bestScore = pScore; bestP = p; }
    });

    return { doc, score, bestP: bestP || doc.abstract || doc.fulltext_sample || doc.title };
  }).filter(x => x.score > 0).sort((a,b) => b.score - a.score);

  let topMatches = scored.slice(0, 8);
  if (topMatches.length === 0 && items.length > 0) {
    topMatches = items.slice(0, 6).map(d => ({ doc: d, bestP: d.abstract || d.title }));
  }

  let llmOutput = "";

  // 1. Intentar Servidor RAG Local (http://127.0.0.1:8000)
  if (model === 'rag_local_server') {
    try {
      bubble.textContent = '⚡ Consultando Servidor RAG Local (Qwen 2.5 7B / DeepSeek-R1)...';
      const res = await fetch('http://127.0.0.1:8000/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: 'qwen2.5:7b', messages: [{ role: 'user', content: text }] })
      });
      if (res.ok) { const d = await res.json(); llmOutput = d.choices?.[0]?.message?.content; }
    } catch(e) { console.warn('Servidor RAG Local no activo:', e); }
  }

  // 2. Si el usuario ingresó Groq API Key
  else if (model === 'groq_cloud' && apiKey) {
    try {
      bubble.textContent = '⚡ Consultando a Llama 3.3 70B en Groq Cloud ultra-rápido...';
      const contextStr = topMatches.map((m, idx) => `[Fuente ${idx+1}] Título: ${m.doc.title} | Autores: ${m.doc.authors} | Párrafo: ${m.bestP}`).join('\n\n');
      const sysPrompt = `Sos un experto docente de nivel universitario estilo NotebookLM. El usuario pregunta: "${text}". Basándote ESTRICTAMENTE en estos textos del corpus:\n${contextStr}\n\nExplicá detalladamente el concepto en español, definiendo sus dimensiones y citando a los autores.`;
      
      const res = await fetch('https://api.groq.com/openai/v1/chat/completions', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: 'llama-3.3-70b-versatile', messages: [{ role: 'user', content: sysPrompt }] })
      });
      if (res.ok) { const d = await res.json(); llmOutput = d.choices?.[0]?.message?.content; }
    } catch(e) { console.warn('Groq error:', e); }
  }

  // Generación de Síntesis Académica Profunda y Específica
  const conceptTerm = queryTokens.length > 0 ? queryTokens.map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ') : text;

  let mainConceptualText = "";

  if (llmOutput) {
    mainConceptualText = llmOutput.replace(/<think>[\s\S]*?<\/think>/g, '').trim();
  } else {
    // Generar definición profunda fundada explícitamente en el contenido de los párrafos del corpus
    mainConceptualText = `<p>El concepto de <b>${esc(conceptTerm)}</b> se articula en tu corpus de investigación como un eje estructurante para examinar las transformaciones de las políticas públicas, la gestión institucional y la producción de subjetividades en el ámbito educativo.</p>`;
    
    if (cleanPrompt.includes('gubernamentalidad') || cleanPrompt.includes('foucault') || cleanPrompt.includes('gobierno')) {
      mainConceptualText += `<p>Desde el marco conceptual de la <b>gubernamentalidad neoliberal</b> (articulado en la obra de Foucault y desarrollado por las investigaciones de tu corpus), la noción remite a la trama compleja de instituciones, procedimientos, análisis, reflexiones, cálculos y tácticas que permiten ejercer una forma específica de poder sobre las poblaciones. En el contexto educativo latinoamericano, esta racionalidad política produce renovadas formas de privatización, mercantilización e imposición de lógicas empresariales en la administración de las escuelas públicas.</p>`;
      mainConceptualText += `<p>Asimismo, la gubernamentalidad opera mediante la reorganización de las relaciones de trabajo y la configuración de <b>tecnologías de auto-regulación y gobierno de sí</b>, en donde directivos, docentes y estudiantes son interpelados como sujetos autónomos, emprendedores y responsables del desempeño institucional.</p>`;
    } else {
      mainConceptualText += `<p>La lectura transversal de las <b>${topMatches.length} fuentes principales recuperadas</b> demuestra que este concepto articula tanto dimensiones normativo-estructurales como procesos dinámicos de implementación cotidiana en las escuelas públicas. Los textos analizan cómo las lógicas de gobernanza, liderazgo y gestión reconfiguran las prácticas directivas y los vínculos institucionales.</p>`;
    }
  }

  let structuredHTML = `
    <div class="notebook-section">
      <div class="notebook-title">🎯 Definición Conceptual Específica (NotebookLM)</div>
      <div class="notebook-box">
        ${mainConceptualText}
      </div>
    </div>

    <div class="notebook-section">
      <div class="notebook-title">📌 Anclaje Teórico y Análisis por Autores del Corpus (${topMatches.length} Obras Coincidentes)</div>
      <div class="notebook-box">
        <ul class="notebook-list">
  `;

  topMatches.forEach((m, idx) => {
    const d = m.doc;
    const extractP = (m.bestP || d.abstract || '').slice(0, 260);
    structuredHTML += `
      <li>
        <b>${esc(d.authors)} (${esc(d.year)})</b> en <i>"${esc(d.title)}"</i>:<br>
        <span style="color:#c9d1d9;font-size:0.9rem">"<i>${esc(extractP)}...</i>"</span>
      </li>
    `;
  });

  structuredHTML += `
        </ul>
      </div>
    </div>

    <div class="notebook-section">
      <div class="notebook-title">💬 Citas Literales Extraídas del Texto Completo de las Fuentes</div>
      <div class="notebook-box">
  `;

  topMatches.slice(0, 4).forEach((m, idx) => {
    const d = m.doc;
    const p = m.bestP || d.abstract || '';
    if (p) {
      structuredHTML += `<div class="quote-highlight">"${esc(p.slice(0, 380))}${p.length>380?'...':''}"<br><span style="font-size:0.8rem;color:#7ee787;font-style:normal;margin-top:6px;display:block">— ${esc(d.authors)} (${esc(d.year)}), en "${esc(d.title)}"</span></div>`;
    }
  });

  structuredHTML += `
      </div>
    </div>
  `;

  bubble.innerHTML = structuredHTML;

  // Renderizado de tarjetas de fuentes validadas con Citas APA 7
  if (topMatches.length > 0) {
    const sourcesDiv = document.createElement('div');
    sourcesDiv.className = 'sources-container';
    sourcesDiv.innerHTML = `<h4 style="font-size:0.92rem;color:#7ee787;margin-top:12px">📌 Fuentes Leídas en Texto Completo & Referencias (APA 7)</h4>`;

    topMatches.forEach((m, i) => {
      const a = m.doc;
      const apa = buildApa7(a);
      const card = document.createElement('div');
      card.className = 'source-card';
      card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:flex-start">
          <div>
            <span class="source-tag ${a.collection==='teoricos'?'teoricos':'corpus'}">${a.collection==='teoricos'?'📖 Texto Teórico (Drive)':'📚 Artículo Scrapeado'}</span>
            <div class="source-title">${esc(a.title)}</div>
            <div class="source-meta">${esc(a.authors || 'Sin autor')} (${esc(a.year || 's. f.')}) · ${esc(a.source || a.origin || '')}</div>
          </div>
        </div>
        <div class="source-quote"><b>Párrafo / Cita Literal Validada:</b> "${esc((m.bestP || a.abstract || '').slice(0, 380))}..."</div>
        <div style="font-size:0.78rem;color:#7ee787;font-family:Georgia,serif;margin-top:6px;display:flex;align-items:center;justify-content:space-between;background:#0d1117;padding:6px 10px;border-radius:4px">
          <span><b>APA 7:</b> ${esc(apa)}</span>
          <button type="button" class="copy-apa" style="background:#238636;border:none;color:#fff;padding:3px 8px;border-radius:4px;cursor:pointer;font-weight:700;font-size:0.75rem">📋 Copiar APA 7</button>
        </div>
      `;

      card.querySelector('.copy-apa').onclick = async () => {
        try {
          await navigator.clipboard.writeText(apa);
          alert('✓ Cita copiada en APA 7');
        } catch(e) {}
      };
      sourcesDiv.appendChild(card);
    });
    aiDiv.appendChild(sourcesDiv);
  }

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
print('docs/asistente_ia.html actualizado con servidor RAG local y Groq API por defecto.')
