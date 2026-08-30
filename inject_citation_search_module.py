#!/usr/bin/env python3
"""Inyecta el Módulo de Consulta de Conceptos y Citas en Normas APA 7 en docs/biblioteca.html."""
from pathlib import Path

p = Path('docs/biblioteca.html')
if not p.exists(): raise SystemExit('docs/biblioteca.html no existe')
html = p.read_text(encoding='utf-8')

js = r'''
<script>
(function(){
  if (window.__citationSearchModuleInstalled) return;
  window.__citationSearchModuleInstalled = true;

  function esc(v){return (v||'').toString().replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
  function norm(v){return(v||'').toString().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'')}

  // Formateador de Cita APA 7 para cualquier artículo o libro
  function buildApa7Citation(a) {
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
    
    let source = a.origin || a.source || (a.collection === 'teoricos' ? 'Biblioteca Teórica' : 'Revista científica');
    let doi = a.doi ? (a.doi.startsWith('http') ? a.doi : 'https://doi.org/' + a.doi) : (a.url || '');

    return `${authorsStr}. (${year}). ${title}. ${source}.${doi ? ' ' + doi : ''}`;
  }

  // Inicializar UI del Módulo de Consulta de Citas
  function initCitationSearchUI() {
    const colBar = document.querySelector('.col-bar');
    if (!colBar) return;
    
    // Botón en la barra superior
    const btnSearchModule = document.createElement('button');
    btnSearchModule.id = 'btnSearchModule';
    btnSearchModule.className = 'col-btn';
    btnSearchModule.style.background = '#8957e5';
    btnSearchModule.style.borderColor = '#8957e5';
    btnSearchModule.style.color = '#fff';
    btnSearchModule.innerHTML = '🔍 Buscador de Conceptos & Citas APA 7';
    colBar.appendChild(btnSearchModule);

    // Contenedor principal de la búsqueda
    const main = document.querySelector('main.library');
    const searchPane = document.createElement('div');
    searchPane.id = 'citationSearchPane';
    searchPane.style.display = 'none';
    searchPane.style.padding = '16px';
    searchPane.style.background = '#161b22';
    searchPane.style.border = '1px solid #30363d';
    searchPane.style.borderRadius = '9px';
    searchPane.style.marginTop = '10px';

    searchPane.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <div>
          <h2 style="margin:0;font-size:1.15rem;color:#79c0ff">🔍 Módulo de Consulta Unificada: Conceptos y Citas APA 7</h2>
          <div style="font-size:0.8rem;color:#8b949e">Busca sobre los <b>2.087 artículos del corpus</b> + los <b>37 textos teóricos de Drive</b> y genera la cita APA 7 lista para copiar.</div>
        </div>
        <button id="closeSearchPaneBtn" type="button" style="padding:4px 10px;background:#21262d;border:1px solid #30363d">✕ Cerrar módulo</button>
      </div>

      <div style="display:grid;grid-template-columns:1fr 200px;gap:10px;margin-bottom:14px">
        <input id="conceptQuery" placeholder="Escribí un concepto o frase (ej: @regulación, gobernanza, Foucault, liderazgo, afectos)..." style="font-size:1rem;padding:10px 14px" autofocus>
        <select id="conceptScope">
          <option value="all">Todos los materiales (2.124)</option>
          <option value="corpus">Solo Corpus Scraper (2.087)</option>
          <option value="teoricos">Solo Textos Teóricos (37)</option>
        </select>
      </div>

      <div id="citationResultsCount" style="font-weight:700;font-size:0.85rem;color:#8b949e;margin-bottom:10px"></div>
      <div id="citationResultsList" style="display:flex;flex-direction:column;gap:12px;max-height:65vh;overflow:auto;padding-right:6px"></div>
    `;

    main.parentNode.insertBefore(searchPane, main.nextSibling);

    btnSearchModule.onclick = () => {
      const isVisible = searchPane.style.display !== 'none';
      searchPane.style.display = isVisible ? 'none' : 'block';
      if (!isVisible) {
        document.getElementById('conceptQuery').focus();
        runConceptSearch();
      }
    };

    document.getElementById('closeSearchPaneBtn').onclick = () => {
      searchPane.style.display = 'none';
    };

    document.getElementById('conceptQuery').oninput = runConceptSearch;
    document.getElementById('conceptScope').onchange = runConceptSearch;
  }

  function runConceptSearch() {
    const qStr = norm(document.getElementById('conceptQuery').value.trim());
    const scope = document.getElementById('conceptScope').value;
    const listEl = document.getElementById('citationResultsList');
    const countEl = document.getElementById('citationResultsCount');
    if (!listEl) return;

    let items = [];
    if (scope === 'all' || scope === 'corpus') items = items.concat(window.A_corpus || []);
    if (scope === 'all' || scope === 'teoricos') items = items.concat(window.A_teoricos || []);

    if (!qStr) {
      countEl.textContent = 'Ingresá un término para buscar conceptos y generar citas APA 7.';
      listEl.innerHTML = '<div style="padding:20px;color:#8b949e;text-align:center">Podés buscar palabras clave, conceptos con @ (ej: @regulación), autores o fragmentos de títulos.</div>';
      return;
    }

    const matches = items.filter(a => {
      const textBlock = norm([
        a.title, a.authors, a.abstract, a.keywords, a.origin, a.source, a.doi,
        a.drive_filename || ''
      ].join(' '));
      return textBlock.includes(qStr);
    });

    countEl.textContent = `Se encontraron ${matches.length.toLocaleString()} referencias coincidentes con "${document.getElementById('conceptQuery').value}"`;
    listEl.innerHTML = '';

    if (matches.length === 0) {
      listEl.innerHTML = '<div style="padding:20px;color:#e3b341;text-align:center">No se encontraron coincidencia para este concepto. Intentá con otro término.</div>';
      return;
    }

    matches.slice(0, 100).forEach(a => {
      const apaCite = buildApa7Citation(a);
      const card = document.createElement('div');
      card.style.background = '#0d1117';
      card.style.border = '1px solid #30363d';
      card.style.borderRadius = '8px';
      card.style.padding = '12px 16px';

      card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px">
          <div>
            <span style="font-size:0.75rem;padding:2px 6px;border-radius:4px;background:${a.collection==='teoricos'?'#238636':'#1f6feb'};color:#fff;font-weight:700">
              ${a.collection==='teoricos'?'📖 Texto Teórico (Drive)':'📚 Corpus Scraper'}
            </span>
            <h3 style="margin:6px 0 4px;font-size:1rem;color:#e6edf3">${esc(a.title)}</h3>
            <div style="font-size:0.8rem;color:#8b949e">${esc(a.authors || 'Sin autor')} · ${esc(a.year || 's. f.')} · ${esc(a.origin || a.source || '')}</div>
          </div>
          <button type="button" class="read-btn" style="padding:6px 12px;background:#1f6feb;border-color:#1f6feb;color:#fff;font-weight:600;white-space:nowrap">📖 Leer y Fichar</button>
        </div>

        ${a.abstract ? `<div style="margin:8px 0;font-size:0.82rem;color:#c9d1d9;line-height:1.4;background:#161b22;padding:8px 10px;border-left:3px solid #79c0ff;border-radius:4px"><b>Fragmento / Resumen:</b> ${esc(a.abstract.slice(0, 280))}${a.abstract.length>280?'...':''}</div>` : ''}

        <div style="margin-top:10px;padding:8px 10px;background:#0b1018;border:1px solid #21262d;border-radius:6px;display:flex;align-items:center;justify-content:space-between;gap:10px">
          <div style="font-size:0.83rem;color:#7ee787;font-family:Georgia,serif;line-height:1.4">
            <b>Cita APA 7:</b> ${esc(apaCite)}
          </div>
          <button type="button" class="copy-apa-btn" style="padding:5px 10px;background:#238636;border-color:#238636;color:#fff;font-weight:700;white-space:nowrap">📋 Copiar Cita</button>
        </div>
      `;

      card.querySelector('.read-btn').onclick = () => {
        if (typeof openReader === 'function') openReader(a);
      };

      const copyBtn = card.querySelector('.copy-apa-btn');
      copyBtn.onclick = async () => {
        try {
          await navigator.clipboard.writeText(apaCite);
          copyBtn.textContent = '✓ ¡Copiada!';
          copyBtn.style.background = '#1f6feb';
          setTimeout(() => {
            copyBtn.textContent = '📋 Copiar Cita';
            copyBtn.style.background = '#238636';
          }, 2500);
        } catch (err) {
          alert('Referencia: ' + apaCite);
        }
      };

      listEl.appendChild(card);
    });
  }

  window.initCitationSearchUI = initCitationSearchUI;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCitationSearchUI);
  } else {
    setTimeout(initCitationSearchUI, 100);
  }
})();
</script>
'''

if 'window.__citationSearchModuleInstalled' not in html:
    html = html.replace('</body>', js + '\n</body>')
p.write_text(html, encoding='utf-8')
print('Módulo de Consulta de Conceptos y Citas APA 7 inyectado con éxito.')
