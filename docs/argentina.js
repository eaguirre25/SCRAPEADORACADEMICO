/* Review decisions remain distinct from the immutable published model assignments. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id), key = 'scrapeador-argentina-reviews-v1';
  let data, reviews, simulation, page=0;
  const states={pending:'Pendiente',include:'Estudia Argentina',exclude:'Excluir del corpus argentino',uncertain:'Revisar / evidencia insuficiente'};
  const topicStates={pending:'Pendiente',validated:'Interpretación validada',needs_changes:'Requiere cambios'};
  const make=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
  const add=(parent,tag,text,cls)=>{const e=make(tag,text,cls);parent.append(e);return e;};
  const fmt=n=>Number(n).toLocaleString('es-AR');
  const percent=n=>n===null||n===undefined?'—':(100*n).toFixed(1)+'%';
  const dialog=$('review-dialog'), content=$('dialog-content');
  const docs=()=>new Map(data.documents.map(d=>[d.record_id,d]));
  function validatedReview(value){
    if(!value||value.schema_version!==1||value.criterion!=='study_location'||!value.documents||!value.topics)throw Error('El archivo debe ser una revisión territorial de Argentina, versión 1.');
    const records=docs(), topicIds=new Set(data.topics.map(t=>t.topic_id));
    for(const [id,r] of Object.entries(value.documents)){
      if(!records.has(id)||!r||!Object.hasOwn(states,r.decision)||typeof r.notes!=='string'||r.notes.length>20000)throw Error('Revisión documental incompatible: '+id);
    }
    for(const [id,r] of Object.entries(value.topics)){
      if(!topicIds.has(id)||!r||!Object.hasOwn(topicStates,r.state)||typeof r.label!=='string'||typeof r.notes!=='string'||r.label.length>500||r.notes.length>20000)throw Error('Revisión de tópico incompatible: '+id);
    }
    if(Object.keys(value.topics).length&&value.model_id!==data.model.model_id)throw Error('Las revisiones de tópicos pertenecen a otra versión del modelo. Importá solo las decisiones documentales.');
    return value;
  }
  function decision(d){return reviews.documents[d.record_id]?.decision||d.decision;}
  function label(t){return reviews.topics[t.topic_id]?.label||t.automatic_label;}
  function open(){dialog.showModal();content.scrollTop=0;}
  function persist(){
    reviews.model_id=data.model.model_id;
    try{localStorage.setItem(key,JSON.stringify(reviews));$('review-status').textContent='Revisión guardada en este navegador. Exportá las decisiones para incorporarlas al corpus y recalcular BERTopic.';}
    catch(_){$('review-status').textContent='El navegador no pudo guardar la revisión. Exportala antes de salir.';}
  }
  function documentDialog(d){
    content.replaceChildren();add(content,'div',d.short_citation,'eyebrow');add(content,'h2',d.title);add(content,'p',d.reference);
    add(content,'h3','Evidencia territorial');
    if(!d.evidence.length)add(content,'p','No se encontró una referencia territorial en título o resumen. La ausencia de evidencia no determina el país del estudio.');
    d.evidence.slice(0,8).forEach(e=>{const box=add(content,'div',undefined,'evidence');add(box,'strong',e.field==='title'?'Título · '+e.term:'Resumen · '+e.term);add(box,'p',e.excerpt);});
    add(content,'p','Fuente bibliográfica: '+d.source+' · Publicación: '+d.publication_year+' · Criterio: objeto de estudio en Argentina, incluidos estudios comparativos.');
    add(content,'h3','Resumen');add(content,'p',d.abstract||'El registro no trae resumen. Consultá la publicación antes de decidir.');
    if(d.url){try{const url=new URL(d.url);if(['https:','http:'].includes(url.protocol)){const a=add(content,'a','Abrir publicación ↗');a.href=url.href;a.target='_blank';a.rel='noopener noreferrer';}}catch(_){}}
    add(content,'label','Decisión territorial');const select=add(content,'select');select.id='document-decision';select.setAttribute('aria-label','Decisión territorial');
    Object.entries(states).forEach(([v,t])=>{const o=add(select,'option',t);o.value=v;});select.value=decision(d);
    add(content,'label','Justificación / corrección');const notes=add(content,'textarea');notes.id='document-notes';notes.setAttribute('aria-label','Justificación territorial');notes.value=reviews.documents[d.record_id]?.notes||d.notes||'';
    add(content,'p','La decisión quedará registrada. Para modificar la composición del análisis y sus tópicos hay que exportarla y ejecutar nuevamente el workflow.','notice');
    const save=add(content,'button','Guardar revisión');save.onclick=()=>{reviews.documents[d.record_id]={decision:select.value,notes:notes.value.trim(),updated_at:new Date().toISOString()};persist();renderList();dialog.close();};open();
  }
  function topicDialog(t){
    content.replaceChildren();add(content,'div','BERTopic independiente · T'+t.topic_id,'eyebrow');add(content,'h2',label(t));
    const members=data.documents.filter(d=>String(d.assignment.topic_id)===t.topic_id);
    add(content,'p',fmt(members.length)+' documentos · '+t.top_words.split(' | ').join(' · '));
    add(content,'label','Nombre del tema');const name=add(content,'input');name.setAttribute('aria-label','Nombre del tema');name.style.width='100%';name.value=label(t);name.maxLength=500;
    add(content,'label','Estado de revisión');const state=add(content,'select');state.setAttribute('aria-label','Estado de revisión');Object.entries(topicStates).forEach(([v,x])=>{const o=add(state,'option',x);o.value=v;});state.value=reviews.topics[t.topic_id]?.state||'pending';
    add(content,'label','Notas de interpretación');const notes=add(content,'textarea');notes.setAttribute('aria-label','Notas de interpretación');notes.value=reviews.topics[t.topic_id]?.notes||'';
    const save=add(content,'button','Guardar interpretación');save.onclick=()=>{reviews.topics[t.topic_id]={label:name.value.trim()||t.automatic_label,state:state.value,notes:notes.value.trim(),updated_at:new Date().toISOString()};persist();renderTopics();drawMap();dialog.close();};
    add(content,'h3','Publicaciones del tema');const search=add(content,'input');search.type='search';search.placeholder='Buscar dentro del tema';search.setAttribute('aria-label','Buscar dentro del tema');const info=add(content,'p'), list=add(content,'div');
    const show=()=>{list.replaceChildren();const q=search.value.toLocaleLowerCase('es');const matches=members.filter(d=>(d.title+' '+d.authors).toLocaleLowerCase('es').includes(q));info.textContent=fmt(matches.length)+' coincidencias; se muestran hasta 30. Podés buscar cualquier publicación del tema.';matches.slice(0,30).forEach(d=>documentRow(list,d));};search.oninput=show;show();open();
  }
  function table(parent,headers,rows){const wrap=add(parent,'div',undefined,'table-scroll'),t=add(wrap,'table'),head=add(t,'thead'),hr=add(head,'tr');headers.forEach(x=>add(hr,'th',x));const body=add(t,'tbody');rows.forEach(r=>{const tr=add(body,'tr');r.forEach(x=>add(tr,'td',String(x)));});}
  function methodDialog(){
    content.replaceChildren();add(content,'div','PROCEDIMIENTO Y TRAZABILIDAD','eyebrow');add(content,'h2','Cómo se construye este mapa');
    add(content,'h3','1 · Del barrido al corpus argentino');
    add(content,'p','Se parte del master bibliográfico aceptado por el workflow temático del proyecto. Se resuelven duplicados exactos con el procedimiento existente y se filtran años de publicación 2020–2026. Se buscan indicios en títulos y resúmenes; una mención territorial produce una candidatura revisable, no una identificación confirmada del lugar de estudio.');
    table(content,['Etapa','Publicaciones'],[['Registros del master',fmt(data.manifest.master_records)],['Publicaciones luego de deduplicación',fmt(data.manifest.canonical_publications)],['Dentro de 2020–2026',fmt(data.manifest.period_publications)],['Candidatos con metadatos suficientes para el ajuste',fmt(data.manifest.modeled_candidates)],['Sin evidencia territorial automática',fmt(data.manifest.no_territorial_evidence)],['Excluidos por puntaje de pertinencia ≤ 0 (recuperables con inclusión manual)',fmt(data.manifest.low_relevance_excluded||0)],['Inclusiones documentales incorporadas al workflow',fmt(data.manifest.human_included)]]);
    add(content,'p','La revisión de corpus permite incluir, excluir o marcar casos dudosos. Los casos sin evidencia pueden incorporarse manualmente. Se conserva el fragmento de evidencia. Las afiliaciones y el repositorio no se usan como país del estudio. 2026 es un año en curso; sus cantidades no se comparan como un año cerrado.');
    add(content,'h3','2 · BERTopic independiente');
    add(content,'p','Se ajusta un nuevo modelo sobre este corpus, usando el mismo modelo de embeddings multilingües, limpieza, combinación de título (0,35), resumen (0,50) y palabras clave (0,15), UMAP, HDBSCAN y c-TF-IDF del workflow. Los pesos se normalizan por los campos disponibles. Se conservan los documentos sin tópico (−1). Los números y etiquetas de temas pertenecen a este ajuste.');
    add(content,'p','Los parámetros se eligen con el mismo procedimiento que el modelo global: cribado de geometrías UMAP (10, 15 y 30 vecinos; 5 y 10 dimensiones; min_dist 0 y 0,1), grilla HDBSCAN sobre las tres mejores, reglas de rechazo (outliers > 45 %, tópico dominante > 35 %, demasiados tópicos en el tamaño mínimo), puntaje multicriterio, cuatro finalistas y estabilidad en cinco semillas (ARI, NMI, centroides y palabras). Como el corpus es mucho menor, solo se escalan los tamaños: los tamaños mínimos de HDBSCAN pasan de 25, 35 y 50 a 7, 10 y 14 (factor 10/35), la mediana mínima de tópico de 20 a 6 y el rango orientativo de tópicos a 4–10. La vectorización y c-TF-IDF son los del modelo global; los topónimos se excluyen solo de las palabras de cada tópico.');
    const m=data.model;const fx=v=>v===''||v==null?'—':Number(v).toFixed(3);
    if(m.selected_parameters){const p=m.selected_parameters;add(content,'p','Solución elegida: UMAP '+p.n_neighbors+' vecinos, '+p.n_components+' dimensiones, min_dist '+p.min_dist+'; HDBSCAN tamaño mínimo '+p.min_cluster_size+', min_samples '+p.min_samples+'. ARI medio entre semillas '+fx(p.stability_ari_mean)+', NMI '+fx(p.stability_nmi_mean)+'.');}
    if(m.parameter_search)table(content,['UMAP (vec./dim./dist.)','HDBSCAN (tam./muestras)','Tópicos','Sin tópico','Puntaje','Rechazo','Estado'],m.parameter_search.map(r=>[r.n_neighbors+' / '+r.n_components+' / '+r.min_dist,r.min_cluster_size+' / '+r.min_samples,r.clusters,percent(Number(r.outlier_share)),fx(r.multi_criteria_score),r.rejection_reasons||'—',r.solution_status==='preferred_provisional'?'✓ elegida':r.solution_status==='competitive'?'finalista':'']));
    if(m.stability)table(content,['Semilla','Tópicos','Sin tópico','ARI','NMI'],m.stability.map(r=>[r.seed,r.topic_count,percent(Number(r.outlier_share)),fx(r.adjusted_rand_index),fx(r.normalized_mutual_information)]));
    add(content,'p','Los tópicos son candidatos exploratorios; la estabilidad y el puntaje no sustituyen la validación del contenido.','notice');
    add(content,'p','ARI y NMI comparan cada semilla con la de referencia (42), incluidos los documentos sin tópico; la comparación de la semilla 42 consigo misma vale 1.');
    add(content,'h3','3 · La red y su lectura');add(content,'p','Cada publicación es un nodo. El enlace usa palabras clave normalizadas y Jaccard ponderado por IDF, calculado nuevamente en el corpus argentino: mínimo dos términos y semejanza ≥ 0,20. No expresa cita bibliográfica. Los tópicos se conectan por similitud c-TF-IDF ≥ 0,35, sin enlaces inventados para unir componentes. Las distancias son una disposición de fuerzas; los tamaños representan grado de conexión o cantidad de publicaciones. Todos los documentos del corpus se conservan, incluidos los aislados y sin tópico.');
    add(content,'h3','Alternativa semántica para publicaciones');add(content,'p','Solo '+data.keyword_audit.coverage.with_clean_keywords+' de '+data.manifest.modeled_candidates+' candidatos tienen palabras clave retenidas. La vista inicial usa los embeddings originales del ajuste, con coseno ≥ 0,70 y cinco vecinos más próximos, exigiendo vecindad recíproca. Es una regla explícita de reducción de enlaces para explorar proximidad textual, no una prueba de validez ni una relación de citación. Se compara k=3, 5 y 10 y coseno mínimo 0,60, 0,70 y 0,80. Todos los documentos permanecen en ambas redes.');if(data.semantic_audit.sensitivity)table(content,['Vecinos','Coseno mínimo','Conexiones','Aislados'],data.semantic_audit.sensitivity.map(r=>[r.neighbors,r.min_similarity,r.edges,r.isolated]));add(content,'h3','Alcance y revisión');add(content,'p','La cobertura corresponde al barrido temático del proyecto y a los metadatos disponibles. Hay posibles menciones incidentales, falsos positivos territoriales y estudios argentinos sin país explícito. También pueden persistir casos de relevancia temática fronteriza. Los topónimos siguen presentes en los embeddings aunque no en las palabras de los tópicos: revisá si un tema se define por territorio o por contenido sustantivo.');
    add(content,'p','Exportá las revisiones, incorporá el JSON en config/argentina_document_reviews.json y ejecutá el workflow «Argentina · BERTopic 2020–2026». La página guarda decisiones en el navegador; no ejecuta entrenamiento en el servidor.');
    add(content,'h3','Referencias metodológicas');
    add(content,'p','Grootendorst, M. (2022). BERTopic: Neural topic modeling with a class-based TF-IDF procedure. arXiv. https://doi.org/10.48550/arXiv.2203.05794');
    add(content,'p','van Eck, N. J., & Waltman, L. (2010). Software survey: VOSviewer, a computer program for bibliometric mapping. Scientometrics, 84, 523–538. https://doi.org/10.1007/s11192-009-0146-3');
    const raw=add(content,'details');add(raw,'summary','Configuración efectiva y huella del corpus');add(raw,'pre',JSON.stringify({corpus_hash:data.manifest.corpus_hash,effective_configuration:data.effective_configuration,screening:data.manifest.settings},null,2));open();
  }
  function documentRow(parent,d){const row=add(parent,'article',undefined,'document-row'),text=add(row,'div');add(text,'p',d.short_citation+' · '+(d.assignment.topic_id===undefined?'Sin ajuste vigente':Number(d.assignment.topic_id)<0?'Sin tópico':'T'+d.assignment.topic_id));add(text,'h3',d.title);add(text,'p',states[decision(d)]+' · '+(d.evidence.length?d.evidence.map(e=>e.term).slice(0,4).join(' · '):'Sin evidencia automática'));const b=add(row,'button','Revisar trabajo');b.onclick=()=>{if(dialog.open)dialog.close();documentDialog(d);};}
  function renderList(){
    const q=$('search').value.toLocaleLowerCase('es'),filter=$('filter').value;
    const matches=data.documents.filter(d=>{
      const dec=decision(d);const mode=filter==='all'||filter==='candidates'&&d.modeled||filter==='pending'&&d.modeled&&dec==='pending'||filter==='without'&&!d.evidence.length||filter==='low_relevance'&&d.low_relevance&&d.evidence.length&&!d.modeled||['include','exclude','uncertain'].includes(filter)&&dec===filter;
      return mode&&(d.title+' '+d.authors+' '+d.abstract).toLocaleLowerCase('es').includes(q);
    });
    page=Math.min(page,Math.max(0,Math.ceil(matches.length/20)-1));const list=$('document-list');list.replaceChildren();matches.slice(page*20,page*20+20).forEach(d=>documentRow(list,d));
    if(!matches.length)add(list,'p','No hay publicaciones con estos filtros.');
    $('page-status').textContent=`${fmt(matches.length)} publicaciones · página ${page+1} de ${Math.max(1,Math.ceil(matches.length/20))}`;
    $('previous').disabled=page===0;$('next').disabled=(page+1)*20>=matches.length;
  }
  function renderTopics(){
    $('topic-cards').replaceChildren();$('legend').replaceChildren();
    data.topics.forEach(t=>{const b=add($('topic-cards'),'button',undefined,'topic-card');add(b,'span','T'+t.topic_id+' · '+fmt(t.document_count)+' documentos','topic-number');add(b,'h3',label(t));add(b,'p',t.top_words.split(' | ').slice(0,5).join(' · '));b.onclick=()=>topicDialog(t);const l=add($('legend'),'button','T'+t.topic_id+' · '+label(t));l.onclick=()=>topicDialog(t);});
    if(!data.topics.length)add($('topic-cards'),'p',data.status==='fitted'?'Este ajuste no encontró agrupamientos; se conservan los documentos sin tópico.':'El ajuste independiente está pendiente.');
  }
  function drawMap(){
    simulation?.stop();const svg=$('network');d3.select(svg).selectAll('*').remove();
    const isTopics=$('view').value==='topics';const semantic=$('relation').value==='semantic';$('relation').disabled=isTopics;const view=structuredClone(isTopics?data.topic_network:semantic?{nodes:data.network.nodes,edges:data.semantic_network.edges}:data.network);
    if(!isTopics){view.nodes.forEach(n=>n.degree=0);view.edges.forEach(e=>{view.nodes[e.source].degree++;view.nodes[e.target].degree++;});}
    $('relation-caption').textContent=(isTopics?'Conexiones por similitud c-TF-IDF ≥ 0,35 entre tópicos.':semantic?'Conexiones por coseno ≥ 0,70 entre los cinco vecinos semánticos más próximos, con vecindad recíproca. Usa los embeddings originales de BERTopic.':'Conexiones por Jaccard ponderado ≥ 0,20 y al menos dos palabras clave compartidas. Solo '+data.keyword_audit.coverage.with_clean_keywords+' registros tienen etiquetas retenidas.')+' La posición es una disposición de fuerzas y el relieve es visual. Tamaño: conexiones en publicaciones; cantidad de documentos en tópicos. Se conservan nodos aislados y documentos sin tópico.';
    const names=new Map(data.topics.map(t=>[t.topic_id,label(t)]));
    if(isTopics)view.nodes.forEach(n=>n.label=names.get(n.id)||n.label);else view.nodes.forEach(n=>{if(names.has(n.topic))n.topic_label=names.get(n.topic);});
    $('net-summary').textContent=fmt(view.nodes.length)+' nodos · '+fmt(view.edges.length)+' conexiones · '+(isTopics?'similitud entre temas':'cada nodo es una publicación');
    simulation=window.StellarNetwork.render({svgEl:svg,model:{label:'Argentina 2020–2026'},view,isTopics,tip:$('tooltip'),onSelect:(n,body)=>{if(!n)return;const b=add(body,'button',isTopics?'Revisar tema':'Revisar pertenencia territorial');b.onclick=()=>isTopics?topicDialog(data.topics.find(t=>t.topic_id===n.id)):documentDialog(docs().get(n.id));}});
  }
  async function start(){
    try{
      const r=await fetch('argentina-data.json');if(!r.ok)throw Error('No se pudo cargar el corpus argentino.');data=await r.json();reviews=structuredClone(data.reviews);
      try{const saved=localStorage.getItem(key);if(saved){const local=JSON.parse(saved);if(local.topics&&Object.keys(local.topics).length&&local.model_id!==data.model.model_id){local.topics={};$('review-status').textContent='Se conservaron las decisiones documentales. Las interpretaciones de tópicos pertenecían a otro ajuste.';}reviews=validatedReview(local);}}catch(_){$('review-status').textContent='Hay revisiones locales de otra versión. Se cargaron las decisiones del workflow.';}
      const assignments=data.documents.filter(d=>d.assignment.topic_id!==undefined).length;
      [['Candidatos en el ajuste',data.manifest.modeled_candidates],['Tópicos propios',data.topics.length],['Documentos sin tópico',data.status==='fitted'?data.outliers:'—'],['Inclusiones documentales',data.manifest.human_included],['Publicaciones de 2026',data.manifest.year_counts['2026']||0]].forEach(([text,n])=>{const s=add($('stats'),'div',undefined,'stat');add(s,'strong',typeof n==='number'?fmt(n):n);add(s,'span',text);});
      $('loading').textContent=data.status==='fitted'?`Ajuste exploratorio sobre ${fmt(assignments)} candidatos territoriales. La revisión documental define su pertenencia. 2026 está en curso.`:'Corpus preparado; el ajuste BERTopic necesita actualizarse antes de interpretar temas.';
      $('loading').className='caption';renderTopics();renderList();drawMap();
      $('method').onclick=methodDialog;$('view').onchange=drawMap;$('relation').onchange=drawMap;
      document.querySelectorAll('[role=tab]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[role=tab]').forEach(x=>x.setAttribute('aria-selected',String(x===b)));document.querySelectorAll('.panel').forEach(x=>x.hidden=x.id!==b.dataset.panel);if(b.dataset.panel==='map')drawMap();});
      ['search','filter'].forEach(id=>$(id).addEventListener(id==='search'?'input':'change',()=>{page=0;renderList();}));
      $('previous').onclick=()=>{page--;renderList();};$('next').onclick=()=>{page++;renderList();};
      $('export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({...reviews,model_id:data.model.model_id},null,2)],{type:'application/json'}));const a=make('a');a.href=url;a.download='argentina_document_reviews.json';a.click();URL.revokeObjectURL(url);};
      $('import').onchange=async()=>{try{const file=$('import').files[0];if(!file)return;if(file.size>5e6)throw Error('El archivo de revisión es demasiado grande.');const value=validatedReview(JSON.parse(await file.text()));reviews={...reviews,documents:{...reviews.documents,...value.documents},topics:{...reviews.topics,...value.topics}};persist();renderList();renderTopics();drawMap();}catch(e){$('review-status').textContent=e.message;}finally{$('import').value='';}};
    }catch(e){$('loading').textContent=e.message+' Recargá la pantalla o volvé al dashboard.';}
  }
  dialog.querySelector('.dialog-close').onclick=()=>dialog.close();start();
})();
