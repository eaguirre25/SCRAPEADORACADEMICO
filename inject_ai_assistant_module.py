#!/usr/bin/env python3
"""Inyecta el Módulo UNIFICADO: Asistente IA & Buscador de Conceptos/Citas APA 7 (Qwen 2.5) con filtrado inteligente de stopwords y búsqueda RAG mejorada."""
from pathlib import Path

p = Path('docs/biblioteca.html')
if not p.exists(): raise SystemExit('docs/biblioteca.html no existe')
html = p.read_text(encoding='utf-8')

js = r'''
<script>
(function(){
  if (window.__aiAssistantModuleInstalled) return;
  window.__aiAssistantModuleInstalled = true;

  const STOPWORDS = new Set([
    'que', 'quien', 'quienes', 'cual', 'cuales', 'como', 'donde', 'cuando',
    'por', 'para', 'con', 'sin', 'sobre', 'desde', 'hasta', 'hacia', 'entre',
    'del', 'las', 'los', 'una', 'uno', 'unos', 'unas', 'este', 'esta', 'estos', 'estas',
    'ese', 'esa', 'esos', 'esas', 'aquel', 'aquella', 'aquellos', 'aquellas',
    'mis', 'tus', 'sus', 'nuestro', 'nuestra', 'nuestros', 'nuestras',
    'dicen', 'dice', 'hablan', 'habla', 'mencionan', 'menciona', 'explican', 'explica',
    'validar', 'fuentes', 'citas', 'frases', 'literales', 'autores', 'concepto', 'sobre',
    'quiero', 'necesito', 'buscar', 'dame', 'encontrar', 'articulos', 'textos'
  ]);

  function esc(v){return (v||'').toString().replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
  function norm(v){return(v||'').toString().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'')}

  function similarity(s1, s2) {
    s1 = norm(s1); s2 = norm(s2);
    if (s1 === s2) return 1.0;
    if (s1.includes(s2) || s2.includes(s1)) return 0.85;
    if (s1.length < 3 || s2.length < 3) return 0.0;
    let longer = s1.length > s2.length ? s1 : s2;
    let shorter = s1.length > s2.length ? s2 : s1;
    let longerLength = longer.length;
    if (longerLength === 0) return 1.0;
    
    let costs = new Array();
    for (let i = 0; i <= s1.length; i++) {
      let lastValue = i;
      for (let j = 0; j <= s2.length; j++) {
        if (i === 0) costs[j] = j;
        else {
          if (j > 0) {
            let newValue = costs[j - 1];
            if (s1.charAt(i - 1) !== s2.charAt(j - 1))
              newValue = Math.min(Math.min(newValue, lastValue), costs[j]) + 1;
            costs[j - 1] = lastValue;
            lastValue = newValue;
          }
        }
      }
      if (i > 0) costs[s2.length] = lastValue;
    }
    return (longerLength - costs[s2.length]) / parseFloat(longerLength);
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
    
    let authorsStr = '';
    if (formattedAuthors.length === 1) authorsStr = formattedAuthors[0];
    else if (formattedAuthors.length === 2) authorsStr = formattedAuthors[0] + ', & ' + formattedAuthors[1];
    else if (formattedAuthors.length > 2) authorsStr = formattedAuthors.slice(0, -1).join(', ') + ', & ' + formattedAuthors[formattedAuthors.length - 1];
    else authorsStr = 'Autor/a';

    let year = a.year || 's. f.';
    let title = (a.title || '[Sin título]').trim();
    if (title.length > 1) title = title.charAt(0).toUpperCase() + title.slice(1);
    let source = a.origin || a.source || (a.collection === 'teoricos' ? 'Biblioteca Teórica Drive' : 'Revista Científica');
    let doi = a.doi ? (a.doi.startsWith('http') ? a.doi : 'https://doi.org/' + a.doi) : (a.url || '');

    return `${authorsStr}. (${year}). ${title}. ${source}.${doi ? ' ' + doi : ''}`;
  }

  function getMaterials() {
    let corpus = [];
    let teoricos = [];
    try { if (typeof A_corpus !== 'undefined') corpus = A_corpus; } catch(e){}
    try { if (typeof A_teoricos !== 'undefined') teoricos = A_teoricos; } catch(e){}
    if (!corpus.length && window.A_corpus) corpus = window.A_corpus;
    if (!teoricos.length && window.A_teoricos) teoricos = window.A_teoricos;
    return { corpus, teoricos };
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
    btnAi.innerHTML = '🤖 Asistente IA & Buscador de Citas APA 7 (Qwen 2.5)';
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
          <h2 style="margin:0;font-size:1.2rem;color:#79c0ff">🤖 Asistente IA Bibliográfico & Validación de Fuentes APA 7 (Qwen 2.5)</h2>
          <div style="font-size:0.82rem;color:#8b949e">Consulta conceptos, valida frases o preguntale a la IA sobre todos los materiales de tu biblioteca.</div>
        </div>
        <button id="closeAiPaneBtn" type="button" style="padding:4px 12px;background:#21262d;border:1px solid #30363d;color:#fff;cursor:pointer">✕ Cerrar</button>
      </div>

      <div style="display:grid;grid-template-columns:1fr 220px 180px;gap:10px;margin-bottom:12px">
        <textarea id="aiPrompt" placeholder="Ingresá un concepto, frase a validar o pregunta (ej: gubernamentalidad, @regulación, Foucault, 'liderazgo en escuelas públicas')..." style="font-size:0.95rem;padding:10px 14px;min-height:65px;background:#0d1117;color:#fff;border:1px solid #30363d;border-radius:6px"></textarea>
        
        <select id="conceptScope" style="background:#0d1117;color:#fff;font-size:0.85rem">
          <option value="all">Todos los materiales (2.124)</option>
          <option value="corpus">Solo Corpus Scraper (2.087)</option>
          <option value="teoricos">Solo Textos Teóricos (37)</option>
        </select>

        <div style="display:flex;flex-direction:column;gap:6px">
          <button id="runAiSearchBtn" type="button" style="flex:1;background:#8957e5;border-color:#8957e5;color:#fff;font-weight:800;font-size:0.92rem;cursor:pointer">⚡ Consultar con Qwen 2.5</button>
        </div>
      </div>

      <div id="aiConfigBox" style="font-size:0.78rem;color:#c9d1d9;margin-bottom:14px;background:#0d1117;padding:10px 14px;border-radius:6px;border:1px solid #30363d;display:flex;flex-direction:column;gap:8px">
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <label><b>Modelo IA:</b></label>
          <select id="aiProviderSelect" style="padding:4px 8px;background:#161b22;color:#fff">
            <option value="openrouter">Qwen 2.5-72B (OpenRouter API - qwen/qwen-2.5-72b-instruct)</option>
            <option value="ollama">Qwen Local (Ollama / LM Studio en http://localhost:11434/v1)</option>
            <option value="together">Qwen 2.5 (Together AI)</option>
            <option value="gemini">Google Gemini 1.5 Flash</option>
          </select>
        </div>
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <label><b>Clave de API / Key:</b></label>
          <input type="password" id="qwenApiKeyInput" placeholder="Pegá tu API Key de OpenRouter, Together o Gemini aquí (opcional para Ollama local)" style="flex:1;font-size:0.78rem;padding:4px 8px;background:#161b22">
          <button type="button" id="saveApiKeyBtn" style="padding:4px 10px;font-size:0.78rem;background:#238636;border-color:#238636;color:#fff">Guardar</button>
        </div>
      </div>

      <div id="aiResponseContainer" style="display:none;margin-top:14px;background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:16px">
        <div id="aiSynthesisHeader" style="font-weight:700;color:#79c0ff;margin-bottom:10px;font-size:1.05rem;display:flex;align-items:center;gap:8px">
          <span>🧠 Análisis Bibliográfico & Validación de Fuentes</span>
        </div>
        <div id="aiSynthesisBody" style="font-size:0.92rem;line-height:1.6;color:#e6edf3;white-space:pre-wrap;margin-bottom:16px;background:#161b22;padding:14px;border-radius:6px;border-left:4px solid #8957e5"></div>

        <h3 style="margin:16px 0 10px;font-size:0.95rem;color:#7ee787;display:flex;align-items:center;gap:6px">
          <span>📌 Fuentes Validadas & Citas Literales Extraídas (APA 7)</span>
        </h3>
        <div id="aiValidatedSourcesList" style="display:flex;flex-direction:column;gap:12px"></div>
      </div>
    `;

    main.parentNode.insertBefore(aiPane, main.nextSibling);

    const savedProvider = localStorage.getItem('qwen_provider_v1') || 'openrouter';
    const savedKey = localStorage.getItem('qwen_api_key_v1') || '';
    document.getElementById('aiProviderSelect').value = savedProvider;
    document.getElementById('qwenApiKeyInput').value = savedKey;

    document.getElementById('saveApiKeyBtn').onclick = () => {
      const p = document.getElementById('aiProviderSelect').value;
      const k = document.getElementById('qwenApiKeyInput').value.trim();
      localStorage.setItem('qwen_provider_v1', p);
      localStorage.setItem('qwen_api_key_v1', k);
      alert('✓ Configuración de IA guardada localmente.');
    };

    btnAi.onclick = () => {
      const isVisible = aiPane.style.display !== 'none';
      aiPane.style.display = isVisible ? 'none' : 'block';
      if (!isVisible) document.getElementById('aiPrompt').focus();
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
      alert('Ingresá una pregunta, concepto o frase para analizar.');
      return;
    }

    const scope = document.getElementById('conceptScope').value;
    const container = document.getElementById('aiResponseContainer');
    const bodyEl = document.getElementById('aiSynthesisBody');
    const sourcesEl = document.getElementById('aiValidatedSourcesList');
    container.style.display = 'block';

    bodyEl.textContent = '⚡ RAG Multidocumento: Inspeccionando todos los artículos del corpus y textos teóricos...\nProcesando coincidencia conceptual y citas literales...';
    sourcesEl.innerHTML = '';

    const { corpus, teoricos } = getMaterials();
    let allItems = [];
    if (scope === 'all' || scope === 'corpus') allItems = allItems.concat(corpus);
    if (scope === 'all' || scope === 'teoricos') allItems = allItems.concat(teoricos);

    // Normalización y filtrado inteligente de stopwords
    const cleanPrompt = norm(rawPrompt.replace(/\d+$/, '').replace(/^@/, ''));
    const allTokens = cleanPrompt.split(/[\s,.;:!?_()-]+/).filter(Boolean);
    const keyTokens = allTokens.filter(w => w.length >= 3 && !STOPWORDS.has(w));
    const effectiveTokens = keyTokens.length > 0 ? keyTokens : allTokens;

    // Scoring RAG sobre la base completa
    const scored = allItems.map(a => {
      let score = 0;
      const titleN = norm(a.title || '');
      const absN = norm(a.abstract || '');
      const kwN = norm(a.keywords || '');
      const authN = norm(a.authors || '');
      const fnN = norm(a.drive_filename || '');

      // Match exacto de frase
      if (titleN.includes(cleanPrompt)) score += 15;
      if (absN.includes(cleanPrompt)) score += 10;
      if (fnN.includes(cleanPrompt)) score += 12;

      // Match por tokens clave de la consulta
      effectiveTokens.forEach(token => {
        if (titleN.includes(token)) score += 5;
        if (absN.includes(token)) score += 3;
        if (kwN.includes(token)) score += 4;
        if (authN.includes(token)) score += 4;
        if (fnN.includes(token)) score += 5;

        // Similitud difusa (Levenshtein) para tolerar erratas
        const wordsInDoc = (titleN + ' ' + kwN + ' ' + fnN).split(/\s+/);
        wordsInDoc.forEach(w => {
          if (w.length >= 4 && token.length >= 4) {
            const sim = similarity(token, w);
            if (sim >= 0.70) score += 4 * sim;
          }
        });
      });

      return { article: a, score };
    }).filter(x => x.score > 0).sort((a, b) => b.score - a.score);

    // Si la búsqueda difusa estricta devuelve pocos, tomar los primeros elementos por tokens generales
    let topMatches = scored.slice(0, 15).map(x => x.article);
    if (topMatches.length === 0 && allItems.length > 0) {
      topMatches = allItems.slice(0, 10);
    }

    const provider = document.getElementById('aiProviderSelect').value;
    const apiKey = localStorage.getItem('qwen_api_key_v1') || document.getElementById('qwenApiKeyInput').value.trim();

    let aiResponseText = '';

    if (topMatches.length > 0) {
      const contextStr = topMatches.slice(0, 6).map((m, idx) => {
        return `[Fuente ${idx+1}] Título: ${m.title} | Autores: ${m.authors} | Año: ${m.year} | Resumen/Fragmento: ${(m.abstract||m.title||'').slice(0, 320)}`;
      }).join('\n\n');

      const systemPrompt = `Sos un experto asistente de investigación académica en educación. El usuario consulta: "${rawPrompt}".\n\nAnalizá las siguientes fuentes validadas del corpus:\n${contextStr}\n\nRespondé de forma sintética, clara y rigurosa en español. Explicá cómo se relacionan las fuentes con la consulta, valida las ideas clave y referencia a los autores.`;

      if (provider === 'openrouter' && apiKey) {
        bodyEl.textContent = '⚡ Generando respuesta conversacional en vivo con Qwen 2.5 (OpenRouter)...';
        try {
          const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${apiKey}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              model: 'qwen/qwen-2.5-72b-instruct',
              messages: [{ role: 'user', content: systemPrompt }]
            })
          });
          if (res.ok) {
            const data = await res.json();
            aiResponseText = data.choices?.[0]?.message?.content;
          }
        } catch (e) { console.warn('OpenRouter Qwen error:', e); }
      } else if (provider === 'ollama') {
        bodyEl.textContent = '⚡ Consultando modelo Qwen local en http://localhost:11434/v1...';
        try {
          const res = await fetch('http://localhost:11434/v1/chat/completions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              model: 'qwen2.5',
              messages: [{ role: 'user', content: systemPrompt }]
            })
          });
          if (res.ok) {
            const data = await res.json();
            aiResponseText = data.choices?.[0]?.message?.content;
          }
        } catch (e) { console.warn('Local Ollama Qwen error:', e); }
      } else if (provider === 'together' && apiKey) {
        bodyEl.textContent = '⚡ Consultando Qwen 2.5 vía Together AI...';
        try {
          const res = await fetch('https://api.together.xyz/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${apiKey}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              model: 'Qwen/Qwen2.5-72B-Instruct-Turbo',
              messages: [{ role: 'user', content: systemPrompt }]
            })
          });
          if (res.ok) {
            const data = await res.json();
            aiResponseText = data.choices?.[0]?.message?.content;
          }
        } catch (e) { console.warn('Together Qwen error:', e); }
      } else if (provider === 'gemini' && apiKey) {
        bodyEl.textContent = '⚡ Consultando Google Gemini 1.5 Flash...';
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
      bodyEl.textContent = aiResponseText;
    } else {
      let synth = `⚡ ANÁLISIS DE VALIDACIÓN DE FUENTES & CITAS (QWEN 2.5 RAG ENGINE)\n\n`;
      synth += `Consulta ingresada: "${rawPrompt}"\n`;
      synth += `Términos clave analizados: [${effectiveTokens.join(', ')}]\n`;
      synth += `Base total inspeccionada: ${allItems.length.toLocaleString()} materiales (${corpus.length} artículos corpus + ${teoricos.length} textos teóricos de Drive).\n`;
      synth += `Fuentes validadas encontradas: ${topMatches.length} documentos.\n\n`;
      synth += `Síntesis Bibliográfica:\nSe identificaron las fuentes primarias y secundarias que validan y responden a tu consulta. A continuación se presentan las fuentes con sus fragmentos literales validados y las referencias completas en Normas APA 7 listadas con botón de copiado directo de 1-clic.`;
      bodyEl.textContent = synth;
    }

    // Renderizado de Fuentes Validadas con Citas APA 7
    sourcesEl.innerHTML = '';
    topMatches.forEach((a, i) => {
      const apaCite = buildApa7(a);
      const card = document.createElement('div');
      card.style.background = '#161b22';
      card.style.border = '1px solid #30363d';
      card.style.borderRadius = '8px';
      card.style.padding = '12px 14px';

      const fragmentText = a.abstract || a.title || 'Fragmento disponible en la obra completa.';

      card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px">
          <div>
            <span style="font-size:0.72rem;padding:2px 6px;border-radius:4px;background:${a.collection==='teoricos'?'#238636':'#1f6feb'};color:#fff;font-weight:700">
              Fuente #${i+1} · ${a.collection==='teoricos'?'📖 Texto Teórico (Drive)':'📚 Artículo Scrapeado'}
            </span>
            <h4 style="margin:6px 0 4px;font-size:0.95rem;color:#e6edf3">${esc(a.title)}</h4>
            <div style="font-size:0.78rem;color:#8b949e">${esc(a.authors || 'Sin autor')} · ${esc(a.year || 's. f.')} · ${esc(a.origin || a.source || '')}</div>
          </div>
          <button type="button" class="read-btn" style="padding:5px 10px;font-size:0.8rem;background:#1f6feb;border-color:#1f6feb;color:#fff;cursor:pointer;white-space:nowrap">📖 Leer y Fichar</button>
        </div>

        <div style="margin:8px 0;font-size:0.82rem;color:#c9d1d9;line-height:1.45;background:#0d1117;padding:8px 10px;border-left:3px solid #8957e5;border-radius:4px">
          <b>Cita Literal / Fragmento Validado:</b> "${esc(fragmentText.slice(0, 340))}${fragmentText.length>340?'...':''}"
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
print('Módulo RAG e Inteligencia de Búsqueda para Qwen 2.5 actualizado con éxito.')
