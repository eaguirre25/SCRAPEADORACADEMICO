/* D3 force layout + high-FPS WebGL/Canvas astrophysical network renderer.
 * Preserves full accessibility, DOM test hooks, and exact edge semantics while
 * delivering nebula cluster clouds, curved energy filaments, orbital shockwaves,
 * animated photon pulses, and 60fps interaction across 9,400+ nodes.
 */
window.StellarNetwork = (() => {
  function render({svgEl, model, view, isTopics, tip, onSelect}) {
    const svg = d3.select(svgEl);
    const detail = document.getElementById('net-detail');
    const body = document.getElementById('net-detail-body');
    const close = document.getElementById('net-detail-close');
    detail.hidden = true;
    let W = svgEl.clientWidth || 800, H = svgEl.clientHeight || 400;
    let transform = d3.zoomIdentity, selected = null, hovered = null, frames = 0;
    let firstFit = false, disposed = false, filterTopic = null, animId = null, pulsePhase = 0;
    svg.attr('width', W).attr('height', H);

    // Build SVG radial gradients for 3D stellar spheres & luminous halos
    const defs = svg.append('defs');
    const glowFilter = defs.append('filter').attr('id', 'stellar-bloom')
      .attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%');
    glowFilter.append('feGaussianBlur').attr('stdDeviation', '3.2').attr('result', 'blur');
    const feMerge = glowFilter.append('feMerge');
    feMerge.append('feMergeNode').attr('in', 'blur');
    feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

    const colors = [...new Set(view.nodes.map(n => n.color || '#7089a3'))];
    const colorRgbMap = new Map();
    colors.forEach((color, i) => {
      const base = d3.color(color) || d3.color('#7089a3');
      const rgb = base.rgb();
      colorRgbMap.set(color, rgb);
      const sphere = defs.append('radialGradient').attr('id', 'stellar-sphere-' + i)
        .attr('cx', '30%').attr('cy', '24%').attr('r', '78%');
      [[0, '#ffffff'], [.15, base.brighter(1.45)], [.48, base], [.85, base.darker(1.8)], [1, base.darker(3.0)]]
        .forEach(([offset, shade]) => sphere.append('stop').attr('offset', offset).attr('stop-color', shade));
      const halo = defs.append('radialGradient').attr('id', 'stellar-halo-' + i);
      [[0, .52], [.38, .22], [.72, .06], [1, 0]].forEach(([offset, opacity]) => halo.append('stop')
        .attr('offset', offset).attr('stop-color', base.brighter(.85)).attr('stop-opacity', opacity));
    });

    // Sprites precalculados por color: esfera sombreada y halo. Se dibujan con drawImage,
    // lo que permite el mismo relieve que las esferas SVG sin un gradiente por nodo y por cuadro.
    const sphereSprites = new Map(), haloSprites = new Map();
    function sphereSprite(color) {
      let s = sphereSprites.get(color);
      if (s) return s;
      const S = 96, c = document.createElement('canvas'); c.width = c.height = S;
      const x = c.getContext('2d'), base = d3.color(color) || d3.color('#7089a3');
      const gr = x.createRadialGradient(S * .30, S * .24, 0, S * .30, S * .24, S * .78);
      [[0, '#ffffff'], [.15, base.brighter(1.45)], [.48, base], [.85, base.darker(1.8)], [1, base.darker(3.0)]]
        .forEach(([o, col]) => gr.addColorStop(o, col.toString()));
      x.beginPath(); x.arc(S / 2, S / 2, S / 2 - 2, 0, Math.PI * 2); x.fillStyle = gr; x.fill();
      x.lineWidth = 1.6; x.strokeStyle = base.copy({opacity: .78}).toString(); x.stroke();
      sphereSprites.set(color, c);
      return c;
    }
    function haloSprite(color) {
      let s = haloSprites.get(color);
      if (s) return s;
      const S = 128, c = document.createElement('canvas'); c.width = c.height = S;
      const x = c.getContext('2d'), base = (d3.color(color) || d3.color('#7089a3')).brighter(.6).rgb();
      const gr = x.createRadialGradient(S / 2, S / 2, S * .1, S / 2, S / 2, S / 2);
      gr.addColorStop(0, `rgba(${base.r},${base.g},${base.b},.62)`);
      gr.addColorStop(.45, `rgba(${base.r},${base.g},${base.b},.2)`);
      gr.addColorStop(1, `rgba(${base.r},${base.g},${base.b},0)`);
      x.fillStyle = gr; x.fillRect(0, 0, S, S);
      haloSprites.set(color, c);
      return c;
    }

    // Multi-layered deep-space starfield with subtle parallax
    const stars = svg.append('g').attr('aria-hidden', 'true').attr('pointer-events', 'none');
    const starData = d3.range(135).map(i => ({
      x: ((i * 73.31 + 19) % 997) / 997,
      y: ((i * 137.17 + 53) % 991) / 991,
      r: i % 15 === 0 ? 1.55 : i % 6 === 0 ? 1.0 : .52,
      tint: i % 11 === 0 ? '#9be2ff' : i % 7 === 0 ? '#ffd8a8' : '#c4deff',
      op: i % 15 === 0 ? .68 : i % 6 === 0 ? .38 : .18
    }));
    const starDots = stars.selectAll('circle').data(starData).join('circle')
      .attr('fill', d => d.tint).attr('opacity', d => d.op).attr('r', d => d.r);
    const placeStars = () => starDots
      .attr('cx', d => (d.x * W + transform.x * 0.04 * d.r + W) % W)
      .attr('cy', d => (d.y * H + transform.y * 0.04 * d.r + H) % H);
    placeStars();

    if (!view.nodes.length) {
      svg.append('text').attr('x', W / 2).attr('y', H / 2).attr('text-anchor', 'middle')
        .attr('fill', '#a9c1db').attr('font-size', 13).text('Este modelo no tiene documentos suficientes para tejer una red.');
      ['net-zoom-in', 'net-zoom-out', 'net-fit'].forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.onclick = null;
      });
      return {stop() {}};
    }

    const g = svg.append('g').attr('class', 'stellar-world');
    const nodes = view.nodes.map((n, idx) => ({...(window.StellarPapers?.[n.id] || {}), ...n, index: idx}));
    const links = view.edges.map(e => ({...e}));
    const isDenseDocs = !isTopics && nodes.length > 900;
    const maxWeight = Math.max(1, ...nodes.map(n => (isTopics ? n.size : n.degree) || 1));
    const radius = d => isTopics
      ? 11 + Math.sqrt((d.size || 1) / maxWeight) * 26
      : 3.6 + Math.pow((d.degree || 0) / maxWeight, 0.72) * 10.5;
    const width = d => isTopics ? Math.max(.9, d.weight * 3.8) : .55 + 2.6 * d.weight;

    // Group centroids for topic nebula clouds & gravitation
    const topicGroups = new Map();
    nodes.forEach((n, idx) => {
      const t = isTopics ? String(n.id) : String(n.topic || '');
      if (t && t !== '-1') {
        if (!topicGroups.has(t)) topicGroups.set(t, {color: n.color || '#58a6ff', label: isTopics ? n.label : (n.topic_label || `T${t}`), indices: []});
        topicGroups.get(t).indices.push(idx);
      }
    });

    // Deterministic spiral seed positions so clusters bloom cleanly and rapidly
    const topicKeys = [...topicGroups.keys()];
    const topicTargets = new Map();
    topicKeys.forEach((tk, i) => {
      const angle = i * 2.399963229728653; // Golden angle
      const dist = isTopics ? 55 * Math.sqrt(i + 1) : 85 * Math.sqrt(i + 1);
      topicTargets.set(tk, {
        x: W / 2 + Math.cos(angle) * dist,
        y: H / 2 + Math.sin(angle) * dist
      });
    });
    nodes.forEach((n, i) => {
      const tk = isTopics ? String(n.id) : String(n.topic || '');
      const target = topicTargets.get(tk);
      const a = i * 2.399963229728653;
      const r = target ? 18 + (i % 17) * 2.5 : 190 + (i % 45) * 4;
      n.x = (target ? target.x : W / 2) + Math.cos(a) * r;
      n.y = (target ? target.y : H / 2) + Math.sin(a) * r;
    });

    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id((_, i) => i)
        .distance(isTopics ? d => 145 - 75 * d.weight : d => 92 - 64 * d.weight)
        .strength(isTopics ? .38 : d => .18 + .65 * d.weight))
      .force('charge', d3.forceManyBody()
        .strength(isTopics ? -520 : -65)
        .distanceMax(isTopics ? 900 : 340))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide(d => radius(d) + (isTopics ? 9 : 2.2)))
      .alphaDecay(isTopics ? .024 : .052);

    // Pre-warm dense document networks so initial view is already a rich galaxy
    if (isDenseDocs) {
      simulation.tick(28);
    }

    const adjacency = new Map(nodes.map(d => [d.index, new Set([d.index])]));
    const incidentMap = new Map(nodes.map(d => [d.index, []]));
    links.forEach(d => {
      adjacency.get(d.source.index).add(d.target.index);
      adjacency.get(d.target.index).add(d.source.index);
      incidentMap.get(d.source.index).push(d);
      incidentMap.get(d.target.index).push(d);
    });

    // Dual-mode Canvas layer: always active to render deep-space nebula clouds,
    // energy filaments, and in dense document mode, high-FPS 3D glossy nodes.
    const canvas = document.createElement('canvas');
    let ctx = null, ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.className = 'stellar-links';
    canvas.setAttribute('aria-hidden', 'true');
    canvas.dataset.links = links.length;
    svgEl.parentElement.insertBefore(canvas, svgEl);
    ctx = canvas.getContext('2d');

    function resizeCanvas() {
      canvas.width = Math.ceil(W * ratio);
      canvas.height = Math.ceil(H * ratio);
    }
    resizeCanvas();

    // For topic networks (small N), keep curved SVG glowing energy filaments + SVG spheres
    const link = isTopics ? g.append('g').attr('pointer-events', 'none').selectAll('line').data(links).join('line')
      .attr('stroke', '#6896c8').attr('stroke-width', width).attr('stroke-opacity', .32)
      .attr('stroke-linecap', 'round') : g.selectAll('.no-svg-links');
    const light = isTopics ? g.append('g').attr('pointer-events', 'none').selectAll('line').data(links).join('line')
      .attr('stroke-width', d => width(d) + 5).attr('stroke-opacity', 0)
      .attr('stroke-linecap', 'round') : g.selectAll('.no-svg-lights');

    function drawCanvasScene() {
      if (!ctx) return;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      ctx.clearRect(0, 0, W, H);
      ctx.save();
      ctx.translate(transform.x, transform.y);
      ctx.scale(transform.k, transform.k);

      const active = selected || hovered;
      const nearby = active ? adjacency.get(active.index) : null;

      // 1. Astrophysical Nebula Clouds behind clusters
      for (const [tk, grp] of topicGroups.entries()) {
        if (grp.indices.length < (isTopics ? 1 : 6)) continue;
        if (filterTopic && filterTopic !== tk) continue;
        let cx = 0, cy = 0, count = 0;
        for (const idx of grp.indices) {
          const n = nodes[idx];
          if (Number.isFinite(n.x) && Number.isFinite(n.y)) {
            cx += n.x; cy += n.y; count++;
          }
        }
        if (!count) continue;
        cx /= count; cy /= count;
        const nebR = isTopics ? 68 : Math.min(220, 40 + Math.sqrt(count) * 14);
        const rgb = colorRgbMap.get(grp.color) || {r: 88, g: 166, b: 255};
        const grad = ctx.createRadialGradient(cx, cy, 2, cx, cy, nebR);
        const boost = (filterTopic === tk || (active && String(isTopics ? active.id : active.topic) === tk)) ? 0.24 : (active ? 0.04 : 0.12);
        grad.addColorStop(0, `rgba(${rgb.r},${rgb.g},${rgb.b},${boost})`);
        grad.addColorStop(0.5, `rgba(${rgb.r},${rgb.g},${rgb.b},${boost * 0.42})`);
        grad.addColorStop(1, `rgba(${rgb.r},${rgb.g},${rgb.b},0)`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(cx, cy, nebR, 0, Math.PI * 2);
        ctx.fill();
      }

      // 2. Links & Synaptic Energy Filaments (for document networks)
      let incidents = 0;
      if (!isTopics) {
        const baseAlpha = active ? 0.032 : (filterTopic ? 0.06 : 0.22);
        ctx.strokeStyle = '#5e88b4';
        ctx.globalAlpha = baseAlpha;
        for (let bucket = 0; bucket < 4; bucket++) {
          ctx.beginPath();
          ctx.lineWidth = (.45 + (bucket + .5) * .58) / Math.pow(transform.k, 0.25);
          for (const e of links) {
            if (Math.min(3, Math.floor(e.weight * 4)) !== bucket) continue;
            if (filterTopic && String(e.source.topic) !== filterTopic && String(e.target.topic) !== filterTopic) continue;
            ctx.moveTo(e.source.x, e.source.y);
            ctx.lineTo(e.target.x, e.target.y);
          }
          ctx.stroke();
        }

        // Highlighted topic links when a legend/topic filter is active
        if (filterTopic && !active) {
          const grp = topicGroups.get(filterTopic);
          const rgb = grp ? (colorRgbMap.get(grp.color) || {r: 130, g: 205, b: 255}) : {r: 130, g: 205, b: 255};
          ctx.beginPath();
          ctx.strokeStyle = `rgb(${rgb.r},${rgb.g},${rgb.b})`;
          ctx.lineWidth = 1.4 / Math.pow(transform.k, 0.25);
          ctx.globalAlpha = 0.55;
          for (const e of links) {
            if (String(e.source.topic) === filterTopic && String(e.target.topic) === filterTopic) {
              ctx.moveTo(e.source.x, e.source.y);
              ctx.lineTo(e.target.x, e.target.y);
            }
          }
          ctx.stroke();
        }

        // Active node glowing filaments + traveling photon pulses
        if (active) {
          const activeEdges = incidentMap.get(active.index) || [];
          incidents = activeEdges.length;
          const aColor = d3.color(active.color || '#79c8ff')?.rgb() || {r: 121, g: 200, b: 255};

          // Outer glow pass
          ctx.beginPath();
          ctx.strokeStyle = `rgba(${aColor.r},${aColor.g},${aColor.b},0.34)`;
          ctx.lineWidth = 5.2 / Math.pow(transform.k, 0.3);
          ctx.globalAlpha = 1;
          for (const e of activeEdges) {
            ctx.moveTo(e.source.x, e.source.y);
            ctx.lineTo(e.target.x, e.target.y);
          }
          ctx.stroke();

          // Core bright filament pass
          ctx.beginPath();
          ctx.strokeStyle = '#e2f4ff';
          ctx.lineWidth = 1.9 / Math.pow(transform.k, 0.3);
          ctx.globalAlpha = 0.94;
          for (const e of activeEdges) {
            ctx.moveTo(e.source.x, e.source.y);
            ctx.lineTo(e.target.x, e.target.y);
          }
          ctx.stroke();

          // Traveling photon particles along active edges
          ctx.fillStyle = '#ffffff';
          for (let i = 0; i < activeEdges.length; i++) {
            const e = activeEdges[i];
            const from = e.source === active ? e.source : e.target;
            const to = e.source === active ? e.target : e.source;
            const t = ((pulsePhase * 0.018 + (i % 7) * 0.14) % 1);
            const px = from.x + (to.x - from.x) * t;
            const py = from.y + (to.y - from.y) * t;
            ctx.beginPath();
            ctx.arc(px, py, 2.3 / Math.pow(transform.k, 0.35), 0, Math.PI * 2);
            ctx.fill();
          }
        }
      } else if (active) {
        // In topic view, draw traveling photon particles on canvas over active topic links
        const activeEdges = incidentMap.get(active.index) || [];
        incidents = activeEdges.length;
        ctx.fillStyle = '#ffffff';
        ctx.globalAlpha = 0.95;
        for (let i = 0; i < activeEdges.length; i++) {
          const e = activeEdges[i];
          const from = e.source === active ? e.source : e.target;
          const to = e.source === active ? e.target : e.source;
          const t = ((pulsePhase * 0.015 + i * 0.19) % 1);
          const px = from.x + (to.x - from.x) * t;
          const py = from.y + (to.y - from.y) * t;
          ctx.beginPath();
          ctx.arc(px, py, 3.2 / Math.pow(transform.k, 0.25), 0, Math.PI * 2);
          ctx.fill();
        }
      }

      // 3. High-FPS 3D Glossy Spheres on Canvas for dense document mode
      if (isDenseDocs) {
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';
        const vx0 = -transform.x / transform.k - 40;
        const vy0 = -transform.y / transform.k - 40;
        const vx1 = (W - transform.x) / transform.k + 40;
        const vy1 = (H - transform.y) / transform.k + 40;

        for (let i = 0; i < nodes.length; i++) {
          const d = nodes[i];
          const x = d.x, y = d.y;
          if (x < vx0 || x > vx1 || y < vy0 || y > vy1) continue;
          const r = radius(d);
          const isAct = d === active;
          const isNear = nearby ? nearby.has(d.index) : (!filterTopic || String(d.topic) === filterTopic);
          const alpha = isAct ? 1 : (nearby ? (isNear ? 0.96 : 0.13) : (filterTopic ? (isNear ? 0.95 : 0.12) : 0.9));
          ctx.globalAlpha = alpha;

          const baseColor = d.color || '#7089a3';
          const rgb = colorRgbMap.get(baseColor) || {r: 112, g: 137, b: 163};

          // Halo for hubs, active, or neighbors
          if (isAct || (nearby && isNear) || d.degree > 12) {
            const haloR = r * (isAct ? 3.8 : 2.3);
            ctx.globalAlpha = alpha * (isAct ? 1 : 0.55);
            ctx.drawImage(haloSprite(baseColor), x - haloR, y - haloR, haloR * 2, haloR * 2);
            ctx.globalAlpha = alpha;
          }

          // Cuerpo esférico: sprite sombreado de cerca, punto plano cuando el nodo mide menos de 2 px.
          if (r * transform.k < 1.7) {
            // Mínimo de ~1,2 px en pantalla para que la vista general conserve su densidad luminosa.
            const rr = Math.max(r, 0.6 / transform.k);
            ctx.fillStyle = baseColor;
            ctx.fillRect(x - rr, y - rr, rr * 2, rr * 2);
          } else {
            ctx.drawImage(sphereSprite(baseColor), x - r, y - r, r * 2, r * 2);
          }

          // Active orbital ring
          if (isAct) {
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 1.8 / Math.pow(transform.k, 0.35);
            ctx.beginPath();
            ctx.arc(x, y, r + 3.2 / Math.pow(transform.k, 0.35), 0, Math.PI * 2);
            ctx.stroke();

            const pulseR = r + 6 + (pulsePhase % 30) * 0.45;
            ctx.strokeStyle = `rgba(${rgb.r},${rgb.g},${rgb.b},${Math.max(0, 0.7 - (pulsePhase % 30) / 42)})`;
            ctx.lineWidth = 1.5 / Math.pow(transform.k, 0.35);
            ctx.beginPath();
            ctx.arc(x, y, pulseR, 0, Math.PI * 2);
            ctx.stroke();
          }
        }
      }

      canvas.dataset.highlighted = incidents;
      ctx.restore();
      ctx.globalAlpha = 1;
    }

    // Create accessible DOM node elements.
    // In dense mode (>900 docs), we keep lightweight hit/a11y nodes without 18,000 gradient circles,
    // while in topics / Argentina view (<900 nodes) we render full SVG spheres + halos + planetary rings.
    // En modo denso los nodos no tienen elementos DOM propios: se dibujan en el canvas y el
    // mouse, el teclado y los lectores de pantalla se atienden a nivel del SVG (ver más abajo).
    const node = g.append('g').selectAll('g').data(isDenseDocs ? [] : nodes).join('g').attr('class', 'stellar-node')
      .attr('tabindex', 0).attr('role', 'button').attr('aria-pressed', 'false')
      .attr('aria-label', d => isTopics ? `T${d.id}: ${d.label}` : `${d.short_citation || d.authors || 'Sin autor'}: ${d.title}`)
      .style('cursor', 'pointer');

    if (!isDenseDocs) {
      node.append('circle').attr('class', 'stellar-halo').attr('r', d => radius(d) * 2.55)
        .attr('fill', d => `url(#stellar-halo-${colors.indexOf(d.color || '#7089a3')})`).attr('pointer-events', 'none');
      if (isTopics) {
        node.append('circle').attr('class', 'stellar-orbit').attr('r', d => radius(d) * 1.34)
          .attr('fill', 'none').attr('stroke', d => d.color || '#7089a3')
          .attr('stroke-opacity', .32).attr('stroke-width', 1.1)
          .attr('stroke-dasharray', '4 3').attr('pointer-events', 'none');
      }
      node.append('circle').attr('class', 'stellar-sphere').attr('r', radius)
        .attr('fill', d => `url(#stellar-sphere-${colors.indexOf(d.color || '#7089a3')})`)
        .attr('stroke', d => d.color || '#7089a3').attr('stroke-opacity', .78).attr('stroke-width', isTopics ? 1.2 : .8);
      node.append('circle').attr('r', d => Math.max(10, radius(d))).attr('fill', 'transparent');
    } else {
      // Lightweight transparent hit target for accessibility and direct clicks
      node.append('circle').attr('class', 'stellar-sphere').attr('r', d => Math.max(7, radius(d)))
        .attr('fill', 'transparent').attr('stroke', 'none');
    }

    // Los registros sin autor se rotulan con el comienzo del título en lugar de "Sin autor, 2024".
    const labelOf = d => {
      if (isTopics) return `T${d.id} · ${(d.label || '').slice(0, 48)}${(d.label || '').length > 48 ? '…' : ''}`;
      const cite = d.short_citation || `${d.authors || 'Sin autor'}, ${d.year || 's. f.'}`;
      if (/^sin autor/i.test(cite) && d.title) return `${d.title.slice(0, 26).trim()}${d.title.length > 26 ? '…' : ''}${d.year ? ', ' + d.year : ''}`;
      return cite;
    };
    // En modo denso las etiquetas son un grupo reducido de <text> que se reasigna al nodo que corresponda.
    const LABEL_SLOTS = 240;
    const captions = g.append('g').attr('aria-hidden', 'true').selectAll('text')
      .data(isDenseDocs ? d3.range(LABEL_SLOTS).map(slot => ({slot, index: -1})) : nodes).join('text')
      .attr('class', 'stellar-label').attr('text-anchor', 'middle')
      .attr('display', isDenseDocs ? 'none' : null)
      .text(d => isDenseDocs ? '' : labelOf(d));

    // Estimate label width arithmetically in dense mode to avoid 9,476 synchronous layout reflows
    const captionWidths = new Map();
    if (isDenseDocs) {
      nodes.forEach(d => {
        const txt = labelOf(d);
        captionWidths.set(d.index, Math.max(48, txt.length * 6.4));
      });
    } else {
      captions.each(function(d) { captionWidths.set(d.index, this.getComputedTextLength()); });
    }

    // Pre-sort nodes by degree/size once so label collision detection doesn't sort 9,476 items per frame
    const baseOrderedNodes = [...nodes].sort((a, b) => (b.degree || b.size || 0) - (a.degree || a.size || 0));

    // Etiquetas del modo denso: se eligen entre los nodos visibles en pantalla (los de más grado primero),
    // de modo que al acercarse a cualquier zona aparezcan sus autores, no solo los de los nodos centrales.
    function layoutLabelsDense() {
      const active = selected || hovered;
      const nearby = active ? adjacency.get(active.index) : null;
      const k = transform.k, fontSize = 12 / k;
      const cap = active ? 140 : Math.max(24, Math.min(LABEL_SLOTS, Math.round(30 + 70 * k)));
      const inView = d => {
        const sx = transform.applyX(d.x), sy = transform.applyY(d.y);
        return sx > -30 && sx < W + 30 && sy > -10 && sy < H + 30;
      };
      const ordered = [];
      if (active) {
        ordered.push(active);
        for (const idx of nearby) if (idx !== active.index && inView(nodes[idx])) ordered.push(nodes[idx]);
      } else {
        for (const d of baseOrderedNodes) {
          if (filterTopic && String(d.topic) !== filterTopic) continue;
          if (!inView(d)) continue;
          ordered.push(d);
          if (ordered.length >= cap * 3) break;
        }
      }
      const occupied = new Set(), shown = [];
      for (const d of ordered) {
        const x = transform.applyX(d.x), y = transform.applyY(d.y + radius(d) + 15 / k);
        const half = (captionWidths.get(d.index) || 96) * 12 / 16 / 2;
        const cells = [];
        for (let ix = Math.floor((x - half - 4) / 20); ix <= Math.floor((x + half + 4) / 20); ix++)
          for (let iy = Math.floor((y - 12) / 16); iy <= Math.floor((y + 3) / 16); iy++) cells.push(`${ix},${iy}`);
        if (d !== active && cells.some(cell => occupied.has(cell))) continue;
        cells.forEach(cell => occupied.add(cell));
        shown.push(d);
        if (shown.length >= Math.min(cap, LABEL_SLOTS)) break;
      }
      captions.each(function (_, i) {
        const d = shown[i];
        if (!d) { if (this.getAttribute('display') !== 'none') this.setAttribute('display', 'none'); return; }
        this.removeAttribute('display');
        if (this.__node !== d) { this.textContent = labelOf(d); this.__node = d; }
        this.setAttribute('x', d.x);
        this.setAttribute('y', d.y + radius(d) + 15 / k);
        this.setAttribute('font-size', d === active ? fontSize * 1.12 : fontSize);
        this.setAttribute('font-weight', d === active ? '700' : '500');
        this.setAttribute('stroke-width', 3.2 / k);
      });
    }

    function layoutLabels() {
      if (isDenseDocs) { layoutLabelsDense(); return; }
      const active = selected || hovered;
      const nearby = active ? adjacency.get(active.index) : null;
      const k = transform.k, fontSize = (isTopics ? 11.5 : 11) / k;
      const occupied = new Set(), visible = new Set();

      const candidates = [];
      if (active) {
        candidates.push(active);
        if (nearby) {
          for (const idx of nearby) {
            if (idx !== active.index) candidates.push(nodes[idx]);
          }
        }
      } else {
        for (const d of baseOrderedNodes) {
          if (filterTopic && String(isTopics ? d.id : d.topic) !== filterTopic) continue;
          if (!isTopics && k < 1.35 && (d.degree || 0) < Math.max(8, maxWeight * 0.38)) continue;
          candidates.push(d);
          if (candidates.length >= (isTopics ? 60 : 95)) break;
        }
      }

      for (const d of candidates) {
        const x = transform.applyX(d.x), y = transform.applyY(d.y + radius(d) + 15 / k);
        if (x < -40 || x > W + 40 || y < -20 || y > H + 20) continue;
        const half = (captionWidths.get(d.index) || 96) * 11 / 16 / 2;
        const cells = [];
        for (let ix = Math.floor((x - half - 4) / 20); ix <= Math.floor((x + half + 4) / 20); ix++)
          for (let iy = Math.floor((y - 12) / 16); iy <= Math.floor((y + 3) / 16); iy++) cells.push(`${ix},${iy}`);
        if (d !== active && cells.some(cell => occupied.has(cell))) continue;
        cells.forEach(cell => occupied.add(cell));
        visible.add(d.index);
      }

      captions
        .attr('display', d => visible.has(d.index) ? null : 'none')
        .filter(d => visible.has(d.index))
        .attr('font-size', d => d === active ? fontSize * 1.12 : fontSize)
        .attr('font-weight', d => d === active ? '700' : '500')
        .attr('stroke-width', 3.2 / k)
        .attr('x', d => d.x)
        .attr('y', d => d.y + radius(d) + 15 / k);
    }

    function updatePulseLoop() {
      const active = selected || hovered;
      if (active && !disposed) {
        if (!animId) {
          const step = () => {
            if (disposed || !(selected || hovered)) { animId = null; return; }
            pulsePhase = (pulsePhase + 1) % 360;
            drawCanvasScene();
            animId = requestAnimationFrame(step);
          };
          animId = requestAnimationFrame(step);
        }
      } else if (animId) {
        cancelAnimationFrame(animId);
        animId = null;
      }
    }

    function highlight() {
      const active = selected || hovered, nearby = active ? adjacency.get(active.index) : null;
      const incident = d => active && (d.source === active || d.target === active);
      if (isTopics) {
        link.attr('stroke', d => incident(d) ? '#e2f4ff' : '#6896c8')
          .attr('stroke-opacity', d => active ? (incident(d) ? .95 : .06) : .32)
          .attr('stroke-width', d => width(d) + (incident(d) ? 1.2 : 0));
        light.attr('stroke', active?.color || '#83c8ff').attr('stroke-opacity', d => incident(d) ? .26 : 0);
      }
      drawCanvasScene();
      if (!isDenseDocs) {
        node.attr('opacity', d => {
          if (nearby) return nearby.has(d.index) ? 1 : .16;
          if (filterTopic) return String(isTopics ? d.id : d.topic) === filterTopic ? 1 : .16;
          return 1;
        }).attr('aria-pressed', d => d === selected ? 'true' : 'false');
        node.select('.stellar-halo').attr('r', d => radius(d) * (d === active ? 3.8 : 2.55));
        node.select('.stellar-sphere')
          .attr('stroke', d => d === active ? '#ffffff' : d.color || '#7089a3')
          .attr('stroke-width', d => d === active ? 2.2 : (isTopics ? 1.2 : .8));
      } else {
        node.attr('aria-pressed', d => d === selected ? 'true' : 'false');
      }
      layoutLabels();
      updatePulseLoop();
    }

    function paragraph(text, className) {
      const p = document.createElement('p'); p.textContent = text;
      if (className) p.className = className; body.appendChild(p); return p;
    }

    function select(d) {
      // La ficha usa campos pesados (referencia, procedencia) que se piden solo al abrir un nodo.
      if (!isTopics && d && window.ensurePaperDetails && !window.StellarPaperDetails) {
        window.ensurePaperDetails().then(() => select(d)).catch(() => selectNow(d));
        return;
      }
      if (!isTopics && d && window.StellarPaperDetails?.[d.id]) Object.assign(d, window.StellarPaperDetails[d.id]);
      selectNow(d);
    }
    function selectNow(d) {
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
          const incidentLinks = (incidentMap.get(d.index) || []).slice().sort((a, b) => b.weight - a.weight);
          if (incidentLinks.length) {
            const evidence = document.createElement('details');
            const summary = document.createElement('summary');
            summary.textContent = (semantic ? 'Ver semejanzas semánticas (' : 'Ver conexiones y etiquetas compartidas (') + incidentLinks.length + ')';
            evidence.appendChild(summary);
            for (const edge of incidentLinks) {
              const other = edge.source === d ? edge.target : edge.source;
              const p = document.createElement('p');
              p.textContent = (other.short_citation || other.title) + (semantic ? ' · coseno ' : ' · semejanza ') + edge.weight.toLocaleString('es-AR', {maximumFractionDigits: 3}) + (semantic ? '' : ' · ' + (edge.shared_keywords || []).join(' · '));
              evidence.appendChild(p);
            }
            body.appendChild(evidence);
          }
          if (d.keyword_excluded?.length) {
            const excluded = document.createElement('details');
            const title = document.createElement('summary');
            title.textContent = 'Ver etiquetas excluidas por el diccionario propuesto';
            excluded.appendChild(title);
            for (const rule of d.keyword_excluded) {
              const p = document.createElement('p');
              p.textContent = rule.original + ' · ' + rule.reason;
              excluded.appendChild(p);
            }
            body.appendChild(excluded);
          }
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
      if (isDenseDocs && d && !suppressReveal) reveal(d);
    }

    close.onclick = () => { const previous = selected; select(null); node.filter(d => d === previous).node()?.focus(); };

    function showTooltip(ev, d) {
      tip.replaceChildren();
      const strong = document.createElement('strong');
      strong.textContent = isTopics ? `T${d.id} · ${d.label}` : d.title;
      tip.appendChild(strong);
      const p = document.createElement('div');
      const deg = adjacency.get(d.index).size - 1;
      p.textContent = isTopics
        ? `${d.size} documentos · ${deg} enlaces temáticos`
        : `${d.short_citation || ''} · ${deg} conexiones${d.topic ? ` · T${d.topic}` : ''}`;
      tip.appendChild(p);
      tip.style.opacity = '1';
      moveTip(ev);
    }

    node.on('mouseover', (ev, d) => {
      hovered = d; highlight(); showTooltip(ev, d);
    }).on('mousemove', moveTip).on('mouseout', () => {
      hovered = null; tip.style.opacity = '0'; highlight();
    }).on('click', (ev, d) => {
      ev.stopPropagation(); select(d);
    }).on('keydown', (ev, d) => {
      if (['Enter', ' '].includes(ev.key)) { ev.preventDefault(); select(d); close.focus(); }
    }).call(d3.drag().on('start', (e, d) => {
      tip.style.opacity = '0'; if (!e.active) simulation.alphaTarget(.3).restart(); d.fx = d.x; d.fy = d.y;
    }).on('drag', (e, d) => {
      d.fx = e.x; d.fy = e.y;
    }).on('end', (e, d) => {
      if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null;
    }));

    function moveTip(ev) {
      tip.style.left = Math.max(6, Math.min(ev.clientX + 14, window.innerWidth - 290)) + 'px';
      tip.style.top = Math.max(6, Math.min(ev.clientY + 12, window.innerHeight - tip.offsetHeight - 8)) + 'px';
    }

    function syncDomNodePositions() {
      node.attr('transform', d => `translate(${d.x},${d.y})`);
    }

    // ── Modo denso: interacción a nivel del SVG ──────────────────────────────────
    // Un índice espacial (quadtree) reemplaza a los ~9.500 elementos DOM invisibles: sirve para
    // pasar el mouse, hacer clic, arrastrar un nodo y recorrerlos con el teclado.
    let qt = null, qtDirty = true, suppressReveal = false, hoverRaf = 0, lastMove = null, userMoved = false;
    const markDirty = () => { qtDirty = true; };
    function rebuildQt() {
      qt = d3.quadtree().x(d => d.x).y(d => d.y).addAll(nodes.filter(d => Number.isFinite(d.x) && Number.isFinite(d.y)));
      qtDirty = false;
    }
    function nodeAtWorld(x, y) {
      if (!isDenseDocs) return null;
      if (qtDirty || !qt) rebuildQt();
      const k = transform.k, c = qt.find(x, y, 16 / k + 14);
      if (!c) return null;
      return Math.hypot(c.x - x, c.y - y) <= Math.max(radius(c) + 2 / k, 9 / k) ? c : null;
    }
    function nodeAtEvent(ev) {
      const [px, py] = d3.pointer(ev, svgEl);
      return nodeAtWorld((px - transform.x) / transform.k, (py - transform.y) / transform.k);
    }
    // Deja a la vista un nodo: lo trae al centro del área libre si quedó fuera de pantalla o bajo la ficha.
    function reveal(d) {
      const usableW = detail.hidden ? W : Math.max(220, W - Math.min(325, W * .48) - 28);
      const sx = transform.applyX(d.x), sy = transform.applyY(d.y);
      if (sx > 56 && sx < usableW - 40 && sy > 56 && sy < H - 56) return;
      svg.transition().duration(360).call(zoom.translateTo, d.x, d.y, [usableW / 2, H / 2]);
    }
    function pickStart() {
      for (const d of baseOrderedNodes) {
        if (filterTopic && String(d.topic) !== filterTopic) continue;
        const sx = transform.applyX(d.x), sy = transform.applyY(d.y);
        if (sx > 0 && sx < W && sy > 0 && sy < H) return d;
      }
      return baseOrderedNodes[0] || null;
    }
    // Recorrido con flechas: salta al nodo más cercano en esa dirección, con preferencia por los conectados.
    function stepSelection(dx, dy) {
      const from = selected;
      if (!from) { const first = pickStart(); if (first) select(first); return; }
      if (qtDirty || !qt) rebuildQt();
      const reach = 260 / transform.k, linked = adjacency.get(from.index), cand = new Map();
      for (const idx of linked) if (idx !== from.index) cand.set(idx, nodes[idx]);
      qt.visit((q, x0, y0, x1, y1) => {
        if (!q.length) {
          let p = q;
          do {
            const d = p.data;
            if (d !== from && Math.abs(d.x - from.x) < reach && Math.abs(d.y - from.y) < reach) cand.set(d.index, d);
          } while ((p = p.next));
        }
        return x0 > from.x + reach || x1 < from.x - reach || y0 > from.y + reach || y1 < from.y - reach;
      });
      let best = null, bestScore = Infinity;
      for (const d of cand.values()) {
        const vx = d.x - from.x, vy = d.y - from.y, dist = Math.hypot(vx, vy) || 1e-6, cos = (vx * dx + vy * dy) / dist;
        if (cos < .5) continue;
        const score = dist * (1.7 - cos) * (linked.has(d.index) ? .55 : 1);
        if (score < bestScore) { bestScore = score; best = d; }
      }
      if (best) select(best);
    }
    if (isDenseDocs) {
      svg.call(d3.drag().container(g.node())
        .subject(ev => nodeAtWorld(ev.x, ev.y))
        .on('start', e => {
          tip.style.opacity = '0'; hovered = null;
          if (!e.active) simulation.alphaTarget(.3).restart();
          e.subject.fx = e.subject.x; e.subject.fy = e.subject.y;
        })
        .on('drag', e => { e.subject.fx = e.x; e.subject.fy = e.y; markDirty(); })
        .on('end', e => {
          if (!e.active) simulation.alphaTarget(0);
          e.subject.fx = null; e.subject.fy = null; markDirty();
        }));
      svg.on('pointermove.stellar', ev => {
        if ((ev.pointerType && ev.pointerType !== 'mouse') || ev.buttons) return;
        lastMove = ev;
        if (hoverRaf) return;
        hoverRaf = requestAnimationFrame(() => {
          hoverRaf = 0;
          if (disposed || !lastMove) return;
          const d = nodeAtEvent(lastMove);
          svgEl.style.cursor = d ? 'pointer' : '';
          if (d !== hovered) {
            hovered = d;
            if (d) showTooltip(lastMove, d); else tip.style.opacity = '0';
            if (!selected) highlight();
          } else if (d) moveTip(lastMove);
        });
      }).on('pointerleave.stellar', () => {
        svgEl.style.cursor = '';
        if (hovered) { hovered = null; tip.style.opacity = '0'; if (!selected) highlight(); }
      });
      svgEl.setAttribute('tabindex', '0');
      svgEl.setAttribute('role', 'application');
      svgEl.setAttribute('aria-roledescription', 'red interactiva de documentos');
      svg.on('keydown.stellar', ev => {
        if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
        const dirs = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]};
        if (dirs[ev.key]) { ev.preventDefault(); stepSelection(...dirs[ev.key]); return; }
        if (ev.key === '+' || ev.key === '=') { ev.preventDefault(); document.getElementById('net-zoom-in')?.click(); }
        else if (ev.key === '-' || ev.key === '_') { ev.preventDefault(); document.getElementById('net-zoom-out')?.click(); }
        else if (ev.key === '0' || ev.key === 'Home') { ev.preventDefault(); document.getElementById('net-fit')?.click(); }
        else if (ev.key === 'f' && selected) { ev.preventDefault(); fit([...adjacency.get(selected.index)].map(i => nodes[i]), 4); }
        else if ((ev.key === 'Enter' || ev.key === ' ')) {
          ev.preventDefault();
          if (!selected) { const first = pickStart(); if (first) select(first); }
          else (body.querySelector('a, summary') || close).focus();
        }
      });
    }

    const zoom = d3.zoom().extent(() => [[0, 0], [W, H]]).scaleExtent([.025, 12])
      .on('zoom', e => {
        if (e.sourceEvent) userMoved = true;
        transform = e.transform;
        g.attr('transform', transform);
        placeStars();
        drawCanvasScene();
        layoutLabels();
      });
    svg.call(zoom).call(zoom.transform, d3.zoomIdentity).on('click.stellar', ev => {
      if (isDenseDocs) {
        const hit = nodeAtEvent(ev);
        if (hit) { select(hit); return; }
      }
      filterTopic = null;
      select(null);
    });
    if (isDenseDocs) {
      // Doble clic: sobre un nodo enfoca su vecindario; sobre el fondo acerca la vista.
      svg.on('dblclick.zoom', null).on('dblclick.stellar', ev => {
        ev.preventDefault();
        firstFit = true;
        const hit = nodeAtEvent(ev);
        if (hit) { select(hit); fit([...adjacency.get(hit.index)].map(i => nodes[i]), 4); }
        else svg.transition().duration(300).call(zoom.scaleBy, 2, d3.pointer(ev, svgEl));
      });
    }

    // Límites para encuadrar. En redes densas se toma el cuerpo conectado de la red (sin el 1 % más
    // alejado en cada borde): los registros aislados que la simulación empuja lejos no encogen la vista,
    // siguen ahí y se alcanzan alejando el zoom.
    function frameBounds(targetNodes, pad) {
      if (!isDenseDocs || targetNodes.length < 400) {
        return [d3.min(targetNodes, d => d.x - radius(d)) - pad, d3.max(targetNodes, d => d.x + radius(d)) + pad,
          d3.min(targetNodes, d => d.y - radius(d)) - pad, d3.max(targetNodes, d => d.y + radius(d)) + pad];
      }
      const connected = targetNodes.filter(d => (d.degree || 0) > 0);
      const base = connected.length >= 50 ? connected : targetNodes;
      const xs = base.map(d => d.x).sort(d3.ascending), ys = base.map(d => d.y).sort(d3.ascending);
      return [d3.quantile(xs, .03) - pad, d3.quantile(xs, .97) + pad, d3.quantile(ys, .03) - pad, d3.quantile(ys, .97) + pad];
    }

    function fit(subsetNodes, maxK = 2.6) {
      const targetNodes = (subsetNodes && subsetNodes.length) ? subsetNodes : nodes;
      const [x0, x1, y0, y1] = frameBounds(targetNodes, 42);
      const k = Math.max(.025, Math.min(maxK, (W - 42) / Math.max(1, x1 - x0), (H - 64) / Math.max(1, y1 - y0)));
      svg.transition().duration(480).call(
        zoom.transform,
        d3.zoomIdentity.translate(W / 2 - k * (x0 + x1) / 2, H / 2 - k * (y0 + y1) / 2).scale(k)
      );
    }

    function focusTopic(topicId) {
      const tk = topicId === null || topicId === undefined ? null : String(topicId);
      filterTopic = (filterTopic === tk) ? null : tk;
      if (filterTopic) {
        const sub = nodes.filter(d => String(isTopics ? d.id : d.topic) === filterTopic);
        if (sub.length) { firstFit = true; fit(sub); }
      } else {
        firstFit = true; fit(nodes);
      }
      highlight();
      return filterTopic;
    }

    function searchNodes(query) {
      const q = (query || '').toString().trim().toLowerCase();
      if (!q) { select(null); return null; }
      const match = nodes.find(d =>
        ((isTopics ? d.label : d.title) || '').toLowerCase().includes(q) ||
        (d.short_citation || '').toLowerCase().includes(q) ||
        (d.authors || '').toLowerCase().includes(q) ||
        ((d.keywords || []).join(' ').toLowerCase().includes(q))
      );
      if (match) {
        firstFit = true;
        suppressReveal = true;
        setTimeout(() => { suppressReveal = false; }, 900);
        select(match);
        const k = Math.max(transform.k, isTopics ? 1.35 : 2.2);
        svg.transition().duration(520).call(
          zoom.transform,
          d3.zoomIdentity.translate(W / 2 - k * match.x, H / 2 - k * match.y).scale(k)
        );
      }
      return match;
    }

    const btnIn = document.getElementById('net-zoom-in');
    const btnOut = document.getElementById('net-zoom-out');
    const btnFit = document.getElementById('net-fit');
    if (btnIn) btnIn.onclick = () => { firstFit = true; svg.transition().duration(240).call(zoom.scaleBy, 1.45); };
    if (btnOut) btnOut.onclick = () => { firstFit = true; svg.transition().duration(240).call(zoom.scaleBy, 1 / 1.45); };
    if (btnFit) btnFit.onclick = () => { firstFit = true; filterTopic = null; fit(); highlight(); };

    svg.on('pointerdown.stellar', () => { firstFit = true; userMoved = true; });
    const escape = e => { if (e.key === 'Escape') { filterTopic = null; select(null); tip.style.opacity = '0'; } };
    document.addEventListener('keydown', escape);

    simulation.on('tick', () => {
      frames++;
      qtDirty = true;
      if (isDenseDocs && frames % 2 !== 0 && simulation.alpha() > .03) return;
      drawCanvasScene();
      if (isTopics) {
        link.attr('x1', d => d.source.x).attr('y1', d => d.source.y).attr('x2', d => d.target.x).attr('y2', d => d.target.y);
        light.attr('x1', d => d.source.x).attr('y1', d => d.source.y).attr('x2', d => d.target.x).attr('y2', d => d.target.y);
      }
      if (!isDenseDocs || frames % 6 === 0 || simulation.alpha() <= .09) {
        syncDomNodePositions();
      }
      if (frames % 10 === 0) layoutLabels();
      if (!firstFit && simulation.alpha() < .14) {
        firstFit = true;
        syncDomNodePositions();
        const [x0, x1, y0, y1] = frameBounds(nodes, 35);
        const k = Math.max(.025, Math.min(2, (W - 35) / Math.max(1, x1 - x0), (H - 60) / Math.max(1, y1 - y0)));
        svg.call(zoom.transform, d3.zoomIdentity.translate(W / 2 - k * (x0 + x1) / 2, H / 2 - k * (y0 + y1) / 2).scale(k));
      }
    });

    simulation.on('end', () => {
      // Al asentarse la red, si nadie movió la vista, se reencuadra sobre el diseño final.
      if (isDenseDocs && !userMoved) fit();
      syncDomNodePositions();
      drawCanvasScene();
      layoutLabels();
    });

    const observer = new ResizeObserver(() => {
      if (disposed) return;
      W = svgEl.clientWidth || W; H = svgEl.clientHeight || H;
      svg.attr('width', W).attr('height', H);
      placeStars(); resizeCanvas(); drawCanvasScene(); layoutLabels();
    });
    observer.observe(svgEl);

    return {
      focusTopic,
      searchNodes,
      stop() {
        disposed = true;
        if (animId) cancelAnimationFrame(animId);
        simulation.stop();
        canvas?.remove();
        observer.disconnect();
        document.removeEventListener('keydown', escape);
        if (hoverRaf) cancelAnimationFrame(hoverRaf);
        svgEl.style.cursor = '';
        svgEl.removeAttribute('tabindex'); svgEl.removeAttribute('role'); svgEl.removeAttribute('aria-roledescription');
        svg.on('.stellar', null).on('.drag', null).on('.zoom', null);
      }
    };
  }
  return {render};
})();
