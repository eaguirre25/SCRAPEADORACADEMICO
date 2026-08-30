#!/usr/bin/env python3
"""Inyecta un lector único: visor PDF embebido (PDF.js / Drive Preview) sin descargas forzadas ni bloqueos de docs.google.com."""
from pathlib import Path

p=Path('docs/biblioteca.html')
if not p.exists(): raise SystemExit('docs/biblioteca.html no existe')
html=p.read_text(encoding='utf-8')

js=r'''
<script>
(function(){
  if(window.__universalReaderInstalled)return; window.__universalReaderInstalled=true;
  const previousOpenReader=window.openReader||openReader;
  const textCache={};
  function e(v){return(v||'').toString().replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
  function articleId(a){return(typeof id==='function')?id(a):(a.record_id||a.doi||a.title)}
  function savedText(a){try{const store=(typeof F!=='undefined')?F:(window.F||{});return(store[articleId(a)]||{}).ocr_text||''}catch(err){return''}}
  async function corpusText(a){
    if(!a.text_file)return'';
    if(textCache[a.text_file]!==undefined)return textCache[a.text_file];
    try{const r=await fetch(a.text_file,{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);const t=await r.text();textCache[a.text_file]=t;return t}catch(err){console.warn('No se pudo cargar texto completo',err);textCache[a.text_file]='';return''}
  }
  function driveUrl(a){return a.drive_preview_url||(a.drive_file_id?'https://drive.google.com/file/d/'+encodeURIComponent(a.drive_file_id)+'/preview':'')}
  function directPdf(a){return a.pdf_url||a.url||''}
  function sourceUrl(a){return a.url||(a.doi?'https://doi.org/'+a.doi:'')}
  function textBody(a,txt,label){
    return '<div class="fallback" style="white-space:pre-wrap;font-family:Georgia,serif;line-height:1.65">'
      +'<div style="position:sticky;top:-28px;background:#fff;padding:8px 0 12px;font-family:Segoe UI,Arial,sans-serif;font-size:12px;color:#555;border-bottom:1px solid #ddd"><b>'+e(label)+'</b> · seleccionable y copiable</div>'+e(txt)+'</div>'
  }
  function abstractBody(a){
    if(a.abstract)return '<article class="fallback" style="font-family:Georgia,serif;line-height:1.72"><div style="font-family:Segoe UI,Arial,sans-serif;color:#555;font-size:12px;margin-bottom:18px"><b>Resumen disponible</b></div><h2 style="font-family:Segoe UI,Arial,sans-serif">'+e(a.title)+'</h2><p style="color:#555;font-family:Segoe UI,Arial,sans-serif">'+e(a.authors||'')+(a.year?' · '+e(a.year):'')+'</p><h3 style="font-family:Segoe UI,Arial,sans-serif">Resumen / abstract</h3><p>'+e(a.abstract)+'</p>'+(a.keywords?'<h3 style="font-family:Segoe UI,Arial,sans-serif">Palabras clave</h3><p>'+e(a.keywords)+'</p>':'')+'</article>';
    return '<div class="fallback"><h2>'+e(a.title)+'</h2><p>'+e(a.authors||'')+(a.year?' · '+e(a.year):'')+'</p><p>No hay resumen ni texto interno para este registro. Probá <b>Sitio del artículo</b>.</p></div>'
  }
  function iframe(src){return '<iframe src="'+e(src)+'" style="width:100%;height:100%;border:0;background:#fff" allow="fullscreen; clipboard-read; clipboard-write"></iframe>'}

  async function renderPdfJsViewer(pdfUrl) {
    const body = document.getElementById('uvBody');
    if (!body) return;
    body.innerHTML = '<div style="height:100%;display:flex;flex-direction:column;background:#323639;color:#e8eaed">'
      +'<div style="padding:6px 12px;background:#202124;border-bottom:1px solid #4a4d51;display:flex;align-items:center;justify-content:space-between;font-size:12px">'
      +'<span id="pdfjsMsg">📄 Carga de PDF embebido (PDF.js)...</span>'
      +'<button type="button" id="pdfjsOpenBtn" style="padding:3px 8px;font-size:11px;background:#3c4043;border:1px solid #5f6368;color:#fff;cursor:pointer">Abrir enlace directo</button>'
      +'</div><div id="pdfjsScroller" style="flex:1;overflow:auto;padding:16px;display:flex;flex-direction:column;align-items:center;gap:16px;background:#525659">'
      +'</div></div>';
    
    const ob = document.getElementById('pdfjsOpenBtn');
    if (ob) ob.onclick = () => window.open(pdfUrl, '_blank');
    
    const scroller = document.getElementById('pdfjsScroller');
    const msg = document.getElementById('pdfjsMsg');

    try {
      if (typeof pdfjsLib === 'undefined') {
        throw new Error('pdfjsLib no cargado');
      }
      pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js';
      
      const loadingTask = pdfjsLib.getDocument({
        url: pdfUrl,
        cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/cmaps/',
        cMapPacked: true
      });
      
      const pdf = await loadingTask.promise;
      if (msg) msg.textContent = `📄 PDF embebido (${pdf.numPages} págs.) · Lectura en visor PDF.js`;

      for (let num = 1; num <= pdf.numPages; num++) {
        const page = await pdf.getPage(num);
        const viewport = page.getViewport({ scale: 1.25 });
        
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.height = viewport.height;
        canvas.width = viewport.width;
        canvas.style.boxShadow = '0 3px 10px rgba(0,0,0,0.4)';
        canvas.style.background = '#ffffff';
        canvas.style.maxWidth = '100%';
        canvas.style.height = 'auto';

        scroller.appendChild(canvas);
        await page.render({ canvasContext: ctx, viewport: viewport }).promise;
      }
    } catch (err) {
      console.warn('CORS / PDF.js render fallback to Mozilla viewer:', err);
      const mozillaViewer = 'https://mozilla.github.io/pdf.js/web/viewer.html?file=' + encodeURIComponent(pdfUrl);
      body.innerHTML = '<iframe src="' + e(mozillaViewer) + '" style="width:100%;height:100%;border:0;background:#fff" allow="fullscreen"></iframe>';
    }
  }

  function pdfBody(a){
    const drive=driveUrl(a),pdf=directPdf(a);
    if(drive){
      const method=a.drive_match_method==='doi_exact'?'DOI exacto':(a.drive_match_method==='strict_title_author_year'?'título + autor + año':'vínculo verificado');
      const fn=a.drive_filename||'archivo de Drive';
      return '<div style="height:100%;display:flex;flex-direction:column;background:#fff">'
        +'<div style="padding:6px 10px;background:#eef7ee;color:#173b17;border-bottom:1px solid #b8d8b8;font:11px Segoe UI,Arial,sans-serif"><b>'+e(fn)+'</b> · '+e(method)+'</div>'
        +'<div style="flex:1;min-height:0">'+iframe(drive)+'</div></div>';
    }
    return '';
  }

  async function renderUniversal(a,mode){
    const viewer=document.getElementById('viewer');if(!viewer)return;
    const drive=driveUrl(a),pdf=directPdf(a),site=sourceUrl(a),local=savedText(a),hasCorpus=!!a.text_file,hasAbstract=!!a.abstract,hasPdf=!!(drive||pdf);
    const bar='<div style="height:44px;display:flex;align-items:center;gap:7px;padding:6px 9px;background:#111820;border-bottom:1px solid #30363d;flex-wrap:wrap">'
      +(hasPdf?'<button id="uvPdf" type="button" style="padding:5px 9px;background:#1f6feb;border-color:#1f6feb;color:#fff"><b>📄 Visor PDF</b></button>':'')
      +'<button id="uvRead" type="button" style="padding:5px 9px">'+(local||hasCorpus?'📝 Texto completo':'📝 Resumen / Texto')+'</button>'
      +(site?'<button id="uvSite" type="button" style="padding:5px 9px">🌐 Sitio de la revista</button>':'')
      +'<span style="margin-left:auto;color:#8b949e;font-size:11px">'+(drive?'PDF en Drive':pdf?'Visor PDF.js (sin descarga)':local||hasCorpus?'texto interno':hasAbstract?'resumen':'fuente externa')+'</span></div>';
    viewer.innerHTML='<div style="height:100%;display:flex;flex-direction:column">'+bar+'<div id="uvBody" style="flex:1;min-height:0"></div></div>';
    const body=document.getElementById('uvBody');
    if(mode==='pdf'){
      if(drive) body.innerHTML=pdfBody(a);
      else if(pdf) renderPdfJsViewer(pdf);
      else body.innerHTML=abstractBody(a);
    }
    else if(mode==='site') body.innerHTML=site?iframe(site):abstractBody(a);
    else if(local) body.innerHTML=textBody(a,local,'Texto completo extraído/OCR');
    else if(hasCorpus){body.innerHTML='<div class="fallback"><p>Cargando texto completo…</p></div>';const txt=await corpusText(a);body.innerHTML=txt?textBody(a,txt,'Texto completo extraído por el scraper'):abstractBody(a)}
    else body.innerHTML=abstractBody(a);

    const r=document.getElementById('uvRead');if(r)r.onclick=()=>renderUniversal(a,'read');
    const p=document.getElementById('uvPdf');if(p)p.onclick=()=>renderUniversal(a,'pdf');
    const s=document.getElementById('uvSite');if(s)s.onclick=()=>renderUniversal(a,'site');
  }
  window.renderUniversalReader=renderUniversal;
  window.openReader=openReader=function(a){
    window.selected=a;previousOpenReader(a);
    const hasPdf=!!(driveUrl(a)||directPdf(a));
    renderUniversal(a,hasPdf?'pdf':'read');
    const tc=document.getElementById('textCheck');
    if(tc){
      if(hasPdf)tc.innerHTML='<div class="textcheck ok">✓ Visor PDF incrustado. Podés leer el trabajo sin salir de la ficha.</div>';
      else if(savedText(a)||a.text_file)tc.innerHTML='<div class="textcheck ok">✓ Texto completo interno disponible: podés seleccionar y copiar citas.</div>';
      else if(a.abstract)tc.innerHTML='<div class="textcheck no">No hay PDF disponible; se muestra el resumen y el acceso al sitio del artículo.</div>';
      else tc.innerHTML='<div class="textcheck no">No hay PDF ni resumen interno; usá Sitio del artículo.</div>';
    }
  }
})();
</script>
'''
if 'window.__universalReaderInstalled' not in html: html=html.replace('</body>',js+'\n</body>')
p.write_text(html,encoding='utf-8')
print('Lector único actualizado con PDF.js (sin bloqueos de Google ni descargas forzadas)')
