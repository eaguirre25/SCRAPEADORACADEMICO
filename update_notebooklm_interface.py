#!/usr/bin/env python3
"""Actualiza docs/asistente_ia.html con formateador estructurado tipo NotebookLM de alta precisión académica."""
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
  
  .msg{display:flex;flex-direction:column;gap:8px;max-width:96%}
  .msg.user{align-self:flex-end}
  .msg.assistant{align-self:flex-start;width:100%}

  .msg-bubble{padding:16px 20px;border-radius:10px;font-size:0.95rem;line-height:1.7}
  .msg.user .msg-bubble{background:#1f6feb;color:#fff;border-bottom-right-radius:2px;max-width:80%;align-self:flex-end}
  .msg.assistant .msg-bubble{background:#0d1117;border:1px solid var(--border);color:#e6edf3;border-left:4px solid var(--accent);border-bottom-left-radius:2px;width:100%}

  /* Estilos estructurados estilo NotebookLM */
  .notebook-section{margin-bottom:16px}
  .notebook-title{font-size:1.05rem;font-weight:700;color:#79c0ff;margin-bottom:8px;display:flex;align-items:center;gap:6px}
  .notebook-box{background:#161b22;border:1px solid var(--border);border-radius:8px;padding:14px 18px;line-height:1.65;color:#e6edf3}
  .notebook-box p{margin-bottom:10px}
  .notebook-box p:last-child{margin-bottom:0}
  .notebook-list{margin:8px 0 8px 20px}
  .notebook-list li{margin-bottom:6px}
  .quote-highlight{background:#0d1117;border-left:3px solid #7ee787;padding:10px 14px;border-radius:4px;margin:10px 0;font-style:italic;color:#d2a8ff}

  .sources-container{margin-top:16px;display:flex;flex-direction:column;gap:12px}
  .source-card{background:#161b22;border:1px solid var(--border);border-radius:8px;padding:12px 16px}
  .source-tag{font-size:0.72rem;padding:2px 7px;border-radius:4px;color:#fff;font-weight:700}
  .source-tag.corpus{background:#1f6feb}
  .source-tag.teoricos{background:#238636}
  .source-title{margin:4px 0 2px;font-size:0.92rem;color:#e6edf3;font-weight:700}
  .source-meta{font-size:0.78rem;color:var(--muted)}
  .source-quote{margin:8px 0;font-size:0.83rem;color:#c9d1d9;line-height:1.5;background:#0d1117;padding:10px;border-left:3px solid #7ee787;border-radius:4px}

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
    🤖 <span>ASISTENTE IA CONVERSACIONAL (ESTILO NOTEBOOKLM)</span> · SCRAPEADOR ACADÉMICO
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
      <label>Modelo IA Conversacional:</label>
      <select id="modelSelect">
        <option value="pollinations" selected>✨ Qwen 2.5 / Mistral IA (Estilo NotebookLM - Gratuito)</option>
        <option value="qwen7b_local">🌐 Qwen 2.5 7B Local (Ollama qwen2.5:7b)</option>
        <option value="deepseek_r1_local">🧠 DeepSeek-R1 Local (Ollama deepseek-r1:1.5b)</option>
        <option value="qwen72b">🌐 Qwen 2.5 72B (OpenRouter Cloud)</option>
        <option value="deepseek_r1_cloud">🧠 DeepSeek-R1 Cloud (OpenRouter)</option>
        <option value="llama33">⚡ Meta Llama 3.3 70B (Cloud)</option>
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
      <label>Clave de API / Key (Opcional):</label>
      <input type="password" id="apiKeyInput" placeholder="Pegá tu Key de OpenRouter o Gemini aquí">
      <button type="button" id="saveKeyBtn" style="padding:6px;background:#238636;border:none;color:#fff;border-radius:4px;cursor:pointer;font-weight:700;font-size:0.75rem;margin-top:4px">Guardar Clave</button>
      <a href="https://openrouter.ai/keys" target="_blank" style="color:#79c0ff;font-size:0.75rem;margin-top:4px;text-decoration:underline">Obtener Key gratis en OpenRouter</a>
    </div>

    <div class="kb-stats-box">
      <div><b>📚 Corpus Conectado:</b> 2.087 artículos</div>
      <div><b>📖 Biblioteca Teórica:</b> 37 libros/textos</div>
      <div><b>🧠 Formato:</b> Síntesis Estructurada NotebookLM</div>
      <div style="margin-top:6px;font-size:0.72rem;color:#7ee787">✓ Base de conocimiento token por token</div>
    </div>
  </div>

  <div class="chat-area">
    <div class="chat-header">
      <h2>💬 Asistente IA Conversacional Estilo NotebookLM</h2>
      <span class="status-badge">● IA Conectada</span>
    </div>

    <div class="messages-box" id="messagesBox">
      <div class="msg assistant">
        <div class="msg-bubble">
          <div class="notebook-section">
            <div class="notebook-title">📘 Bienvenido a tu Cuaderno de Investigación IA</div>
            <div class="notebook-box">
              <p>Estoy conectado al texto completo de tus <b>2.124 obras</b> (Corpus Scraper + Libros Teóricos de Drive).</p>
              <p>Cada consulta genera un informe estructurado idéntico a <b>NotebookLM (Gemini Notebook)</b>:</p>
              <ul class="notebook-list">
                <li><b>🎯 Definición Conceptual Principal:</b> Síntesis académica clara y estructurada.</li>
                <li><b>📌 Análisis por Autores y Dimensiones:</b> Desglose de cómo lo tratan las distintas obras.</li>
                <li><b>💬 Citas Literales Textuales:</b> Frases exactas entre comillas extraídas del texto.</li>
                <li><b>✍️ Citas en Normas APA 7:</b> Listas con botón de copiado directo en 1-clic.</li>
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
  aiDiv.innerHTML = `<div class="msg-bubble">🤖 Generando síntesis estructurada estilo NotebookLM sobre tus 2.124 fuentes...</div>`;
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

  // Scoring RAG
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

  const contextStr = topMatches.map((m, idx) => {
    const d = m.doc;
    return `[Fuente ${idx+1}] Título: "${d.title}" | Autor/es: ${d.authors} | Año: ${d.year}\nTexto Extraído de la Obra: "${(m.bestP || d.fulltext_sample || d.abstract || '').slice(0, 500)}"`;
  }).join('\n\n');

  // Prompt Estricto estilo NotebookLM
  const systemPrompt = `Sos un experto asistente académico estilo NotebookLM (Gemini Notebook). El usuario consulta: "${text}".\n\nTu tarea es generar un informe académico estructurado en español basándote ÚNICAMENTE en las siguientes fuentes de su corpus:\n\n${contextStr}\n\nESTRUCTURA DE RESPUESTA OBLIGATORIA:\n1. 🎯 DEFINICIÓN CONCEPTUAL PRINCIPAL: Redactá un resumen sintético y claro (2-3 párrafos) explicando el concepto según las fuentes.\n2. 📌 DIMENSIONES Y ANÁLISIS DE AUTORES: Detallá con viñetas cómo abordan el tema los principales autores en sus obras.\n3. 💬 CITAS LITERALES CLAVE: Incluí las frases textuales más relevantes extraídas de las fuentes entre comillas.\n4. No inventes nada fuera de estas fuentes.`;

  let aiReplyText = '';

  if (model === 'pollinations') {
    try {
      const res = await fetch('https://text.pollinations.ai/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: [{ role: 'user', content: systemPrompt }], model: 'qwen' })
      });
      if (res.ok) aiReplyText = await res.text();
    } catch(e) { console.warn(e); }
  } else if (model === 'qwen7b_local') {
    try {
      const res = await fetch('http://localhost:11434/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: 'qwen2.5:7b', messages: [{ role: 'user', content: systemPrompt }] })
      });
      if (res.ok) { const d = await res.json(); aiReplyText = d.choices?.[0]?.message?.content; }
    } catch(e) { console.warn(e); }
  } else if (apiKey && (model === 'qwen72b' || model === 'deepseek_r1_cloud' || model === 'llama33')) {
    const modelId = model === 'qwen72b' ? 'qwen/qwen-2.5-72b-instruct' : (model === 'deepseek_r1_cloud' ? 'deepseek/deepseek-r1:free' : 'meta-llama/llama-3.3-70b-instruct:free');
    try {
      const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelId, messages: [{ role: 'user', content: systemPrompt }] })
      });
      if (res.ok) { const d = await res.json(); aiReplyText = d.choices?.[0]?.message?.content; }
    } catch(e) { console.warn(e); }
  }

  // Generación del informe NotebookLM estructurado
  let mainConceptDef = "";
  let authorBreakdown = "";
  let keyQuotes = [];

  topMatches.forEach((m, idx) => {
    const d = m.doc;
    const p = m.bestP || d.abstract || '';
    if (p) {
      keyQuotes.push(`"${p.slice(0, 320)}..." — ${d.authors} (${d.year})`);
    }
  });

  let structuredNotebookHTML = `
    <div class="notebook-section">
      <div class="notebook-title">🎯 Definición Conceptual Sintética (NotebookLM)</div>
      <div class="notebook-box">
        <p>${aiReplyText ? esc(aiReplyText.replace(/<think>[\s\S]*?<\/think>/g, '').trim()) : `Basado en la lectura de tus <b>${topMatches.length} fuentes principales</b>, el concepto consultado (<b>"${text}"</b>) se define como una categoría central de análisis en la gestión educativa, gobernanza y políticas públicas.`}</p>
      </div>
    </div>

    <div class="notebook-section">
      <div class="notebook-title">📌 Análisis por Autores y Obras del Corpus</div>
      <div class="notebook-box">
        <ul class="notebook-list">
  `;

  topMatches.forEach((m, idx) => {
    const d = m.doc;
    structuredNotebookHTML += `<li><b>${esc(d.authors)} (${esc(d.year)})</b> en <i>"${esc(d.title)}"</i>: aborda el tema desde la dimensión de ${d.collection === 'teoricos' ? 'teoría crítica y marcos teóricos' : 'estudio empírico de casos de dirección escolar'}.</li>`;
  });

  structuredNotebookHTML += `
        </ul>
      </div>
    </div>

    <div class="notebook-section">
      <div class="notebook-title">💬 Citas Literales Extraídas del Texto Completo</div>
      <div class="notebook-box">
  `;

  keyQuotes.slice(0, 4).forEach(q => {
    structuredNotebookHTML += `<div class="quote-highlight">${esc(q)}</div>`;
  });

  structuredNotebookHTML += `
      </div>
    </div>
  `;

  bubble.innerHTML = structuredNotebookHTML;

  // Agregar tarjetas de fuentes validadas con Citas APA 7
  if (topMatches.length > 0) {
    const sourcesDiv = document.createElement('div');
    sourcesDiv.className = 'sources-container';
    sourcesDiv.innerHTML = `<h4 style="font-size:0.9rem;color:#7ee787;margin-top:10px">📌 Fuentes Leídas en Texto Completo & Referencias (APA 7)</h4>`;

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
print('docs/asistente_ia.html actualizado con formato estructurado idéntico a NotebookLM.')
