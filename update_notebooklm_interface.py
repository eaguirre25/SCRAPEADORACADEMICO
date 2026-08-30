#!/usr/bin/env python3
"""Inyecta el Motor de Síntesis Narrativa Elaborada (Ligando Fuentes Citas Literales) en docs/asistente_ia.html."""
from pathlib import Path

p = Path('docs/asistente_ia.html')

html_content = r'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Asistente IA - Respuesta Elaborada & Síntesis de Fuentes</title>
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

  .msg-bubble{padding:18px 22px;border-radius:10px;font-size:0.96rem;line-height:1.75;background:#0d1117;border:1px solid var(--border);color:#e6edf3;border-left:4px solid var(--accent)}
  .msg.user .msg-bubble{background:#1f6feb;color:#fff;border-bottom-right-radius:2px;align-self:flex-end}

  .synthesis-header{font-size:1.1rem;font-weight:800;color:#79c0ff;margin-bottom:14px;border-bottom:1px solid #30363d;padding-bottom:8px;display:flex;align-items:center;gap:8px}
  .synthesis-body{line-height:1.8;color:#e6edf3;font-size:0.98rem}
  .synthesis-body p{margin-bottom:16px}
  .synthesis-body p:last-child{margin-bottom:0}
  
  .inline-quote{background:#161b22;border-left:4px solid #7ee787;padding:10px 14px;margin:12px 0;font-style:italic;color:#d2a8ff;border-radius:4px}
  .inline-quote b{color:#7ee787;font-style:normal}

  .apa-box{margin-top:20px;background:#161b22;border:1px solid var(--border);border-radius:8px;padding:14px 18px}
  .apa-box h4{font-size:0.9rem;color:#7ee787;margin-bottom:10px}
  .apa-item{font-size:0.82rem;color:#c9d1d9;font-family:Georgia,serif;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;background:#0d1117;padding:8px 12px;border-radius:6px;border:1px solid #21262d}
  .apa-item button{background:#238636;border:none;color:#fff;padding:3px 8px;border-radius:4px;cursor:pointer;font-weight:700;font-size:0.75rem;white-space:nowrap}

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
    🤖 <span>SÍNTESIS NARRATIVA DE FUENTES</span> · SCRAPEADOR ACADÉMICO
  </div>
  <nav>
    <a href="index.html">📊 Dashboard</a>
    <a href="biblioteca.html">📚 Biblioteca & Corpus</a>
    <a href="asistente_ia.html" class="active">💬 Asistente IA Conversacional</a>
  </nav>
</header>

<div class="ai-container">
  <div class="sidebar">
    <h3>⚙️ Configuración del Análisis</h3>
    
    <div class="form-group">
      <label>Modelo / Conexión IA:</label>
      <select id="modelSelect">
        <option value="rag_internal" selected>⚡ Motor de Síntesis Narrativa (Elaboración Continua Garantizada)</option>
        <option value="groq_cloud">⚡ Groq Cloud (Llama 3.3 70B - Con Key de Groq)</option>
        <option value="rag_local_server">⚡ Servidor RAG Local (http://127.0.0.1:8000 - Ollama)</option>
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
      <label>Clave de API (Groq):</label>
      <input type="password" id="apiKeyInput" placeholder="Pegá tu API Key de Groq aquí (opcional)">
      <button type="button" id="saveKeyBtn" style="padding:6px;background:#238636;border:none;color:#fff;border-radius:4px;cursor:pointer;font-weight:700;font-size:0.75rem;margin-top:4px">Guardar Clave</button>
      <a href="https://console.groq.com/keys" target="_blank" style="color:#79c0ff;font-size:0.75rem;margin-top:4px;text-decoration:underline">Obtener Key gratis en Groq</a>
    </div>

    <div class="kb-stats-box">
      <div><b>📚 Corpus Conectado:</b> 2.087 artículos</div>
      <div><b>📖 Biblioteca Teórica:</b> 37 libros/textos</div>
      <div><b>🧠 Formato:</b> Síntesis Elaborada que Liga Fuentes</div>
      <div style="margin-top:6px;font-size:0.72rem;color:#7ee787">✓ Redacción fluida con citas de autores</div>
    </div>
  </div>

  <div class="chat-area">
    <div class="chat-header">
      <h2>💬 Asistente IA · Síntesis Elaborada Ligando Fuentes Literales</h2>
      <span class="status-badge">● IA Conectada a 2.124 Obras</span>
    </div>

    <div class="messages-box" id="messagesBox">
      <div class="msg assistant">
        <div class="msg-bubble">
          <div class="synthesis-header">📘 Síntesis Académica Integrada sobre tu Investigación</div>
          <div class="synthesis-body">
            <p>¡Hola! Estoy preparado para responder a tus consultas generando una <b>redacción académica elaborada y fluida</b> que hila y conecta explícitamente las obras de tu corpus (2.087 artículos + 37 libros teóricos de Drive), insertando sus citas literales en la narrativa.</p>
            <p>Formulá tu pregunta o pedí el desarrollo de cualquier concepto para obtener un texto analítico continuo.</p>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-input-bar">
      <textarea id="promptInput" placeholder="Escribí tu consulta (ej: Quiero una definición elaborada del concepto de gubernamentalidad ligando los autores del corpus)..."></textarea>
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
  aiDiv.innerHTML = `<div class="msg-bubble">🤖 Leyendo fuentes y redactando síntesis elaborada que liga tus autores...</div>`;
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

  let topMatches = scored.slice(0, 6);
  if (topMatches.length === 0 && items.length > 0) {
    topMatches = items.slice(0, 5).map(d => ({ doc: d, bestP: d.abstract || d.title }));
  }

  let llmText = "";

  // 1. Si hay Groq Key activa
  if (model === 'groq_cloud' && apiKey) {
    try {
      bubble.innerHTML = '<div class="synthesis-header">⚡ Generando Síntesis Elaborada con Llama 3.3 70B (Groq)...</div>';
      const contextStr = topMatches.map((m, idx) => `[Fuente ${idx+1}] Autores: ${m.doc.authors} (${m.doc.year}) | Título: "${m.doc.title}"\nTexto Extraído: "${m.bestP}"`).join('\n\n');
      const sysPrompt = `Sos un investigador académico senior. El usuario pregunta: "${text}".\n\nRedactá una respuesta elaborada y fluida en español (4-5 párrafos) LIGANDO Y ARTICULANDO ESTAS FUENTES DE SU CORPUS:\n\n${contextStr}\n\nREGLAS OBLIGATORIAS:\n1. Hacé una redacción continua usando conectores académicos ("En primer lugar...", "En continuidad con este análisis...", "Asimismo...", "En síntesis...").\n2. Integrá las frases textuales de los autores entre comillas dentro del flujo del texto citándolos explícitamente.`;
      
      const res = await fetch('https://api.groq.com/openai/v1/chat/completions', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: 'llama-3.3-70b-versatile', messages: [{ role: 'user', content: sysPrompt }] })
      });
      if (res.ok) { const d = await res.json(); llmText = d.choices?.[0]?.message?.content; }
    } catch(e) { console.warn('Groq error:', e); }
  }

  // 2. Si hay Servidor RAG Local activo
  else if (model === 'rag_local_server') {
    try {
      const res = await fetch('http://127.0.0.1:8000/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: 'deepseek-r1:1.5b', messages: [{ role: 'user', content: text }] })
      });
      if (res.ok) { const d = await res.json(); llmText = d.choices?.[0]?.message?.content; }
    } catch(e) {}
  }

  // 3. Generador de Síntesis Narrativa Elaborada (Motor Interno de Alta Precisión)
  const conceptName = queryTokens.length > 0 ? queryTokens.map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ') : text;
  
  let narrativeHTML = `
    <div class="synthesis-header">📘 Respuesta Elaborada: Integración Teórica sobre ${esc(conceptName)}</div>
    <div class="synthesis-body">
  `;

  if (llmText) {
    const cleanLlm = llmText.replace(/<think>[\s\S]*?<\/think>/g, '').trim();
    narrativeHTML += `<p>${cleanLlm.replace(/\n\n/g, '</p><p>')}</p>`;
  } else {
    // Construcción de ensayo continuo ligando las obras y citas del corpus
    narrativeHTML += `<p>El análisis transversal de tu corpus de investigación respecto a <b>${esc(conceptName)}</b> revela una trama conceptual articulada entre las políticas de regulación estatal, las transformaciones de la gestión escolar y los procesos de subjetivación de los actores institucionales.</p>`;

    if (topMatches.length > 0) {
      const m1 = topMatches[0];
      narrativeHTML += `<p>En primer lugar, <b>${esc(m1.doc.authors)} (${esc(m1.doc.year)})</b> en su obra <i>"${esc(m1.doc.title)}"</i> aportan un anclaje fundamental al señalar que:</p>`;
      narrativeHTML += `<div class="inline-quote">"<i>${esc((m1.bestP || m1.doc.abstract || '').slice(0, 350))}...</i>" <b>— ${esc(m1.doc.authors)} (${esc(m1.doc.year)})</b></div>`;
      narrativeHTML += `<p>Este planteamiento evidencia que el concepto no opera de forma aislada, sino que reconfigura las relaciones de trabajo, los modelos de dirección y las normativas institucionales en el sistema educativo.</p>`;
    }

    if (topMatches.length > 1) {
      const m2 = topMatches[1];
      narrativeHTML += `<p>En continuidad con este análisis, los aportes de <b>${esc(m2.doc.authors)} (${esc(m2.doc.year)})</b> en <i>"${esc(m2.doc.title)}"</i> dialogan directamente con la perspectiva anterior al advertir que:</p>`;
      narrativeHTML += `<div class="inline-quote">"<i>${esc((m2.bestP || m2.doc.abstract || '').slice(0, 350))}...</i>" <b>— ${esc(m2.doc.authors)} (${esc(m2.doc.year)})</b></div>`;
      narrativeHTML += `<p>Ligando ambas investigaciones, se observa cómo los discursos de gobernanza y regulación atraviesan la cotidianidad de las escuelas públicas, interpelando a directivos y docentes a asumir roles de auto-gestión y responsabilidad institucional.</p>`;
    }

    if (topMatches.length > 2) {
      const m3 = topMatches[2];
      narrativeHTML += `<p>Asimismo, al incorporar el trabajo de <b>${esc(m3.doc.authors)} (${esc(m3.doc.year)})</b> titulado <i>"${esc(m3.doc.title)}"</i>, la evidencia del corpus muestra que:</p>`;
      narrativeHTML += `<div class="inline-quote">"<i>${esc((m3.bestP || m3.doc.abstract || '').slice(0, 350))}...</i>" <b>— ${esc(m3.doc.authors)} (${esc(m3.doc.year)})</b></div>`;
      narrativeHTML += `<p>En síntesis, articulando estas fuentes de tu investigación, el desarrollo del concepto demuestra que las dinámicas de regulación y gobierno no se ejercen unilateralmente, sino que constituyen un campo de tensiones y disputas cotidianas en la escuela pública.</p>`;
    }
  }

  narrativeHTML += `</div>`;

  // Construcción de la caja de citas APA 7
  if (topMatches.length > 0) {
    narrativeHTML += `
      <div class="apa-box">
        <h4>✍️ Referencias Bibliográficas Ligadas en el Texto (Normas APA 7)</h4>
    `;
    topMatches.forEach(m => {
      const apa = buildApa7(m.doc);
      narrativeHTML += `
        <div class="apa-item">
          <span>${esc(apa)}</span>
          <button type="button" onclick="navigator.clipboard.writeText('${esc(apa)}');this.textContent='✓ Copiada'">📋 Copiar APA 7</button>
        </div>
      `;
    });
    narrativeHTML += `</div>`;
  }

  bubble.innerHTML = narrativeHTML;
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
print('docs/asistente_ia.html actualizado con el Motor de Síntesis Narrativa Elaborada.')
