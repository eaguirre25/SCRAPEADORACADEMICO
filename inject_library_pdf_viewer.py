#!/usr/bin/env python3
"""Mejora el lector: prioriza la copia del PDF en Google Drive y evita Google Docs Viewer."""
from pathlib import Path

p=Path('docs/biblioteca.html')
if not p.exists(): raise SystemExit('docs/biblioteca.html no existe')
html=p.read_text(encoding='utf-8')

js=r'''
<script>
(function(){
  if(window.__libraryPdfViewerInstalled)return;
  window.__libraryPdfViewerInstalled=true;
  const baseOpenReader=window.openReader||openReader;
  function escV(v){return(v||'').toString().replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
  function currentFicha(a){try{const fid=(typeof id==='function')?id(a):(a.record_id||a.doi||a.title);const store=(typeof F!=='undefined')?F:(window.F||{});return store[fid]||{}}catch(e){return{}}}
  function showSavedText(a){
    const f=currentFicha(a); if(!f.ocr_text)return false;
    const viewer=document.getElementById('viewer'); if(!viewer)return false;
    viewer.innerHTML='<div class="fallback" style="white-space:pre-wrap;font-family:Georgia,serif;line-height:1.58">'
      +'<div style="position:sticky;top:0;background:#fff;padding:8px 0 12px;font-family:Segoe UI,Arial,sans-serif;font-size:12px;color:#555">'
      +'<b>Texto guardado · '+escV(f.ocr_language_label||'texto extraído')+'</b> · seleccionable y copiable</div>'
      +escV(f.ocr_text)+'</div>';
    return true;
  }
  function renderDrive(a){
    const viewer=document.getElementById('viewer'); if(!viewer)return;
    const preview=a.drive_preview_url||(a.drive_file_id?('https://drive.google.com/file/d/'+encodeURIComponent(a.drive_file_id)+'/preview'):'');
    const open=a.drive_open_url||(a.drive_file_id?('https://drive.google.com/file/d/'+encodeURIComponent(a.drive_file_id)+'/view'):'');
    if(!preview){
      viewer.innerHTML='<div class="fallback"><h3>PDF todavía no vinculado a Drive</h3><p>Este registro aún no tiene asociado el ID de su copia en Google Drive. El manifiesto de Drive se está incorporando para que el lector deje de depender del sitio de la revista.</p><p>Mientras tanto podés usar <b>Abrir original</b> o <b>Revisar / generar OCR</b>.</p></div>';
      return;
    }
    viewer.innerHTML='<div style="height:100%;display:flex;flex-direction:column;background:#20242a">'
      +'<div style="padding:7px 10px;background:#111820;border-bottom:1px solid #30363d;display:flex;gap:8px;align-items:center;font-size:12px">'
      +'<span style="color:#7ee787">PDF desde tu Google Drive</span>'
      +(open?'<button type="button" id="openDriveBtn" style="padding:4px 8px">Abrir en Drive</button>':'')
      +'<button type="button" id="savedTextBtn" style="padding:4px 8px">Ver texto guardado</button>'
      +'</div><iframe id="articlePdfFrame" src="'+escV(preview)+'" style="flex:1;width:100%;border:0;background:#fff" allow="fullscreen"></iframe></div>';
    const ob=document.getElementById('openDriveBtn');if(ob)ob.onclick=()=>window.open(open,'_blank');
    const sb=document.getElementById('savedTextBtn');if(sb)sb.onclick=()=>{if(!showSavedText(a)){const tc=document.getElementById('textCheck');if(tc)tc.innerHTML='<div class="textcheck no">Todavía no hay texto guardado para este artículo. Usá “Revisar / generar OCR”.</div>'}};
  }
  window.openReader=openReader=function(a){
    window.selected=a; baseOpenReader(a);
    if(!showSavedText(a))renderDrive(a);
  };
})();
</script>
'''
if 'window.__libraryPdfViewerInstalled' not in html:
    html=html.replace('</body>',js+'\n</body>')
p.write_text(html,encoding='utf-8')
print('Visor de Google Drive inyectado en docs/biblioteca.html')
