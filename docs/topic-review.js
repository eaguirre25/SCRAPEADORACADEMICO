/* Explicit user review, stored locally and exportable. Algorithmic evidence is preserved. */
(() => {
  const storageKey='scrapeador-topic-reviews-v1';
  const recordsKey=(model,topic)=>`${model}:${topic}`;
  let reviews={},storageOK=true,active=null,returnFocus=null,modelData=null,page=0,filtered=[];
  try{reviews=JSON.parse(localStorage.getItem(storageKey)||'{}');if(!reviews||typeof reviews!=='object'||Array.isArray(reviews))reviews={};}catch(_){storageOK=false;}
  const status=document.getElementById('topic-review-status');
  const dialog=document.createElement('dialog');dialog.className='topic-dialog';dialog.setAttribute('aria-labelledby','review-title');
  dialog.innerHTML=`<div class="review-head"><div><small id="review-model"></small><h2 id="review-title"></h2></div><button type="button" id="review-close" aria-label="Cerrar revisión">×</button></div><div class="review-body"><div class="review-grid"><section><h3>Información del tema</h3><div id="review-summary"></div><div id="review-evidence" class="review-evidence"></div></section><section><h3>Tu revisión</h3><p>Revisá los documentos antes de aprobar el nombre del tema. Las decisiones registran tu evaluación y conservan los resultados originales.</p><form id="review-form"><label>Nombre del tema<input id="review-label" required maxlength="250"></label><label>Estado de tu revisión<select id="review-state"><option value="pending">Pendiente</option><option value="validated">Validado por mí</option><option value="needs_changes">Requiere correcciones</option></select></label><label>Notas, motivos o propuesta de reorganización<textarea id="review-notes" maxlength="10000"></textarea></label><button type="submit">Guardar revisión</button><p id="review-save-status" class="review-save-note" role="status"></p></form></section></div><section class="review-documents"><h3>Documentos asignados por el modelo</h3><input class="review-search" id="review-search" type="search" placeholder="Buscar título, autor o año" aria-label="Buscar documentos del tema"><p class="review-data-status" id="review-data-status"></p><div id="review-document-list"></div><div class="review-pagination"><button type="button" id="review-prev">Anterior</button><span id="review-page"></span><button type="button" id="review-next">Siguiente</button></div></section></div>`;
  document.body.appendChild(dialog);
  const el=id=>document.getElementById(id);
  function persist(){try{localStorage.setItem(storageKey,JSON.stringify(reviews));storageOK=true;return true;}catch(_){storageOK=false;status.textContent='El navegador no pudo guardar. Exportá las revisiones para conservarlas.';return false;}}
  function topicNodes(model){return NETWORKS[model]?.topics.nodes||[];}
  const originals={};for(const [model,net]of Object.entries(NETWORKS))for(const t of net.topics.nodes)originals[recordsKey(model,t.id)]=t.label;
  function applyReviews(){
    document.querySelectorAll('.tm-card[data-model]').forEach(card=>{
      const key=recordsKey(card.dataset.model,card.dataset.topic),r=reviews[key];
      if(!card.dataset.originalLabel)card.dataset.originalLabel=card.querySelector('.tm-title').textContent;
      card.querySelector('.tm-title').textContent=r?.label||card.dataset.originalLabel;
      card.setAttribute('aria-label','Revisar tema '+card.querySelector('.tm-title').textContent);
      const prompt=card.querySelector('.tm-open');prompt.classList.toggle('local-reviewed',!!r&&r.state==='validated');
      prompt.textContent=r?.state==='validated'?'Revisión guardada · Abrir ficha →':r?.state==='needs_changes'?'Correcciones guardadas · Abrir ficha →':'Abrir ficha y revisar →';
    });
    for(const [model,net]of Object.entries(NETWORKS)){
      for(const t of net.topics.nodes)t.label=reviews[recordsKey(model,t.id)]?.label||originals[recordsKey(model,t.id)];
      const labels=new Map(net.topics.nodes.map(t=>[String(t.id),t.label]));
      for(const d of net.documents.nodes)if(labels.has(String(d.topic)))d.topic_label=labels.get(String(d.topic));
    }
  }
  function saveForm(){
    const key=recordsKey(active.model,active.topic);reviews[key]={...(reviews[key]||{}),model:active.model,topic:active.topic,label:el('review-label').value.trim(),state:el('review-state').value,notes:el('review-notes').value,updated_at:new Date().toISOString(),documents:reviews[key]?.documents||{}};
    const saved=persist();el('review-save-status').textContent=saved?'Guardado en este navegador. Exportá para conservar una copia o trasladarla a otro equipo.':'No se pudo guardar en el navegador. Exportá antes de cerrar.';
    applyReviews();renderNetwork(false);
  }
  function markDocument(id,value){
    const key=recordsKey(active.model,active.topic),r=reviews[key]||{model:active.model,topic:active.topic,state:'pending',label:el('review-label').value.trim(),notes:'',documents:{}};
    r.documents||={};r.documents[id]=value;r.updated_at=new Date().toISOString();reviews[key]=r;persist();
    el('review-save-status').textContent=storageOK?'Decisión documental guardada en este navegador.':'Exportá para conservar la decisión documental.';
  }
  function renderDocs(){
    const list=el('review-document-list');list.replaceChildren();const selected=filtered.slice(page*20,page*20+20);
    const decisions=reviews[recordsKey(active.model,active.topic)]?.documents||{};
    for(const doc of selected){
      const paper=window.StellarPapers?.[doc.id]||doc.paper||{},row=document.createElement('div');row.className='review-document';
      const text=document.createElement('div'),title=document.createElement('strong');title.textContent=paper.title||'Título no disponible';text.appendChild(title);
      const cite=document.createElement('small');cite.textContent=paper.short_citation||[paper.authors,paper.year].filter(Boolean).join(', ');text.appendChild(cite);
      const signals=document.createElement('small');signals.textContent=[doc.ambiguous?'Asignación fronteriza':'',doc.silhouette!==''&&Number(doc.silhouette)<0?'Silueta negativa':''].filter(Boolean).join(' · ');text.appendChild(signals);
      try{const u=new URL(paper.url);if(['http:','https:'].includes(u.protocol)){const a=document.createElement('a');a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';a.textContent='Abrir publicación ↗';text.appendChild(a);}}catch(_){}
      const choice=document.createElement('select');choice.setAttribute('aria-label','Revisión de '+(paper.title||doc.id));
      for(const [value,label]of [['pending','Sin revisar'],['fits','Pertinente al tema'],['question','Revisar asignación'],['reassign','Propongo otro tema'],['exclude','Propongo excluir']]){const option=new Option(label,value);choice.appendChild(option);}
      choice.value=decisions[doc.id]||'pending';choice.onchange=()=>markDocument(doc.id,choice.value);row.append(text,choice);list.appendChild(row);
    }
    const pages=Math.max(1,Math.ceil(filtered.length/20));el('review-page').textContent=`${filtered.length} documentos · página ${page+1} de ${pages}`;
    el('review-prev').disabled=page===0;el('review-next').disabled=page+1>=pages;
  }
  function filterDocs(){
    const q=el('review-search').value.toLocaleLowerCase();
    filtered=(active.members||[]).filter(d=>{const p=window.StellarPapers?.[d.id]||d.paper||{};return [p.title,p.authors,p.year].join(' ').toLocaleLowerCase().includes(q);});page=0;renderDocs();
  }
  async function open(card){
    returnFocus=card;active={model:card.dataset.model,topic:card.dataset.topic,members:[]};const current=active;
    const key=recordsKey(active.model,active.topic),r=reviews[key]||{};
    el('review-model').textContent=NETWORKS[active.model]?.label||active.model;
    el('review-title').textContent=card.querySelector('.tm-title').textContent;
    el('review-summary').replaceChildren();const p=document.createElement('p');p.textContent=card.querySelector('.tm-meta').textContent+' · '+card.querySelectorAll('.tm-meta')[1].textContent;el('review-summary').appendChild(p);
    const words=document.createElement('p');words.textContent='Palabras representativas: '+card.querySelector('.tm-words').textContent;el('review-summary').appendChild(words);
    el('review-evidence').replaceChildren(card.querySelector('.tm-evidence').content.cloneNode(true));
    el('review-evidence').querySelectorAll('details').forEach(d=>d.open=true);
    const glossary=document.createElement('p');glossary.className='review-save-note';glossary.textContent='Cómo leer las señales: provisional indica revisión pendiente; fronterizo, una asignación menos clara; metadatos territoriales insuficientes, falta de información de países; contaminación, posible contenido ajeno al alcance. Son indicadores para revisar, no errores confirmados. La validación local registra tu decisión y conserva estos diagnósticos originales.';el('review-evidence').appendChild(glossary);
    el('review-label').value=r.label||card.dataset.originalLabel||card.querySelector('.tm-title').textContent;el('review-state').value=r.state||'pending';el('review-notes').value=r.notes||'';
    el('review-save-status').textContent=r.updated_at?'Último guardado: '+new Date(r.updated_at).toLocaleString('es-AR'):'Las decisiones se guardan en este navegador y se pueden exportar.';
    el('review-search').value='';el('review-document-list').replaceChildren();el('review-data-status').textContent='Cargando documentos…';el('review-page').textContent='';
    dialog.showModal();
    try{
      if(!modelData){const response=await fetch('topic-review-data.json');if(!response.ok)throw Error('HTTP '+response.status);modelData=await response.json();}
      if(active!==current)return;
      active.members=modelData.models[active.model]?.topics[active.topic]||[];
      el('review-data-status').textContent='Listado completo de asignaciones exportadas por el modelo. Las propuestas de reasignación o exclusión quedan registradas para revisión.';filterDocs();
    }catch(_){if(active===current)el('review-data-status').textContent='No se pudo cargar el listado. Cerrá y volvé a abrir la ficha para reintentar.';}
  }
  document.querySelectorAll('.tm-card[data-model]').forEach(card=>{
    card.addEventListener('click',()=>open(card));card.addEventListener('keydown',event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();open(card);}});
  });
  el('review-close').onclick=()=>dialog.close();dialog.addEventListener('close',()=>returnFocus?.focus());
  el('review-form').onsubmit=event=>{event.preventDefault();saveForm();};
  el('review-search').oninput=filterDocs;el('review-prev').onclick=()=>{if(page>0){page--;renderDocs();}};el('review-next').onclick=()=>{if((page+1)*20<filtered.length){page++;renderDocs();}};
  el('topic-export').onclick=()=>{
    const payload={schema:'scrapeador-topic-reviews-v1',exported_at:new Date().toISOString(),reviews};
    const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='revisiones-tematicas-'+new Date().toISOString().slice(0,10)+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
    status.textContent='Exportación preparada. Conservá el archivo para recuperar tus decisiones.';
  };
  el('topic-import').onchange=async event=>{
    try{
      const data=JSON.parse(await event.target.files[0].text());if(data.schema!=='scrapeador-topic-reviews-v1'||!data.reviews||Array.isArray(data.reviews))throw Error();
      const staged={...reviews};
      for(const [key,r]of Object.entries(data.reviews)){
        if(!r||typeof r!=='object'||!NETWORKS[r.model]||!topicNodes(r.model).some(t=>String(t.id)===String(r.topic))||key!==recordsKey(r.model,r.topic))throw Error();
        if(!['pending','validated','needs_changes'].includes(r.state)||typeof r.label!=='string'||typeof r.notes!=='string'||r.label.length>250||r.notes.length>10000)throw Error();
        if(reviews[key]?.updated_at&&reviews[key].updated_at>r.updated_at)continue;
        if(r.documents&&Object.values(r.documents).some(v=>!['pending','fits','question','reassign','exclude'].includes(v)))throw Error();
        staged[key]=r;
      }
      reviews=staged;persist();applyReviews();renderNetwork(false);status.textContent=storageOK?'Revisiones importadas y guardadas en este navegador.':'Importadas; exportá una copia porque el guardado local no está disponible.';
    }catch(_){status.textContent='Archivo de revisión incompatible o inválido. Las decisiones existentes se conservan.';}
    event.target.value='';
  };
  applyReviews();if(!storageOK)status.textContent='Guardado local no disponible. Exportá las revisiones para conservarlas.';
})();
