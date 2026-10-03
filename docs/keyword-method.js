/* Read-only methodological audit. All figures come from the generated JSON. */
(()=>{
 let audit=null;const dialog=document.createElement('dialog');dialog.className='topic-dialog';dialog.setAttribute('aria-labelledby','keyword-title');
 dialog.innerHTML='<div class="review-head"><h2 id="keyword-title">Método y comparación de la red documental</h2><button type="button" id="keyword-close" aria-label="Cerrar método">×</button></div><div class="review-body" id="keyword-body"></div>';document.body.appendChild(dialog);
 const body=document.getElementById('keyword-body');
 const text=(parent,tag,value)=>{const el=document.createElement(tag);el.textContent=value;parent.appendChild(el);return el;};
 const percent=v=>v==null?'Sin datos':(v*100).toLocaleString('es-AR',{maximumFractionDigits:1})+'%';
 function table(headers,rows){const wrap=document.createElement('div');wrap.className='method-table-wrap';const t=document.createElement('table');t.className='method-table';const head=t.createTHead().insertRow();headers.forEach(h=>text(head,'th',h));const b=t.createTBody();for(const row of rows){const tr=b.insertRow();for(const value of row)text(tr,'td',String(value));}wrap.appendChild(t);body.appendChild(wrap);}
 function render(){
  body.replaceChildren();
  text(body,'h3','Qué representa la red');text(body,'p','Cada nodo representa un registro del corpus maestro. Los enlaces expresan semejanza de sus etiquetas; el color expresa el tema asignado por STM o BERTopic. Son dos criterios independientes.');
  text(body,'h3','Procedencia y cobertura');const c=audit.coverage;
  text(body,'p',`${c.records.toLocaleString('es-AR')} registros · ${c.with_raw_keywords.toLocaleString('es-AR')} con etiquetas originales · ${c.with_clean_keywords.toLocaleString('es-AR')} con etiquetas después de las exclusiones propuestas. Todos los registros permanecen en la red.`);
  table(['Fuente del registro','Registros','Con etiquetas originales','Con etiquetas retenidas'],Object.entries(audit.by_source).map(([source,v])=>[source,v.records,v.with_raw_keywords,v.with_clean_keywords]));
  for(const note of audit.limitations)text(body,'p',note);
  text(body,'h3','Semejanza normalizada');text(body,'p','Jaccard ponderado: suma de los pesos de las etiquetas compartidas, dividida por la suma de los pesos de todas las etiquetas de ambos documentos, sin repetirlas. El resultado va de 0 a 1.');
  text(body,'p','IDF da más peso a etiquetas menos frecuentes en este corpus. '+audit.method.idf+'. N cuenta solamente los registros que conservan etiquetas. Cada enlace también requiere al menos dos etiquetas diferentes compartidas.');
  text(body,'p','Se consideran todas las etiquetas retenidas. Se quitaron los recortes de doce etiquetas y de cuarenta apariciones; las exclusiones ahora están identificadas en el diccionario.');
  text(body,'h3','Comparación de configuraciones');text(body,'p',audit.selection_reason);
  table(['Configuración','Enlaces','Registros conectados','Aislados','Componentes con enlaces','Componente mayor'],Object.values(audit.sensitivity).map(v=>[v.label,v.edges,v.connected_records,v.isolated_records,v.components_with_links,v.largest_component]));
  const old=audit.legacy;text(body,'p',`Referencia anterior: ${old.edges} enlaces, ${old.connected_records} registros conectados y ${old.isolated_records} aislados. Usaba coincidencia exacta, doce etiquetas como máximo y descarte de etiquetas presentes en más de cuarenta registros. La comparación incluye simultáneamente limpieza y cambio de medida.`);
  text(body,'h3','Comparación con los temas del modelo activo');
  text(body,'p',NETWORKS[currentModel].label+'. Se comparan solamente enlaces cuyos dos extremos tienen un tema vinculado; los casos sin asignación quedan fuera de este cálculo.');
  const agreement=audit.topic_comparison[currentModel]||{};
  table(['Configuración','Enlaces comparables','Dentro del mismo tema','Pares asignados del mismo tema (referencia)'],Object.entries(agreement).map(([key,v])=>[audit.profiles[key].label,v.eligible_edges,percent(v.same_topic_share),percent(v.all_assigned_pair_same_topic_share)]));
  text(body,'p','Es una comparación descriptiva. Las medidas comparten información textual y los modelos tienen coberturas distintas; estos porcentajes no prueban la validez de los temas.');
  const details=document.createElement('details');text(details,'summary','Ver exclusiones propuestas y su frecuencia');for(const v of audit.excluded_terms)text(details,'p',`${v.term}: ${v.documents} registros`);body.appendChild(details);
  const merged=document.createElement('details');text(merged,'summary','Ver equivalencias aplicadas');for(const v of audit.merged_terms)text(merged,'p',`${v.original} → ${v.canonical}: ${v.documents} registros`);body.appendChild(merged);
  text(body,'p','El diccionario es una propuesta revisable. Dirección, gestión y liderazgo mantienen entradas diferenciadas; tampoco se fusionan liderazgo pedagógico e instruccional. No se modifica el texto original ni las asignaciones de los modelos.');
  const links=document.createElement('p');for(const [label,url]of [['Descargar diccionario','keyword-thesaurus.csv'],['Descargar auditoría completa','keyword-network-audit.json']]){const a=document.createElement('a');a.href=url;a.download='';a.textContent=label;a.className='method-download';links.appendChild(a);}body.appendChild(links);
  text(body,'h3','Referencias metodológicas');for(const source of audit.sources){const p=text(body,'p',source.apa+' ');const a=document.createElement('a');a.href=source.url;a.target='_blank';a.rel='noopener noreferrer';a.textContent=source.url;p.appendChild(a);}
 }
 document.getElementById('keyword-audit-open').onclick=async()=>{body.replaceChildren();text(body,'p','Cargando auditoría…');dialog.showModal();try{if(!audit){const r=await fetch('keyword-network-audit.json');if(!r.ok)throw Error();audit=await r.json();}render();}catch(_){body.replaceChildren();text(body,'p','No se pudo cargar. Cerrá y volvé a abrir para reintentar.');}};
 document.getElementById('keyword-close').onclick=()=>dialog.close();dialog.addEventListener('close',()=>document.getElementById('keyword-audit-open').focus());
})();
