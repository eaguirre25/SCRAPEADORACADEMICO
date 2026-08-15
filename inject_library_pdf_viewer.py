#!/usr/bin/env python3
"""Mejora el lector: usa visor embebido alternativo y mantiene OCR disponible."""
from pathlib import Path

p = Path('docs/biblioteca.html')
if not p.exists():
    raise SystemExit('docs/biblioteca.html no existe')

html = p.read_text(encoding='utf-8')

js = r'''
<script>
(function(){
  if (window.__libraryPdfViewerInstalled) return;
  window.__libraryPdfViewerInstalled = true;

  const baseOpenReader = window.openReader || openReader;

  function escapeV(v){
    return (v||'').toString().replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  }

  function showSavedText(a){
    try {
      const fid = (typeof id==='function') ? id(a) : (a.record_id||a.doi||a.title);
      const f = (window.F||F||{})[fid] || {};
      if (f.ocr_text) {
        const viewer=document.getElementById('viewer');
        viewer.innerHTML='<div class="fallback" style="white-space:pre-wrap;font-family:Georgia,serif;line-height:1.55">'
          +'<div style="position:sticky;top:0;background:#fff;padding:8px 0 12px;font-family:Segoe UI,Arial,sans-serif;font-size:12px;color:#555">'
          +'<b>Texto guardado · '+escapeV(f.ocr_language_label||'OCR/texto extraído')+'</b> · seleccionable y copiable'</n          +'</div>'+escapeV(f.ocr_text)+'</div>';
        return true;
      }
    } catch(e) { console.warn(e); }
    return false;
  }

  function renderPdf(a){
    const viewer=document.getElementById('viewer');
    if(!viewer) return;
    const src=a.pdf_url||'';
    if(!src){
      viewer.innerHTML='<div class="fallback"><h3>No hay PDF directo disponible</h3><p>Este registro tiene una página de origen, pero no una URL PDF incrustable. Podés usar <b>Abrir original</b> o <b>Revisar / generar OCR</b> si el PDF está accesible.</p></div>';
      return;
    }
    const google='https://docs.google.com/gview?embedded=1&url='+encodeURIComponent(src);
    viewer.innerHTML='<div style="height:100%;display:flex;flex-direction:column;background:#20242a">'
      +'<div style="padding:7px 10px;background:#111820;border-bottom:1px solid #30363d;display:flex;gap:8px;align-items:center;font-size:12px">'
      +'<span style="color:#8b949e">Visor PDF alternativo</span>'
      +'<button type="button" id="directPdfBtn" style="padding:4px 8px">Probar PDF directo</button>'
      +'<button type="button" id="savedTextBtn" style="padding:4px 8px">Ver texto guardado</button>'
      +'</div>'
      +'<iframe id="articlePdfFrame" src="'+escapeV(google)+'" style="flex:1;width:100%;border:0;background:#fff" allow="fullscreen"></iframe>'
      +'</div>';
    const direct=document.getElementById('directPdfBtn');
    if(direct) direct.onclick=()=>{document.getElementById('articlePdfFrame').src=src;};
    const saved=document.getElementById('savedTextBtn');
    if(saved) saved.onclick=()=>{
      if(!showSavedText(a)){
        const tc=document.getElementById('textCheck');
        if(tc) tc.innerHTML='<div class="textcheck no">Todavía no hay texto OCR guardado para este artículo. Usá “Revisar / generar OCR”.</div>';
      }
    };
  }

  window.openReader = openReader = function(a){
    window.selected=a;
    baseOpenReader(a);
    // Si ya se generó OCR/texto en una sesión anterior, priorizarlo: es lo más fiable para copiar citas.
    if(!showSavedText(a)) renderPdf(a);
  };
})();
</script>
'''

# Corregir accidentalmente una secuencia inválida si esta versión ya existiera.
js = js.replace("+'</n          +", "+")

if 'window.__libraryPdfViewerInstalled' not in html:
    html = html.replace('</body>', js + '\n</body>')

p.write_text(html, encoding='utf-8')
print('Visor PDF alternativo inyectado en docs/biblioteca.html')
