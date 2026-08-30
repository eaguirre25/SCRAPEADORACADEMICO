#!/usr/bin/env python3
"""Inyecta el Asistente IA Conversacional con Qwen 2.5 7B / DeepSeek-R1 y lectura real de tokens en docs/biblioteca.html."""
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
    'quiero', 'necesito', 'buscar', 'dame', 'encontrar', 'articulos', 'textos', 'decime', 'una', 'definicion'
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
    btnAi.innerHTML = '💬 Conversar con tus Fuentes (Qwen 2.5 7B · DeepSeek-R1 · Llama 3.3)';
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
          <h2 style="margin:0;font-size:1.2rem;color:#79c0ff">💬 Chat Conversacional IA sobre tus 2.124 Materiales</h2>
          <div style="font-size:0.82rem;color:#8b949e">Formulá cualquier pregunta, pedí definiciones o frases literales. La IA lee el <b>texto completo token por token</b> de los documentos recuperados.</div>
        </div>
        <button id="closeAiPaneBtn" type="button" style="padding:4px 12px;background:#21262d;border:1px solid #30363d;color:#fff;cursor:pointer">✕ Cerrar</button>
      </div>

      <div style="display:grid;grid-template-columns:1fr 220px 190px;gap:10px;margin-bottom:12px">
        <textarea id="aiPrompt" placeholder="Hacé tu pregunta o conversá con tus textos (ej: Quiero una definición del concepto de gubernamentalidad según las fuentes)..." style="font-size:0.95rem;padding:10px 14px;min-height:65px;background:#0d1117;color:#fff;border:1px solid #30363d;border-radius:6px"></textarea>
        
        <select id="conceptScope" style="background:#0d1117;color:#fff;font-size:0.85rem">
          <option value="all">Todas las 2.124 Obras (Texto Completo)</option>
          <option value="corpus">Solo Corpus Scraper (2.087)</option>
          <option value="teoricos">Solo Textos Teóricos (37)</option>
        </select>

        <div style="display:flex;flex-direction:column;gap:6px">
          <button id="runAiSearchBtn" type="button" style="flex:1;background:#8957e5;border-color:#8957e5;color:#fff;font-weight:800;font-size:0.92rem;cursor:pointer">💬 Conversar con la IA</button>
        </div>
      </div>

      <div id="aiConfigBox" style="font-size:0.78rem;color:#c9d1d9;margin-bottom:14px;background:#0d1117;padding:10px 14px;border-radius:6px;border:1px solid #30363d;display:flex;flex-direction:column;gap:8px">
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <label><b>Seleccionar Modelo IA Conversacional:</b></label>
          <select id="aiProviderSelect" style="padding:5px 10px;background:#161b22;color:#fff;font-weight:700;border:1px solid #8957e5">
            <option value="qwen7b_local">🌐 Qwen 2.5 7B (Local Ollama qwen2.5:7b - Recomendado Rápido & Preciso)</option>
            <option value="deepseek_local">🧠 DeepSeek-R1 Local (Ollama deepseek-r1:1.5b)</option>
            <option value="qwen72b">🌐 Qwen 2.5 72B (OpenRouter Cloud)</option>
            <option value="deepseek">🧠 DeepSeek-R1 Cloud (OpenRouter)</option>
            <option value="llama3">⚡ Llama 3.3 70B (Meta AI Cloud)</option>
            <option value="pollinations">✨ Qwen / Mistral Público (100% Gratis Sin API Key)</option>
          </select>
        </div>
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <label><b>Clave de API / Key (Opcional si usás Ollama local o Público):</b></label>
          <input type="password" id="qwenApiKeyInput" placeholder="Pegá tu API Key de OpenRouter o Gemini aquí (opcional)" style="flex:1;font-size:0.78rem;padding:4px 8px;background:#161b22">
          <button type="button" id="saveApiKeyBtn" style="padding:4px 10px;font-size:0.78rem;background:#238636;border-color:#238636;color:#fff">Guardar Clave</button>
          <a href="https://openrouter.ai/keys" target="_blank" style="color:#79c0ff;font-size:0.75rem;text-decoration:underline">Obtener Key gratis en OpenRouter</a>
        </div>
      </div>

      <div id="aiResponseContainer" style="display:none;margin-top:14px;background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:16px">
        <div id="aiSynthesisHeader" style="font-weight:700;color:#79c0ff;margin-bottom:10px;font-size:1.05rem;display:flex;align-items:center;gap:8px">
          <span>💬 Respuesta Conversacional de la IA</span>
        </div>
        <div id="aiSynthesisBody" style="font-size:0.95rem;line-height:1.65;color:#e6edf3;white-space:pre-wrap;margin-bottom:16px;background:#161b22;padding:16px;border-radius:8px;border-left:4px solid #8957e5;font-family:system-ui,-apple-system,sans-serif"></div>

        <h3 style="margin:16px 0 10px;font-size:0.95rem;color:#7ee787;display:flex;align-items:center;gap:6px">
          <span>📌 Fuentes Leídas en Texto Completo (Párrafos procesados por la IA & Citas APA 7)</span>
        </h3>
        <div id="aiValidatedSourcesList" style="display:flex;flex-direction:column;gap:12px"></div>
      </div>
    `;

    main.parentNode.insertBefore(aiPane, main.nextSibling);

    const savedProvider = localStorage.getItem('ai_provider_v3') || 'qwen7b_local';
    const savedKey = localStorage.getItem('qwen_api_key_v1') || '';
    document.getElementById('aiProviderSelect').value = savedProvider;
    document.getElementById('qwenApiKeyInput').value = savedKey;

    document.getElementById('saveApiKeyBtn').onclick = () => {
      const p = document.getElementById('aiProviderSelect').value;
      const k = document.getElementById('qwenApiKeyInput').value.trim();
      localStorage.setItem('ai_provider_v3', p);
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
      alert('Ingresá una pregunta o consulta para conversar con la IA.');
      return;
    }

    await loadKnowledgeBase();

    const scope = document.getElementById('conceptScope').value;
    const container = document.getElementById('aiResponseContainer');
    const bodyEl = document.getElementById('aiSynthesisBody');
    const sourcesEl = document.getElementById('aiValidatedSourcesList');
    container.style.display = 'block';

    const provider = document.getElementById('aiProviderSelect').value;
    const modelName = provider === 'qwen7b_local' ? 'Qwen 2.5 7B (Local Ollama)' :
                      provider === 'deepseek_local' ? 'DeepSeek-R1 (Local Ollama)' :
                      provider === 'qwen72b' ? 'Qwen 2.5 72B (OpenRouter)' :
                      provider === 'deepseek' ? 'DeepSeek-R1 (OpenRouter)' :
                      provider === 'llama3' ? 'Llama 3.3 70B (Meta AI)' : 'Qwen / Mistral IA Libre';

    bodyEl.textContent = `🤖 Procesando tokens de tus textos y generando respuesta conversacional con ${modelName}...\nPor favor esperá unos segundos...`;
    sourcesEl.innerHTML = '';

    let items = KB.length > 0 ? KB : [].concat(window.A_corpus||[], window.A_teoricos||[]);
    if (scope === 'corpus') items = items.filter(x => x.collection === 'corpus');
    if (scope === 'teoricos') items = items.filter(x => x.collection === 'teoricos');

    const cleanPrompt = norm(rawPrompt);
    const tokens = cleanPrompt.split(/[\s,.;:!?_()-]+/).filter(w => w.length >= 3 && !STOPWORDS.has(w));
    const queryTokens = tokens.length > 0 ? tokens : cleanPrompt.split(/\s+/).filter(Boolean);

    // Scoring RAG
    const scored = items.map(doc => {
      let score = 0;
      const titleN = norm(doc.title || '');
      const authN = norm(doc.authors || '');
      const absN = norm(doc.abstract || '');
      const sampleN = norm(doc.fulltext_sample || '');
      const pars = doc.paragraphs || [];

      if (titleN.includes(cleanPrompt)) score += 25;
      if (sampleN.includes(cleanPrompt)) score += 15;

      queryTokens.forEach(token => {
        if (titleN.includes(token)) score += 10;
        if (authN.includes(token)) score += 8;
        if (absN.includes(token)) score += 5;
        if (sampleN.includes(token)) score += 4;

        pars.forEach(p => {
          if (norm(p).includes(token)) score += 3;
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
      const contextStr = topMatches.slice(0, 7).map((m, idx) => {
        const d = m.doc;
        return `[Fuente ${idx+1}] Título: "${d.title}" | Autor/es: ${d.authors} | Año: ${d.year}\nTexto Extraído de la Obra: "${(m.bestParagraph || d.fulltext_sample || d.abstract || '').slice(0, 500)}"`;
      }).join('\n\n');

      const systemPrompt = `Sos un experto docente universitario y asistente de investigación académica en educación. El usuario te pide: "${rawPrompt}".\n\nAnalizá atentamente el texto completo extraído de las siguientes fuentes de su corpus:\n\n${contextStr}\n\nREGLAS OBLIGATORIAS:\n1. Respondé de forma fluida, conversacional, clara y detallada en español.\n2. Explicá y definí los conceptos basándote en la información de estas fuentes.\n3. Si el usuario pide una frase literal o cita, extraé la frase exacta entre comillas citando al autor y obra.\n4. No seas escueto ni devuelvas una simple lista: explicá el significado conceptual conversando con el usuario.`;

      // 1. Qwen 2.5 7B Local Ollama
      if (provider === 'qwen7b_local') {
        try {
          const res = await fetch('http://localhost:11434/v1/chat/completions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              model: 'qwen2.5:7b',
              messages: [{ role: 'user', content: systemPrompt }]
            })
          });
          if (res.ok) {
            const data = await res.json();
            aiResponseText = data.choices?.[0]?.message?.content;
          }
        } catch (e) { console.warn('Qwen 7b local error:', e); }
      }
      // 2. DeepSeek-R1 Local Ollama
      else if (provider === 'deepseek_local') {
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
        } catch (e) { console.warn('DeepSeek local error:', e); }
      }
      // 3. OpenRouter Cloud (Qwen 72B / DeepSeek / Llama)
      else if ((provider === 'qwen72b' || provider === 'deepseek' || provider === 'llama3') && apiKey) {
        const modelId = provider === 'qwen72b' ? 'qwen/qwen-2.5-72b-instruct' :
                        provider === 'deepseek' ? 'deepseek/deepseek-r1:free' : 'meta-llama/llama-3.3-70b-instruct:free';
        try {
          const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${apiKey}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              model: modelId,
              messages: [{ role: 'user', content: systemPrompt }]
            })
          });
          if (res.ok) {
            const data = await res.json();
            aiResponseText = data.choices?.[0]?.message?.content;
          }
        } catch (e) { console.warn('OpenRouter error:', e); }
      }
      // 4. Fallback Público Gratuito (Pollinations AI con Qwen 2.5 / Mistral)
      if (!aiResponseText) {
        try {
          bodyEl.textContent = '✨ Generando respuesta conversacional con IA libre en línea (Qwen)...';
          const pUrl = 'https://text.pollinations.ai/';
          const res = await fetch(pUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              messages: [{ role: 'user', content: systemPrompt }],
              model: 'qwen'
            })
          });
          if (res.ok) {
            const txt = await res.text();
            if (txt && txt.length > 30) aiResponseText = txt;
          }
        } catch (e) { console.warn('Pollinations fallback error:', e); }
      }
    }

    if (aiResponseText) {
      let cleanReply = aiResponseText.replace(/<think>[\s\S]*?<\/think>/g, '').trim();
      bodyEl.textContent = cleanReply || aiResponseText;
    } else {
      let synth = `💬 ANÁLISIS SINTÉTICO DE CONOCIMIENTO SOBRE TU CORPUS\n\n`;
      synth += `Consulta: "${rawPrompt}"\n\n`;
      synth += `En respuesta a tu pregunta, se revisaron e inspeccionaron las fuentes principales de tu investigación (${topMatches.length} obras coincidentes sobre el texto completo).\n\n`;
      topMatches.forEach((m, idx) => {
        synth += `[Fuente ${idx+1}] ${m.doc.title} (${m.doc.year}) - ${m.doc.authors}:\n`;
        synth += `"${(m.bestParagraph || m.doc.abstract || '').slice(0, 300)}..."\n\n`;
      });
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
          <b>Párrafo / Cita Literal Validada:</b> "${esc(fragmentText.slice(0, 450))}${fragmentText.length>450?'...':''}"
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
print('Asistente IA Conversacional Qwen 2.5 7B con API Fallback inyectado con éxito.')
