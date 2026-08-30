#!/usr/bin/env python3
"""Inyecta metadatos bibliográficos por tipo de obra y generador APA 7 editable."""
from pathlib import Path

p=Path('docs/biblioteca.html')
if not p.exists(): raise SystemExit('docs/biblioteca.html no existe')
html=p.read_text(encoding='utf-8')

js=r'''
<script>
(function(){
  if(window.__apa7MetadataInstalled) return;
  window.__apa7MetadataInstalled=true;
  const previousOpenReader=window.openReader || openReader;

  function q(sel, root=document){return root.querySelector(sel)}
  function qa(sel, root=document){return [...root.querySelectorAll(sel)]}
  function esc(v){return (v||'').toString().replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
  function aid(a){try{return id(a)}catch(e){return a.record_id||a.doi||a.title}}
  function field(k){return q('[data-k="'+k+'"]')}
  function val(k){const el=field(k); return el?el.value.trim():''}
  function setv(k,v){const el=field(k); if(el && !el.value) el.value=v||''}

  function splitAuthors(raw){
    return (raw||'').split(/\s*;\s*|\s*\|\s*/).map(x=>x.trim()).filter(Boolean);
  }
  function initials(given){
    return (given||'').split(/[\s-]+/).filter(Boolean).map(x=>x.charAt(0).toUpperCase()+'.').join(' ');
  }
  function bestAuthor(name){
    name=(name||'').trim(); if(!name) return '';
    if(name.includes(',')){
      let [sur,...rest]=name.split(','); return sur.trim()+', '+initials(rest.join(' ').trim());
    }
    const t=name.split(/\s+/).filter(Boolean); if(t.length===1) return t[0];
    const particles=new Set(['de','del','la','las','los','da','das','do','dos','di','van','von']);
    let start=Math.max(1,t.length-2);
    while(start>1 && particles.has(t[start-1].toLowerCase())) start--;
    // Si el bloque final contiene partículas hispanas, incluir un apellido previo.
    if(start>1 && t.slice(start).some(x=>particles.has(x.toLowerCase()))) start--;
    const given=t.slice(0,start).join(' '), sur=t.slice(start).join(' ');
    return sur+', '+initials(given);
  }
  function proposedAuthors(raw){return splitAuthors(raw).map(bestAuthor).join('\n')}
  function apaAuthors(raw){
    let arr=(raw||'').split(/\n+/).map(x=>x.trim()).filter(Boolean);
    if(!arr.length) return '';
    if(arr.length===1) return arr[0];
    if(arr.length===2) return arr[0]+', & '+arr[1];
    return arr.slice(0,-1).join(', ')+', & '+arr[arr.length-1];
  }
  function sentenceTitle(s){
    s=(s||'').trim(); if(!s) return '';
    return s.charAt(0).toUpperCase()+s.slice(1);
  }
  function doiUrl(v){
    v=(v||'').trim(); if(!v) return '';
    v=v.replace(/^https?:\/\/(dx\.)?doi\.org\//i,'');
    return 'https://doi.org/'+v;
  }
  function enddot(s){s=(s||'').trim(); return s && !/[.!?]$/.test(s)?s+'.':s}
  function pagesNorm(v){return (v||'').trim().replace(/^pp?\.\s*/i,'')}

  function apa7(){
    const type=val('tipo_publicacion')||'article';
    const authors=apaAuthors(val('autores_apa')) || val('autores');
    const year=val('anio')||'s. f.';
    const title=sentenceTitle(val('titulo'));
    const doi=doiUrl(val('doi'));
    const url=val('url_biblio');
    let out='';
    if(type==='article'){
      const journal=val('revista'), vol=val('volumen'), num=val('numero'), pages=pagesNorm(val('paginas_biblio'));
      out=`${enddot(authors)} (${year}). ${enddot(title)} ${journal}`;
      if(vol) out+=`, ${vol}`;
      if(num) out+=`(${num})`;
      if(pages) out+=`, ${pages}`;
      out+='.';
      if(doi) out+=' '+doi; else if(url) out+=' '+url;
    } else if(type==='thesis'){
      const degree=val('tipo_tesis')||'Tesis'; const inst=val('institucion'); const repo=val('repositorio');
      out=`${enddot(authors)} (${year}). ${title} [${degree}, ${inst||'Institución'}].`;
      if(repo) out+=` ${repo}.`; if(url||doi) out+=' '+(doi||url);
    } else if(type==='book'){
      const edition=val('edicion'), publisher=val('editorial');
      out=`${enddot(authors)} (${year}). ${title}`;
      if(edition) out+=` (${edition})`;
      out+='.'; if(publisher) out+=` ${publisher}.`; if(doi||url) out+=' '+(doi||url);
    } else if(type==='chapter'){
      const eds=val('editores'), book=val('titulo_libro'), pages=pagesNorm(val('paginas_biblio')), publisher=val('editorial');
      out=`${enddot(authors)} (${year}). ${enddot(title)} En ${eds||'Editor/a'} (Ed.), ${book||'Título del libro'}`;
      if(pages) out+=` (pp. ${pages})`; out+='.'; if(publisher) out+=` ${publisher}.`; if(doi||url) out+=' '+(doi||url);
    } else if(type==='report'){
      const org=val('institucion')||val('editorial'); const n=val('numero_informe');
      out=`${enddot(authors||org)} (${year}). ${title}`;
      if(n) out+=` (Informe n.º ${n})`; out+='.'; if(org && authors!==org) out+=` ${org}.`; if(doi||url) out+=' '+(doi||url);
    }
    return out.replace(/\s+/g,' ').replace(/\s+\./g,'.').trim();
  }

  function row(label,k,placeholder=''){
    return `<div class="form bib-extra"><label>${esc(label)}</label><input data-k="${esc(k)}" placeholder="${esc(placeholder)}"></div>`;
  }
  function area(label,k,placeholder=''){
    return `<div class="form bib-extra"><label>${esc(label)}</label><textarea data-k="${esc(k)}" placeholder="${esc(placeholder)}" style="min-height:58px"></textarea></div>`;
  }
  function dynamicFields(type){
    if(type==='article') return `<div class="g2">${row('Revista','revista')}${row('Volumen','volumen')}</div><div class="g2">${row('Número','numero')}${row('Páginas','paginas_biblio','23–41')}</div>`;
    if(type==='thesis') return `<div class="g2">${row('Tipo de tesis','tipo_tesis','Tesis doctoral / Tesis de maestría')}${row('Institución','institucion')}</div><div class="g2">${row('Repositorio','repositorio')}${row('URL','url_biblio')}</div>`;
    if(type==='book') return `<div class="g2">${row('Editorial','editorial')}${row('Edición','edicion','2.ª ed.')}</div>${row('URL','url_biblio')}`;
    if(type==='chapter') return `${area('Editor/es del libro (formato APA)','editores','Apellido, N. N.; Apellido, N. N.')}${row('Título del libro','titulo_libro')}<div class="g2">${row('Páginas del capítulo','paginas_biblio','23–41')}${row('Editorial','editorial')}</div>${row('URL','url_biblio')}`;
    return `<div class="g2">${row('Institución / organismo','institucion')}${row('Número de informe','numero_informe')}</div>${row('URL','url_biblio')}`;
  }

  function install(a){
    const sheet=document.getElementById('sheet'); if(!sheet) return;
    const apa=field('apa'); if(!apa) return;
    // Quitar una instalación anterior al reabrir/cambiar registro.
    qa('.apa7-added',sheet).forEach(x=>x.remove());
    const f=(typeof F!=='undefined' ? F[aid(a)] : null)||{};
    const wrap=document.createElement('div'); wrap.className='apa7-added';
    wrap.innerHTML=`
      <h2 style="margin-top:4px">Metadatos bibliográficos</h2>
      <div class="form"><label>Tipo de publicación</label><select data-k="tipo_publicacion" id="tipoPublicacionApa">
        <option value="article">Artículo de revista</option><option value="thesis">Tesis</option><option value="book">Libro</option><option value="chapter">Capítulo de libro</option><option value="report">Informe / documento</option>
      </select></div>
      <div class="form"><label>Autores para APA 7 · uno por línea, en formato Apellido, Iniciales</label><textarea data-k="autores_apa" id="autoresApa7" style="min-height:68px"></textarea><div class="taghint">La propuesta automática puede corregirse manualmente; queda guardada para este registro.</div></div>
      <div id="apaDynamicFields"></div>
      <div style="display:flex;gap:7px;align-items:center;margin:-2px 0 10px"><button type="button" id="regenApa7">Regenerar APA 7</button><span class="meta">La referencia final sigue siendo editable.</span></div>`;
    // Insertar antes del campo APA existente.
    const apaForm=apa.closest('.form'); apaForm.parentNode.insertBefore(wrap,apaForm);
    const type=q('#tipoPublicacionApa'); type.value=f.tipo_publicacion||'article';
    q('#autoresApa7').value=f.autores_apa||proposedAuthors(a.authors||val('autores'));

    function rebuild(){
      const current={}; qa('[data-k]',wrap).forEach(e=>current[e.dataset.k]=e.value);
      q('#apaDynamicFields').innerHTML=dynamicFields(type.value);
      qa('[data-k]',q('#apaDynamicFields')).forEach(e=>{
        if(f[e.dataset.k]!==undefined) e.value=f[e.dataset.k];
        else if(current[e.dataset.k]!==undefined) e.value=current[e.dataset.k];
      });
      // Pre-carga desde metadatos conocidos.
      if(type.value==='article'){
        setv('revista', f.revista || a.journal || a.source || a.origin || '');
        setv('volumen', f.volumen || a.volume || ''); setv('numero', f.numero || a.issue || ''); setv('paginas_biblio', f.paginas_biblio || a.pages_biblio || '');
      }
      if(!val('url_biblio')) setv('url_biblio',f.url_biblio||a.url||'');
      qa('[data-k]',wrap).forEach(e=>{e.addEventListener('input',changed);e.addEventListener('change',changed)});
      changed(false);
    }
    function changed(regen=true){
      if(regen){ apa.value=apa7(); apa.dispatchEvent(new Event('input',{bubbles:true})); }
      try{ if(typeof autosave==='function') autosave(); }catch(e){}
    }
    type.addEventListener('change',()=>{rebuild(); apa.value=apa7(); apa.dispatchEvent(new Event('input',{bubbles:true}))});
    q('#regenApa7').onclick=()=>{apa.value=apa7(); apa.dispatchEvent(new Event('input',{bubbles:true})); try{autosave()}catch(e){}};
    rebuild();
    // Reemplazar la vieja cita preliminar por APA 7 si todavía no fue corregida manualmente.
    if(!f.apa || /Autor\/a|https:\/\/doi\.org|\(s\. f\.\)/.test(f.apa) || f.apa===apa.value){
      apa.value=apa7(); apa.dispatchEvent(new Event('input',{bubbles:true}));
    }
    const lab=apaForm.querySelector('label'); if(lab) lab.textContent='Referencia APA 7 (generada automáticamente y editable)';
  }

  window.openReader=openReader=function(a){ previousOpenReader(a); setTimeout(()=>install(a),0); };
})();
</script>
'''

if 'window.__apa7MetadataInstalled' not in html:
    html=html.replace('</body>',js+'\n</body>')
p.write_text(html,encoding='utf-8')
print('Metadatos por tipo y generador APA 7 inyectados')
