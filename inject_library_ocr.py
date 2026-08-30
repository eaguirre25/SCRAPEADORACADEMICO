#!/usr/bin/env python3
"""Inyecta revisión/generación OCR en docs/biblioteca.html tras generar la biblioteca."""
from pathlib import Path

p = Path('docs/biblioteca.html')
if not p.exists():
    raise SystemExit('docs/biblioteca.html no existe')

html = p.read_text(encoding='utf-8')

libs = '''\n<script src="https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.min.js"></script>\n<script src="https://cdn.jsdelivr.net/npm/tesseract.js@7/dist/tesseract.min.js"></script>\n'''
if 'tesseract.js@7' not in html:
    html = html.replace('</head>', libs + '</head>')

# Botón contextual en el lector.
needle = '<button onclick="externalOpen()">Abrir original</button>'
button = '<button id="ocrBtn" onclick="reviewOCR()">Revisar / generar OCR</button>' + needle
if 'id="ocrBtn"' not in html and needle in html:
    html = html.replace(needle, button)

ocr_js = r'''
<script>
(function(){
  if (window.__libraryOCRInstalled) return;
  window.__libraryOCRInstalled = true;
  if (window.pdfjsLib) {
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js';
  }

  const OCR_LANGS = {
    spa: {label:'Español', words:[' el ',' la ',' los ',' las ',' de ',' que ',' para ',' una ',' dirección ',' escuela ',' educación ',' escolar ',' desigualdad ',' docente ']},
    eng: {label:'Inglés', words:[' the ',' of ',' and ',' to ',' in ',' school ',' education ',' leadership ',' teachers ',' students ',' policy ']},
    por: {label:'Portugués', words:[' de ',' que ',' para ',' uma ',' escola ',' educação ',' gestão ',' professores ',' alunos ',' ensino ']}
  };

  function inferOCRLanguage(a){
    const raw = (' ' + ((a&&a.title)||'') + ' ' + ((a&&a.abstract)||'') + ' ' + ((a&&a.keywords)||'') + ' ').toLowerCase();
    const scores = {};
    for (const [code,info] of Object.entries(OCR_LANGS)) {
      scores[code] = info.words.reduce((n,w)=>n + (raw.split(w).length-1),0);
    }
    // Acentos distintivos como apoyo cuando hay pocos metadatos.
    scores.spa += (raw.match(/[ñ¿¡]/g)||[]).length * 2;
    scores.por += (raw.match(/[ãõç]/g)||[]).length * 2;
    scores.eng += (raw.match(/\b(the|with|from|between|through)\b/g)||[]).length;
    let code = Object.entries(scores).sort((a,b)=>b[1]-a[1])[0][0];
    if (Math.max(...Object.values(scores)) === 0) code = 'spa';
    return {code, label:OCR_LANGS[code].label, scores};
  }

  function setOCRStatus(msg, cls=''){
    const box = document.getElementById('textCheck');
    if (!box) return;
    box.innerHTML = '<div class="textcheck '+cls+'">'+msg+'</div>';
  }

  function showOCRText(text, langLabel){
    const viewer = document.getElementById('viewer');
    if (!viewer) return;
    viewer.innerHTML = '<div class="fallback" style="white-space:pre-wrap;font-family:Georgia,serif;line-height:1.55"><div style="position:sticky;top:0;background:white;padding:6px 0 10px;font-family:Segoe UI,Arial,sans-serif;font-size:12px;color:#555"><b>Texto OCR · '+langLabel+'</b> · seleccionable y copiable · los separadores indican la página</div>'+escapeOCR(text)+'</div>';
  }

  function escapeOCR(v){
    return (v||'').replace(/[&<>]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[m]));
  }

  async function getPdfSource(a){
    if (!a) throw new Error('No hay artículo seleccionado.');
    const src = a.pdf_url || a.url;
    if (!src) throw new Error('Este registro no tiene URL de PDF disponible.');
    return src;
  }

  async function inspectNativeText(pdf, maxPages=3){
    let chars=0, pages=0;
    for (let n=1;n<=Math.min(pdf.numPages,maxPages);n++){
      const page=await pdf.getPage(n);
      const tc=await page.getTextContent();
      const txt=(tc.items||[]).map(i=>i.str||'').join(' ').trim();
      chars += txt.length; pages++;
    }
    return {chars,pages,avg:pages?chars/pages:0,hasText:pages ? chars/pages >= 120 : false};
  }

  async function extractNativeText(pdf){
    const chunks=[];
    for(let n=1;n<=pdf.numPages;n++){
      setOCRStatus('Extrayendo texto existente · página '+n+' de '+pdf.numPages+'…','ok');
      const page=await pdf.getPage(n);
      const tc=await page.getTextContent();
      const txt=(tc.items||[]).map(i=>i.str||'').join(' ').trim();
      chunks.push('\\n\\n===== PÁGINA '+n+' =====\\n\\n'+txt);
    }
    return chunks.join('');
  }

  async function runOCR(pdf, lang){
    const chunks=[];
    const worker = await Tesseract.createWorker(lang, 1, {
      logger: m => {
        if (m && m.status === 'recognizing text' && typeof m.progress === 'number') {
          const pct=Math.round(m.progress*100);
          setOCRStatus('OCR '+OCR_LANGS[lang].label+' · '+pct+'% de la página actual…','');
        }
      }
    });
    try {
      for(let n=1;n<=pdf.numPages;n++){
        setOCRStatus('OCR '+OCR_LANGS[lang].label+' · página '+n+' de '+pdf.numPages+'…','');
        const page=await pdf.getPage(n);
        const viewport=page.getViewport({scale:1.65});
        const canvas=document.createElement('canvas');
        const ctx=canvas.getContext('2d',{willReadFrequently:true});
        canvas.width=Math.ceil(viewport.width); canvas.height=Math.ceil(viewport.height);
        await page.render({canvasContext:ctx,viewport}).promise;
        const ret=await worker.recognize(canvas);
        const txt=((ret&&ret.data&&ret.data.text)||'').trim();
        chunks.push('\\n\\n===== PÁGINA '+n+' =====\\n\\n'+txt);
        canvas.width=1; canvas.height=1;
      }
    } finally {
      await worker.terminate();
    }
    return chunks.join('');
  }

  window.reviewOCR = async function(){
    if (!window.selected) {
      setOCRStatus('No hay artículo seleccionado.','no'); return;
    }
    const btn=document.getElementById('ocrBtn');
    if(btn){btn.disabled=true;btn.textContent='Revisando OCR…';}
    try{
      if(!window.pdfjsLib || !window.Tesseract) throw new Error('No se pudieron cargar los componentes OCR. Recargá la página.');
      const src=await getPdfSource(window.selected);
      const inferred=inferOCRLanguage(window.selected);
      setOCRStatus('Idioma probable: '+inferred.label+' · verificando capa de texto…','');
      const pdf=await pdfjsLib.getDocument({url:src,withCredentials:false}).promise;
      const native=await inspectNativeText(pdf);
      let text, mode;
      if(native.hasText){
        text=await extractNativeText(pdf);
        mode='texto nativo';
        setOCRStatus('✓ Texto copiable detectado · OCR innecesario · idioma probable: '+inferred.label,'ok');
      }else{
        setOCRStatus('Sin texto suficiente · iniciando OCR en '+inferred.label+'…','no');
        text=await runOCR(pdf,inferred.code);
        mode='ocr';
        setOCRStatus('✓ OCR generado · '+inferred.label+' · '+pdf.numPages+' páginas','ok');
      }
      const fid=(window.id && id(window.selected)) || window.selected.record_id || window.selected.doi || window.selected.title;
      window.F = window.F || {};
      const f={...(F[fid]||{})};
      f.ocr_text=text; f.ocr_language=inferred.code; f.ocr_language_label=inferred.label; f.ocr_mode=mode; f.ocr_pages=pdf.numPages; f.ocr_updated_at=new Date().toISOString();
      F[fid]=f;
      if(typeof saveMaster==='function') await saveMaster();
      showOCRText(text,inferred.label);
    }catch(err){
      console.error(err);
      const msg=(err&&err.message)||String(err);
      setOCRStatus('⚠ No se pudo revisar OCR dentro de la página: '+msg+' Puede deberse a restricciones de acceso/CORS del PDF.','no');
    }finally{
      if(btn){btn.disabled=false;btn.textContent='Revisar / generar OCR';}
    }
  };
})();
</script>
'''

if 'window.__libraryOCRInstalled' not in html:
    html = html.replace('</body>', ocr_js + '\n</body>')

p.write_text(html, encoding='utf-8')
print('OCR interactivo inyectado en docs/biblioteca.html')
