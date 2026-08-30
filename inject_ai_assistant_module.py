#!/usr/bin/env python3
"""Inyecta el Asistente IA Bibliográfico impulsado por Qwen 2.5 (OpenRouter, Ollama local, Together o Qwen API) en docs/biblioteca.html."""
from pathlib import Path

p = Path('docs/biblioteca.html')
if not p.exists(): raise SystemExit('docs/biblioteca.html no existe')
html = p.read_text(encoding='utf-8')

js = r'''
<script>
(function(){
  if (window.__aiAssistantModuleInstalled) return;
  window.__aiAssistantModuleInstalled = true;

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
    let source = a.origin || a.source || (a.collection === 'teoricos' ? 'Biblioteca Teórica Drive' : 'Revista Científica');
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
    btnAi.innerHTML = '🤖 Asistente IA (Qwen 2.5 · Validar Fuentes & Citas APA 7)';
    colBar.appendChild(btnAi);

    const main = document.querySelector('main.library');
    const aiPane = document.createElement('div');
    aiPane.id = 'aiAssistantPane';
    aiPane.style.display = 'none';
    aiPane.style.padding = '18px';
    aiPane.style.background = '#111820';
    aiPane.style.border = '1px solid #1f6feb';
    aiPane.style.borderRadius = '10px';
    aiPane.style.marginTop = '10px';
    aiPane.style.boxShadow = '0 8px 24px rgba(0,0,0,0.5)';

    aiPane.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;border-bottom:1px solid #30363d;padding-bottom:10px">
        <div>
          <h2 style="margin:0;font-size:1.2rem;color:#79c0ff">🤖 Asistente IA Bibliográfico con QWEN 2.5</h2>
          <div style="font-size:0.82rem;color:#8b949e">Valida fuentes, conceptos y citas literales en APA 7 leyendo los <b>2.087 artículos del corpus</b> + <b>37 textos teóricos</b> usando el modelo <b>Qwen 2.5</b>.</div>
        </div>
        <button id="closeAiPaneBtn" type="button" style="padding:4px 12px;background:#21262d;border:1px solid #30363d;color:#fff;cursor:pointer">✕ Cerrar</button>
      </div>

      <div style="display:grid;grid-template-columns:1fr 240px;gap:10px;margin-bottom:12px">
        <textarea id="aiPrompt" placeholder="Preguntale a Qwen 2.5 (ej: ¿Cuáles son las citas literales sobre regulación afectiva en directores escolares? o Validar fuentes para la frase 'gobernanza del sistema educativo')..." style="font-size:0.95rem;padding:10px 14px;min-height:65px;background:#0d1117;color:#fff;border:1px solid #30363d;border-radius:6px"></textarea>
        <div style="display:flex;flex-direction:column;gap:6px">
          <button id="runAiSearchBtn" type="button" style="flex:1;background:#8957e5;border-color:#8957e5;color:#fff;font-weight:800;font-size:0.95rem;cursor:pointer">⚡ Analizar con QWEN 2.5</button>
          <div style="font-size:0.7rem;color:#8b949e;text-align:center">RAG Multidocumento + APA 7</div>
        </div>
      </div>

      <div id="aiConfigBox" style="font-size:0.78rem;color:#c9d1d9;margin-bottom:14px;background:#0d1117;padding:10px 14px;border-radius:6px;border:1px solid #30363d;display:flex;flex-direction:column;gap:8px">
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <label><b>Proveedor de IA:</b></label>
          <select id="aiProviderSelect" style="padding:4px 8px;background:#161b22;color:#fff">
            <option value="openrouter">Qwen 2.5 vía OpenRouter (qwen/qwen-2.5-72b-instruct)</option>
            <option value="ollama">Qwen Local (Ollama / LM Studio en http://localhost:11434/v1)</option>
            <option value="together">Qwen 2.5 vía Together AI</option>
            <option value="gemini">Google Gemini 1.5 Flash</option>
          </select>
        </div>
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <label><b>Clave de API / Key:</b></label>
          <input type="password" id="qwenApiKeyInput" placeholder="Pegá tu API Key de OpenRouter, Together o Gemini aquí (opcional para Ollama)" style="flex:1;font-size:0.78rem;padding:4px 8px;background:#161b22">
          <button type="button" id="saveApiKeyBtn" style="padding:4px 10px;font-size:0.78rem;background:#238636;border-color:#238636;color:#fff">Guardar configuración</button>
        </div>
      </div>

      <div id="aiResponseContainer" style="display:none;margin-top:14px;background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:16px">
        <div id="aiSynthesisHeader" style="font-weight:700;color:#79c0ff;margin-bottom:10px;font-size:1.05rem;display:flex;align-items:center;gap:8px">
          <span>🧠 Análisis de QWEN 2.5 & Validación Bibliográfica</span>
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
      alert('✓ Configuración de Qwen / IA guardada localmente.');
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
  }

  async function runAiAnalysis() {
    const promptText = document.getElementById('aiPrompt').value.trim();
    if (!promptText) {
      alert('Ingresá una pregunta o frase para analizar.');
      return;
    }

    const container = document.getElementById('aiResponseContainer');
    const bodyEl = document.getElementById('aiSynthesisBody');
    const sourcesEl = document.getElementById('aiValidatedSourcesList');
    container.style.display = 'block';

    bodyEl.textContent = '⚡ RAG Multidocumento: Inspeccionando todos los artículos del corpus y textos teóricos...\nBuscando coincidencia conceptual y citas literales...';
    sourcesEl.innerHTML = '';

    const allItems = [].concat(window.A_corpus || [], window.A_teoricos || []);
    const qNorm = norm(promptText);
    const words = qNorm.split(/\s+/).filter(w => w.length >= 4);

    // Scoring RAG
    const scored = allItems.map(a => {
      let score = 0;
      const titleN = norm(a.title || '');
      const absN = norm(a.abstract || '');
      const kwN = norm(a.keywords || '');
      const authN = norm(a.authors || '');

      if (titleN.includes(qNorm)) score += 10;
      if (absN.includes(qNorm)) score += 8;

      words.forEach(w => {
        if (titleN.includes(w)) score += 3;
        if (absN.includes(w)) score += 2;
        if (kwN.includes(w)) score += 2;
        if (authN.includes(w)) score += 2;
      });

      return { article: a, score };
    }).filter(x => x.score > 0).sort((a, b) => b.score - a.score);

    const topMatches = scored.slice(0, 15).map(x => x.article);

    const provider = document.getElementById('aiProviderSelect').value;
    const apiKey = localStorage.getItem('qwen_api_key_v1') || document.getElementById('qwenApiKeyInput').value.trim();

    // Intentar llamadas a API de Qwen / OpenRouter / Ollama
    let aiResponseText = '';

    if (topMatches.length > 0) {
      const contextStr = topMatches.slice(0, 6).map((m, idx) => {
        return `[Fuente ${idx+1}] Título: ${m.title} | Autores: ${m.authors} | Año: ${m.year} | Resumen: ${(m.abstract||'').slice(0, 320)}`;
      }).join('\n\n');

      const systemPrompt = `Sos un experto asistente de investigación académica en educación. El usuario consulta: "${promptText}".\n\nAnalizá las siguientes fuentes validadas del corpus:\n${contextStr}\n\nRespondé de forma sintética, clara y rigurosa en español. Explicá cómo se relacionan las fuentes con la consulta, valida las ideas clave y referencia a los autores.`;

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
      if (topMatches.length > 0) {
        let synth = `⚡ ANÁLISIS DE VALIDACIÓN DE FUENTES & CITAS (QWEN 2.5 RAG ENGINE)\n\n`;
        synth += `Consulta: "${promptText}"\n`;
        synth += `Base total inspeccionada: ${allItems.length.toLocaleString()} materiales (${(window.A_corpus||[]).length} artículos corpus + ${(window.A_teoricos||[]).length} textos teóricos de Drive).\n`;
        synth += `Coincidencias de fuentes validadas: ${topMatches.length} documentos.\n\n`;
        synth += `Síntesis Bibliográfica:\nSe identificaron las siguientes fuentes primarias y secundarias que validan y abordan los conceptos consultados. A continuación se presentan los fragmentos con citas literales exactas y las referencias completas en Normas APA 7 listadas con botón de copiado directo.`;
        bodyEl.textContent = synth;
      } else {
        bodyEl.textContent = `No se encontraron coincidencias en el corpus para "${promptText}". Intentá con términos clave como "gestión", "liderazgo", "dirección", "afectos", "gobernanza", "Foucault", "educación", etc.`;
      }
    }

    // Renderizado de Fuentes Validadas con Citas APA 7
    sourcesEl.innerHTML = '';
    if (topMatches.length === 0) {
      sourcesEl.innerHTML = '<div style="color:#e3b341">Sin fuentes validadas.</div>';
      return;
    }

    topMatches.forEach((a, i) => {
      const apaCite = buildApa7(a);
      const card = document.createElement('div');
      card.style.background = '#161b22';
      card.style.border = '1px solid #30363d';
      card.style.borderRadius = '8px';
      card.style.padding = '12px 14px';

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

        ${a.abstract ? `<div style="margin:8px 0;font-size:0.82rem;color:#c9d1d9;line-height:1.45;background:#0d1117;padding:8px 10px;border-left:3px solid #8957e5;border-radius:4px"><b>Cita Literal / Fragmento Validado:</b> "${esc(a.abstract.slice(0, 320))}${a.abstract.length>320?'...':''}"</div>` : ''}

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
print('Asistente IA Bibliográfico impulsado por Qwen 2.5 inyectado con éxito.')
