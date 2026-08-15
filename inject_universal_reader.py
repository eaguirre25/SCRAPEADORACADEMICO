#!/usr/bin/env python3
"""Inyecta un lector universal: nunca deja el panel vacío y ofrece abstract, PDF/Drive y sitio original."""
from pathlib import Path

p = Path('docs/biblioteca.html')
if not p.exists():
    raise SystemExit('docs/biblioteca.html no existe')
html = p.read_text(encoding='utf-8')

js = r'''
<script>
(function(){
  if (window.__universalReaderInstalled) return;
  window.__universalReaderInstalled = true;

  const previousOpenReader = window.openReader || openReader;

  function e(v){return (v||'').toString().replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
  function articleId(a){return (typeof id==='function') ? id(a) : (a.record_id||a.doi||a.title);}
  function savedText(a){
    try {
      const store = (typeof F!=='undefined') ? F : (window.F||{});
      const f = store[articleId(a)] || {};
      return f.ocr_text || '';
    } catch(err){ return ''; }
  }
  function driveUrl(a){return a.drive_file_id ? 'https://drive.google.com/file/d/'+encodeURIComponent(a.drive_file_id)+'/preview' : '';}
  function directPdf(a){return a.pdf_url || '';}
  function sourceUrl(a){return a.url || (a.doi ? 'https://doi.org/'+a.doi : '');}

  function readingFallback(a){
    const txt=savedText(a);
    if(txt){
      return '<div class="fallback" style="white-space:pre-wrap;font-family:Georgia,serif;line-height:1.65">'
        +'<div style="position:sticky;top:-28px;background:#fff;padding:8px 0 12px;font-family:Segoe UI,Arial,sans-serif;font-size:12px;color:#555;border-bottom:1px solid #ddd">'
        +'<b>Texto completo extraído/OCR</b> · seleccionable y copiable</div>'+e(txt)+'</div>';
    }
    if(a.abstract){
      return '<article class="fallback" style="font-family:Georgia,serif;line-height:1.72">'
        +'<div style="font-family:Segoe UI,Arial,sans-serif;color:#555;font-size:12px;margin-bottom:18px"><b>Resumen disponible</b> · este registro todavía no tiene texto completo interno.</div>'
        +'<h2 style="font-family:Segoe UI,Arial,sans-serif">'+e(a.title)+'</h2>'
        +'<p style="color:#555;font-family:Segoe UI,Arial,sans-serif">'+e(a.authors||'')+(a.year?' · '+e(a.year):'')+'</p>'
        +'<h3 style="font-family:Segoe UI,Arial,sans-serif">Resumen / abstract</h3><p>'+e(a.abstract)+'</p>'
        +(a.keywords?'<h3 style="font-family:Segoe UI,Arial,sans-serif">Palabras clave</h3><p>'+e(a.keywords)+'</p>':'')+'</article>';
    }
    return '<div class="fallback"><h2>'+e(a.title)+'</h2><p>'+e(a.authors||'')+(a.year?' · '+e(a.year):'')+'</p><p>No hay resumen ni texto completo almacenado para este registro. Usá la pestaña <b>Sitio del artículo</b> para consultar la versión disponible en la revista.</p></div>';
  }

  function frame(src, label){
    if(!src) return '<div class="fallback"><h3>'+e(label)+'</h3><p>Esta fuente no está disponible para este registro.</p></div>';
    return '<iframe src="'+e(src)+'" style="width:100%;height:100%;border:0;background:#fff" allow="fullscreen"></iframe>';
  }

  function renderUniversal(a, mode){
    const viewer=document.getElementById('viewer'); if(!viewer) return;
    const drive=driveUrl(a), pdf=directPdf(a), site=sourceUrl(a), hasSaved=!!savedText(a), hasAbstract=!!a.abstract;
    const bar='<div style="height:44px;display:flex;align-items:center;gap:7px;padding:6px 9px;background:#111820;border-bottom:1px solid #30363d;flex-wrap:wrap">'
      +'<button id="uvRead" type="button" style="padding:5px 9px">'+(hasSaved?'Texto completo':'Texto / resumen')+'</button>'
      +(drive||pdf?'<button id="uvPdf" type="button" style="padding:5px 9px">PDF'+(drive?' · Drive':'')+'</button>':'')
      +(site?'<button id="uvSite" type="button" style="padding:5px 9px">Sitio del artículo</button>':'')
      +'<span style="margin-left:auto;color:#8b949e;font-size:11px">'+(hasSaved?'texto interno disponible':hasAbstract?'resumen interno disponible':'solo fuente externa')+'</span></div>';
    let body='';
    if(mode==='pdf') body=drive?frame(drive,'PDF en Google Drive'):frame(pdf,'PDF directo');
    else if(mode==='site') body=frame(site,'Sitio del artículo');
    else body=readingFallback(a);
    viewer.innerHTML='<div style="height:100%;display:flex;flex-direction:column">'+bar+'<div style="flex:1;min-height:0">'+body+'</div></div>';
    const r=document.getElementById('uvRead'); if(r) r.onclick=()=>renderUniversal(a,'read');
    const p=document.getElementById('uvPdf'); if(p) p.onclick=()=>renderUniversal(a,'pdf');
    const s=document.getElementById('uvSite'); if(s) s.onclick=()=>renderUniversal(a,'site');
  }

  window.renderUniversalReader = renderUniversal;

  window.openReader = openReader = function(a){
    window.selected=a;
    previousOpenReader(a);
    // Vista inicial segura: nunca vacía. Si ya hay texto guardado o solo resumen, mostrarlo.
    // Si hay una copia de Drive, ofrecerla a un clic sin abandonar la ficha.
    renderUniversal(a,'read');
    const tc=document.getElementById('textCheck');
    if(tc){
      if(savedText(a)) tc.innerHTML='<div class="textcheck ok">✓ Texto completo interno disponible: podés seleccionar y copiar citas.</div>';
      else if(a.text_status==='ok') tc.innerHTML='<div class="textcheck ok">✓ El extractor detectó texto en el PDF. Podés usar PDF/Drive o generar una copia de texto con OCR/extracción.</div>';
      else if(a.abstract) tc.innerHTML='<div class="textcheck no">Resumen disponible. Para texto completo, probá PDF/Drive o Sitio del artículo.</div>';
      else tc.innerHTML='<div class="textcheck no">Solo hay una fuente externa registrada. Probá Sitio del artículo.</div>';
    }
  };
})();
</script>
'''

if 'window.__universalReaderInstalled' not in html:
    html = html.replace('</body>', js + '\n</body>')
p.write_text(html, encoding='utf-8')
print('Lector universal inyectado')
