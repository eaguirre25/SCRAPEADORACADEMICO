/* D3 force layout: stellar shading changes appearance, never edge semantics. */
window.StellarNetwork = (() => {
  function render({svgEl, model, view, isTopics, tip, onSelect}) {
    const svg = d3.select(svgEl);
    const detail = document.getElementById('net-detail');
    const body = document.getElementById('net-detail-body');
    const close = document.getElementById('net-detail-close');
    detail.hidden = true;
    let W = svgEl.clientWidth || 800, H = svgEl.clientHeight || 400;
    let transform = d3.zoomIdentity, selected = null, hovered = null, frames = 0;
    let firstFit = false, disposed = false;
    svg.attr('width', W).attr('height', H);
    const defs = svg.append('defs');
    const colors = [...new Set(view.nodes.map(n => n.color || '#7089a3'))];
    colors.forEach((color, i) => {
      const base = d3.color(color) || d3.color('#7089a3');
      const sphere = defs.append('radialGradient').attr('id', 'stellar-sphere-' + i)
        .attr('cx', '30%').attr('cy', '25%').attr('r', '78%');
      [[0, '#f3faff'], [.16, base.brighter(1.3)], [.45, base], [1, base.darker(2.5)]]
        .forEach(([offset, shade]) => sphere.append('stop').attr('offset', offset).attr('stop-color', shade));
      const halo = defs.append('radialGradient').attr('id', 'stellar-halo-' + i);
      [[0, .38], [.45, .15], [1, 0]].forEach(([offset, opacity]) => halo.append('stop')
        .attr('offset', offset).attr('stop-color', base.brighter(.7)).attr('stop-opacity', opacity));
    });
    const stars = svg.append('g').attr('aria-hidden', 'true').attr('pointer-events', 'none');
    const starData = d3.range(95).map(i => ({x: ((i * 73.31 + 19) % 997) / 997,
      y: ((i * 137.17 + 53) % 991) / 991, r: i % 9 === 0 ? 1.1 : .55}));
    const starDots = stars.selectAll('circle').data(starData).join('circle')
      .attr('fill', '#b9d8ff').attr('opacity', (_, i) => i % 9 === 0 ? .5 : .2).attr('r', d => d.r);
    const placeStars = () => starDots.attr('cx', d => d.x * W).attr('cy', d => d.y * H);
    placeStars();
    if (!view.nodes.length) {
      svg.append('text').attr('x', W / 2).attr('y', H / 2).attr('text-anchor', 'middle')
        .attr('fill', '#a9c1db').attr('font-size', 13).text('Este modelo no tiene documentos suficientes para tejer una red.');
      ['net-zoom-in', 'net-zoom-out', 'net-fit'].forEach(id => document.getElementById(id).onclick = null);
      return {stop() {}};
    }
    const g = svg.append('g').attr('class', 'stellar-world');
    const nodes = view.nodes.map(n => ({...(window.StellarPapers?.[n.id] || {}), ...n}));
    const links = view.edges.map(e => ({...e}));
    const maxWeight = Math.max(1, ...nodes.map(n => (isTopics ? n.size : n.degree) || 1));
    const radius = d => isTopics ? 9 + Math.sqrt((d.size || 1) / maxWeight) * 24 : 4 + ((d.degree || 0) / maxWeight) * 9;
    const width = d => isTopics ? Math.max(.6, d.weight * 3) : .5 + 2.5 * d.weight;
    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id((_, i) => i)
        .distance(isTopics ? d => 130 - 70 * d.weight : d => 100 - 70 * d.weight)
        .strength(isTopics ? .35 : d => .15 + .65 * d.weight))
      .force('charge', d3.forceManyBody().strength(isTopics ? -430 : -70))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide(d => radius(d) + (isTopics ? 7 : 2)))
      .alphaDecay(isTopics ? .0228 : .045);
    // Only actual exported links are illuminated. The background is decorative.
    const adjacency = new Map(nodes.map(d => [d.index, new Set([d.index])]));
    links.forEach(d => {adjacency.get(d.source.index).add(d.target.index); adjacency.get(d.target.index).add(d.source.index);});
    // Canvas retains every lexical link while avoiding tens of thousands of SVG lines.
    const canvas = isTopics ? null : document.createElement('canvas');
    let ctx = null, ratio = window.devicePixelRatio || 1;
    if(canvas){canvas.className='stellar-links';canvas.setAttribute('aria-hidden','true');canvas.dataset.links=links.length;svgEl.parentElement.insertBefore(canvas,svgEl);ctx=canvas.getContext('2d');}
    function resizeCanvas(){if(!canvas)return;canvas.width=Math.ceil(W*ratio);canvas.height=Math.ceil(H*ratio);}
    resizeCanvas();
    const link = isTopics ? g.append('g').attr('pointer-events', 'none').selectAll('line').data(links).join('line')
      .attr('stroke', '#587b9e').attr('stroke-width', width).attr('stroke-opacity', .24) : g.selectAll('.no-svg-links');
    const light = isTopics ? g.append('g').attr('pointer-events', 'none').selectAll('line').data(links).join('line')
      .attr('stroke-width', d => width(d) + 4).attr('stroke-opacity', 0) : g.selectAll('.no-svg-lights');
    function drawLinks(){
      if(!ctx)return;ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,W,H);ctx.translate(transform.x,transform.y);ctx.scale(transform.k,transform.k);
      const active=selected||hovered;let incidents=0;ctx.strokeStyle='#587b9e';ctx.globalAlpha=active?.035:.24;
      for(let bucket=0;bucket<4;bucket++){ctx.beginPath();ctx.lineWidth=.5+(bucket+.5)*.625;
        for(const e of links)if(Math.min(3,Math.floor(e.weight*4))===bucket){ctx.moveTo(e.source.x,e.source.y);ctx.lineTo(e.target.x,e.target.y);}ctx.stroke();}
      if(active){ctx.beginPath();ctx.strokeStyle='#d3edff';ctx.lineWidth=2.4;ctx.globalAlpha=.92;
        for(const e of links)if(e.source===active||e.target===active){ctx.moveTo(e.source.x,e.source.y);ctx.lineTo(e.target.x,e.target.y);incidents++;}ctx.stroke();}
      canvas.dataset.highlighted=incidents;ctx.globalAlpha=1;
    }
    const node = g.append('g').selectAll('g').data(nodes).join('g').attr('class', 'stellar-node')
      .attr('tabindex', 0).attr('role', 'button').attr('aria-pressed', 'false')
      .attr('aria-label', d => isTopics ? `T${d.id}: ${d.label}` : `${d.short_citation || d.authors || 'Sin autor'}: ${d.title}`)
      .style('cursor', 'pointer');
    node.append('circle').attr('class', 'stellar-halo').attr('r', d => radius(d) * 2.4)
      .attr('fill', d => `url(#stellar-halo-${colors.indexOf(d.color || '#7089a3')})`).attr('pointer-events', 'none');
    node.append('circle').attr('class', 'stellar-sphere').attr('r', radius)
      .attr('fill', d => `url(#stellar-sphere-${colors.indexOf(d.color || '#7089a3')})`)
      .attr('stroke', d => d.color || '#7089a3').attr('stroke-opacity', .65).attr('stroke-width', .7);
    // A larger transparent hit target keeps small document nodes usable.
    node.append('circle').attr('r', d => Math.max(10, radius(d))).attr('fill', 'transparent');
    const captions = g.append('g').selectAll('text').data(nodes).join('text')
      .attr('class', 'stellar-label').attr('text-anchor', 'middle')
      .text(d => isTopics ? `T${d.id} · ${(d.label || '').slice(0, 48)}${(d.label || '').length > 48 ? '…' : ''}` : d.short_citation || `${d.authors || 'Sin autor'}, ${d.year || 's. f.'}`);
    const captionWidths = new Map();
    captions.each(function(d) {captionWidths.set(d.index, this.getComputedTextLength());});
    function layoutLabels() {
      const active = selected || hovered;
      const nearby = active ? adjacency.get(active.index) : null;
      const k = transform.k, fontSize = 11 / k;
      captions.attr('font-size', fontSize).attr('stroke-width', 3 / k)
        .attr('x', d => d.x).attr('y', d => d.y + radius(d) + 15 / k);
      const occupied = new Set(), visible = new Set();
      const ordered = [...nodes].sort((a, b) => {
        const rank = d => d === active ? 3 : nearby?.has(d.index) ? 2 : 0;
        return rank(b) - rank(a) || (b.degree || b.size || 0) - (a.degree || a.size || 0);
      });
      for (const d of ordered) {
        if (!isTopics && k < 1.6 && !nearby?.has(d.index)) continue;
        if (nearby && !nearby.has(d.index)) continue;
        const x = transform.applyX(d.x), y = transform.applyY(d.y + radius(d) + 15 / k);
        if (x < 0 || x > W || y < 0 || y > H) continue;
        // Measured at default 16px, rendered at constant 11px screen size.
        const half = (captionWidths.get(d.index) || 100) * 11 / 16 / 2;
        const cells = [];
        for (let ix = Math.floor((x - half - 4) / 20); ix <= Math.floor((x + half + 4) / 20); ix++)
          for (let iy = Math.floor((y - 12) / 16); iy <= Math.floor((y + 3) / 16); iy++) cells.push(`${ix},${iy}`);
        if (d !== active && cells.some(cell => occupied.has(cell))) continue;
        cells.forEach(cell => occupied.add(cell)); visible.add(d.index);
      }
      captions.attr('display', d => visible.has(d.index) ? null : 'none');
    }
    function highlight() {
      const active = selected || hovered, nearby = active ? adjacency.get(active.index) : null;
      const incident = d => active && (d.source === active || d.target === active);
      link.attr('stroke', d => incident(d) ? '#d3edff' : '#587b9e')
        .attr('stroke-opacity', d => active ? incident(d) ? .92 : .035 : .24)
        .attr('stroke-width', d => width(d) + (incident(d) ? .8 : 0));
      light.attr('stroke', active?.color || '#83c8ff').attr('stroke-opacity', d => incident(d) ? .18 : 0);
      drawLinks();
      node.attr('opacity', d => nearby && !nearby.has(d.index) ? .19 : 1)
        .attr('aria-pressed', d => d === selected ? 'true' : 'false');
      node.select('.stellar-halo').attr('r', d => radius(d) * (d === active ? 3.6 : 2.4));
      node.select('.stellar-sphere').attr('stroke', d => d === active ? '#e8f6ff' : d.color || '#7089a3')
        .attr('stroke-width', d => d === active ? 1.8 : .7);
      layoutLabels();
    }
    function paragraph(text, className) {
      const p = document.createElement('p'); p.textContent = text;
      if (className) p.className = className; body.appendChild(p); return p;
    }
    function select(d) {
      selected = d; hovered = null; tip.style.opacity = '0';
      detail.hidden = !d; body.replaceChildren();
      if (d) {
        paragraph(isTopics ? 'Tópico · ' + model.label : d.short_citation, 'detail-kicker');
        const h = document.createElement('h3'); h.textContent = isTopics ? d.label : d.title; body.appendChild(h);
        paragraph(isTopics ? `${d.size} documentos · ${(d.words || []).join(' · ')}` : d.topic ? `T${d.topic} · ${d.topic_label || 'Tema sin etiqueta'}` : d.topic_label || 'Sin tema asignado');
        paragraph(`${adjacency.get(d.index).size - 1} conexiones directas en esta red`);
        if (!isTopics) {
          const semantic = links.some(e => e.relation === 'semantic');
          if (semantic) paragraph('Conexiones por coseno de embeddings multilingües. No representan citas ni términos necesariamente idénticos.', 'detail-missing');
          paragraph('Etiquetas retenidas: ' + ((d.keywords || []).join(' · ') || 'Ninguna'), 'detail-missing');
          paragraph('Procedencia: ' + (d.keyword_provenance?.label || 'Sin trazabilidad'), 'detail-missing');
          const incidentLinks=links.filter(e=>e.source===d||e.target===d).sort((a,b)=>b.weight-a.weight);
          if(incidentLinks.length){const evidence=document.createElement('details');const summary=document.createElement('summary');summary.textContent=(semantic?'Ver semejanzas semánticas (':'Ver conexiones y etiquetas compartidas (')+incidentLinks.length+')';evidence.appendChild(summary);
            for(const edge of incidentLinks){const other=edge.source===d?edge.target:edge.source;const p=document.createElement('p');p.textContent=(other.short_citation||other.title)+(semantic?' · coseno ':' · semejanza ')+edge.weight.toLocaleString('es-AR',{maximumFractionDigits:3})+(semantic?'':' · '+(edge.shared_keywords||[]).join(' · '));evidence.appendChild(p);}body.appendChild(evidence);}
          if(d.keyword_excluded?.length){const excluded=document.createElement('details');const title=document.createElement('summary');title.textContent='Ver etiquetas excluidas por el diccionario propuesto';excluded.appendChild(title);for(const rule of d.keyword_excluded){const p=document.createElement('p');p.textContent=rule.original+' · '+rule.reason;excluded.appendChild(p);}body.appendChild(excluded);}
          paragraph(d.reference || `${d.authors || 'Sin autor'} (${d.year || 's. f.'}). ${d.title}.`, 'detail-reference');
          if (d.reference_missing?.length) paragraph('Datos por completar: ' + d.reference_missing.join(', '), 'detail-missing');
          try {
            const url = new URL(d.url);
            if (['https:', 'http:'].includes(url.protocol)) {
              const a = document.createElement('a'); a.href = url.href; a.target = '_blank'; a.rel = 'noopener noreferrer';
              a.textContent = 'Abrir publicación ↗'; body.appendChild(a);
            }
          } catch (_) { /* Missing URL: leave the reference readable. */ }
        }
      }
      if (onSelect) onSelect(d, body);
      highlight();
    }
    close.onclick = () => {const previous = selected; select(null); node.filter(d => d === previous).node()?.focus();};
    node.on('mouseover', (ev, d) => {
      hovered = d; highlight(); tip.replaceChildren();
      const strong = document.createElement('strong'); strong.textContent = isTopics ? d.label : d.title; tip.appendChild(strong);
      const p = document.createElement('div'); p.textContent = isTopics ? `${d.size} documentos` : d.short_citation; tip.appendChild(p);
      tip.style.opacity = '1'; moveTip(ev);
    }).on('mousemove', moveTip).on('mouseout', () => {hovered = null; tip.style.opacity = '0'; highlight();})
      .on('click', (ev, d) => {ev.stopPropagation(); select(d);})
      .on('keydown', (ev, d) => {if (['Enter', ' '].includes(ev.key)) {ev.preventDefault(); select(d); close.focus();}})
      .call(d3.drag().on('start', (e, d) => {
        tip.style.opacity = '0'; if (!e.active) simulation.alphaTarget(.3).restart(); d.fx = d.x; d.fy = d.y;
      }).on('drag', (e, d) => {d.fx = e.x; d.fy = e.y;})
        .on('end', (e, d) => {if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null;}));
    function moveTip(ev) {
      tip.style.left = Math.max(6, Math.min(ev.clientX + 14, window.innerWidth - 280)) + 'px';
      tip.style.top = Math.max(6, Math.min(ev.clientY + 12, window.innerHeight - tip.offsetHeight - 8)) + 'px';
    }
    const zoom = d3.zoom().extent(() => [[0, 0], [W, H]]).scaleExtent([.025, 10])
      .on('zoom', e => {transform = e.transform; g.attr('transform', transform); drawLinks(); layoutLabels();});
    svg.call(zoom).call(zoom.transform, d3.zoomIdentity).on('click.stellar', () => select(null));
    function fit() {
      const x0 = d3.min(nodes, d => d.x - radius(d)) - 35, x1 = d3.max(nodes, d => d.x + radius(d)) + 35;
      const y0 = d3.min(nodes, d => d.y - radius(d)) - 35, y1 = d3.max(nodes, d => d.y + radius(d)) + 35;
      const k = Math.max(.025, Math.min(2, (W - 35) / (x1 - x0), (H - 60) / (y1 - y0)));
      svg.call(zoom.transform, d3.zoomIdentity.translate(W / 2 - k * (x0 + x1) / 2, H / 2 - k * (y0 + y1) / 2).scale(k));
    }
    document.getElementById('net-zoom-in').onclick = () => {firstFit = true; svg.call(zoom.scaleBy, 1.4);};
    document.getElementById('net-zoom-out').onclick = () => {firstFit = true; svg.call(zoom.scaleBy, 1 / 1.4);};
    document.getElementById('net-fit').onclick = () => {firstFit = true; fit();};
    svg.on('pointerdown.stellar', () => {firstFit = true;});
    const escape = e => {if (e.key === 'Escape') {select(null); tip.style.opacity = '0';}};
    document.addEventListener('keydown', escape);
    simulation.on('tick', () => {
      frames++;if(!isTopics && frames%3!==0 && simulation.alpha()>.02)return;
      drawLinks();
      link.attr('x1', d => d.source.x).attr('y1', d => d.source.y).attr('x2', d => d.target.x).attr('y2', d => d.target.y);
      light.attr('x1', d => d.source.x).attr('y1', d => d.source.y).attr('x2', d => d.target.x).attr('y2', d => d.target.y);
      if (nodes.length < 1000 || frames % 2 === 0) node.attr('transform', d => `translate(${d.x},${d.y})`);
      captions.filter(function(){return this.getAttribute('display') !== 'none';}).attr('x', d => d.x).attr('y', d => d.y + radius(d) + 15 / transform.k);
      if (frames % 12 === 0) layoutLabels();
      if (!firstFit && simulation.alpha() < .09) {firstFit = true; fit();}
    });
    const observer = new ResizeObserver(() => {
      if (disposed) return;
      W = svgEl.clientWidth || W; H = svgEl.clientHeight || H;
      svg.attr('width', W).attr('height', H); placeStars(); resizeCanvas(); drawLinks(); layoutLabels();
    });
    observer.observe(svgEl);
    return {stop() {disposed = true; simulation.stop(); canvas?.remove(); observer.disconnect(); document.removeEventListener('keydown', escape); svg.on('.stellar', null);}};
  }
  return {render};
})();
