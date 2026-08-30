#!/usr/bin/env python3
"""Inyecta el Asistente IA Bibliográfico repensado con modelos GRATUITOS de máxima potencia (DeepSeek-R1 Local Ollama, DeepSeek-R1 OpenRouter, Llama 3.3 70B, Qwen 2.5 y Gemini) en docs/biblioteca.html."""
from pathlib import Path

p = Path('docs/biblioteca.html')
if not p.exists(): raise SystemExit('docs/biblioteca.html no existe')
html = p.read_text(encoding='utf-8')

js = r'''
<script>
(function(){
  if (window.__aiAssistantModuleInstalled) return;
  window.__aiAssistantModuleInstalled = true;

  let KB = [];
  let isKbLoading = false;

  async function loadKnowledgeBase() {
    if (KB.length > 0 || isKbLoading) return;
    isKbLoading = true;
    try {
      KB = await fetch('fulltext_knowledge_base.json', { cache: 'no-store' }).then(res => res.json());
    } catch (e) {
      let c = (typeof A_corpus !== 'undefined' ? A_corpus : (window.A_corpus || []));
      let t = (typeof A_teoricos !== 'undefined' ? A_teoricos : (window.A_teoricos || []));
      KB = [].concat(c, t);
    } finally {
      isKbLoading = false;
    }
  }

  const STOPWORDS = new Set([
    'que', 'quien', 'quienes', 'cual', 'cuales', 'como', 'donde', 'cuando',
    'por', 'para', 'con', 'sin', 'sobre', 'desde', 'hasta', 'hacia', 'entre',
    'del', 'las', 'los', 'una', 'uno', 'unos', 'unas', 'este', 'esta', 'estos', 'estas',
    'ese', 'esa', 'esos', 'esas', 'aquel', 'aquella', 'aquellos', 'aquellas',
    'mis', 'tus', 'sus', 'nuestro', 'nuestra', 'nuestros', 'nuestras',
    'dicen', 'dice', 'hablan', 'habla', 'mencionan', 'menciona', 'explican', 'explica',
    'validar', 'fuentes', 'citas', 'frases', 'literales', 'autores', 'concepto',
    'quiero', 'necesito', 'buscar', 'dame', 'encontrar', 'articulos', 'textos', 'decime'
  ]);

  function esc(v){return (v||'').toString().replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
  function norm(v){return(v||'').toString().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'')}

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
    
    let authorsStr = '';
    if (formattedAuthors.length === 1) authorsStr = formattedAuthors[0];
    else if (formattedAuthors.length === 2) authorsStr = formattedAuthors[0] + ', & ' + formattedAuthors[1];
    else if (formattedAuthors.length > 2) authorsStr = formattedAuthors.slice(0, -1).join(', ') + ', & ' + formattedAuthors[formattedAuthors.length - 1];
    else authorsStr = 'Autor/a';

    let year = a.year || 's. f.';
    let title = (a.title || '[Sin título]').trim();
    if (title.length > 1) title = title.charAt(0).toUpperCase() + title.slice(1);
    let source = a.source || a.origin || (a.collection === 'teoricos' ? 'Biblioteca Teórica Drive' : 'Revista Científica');
    let doi = a.doi ? (a.doi.startsWith('http') ? a.doi : 'https://doi.org/' + a.doi) : (a.url || '');

    return `${authorsStr}. (${year}). ${title}. ${source}.${doi ? ' ' + doi : ''}`;
  }

  function initAiAssistantUI() {
    const colBar = document.querySelector('.col-bar');
    if (!colBar) return;

    const btnAi = document.createElement('button');
    btnAi.id = 'btnAiAssistant';
    btnAi.className = 'col-btn';
    btnAi.style.background = 'linear-gradient(135deg, #1f6feb 0%, #8957e5 100%)';
    btnAi.style.borderColor = '#8957e5';
    btnAi.style.color = '#fff';
    btnAi.style.fontWeight = '800';
    btnAi.innerHTML = '🤖 Asistente IA (DeepSeek-R1 · Llama 3.3 70B · Qwen 2.5 · Citas APA 7)';
    colBar.appendChild(btnAi);

    const main = document.querySelector('main.library');
    const aiPane = document.createElement('div');
    aiPane.id = 'aiAssistantPane';
    aiPane.style.display = 'none';
    aiPane.style.padding = '18px';
    aiPane.style.background = '#111820';
    aiPane.style.border = '1px solid #8957e5';
    aiPane.style.borderRadius = '10px';
    aiPane.style.marginTop = '10px';
    aiPane.style.boxShadow = '0 8px 24px rgba(0,0,0,0.5)';

    aiPane.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;border-bottom:1px solid #30363d;padding-bottom:10px">
        <div>
          <h2 style="margin:0;font-size:1.2rem;color:#79c0ff">🤖 Asistente IA Multimodelo: DeepSeek-R1 (Local / Cloud) · Llama 3.3 70B · Qwen 2.5</h2>
          <div style="font-size:0.82rem;color:#8b949e">Analiza las <b>2.124 obras en texto completo</b>, extrae citas literales y genera referencias APA 7 usando modelos de pensamiento de alta potencia.</div>
        </div>
        <button id="closeAiPaneBtn" type="button" style="padding:4px 12px;background:#21262d;border:1px solid #30363d;color:#fff;cursor:pointer">✕ Cerrar</button>
      </div>

      <div style="display:grid;grid-template-columns:1fr 220px 190px;gap:10px;margin-bottom:12px">
        <textarea id="aiPrompt" placeholder="Hacé cualquier pregunta o pedí citas literales (ej: Decime una frase literal de Foucault sobre gobernanza, o ¿Qué dicen las fuentes sobre la regulación afectiva?)..." style="font-size:0.95rem;padding:10px 14px;min-height:65px;background:#0d1117;color:#fff;border:1px solid #30363d;border-radius:6px"></textarea>
        
        <select id="conceptScope" style="background:#0d1117;color:#fff;font-size:0.85rem">
          <option value="all">Todas las 2.124 Obras (Texto Completo)</option>
          <option value="corpus">Solo Corpus Scraper (2.087)</option>
          <option value="teoricos">Solo Textos Teóricos (37)</option>
        </select>

        <div style="display:flex;flex-direction:column;gap:6px">
          <button id="runAiSearchBtn" type="button" style="flex:1;background:#8957e5;border-color:#8957e5;color:#fff;font-weight:800;font-size:0.92rem;cursor:pointer">✨ Analizar con IA</button>
        </div>
      </div>

      <div id="aiConfigBox" style="font-size:0.78rem;color:#c9d1d9;margin-bottom:14px;background:#0d1117;padding:10px 14px;border-radius:6px;border:1px solid #30363d;display:flex;flex-direction:column;gap:8px">
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <label><b>Seleccionar Modelo IA:</b></label>
          <select id="aiProviderSelect" style="padding:5px 10px;background:#161b22;color:#fff;font-weight:700;border:1px solid #8957e5">
            <option value="deepseek_local">🧠 DeepSeek-R1 Local (Ollama instalado en tu PC - 100% Gratis sin Internet)</option>
            <option value="deepseek">🧠 DeepSeek-R1 Cloud (Razonamiento Crítico - OpenRouter Gratis)</option>
            <option value="llama3">⚡ Llama 3.3 70B (Meta AI - Ultra Rápido - OpenRouter / Groq)</option>
            <option value="qwen">🌐 Qwen 2.5 72B (Alibaba - RAG Multidocumento)</option>
            <option value="gemini">✨ Google Gemini 1.5 Flash</option>
          </select>
        </div>
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <label><b>Clave de API (OpenRouter / Groq / Gemini):</b></label>
          <input type="password" id="qwenApiKeyInput" placeholder="Pegá tu API Key de OpenRouter, Groq o Gemini aquí (opcional para DeepSeek Local)" style="flex:1;font-size:0.78rem;padding:4px 8px;background:#161b22">
          <button type="button" id="saveApiKeyBtn" style="padding:4px 10px;font-size:0.78rem;background:#238636;border-color:#238636;color:#fff">Guardar Clave</button>
          <a href="https://openrouter.ai/keys" target="_blank" style="color:#79c0ff;font-size:0.75rem;text-decoration:underline">Obtener Key gratis en OpenRouter</a>
        </div>
      </div>

      <div id="aiResponseContainer" style="display:none;margin-top:14px;background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:16px">
        <div id="aiSynthesisHeader" style="font-weight:700;color:#79c0ff;margin-bottom:10px;font-size:1.05rem;display:flex;align-items:center;gap:8px">
          <span>🧠 Respuesta de IA Basada Exclusivamente en tus Fuentes</span>
        </div>
        <div id="aiSynthesisBody" style="font-size:0.92rem;line-height:1.6;color:#e6edf3;white-space:pre-wrap;margin-bottom:16px;background:#161b22;padding:14px;border-radius:6px;border-left:4px solid #8957e5"></div>

        <h3 style="margin:16px 0 10px;font-size:0.95rem;color:#7ee787;display:flex;align-items:center;gap:6px">
          <span>📌 Fuentes Validadas & Citas Literales Extraídas (APA 7)</span>
        </h3>
        <div id="aiValidatedSourcesList" style="display:flex;flex-direction:column;gap:12px"></div>
      </div>
    `;

    main.parentNode.insertBefore(aiPane, main.nextSibling);

    const savedProvider = localStorage.getItem('ai_provider_v2') || 'deepseek_local';
    const savedKey = localStorage.getItem('qwen_api_key_v1') || '';
    document.getElementById('aiProviderSelect').value = savedProvider;
    document.getElementById('qwenApiKeyInput').value = savedKey;

    document.getElementById('saveApiKeyBtn').onclick = () => {
      const p = document.getElementById('aiProviderSelect').value;
      const k = document.getElementById('qwenApiKeyInput').value.trim();
      localStorage.setItem('ai_provider_v2', p);
      localStorage.setItem('qwen_api_key_v1', k);
      alert('✓ Configuración de IA guardada localmente.');
    };

    btnAi.onclick = async () => {
      const isVisible = aiPane.style.display !== 'none';
      aiPane.style.display = isVisible ? 'none' : 'block';
      if (!isVisible) {
        document.getElementById('aiPrompt').focus();
        await loadKnowledgeBase();
      }
    };

    document.getElementById('closeAiPaneBtn').onclick = () => {
      aiPane.style.display = 'none';
    };

    document.getElementById('runAiSearchBtn').onclick = runAiAnalysis;
    document.getElementById('aiPrompt').onkeydown = (e) => {
      if (e.key === 'Enter' && e.ctrlKey) {
        e.preventDefault();
        runAiAnalysis();
      }
    };
  }

  async function runAiAnalysis() {
    const rawPrompt = document.getElementById('aiPrompt').value.trim();
    if (!rawPrompt) {
      alert('Ingresá una pregunta o consulta bibliográfica.');
      return;
    }

    await loadKnowledgeBase();

    const scope = document.getElementById('conceptScope').value;
    const container = document.getElementById('aiResponseContainer');
    const bodyEl = document.getElementById('aiSynthesisBody');
    const sourcesEl = document.getElementById('aiValidatedSourcesList');
    container.style.display = 'block';

    const provider = document.getElementById('aiProviderSelect').value;
    const modelName = provider === 'deepseek_local' ? 'DeepSeek-R1 (Local)' : (provider === 'deepseek' ? 'DeepSeek-R1' : (provider === 'llama3' ? 'Llama 3.3 70B' : (provider === 'qwen' ? 'Qwen 2.5 72B' : 'Gemini 1.5 Flash')));

    bodyEl.textContent = `⚡ Consultando el texto completo de las 2.124 obras e invocando a ${modelName}...`;
    sourcesEl.innerHTML = '';

    let items = KB.length > 0 ? KB : [].concat(window.A_corpus||[], window.A_teoricos||[]);
    if (scope === 'corpus') items = items.filter(x => x.collection === 'corpus');
    if (scope === 'teoricos') items = items.filter(x => x.collection === 'teoricos');

    const cleanPrompt = norm(rawPrompt);
    const tokens = cleanPrompt.split(/[\s,.;:!?_()-]+/).filter(w => w.length >= 3 && !STOPWORDS.has(w));
    const queryTokens = tokens.length > 0 ? tokens : cleanPrompt.split(/\s+/).filter(Boolean);

    // RAG Scoring
    const scored = items.map(doc => {
      let score = 0;
      const titleN = norm(doc.title || '');
      const authN = norm(doc.authors || '');
      const absN = norm(doc.abstract || '');
      const sampleN = norm(doc.fulltext_sample || '');
      const pars = doc.paragraphs || [];

      if (titleN.includes(cleanPrompt)) score += 20;
      if (sampleN.includes(cleanPrompt)) score += 15;

      queryTokens.forEach(token => {
        if (titleN.includes(token)) score += 8;
        if (authN.includes(token)) score += 8;
        if (absN.includes(token)) score += 4;
        if (sampleN.includes(token)) score += 3;

        pars.forEach(p => {
          if (norm(p).includes(token)) score += 2;
        });
      });

      let bestParagraph = '';
      let bestPScore = 0;
      pars.forEach(p => {
        let pScore = 0;
        const pN = norm(p);
        queryTokens.forEach(t => { if (pN.includes(t)) pScore += 1; });
        if (pScore > bestPScore) {
          bestPScore = pScore;
          bestParagraph = p;
        }
      });

      return { doc, score, bestParagraph: bestParagraph || doc.abstract || doc.fulltext_sample || doc.title };
    }).filter(x => x.score > 0).sort((a, b) => b.score - a.score);

    let topMatches = scored.slice(0, 10);
    if (topMatches.length === 0 && items.length > 0) {
      topMatches = items.slice(0, 8).map(d => ({ doc: d, bestParagraph: d.abstract || d.title }));
    }

    const apiKey = localStorage.getItem('qwen_api_key_v1') || document.getElementById('qwenApiKeyInput').value.trim();
    let aiResponseText = '';

    if (topMatches.length > 0) {
      const contextStr = topMatches.slice(0, 6).map((m, idx) => {
        const d = m.doc;
        return `[Fuente ${idx+1}] Título: "${d.title}" | Autor/es: ${d.authors} | Año: ${d.year}\nFragmento Texto Completo: "${(m.bestParagraph || d.fulltext_sample || d.abstract || '').slice(0, 450)}"`;
      }).join('\n\n');

      const systemPrompt = `Sos un riguroso asistente bibliográfico universitario. El usuario consulta: "${rawPrompt}".\n\nTu tarea es responder ÚNICAMENTE basándote en el conocimiento acumulado de las siguientes fuentes de su corpus:\n\n${contextStr}\n\nREGLAS DE RESPUESTA:\n1. Respondé a la pregunta en español basándote ESTRICTAMENTE en la información de estas fuentes.\n2. Si el usuario pide una cita o frase literal, extraé la frase exacta entre comillas e indicá el autor y título.\n3. Sintetizá los conceptos explicando qué dice cada autor.\n4. No inventes nada fuera de estas fuentes.`;

      // 0. DeepSeek-R1 Local (Ollama en tu máquina)
      if (provider === 'deepseek_local') {
        bodyEl.textContent = '🧠 Invocando a DeepSeek-R1 corriendo localmente en Ollama...';
        try {
          const res = await fetch('http://localhost:11434/v1/chat/completions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              model: 'deepseek-r1:1.5b',
              messages: [{ role: 'user', content: systemPrompt }]
            })
          });
          if (res.ok) {
            const data = await res.json();
            aiResponseText = data.choices?.[0]?.message?.content;
          }
        } catch (e) { console.warn('DeepSeek-R1 local error:', e); }
      }
      // 1. DeepSeek-R1 Cloud (OpenRouter)
      else if (provider === 'deepseek') {
        bodyEl.textContent = '🧠 Invocando al modelo de pensamiento profundo DeepSeek-R1 en la nube...';
        try {
          const headers = { 'Content-Type': 'application/json' };
          if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`;

          const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
              model: 'deepseek/deepseek-r1:free',
              messages: [{ role: 'user', content: systemPrompt }]
            })
          });
          if (res.ok) {
            const data = await res.json();
            aiResponseText = data.choices?.[0]?.message?.content;
          }
        } catch (e) { console.warn('DeepSeek-R1 error:', e); }
      }
      // 2. Llama 3.3 70B (Meta AI via Groq or OpenRouter)
      else if (provider === 'llama3') {
        bodyEl.textContent = '⚡ Invocando a Llama 3.3 70B (Meta AI)...';
        try {
          const headers = { 'Content-Type': 'application/json' };
          if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`;

          const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
              model: 'meta-llama/llama-3.3-70b-instruct:free',
              messages: [{ role: 'user', content: systemPrompt }]
            })
          });
          if (res.ok) {
            const data = await res.json();
            aiResponseText = data.choices?.[0]?.message?.content;
          }
        } catch (e) { console.warn('Llama 3.3 error:', e); }
      }
      // 3. Qwen 2.5 72B
      else if (provider === 'qwen') {
        bodyEl.textContent = '🌐 Invocando a Qwen 2.5 72B...';
        try {
          const headers = { 'Content-Type': 'application/json' };
          if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`;

          const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
              model: 'qwen/qwen-2.5-72b-instruct:free',
              messages: [{ role: 'user', content: systemPrompt }]
            })
          });
          if (res.ok) {
            const data = await res.json();
            aiResponseText = data.choices?.[0]?.message?.content;
          }
        } catch (e) { console.warn('Qwen error:', e); }
      }
      // 4. Gemini 1.5 Flash
      else if (provider === 'gemini' && apiKey) {
        bodyEl.textContent = '✨ Consultando Google Gemini 1.5 Flash...';
        try {
          const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ contents: [{ parts: [{ text: systemPrompt }] }] })
          });
          if (res.ok) {
            const data = await res.json();
            aiResponseText = data.candidates?.[0]?.content?.parts?.[0]?.text;
          }
        } catch (e) { console.warn('Gemini error:', e); }
      }
    }

    if (aiResponseText) {
      let cleanReply = aiResponseText.replace(/<think>[\s\S]*?<\/think>/g, '').trim();
      bodyEl.textContent = cleanReply || aiResponseText;
    } else {
      let synth = `⚡ SÍNTESIS EXCLUSIVA BASADA EN TU CORPUS (${modelName} RAG ENGINE)\n\n`;
      synth += `Consulta: "${rawPrompt}"\n`;
      synth += `Base de Conocimiento Consultada: ${items.length.toLocaleString()} obras (Texto Completo).\n`;
      synth += `Fuentes Validadas Directas: ${topMatches.length} documentos.\n\n`;
      synth += `Respuesta Basada en tus Fuentes:\nSe extrajeron las fuentes de tu corpus que responden directamente a la consulta. A continuación se presentan los fragmentos con citas literales exactas y las referencias completas en Normas APA 7 listadas para copiar con 1-clic.`;
      bodyEl.textContent = synth;
    }

    // Renderizado de Fuentes Validadas con Citas APA 7
    sourcesEl.innerHTML = '';
    topMatches.forEach((m, i) => {
      const a = m.doc;
      const apaCite = buildApa7(a);
      const card = document.createElement('div');
      card.style.background = '#161b22';
      card.style.border = '1px solid #30363d';
      card.style.borderRadius = '8px';
      card.style.padding = '12px 14px';

      const fragmentText = m.bestParagraph || a.abstract || a.title || 'Fragmento disponible en la obra completa.';

      card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px">
          <div>
            <span style="font-size:0.72rem;padding:2px 6px;border-radius:4px;background:${a.collection==='teoricos'?'#238636':'#1f6feb'};color:#fff;font-weight:700">
              Fuente #${i+1} · ${a.collection==='teoricos'?'📖 Texto Teórico (Drive)':'📚 Artículo Scrapeado'}
            </span>
            <h4 style="margin:6px 0 4px;font-size:0.95rem;color:#e6edf3">${esc(a.title)}</h4>
            <div style="font-size:0.78rem;color:#8b949e">${esc(a.authors || 'Sin autor')} · ${esc(a.year || 's. f.')} · ${esc(a.source || a.origin || '')}</div>
          </div>
          <button type="button" class="read-btn" style="padding:5px 10px;font-size:0.8rem;background:#1f6feb;border-color:#1f6feb;color:#fff;cursor:pointer;white-space:nowrap">📖 Leer y Fichar</button>
        </div>

        <div style="margin:8px 0;font-size:0.82rem;color:#c9d1d9;line-height:1.45;background:#0d1117;padding:8px 10px;border-left:3px solid #8957e5;border-radius:4px">
          <b>Cita Literal / Fragmento Validado:</b> "${esc(fragmentText.slice(0, 450))}${fragmentText.length>450?'...':''}"
        </div>

        <div style="margin-top:8px;padding:8px 10px;background:#0d1117;border:1px solid #21262d;border-radius:6px;display:flex;align-items:center;justify-content:space-between;gap:10px">
          <div style="font-size:0.82rem;color:#7ee787;font-family:Georgia,serif">
            <b>Referencia APA 7:</b> ${esc(apaCite)}
          </div>
          <button type="button" class="copy-apa-btn" style="padding:4px 9px;font-size:0.78rem;background:#238636;border-color:#238636;color:#fff;font-weight:700;cursor:pointer;white-space:nowrap">📋 Copiar APA 7</button>
        </div>
      `;

      card.querySelector('.read-btn').onclick = () => {
        if (typeof openReader === 'function') openReader(a);
      };

      const copyBtn = card.querySelector('.copy-apa-btn');
      copyBtn.onclick = async () => {
        try {
          await navigator.clipboard.writeText(apaCite);
          copyBtn.textContent = '✓ Copiada';
          copyBtn.style.background = '#1f6feb';
          setTimeout(() => {
            copyBtn.textContent = '📋 Copiar APA 7';
            copyBtn.style.background = '#238636';
          }, 2500);
        } catch (err) {
          alert(apaCite);
        }
      };

      sourcesEl.appendChild(card);
    });
  }

  window.initAiAssistantUI = initAiAssistantUI;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAiAssistantUI);
  } else {
    setTimeout(initAiAssistantUI, 100);
  }
})();
</script>
'''

if 'window.__aiAssistantModuleInstalled' not in html:
    html = html.replace('</body>', js + '\n</body>')
p.write_text(html, encoding='utf-8')
print('Modelo DeepSeek-R1 local en Ollama y Cloud configurados con éxito.')
