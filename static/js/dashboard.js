WorkspacePage.run(({on, addEventListener, requestAnimationFrame, ResizeObserver, MutationObserver}) => {
/* Local SVG charts. Only server-aggregated values enter this renderer. */
(() => {
  'use strict';
  const ns = 'http://www.w3.org/2000/svg';
  const format = value => Number(value).toLocaleString('en-US');
  const nodes = [];
  const el = (tag, attrs = {}, text) => {
    const node = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const tone = index => `var(--chart-tone-${index % 6})`;
  // Monotone cubic interpolation follows recorded points without overshooting
  // a flat month or inventing a dip in cumulative membership.
  function smoothPath(points) {
    if (points.length < 2) return `M${points[0]}`;
    const slopes = points.slice(1).map((p, i) => (p[1] - points[i][1]) / (p[0] - points[i][0]));
    const tangents = points.map((_, i) => {
      if (!i) return slopes[0];
      if (i === points.length - 1) return slopes.at(-1);
      const a = slopes[i - 1], b = slopes[i];
      return a * b <= 0 ? 0 : 2 * a * b / (a + b);
    });
    return points.slice(1).reduce((path, p, i) => {
      const a = points[i], third = (p[0] - a[0]) / 3;
      return `${path} C${a[0] + third},${a[1] + tangents[i] * third} ${p[0] - third},${p[1] - tangents[i + 1] * third} ${p}`;
    }, `M${points[0]}`);
  }
  function wrapped(text, width, font) {
    const limit = Math.max(6, Math.floor(width / (font * .56)));
    const words = String(text).match(new RegExp(`.{1,${limit}}(?:\\s|$)|.{1,${limit}}`, 'g')) || [''];
    return words.map(word => word.trim());
  }
  function draw(host, data) {
    host.hidden = false;
    const font = parseFloat(getComputedStyle(host).fontSize);
    // clientWidth rounds fractional pixels up. Fit inside the actual viewport
    // so zoom/text scaling cannot introduce an unnecessary scrollbar.
    const gutter = host.offsetWidth - host.clientWidth;
    const availableWidth = Math.floor(host.getBoundingClientRect().width - gutter);
    const outerWidth = data.kind === 'member-donut' ? Math.max(availableWidth, 1) : Math.max(availableWidth, font * 14);
    const padding = font * .5, width = outerWidth - padding * 2;
    const canvas = el('svg', {width: outerWidth, role: 'presentation', 'aria-hidden': 'true'});
    canvas.dataset.adminChart = data.kind;
    canvas.style.width = `${outerWidth}px`;
    const svg = el('g', {transform: `translate(${padding},${padding})`});
    canvas.append(svg);
    const defs = el('defs');
    const gradientId = `${host.dataset.chart}-area-fill`;
    const gradient = el('linearGradient', {id: gradientId, x1: 0, y1: 0, x2: 0, y2: 1});
    gradient.append(el('stop', {offset: '0%', 'stop-color': tone(0), 'stop-opacity': .4}),
      el('stop', {offset: '100%', 'stop-color': data.kind === 'line' ? 'var(--violet)' : tone(0), 'stop-opacity': .07}));
    defs.append(gradient); canvas.prepend(defs);
    const text = (x, y, value, attrs = {}) => svg.append(el('text', {x, y, fill: 'var(--ink)', 'font-size': font,
      ...(attrs['font-size'] >= font * 1.5 || String(value).endsWith('%') ? {'data-motion-number':''} : {}), ...attrs}, value));
    const line = (x1, y1, x2, y2, attrs = {}) => svg.append(el('line', {x1, y1, x2, y2, stroke: 'var(--chart-axis)', ...attrs}));
    let height = 0, visibleRowsHeight = null;
    const scatterTargets = [];
    const labels = data.labels, series = data.series;
    const values = series[0]?.values || [];
    const growth = host.dataset.chart === 'membership-area';
    const maximum = list => Math.max(0, ...list);
    const scale = max => Math.max(1, Math.ceil(max / 4)) * 4;
    if (data.kind === 'member-donut') {
      // Ring areas partition classifications; legend shares retain the distinct
      // member denominator because one member can have multiple classifications.
      const color = index => `var(--chart-tone-${index % 12})`;
      const sideBySide = width >= font * 19;
      const ringWidth = sideBySide ? width * .4 : width;
      const ringHeight = font * 12;
      const cx = ringWidth / 2, cy = ringHeight / 2;
      const radius = Math.min(ringWidth * .46, font * 4.7), inner = radius * .67;
      const legendX = sideBySide ? ringWidth + font : 0;
      const legendWidth = width - legendX;
      const compactLegend = legendWidth >= font * 12;
      const labelWidth = legendWidth - font * 6;
      const labelLimit = Math.max(6, Math.floor(labelWidth / (font * .7 * .56)));
      let y = sideBySide ? font : ringHeight + font;
      const legend = [];
      values.forEach((value, i) => {
        const fraction = data.denominator ? value / data.denominator : 0;
        const percentage = `${(fraction * 100).toFixed(1)}%`;
        const label = labels[i].length > labelLimit ? `${labels[i].slice(0, labelLimit - 1)}…` : labels[i];
        const parts = compactLegend ? [label] : wrapped(labels[i], legendWidth - font * 1.2, font * .7);
        legend.push({i, parts, amount:`${format(value)} (${percentage})`, y});
        y += font * (compactLegend ? 1.75 : (parts.length + 1) * 1.05 + .6);
      });
      height = Math.max(y, ringHeight);
      const ringY = sideBySide ? height / 2 : cy;
      canvas.dataset.motionCenter = JSON.stringify([cx, ringY, radius + font]);
      const point = (r, angle) => [cx + r * Math.cos(angle), ringY + r * Math.sin(angle)];
      if (data.total) {
        let start = -Math.PI / 2;
        values.forEach((value, i) => {
          const fraction = value / data.total, end = start + fraction * Math.PI * 2;
          if (value > 0) {
            const segment = value === data.total
              ? el('circle', {cx, cy:ringY, r:(radius + inner) / 2, fill:'none', stroke:color(i), 'stroke-width':radius - inner})
              : el('path', {d:`M${point(radius, start)} A${radius},${radius} 0 ${fraction > .5 ? 1 : 0},1 ${point(radius, end)} L${point(inner, end)} A${inner},${inner} 0 ${fraction > .5 ? 1 : 0},0 ${point(inner, start)} Z`,
                fill:color(i), stroke:'var(--surface)', 'stroke-width':1.5});
            segment.setAttribute('data-member-segment', i);
            segment.setAttribute('data-value', value);
            segment.setAttribute('data-fraction', fraction);
            segment.append(el('title', {}, `${labels[i]}: ${format(value)} of ${format(data.denominator)} members (${(value / data.denominator * 100).toFixed(1)}%)`));
            svg.append(segment);
          }
          start = end;
        });
      } else {
        svg.append(el('circle', {cx, cy:ringY, r:(radius + inner) / 2, fill:'none', stroke:'var(--chart-track)', 'stroke-width':radius - inner}));
      }
      const numberSize = Math.min(font * 1.8, inner * 1.5 / Math.max(1, format(data.denominator).length * .6));
      text(cx, ringY, format(data.denominator), {'text-anchor':'middle', 'font-size':numberSize, 'font-weight':700, 'data-member-total':''});
      text(cx, ringY + Math.min(font * 1.4, inner * .6), 'members', {'text-anchor':'middle', 'font-size':Math.min(font * .85, inner * .42), fill:'var(--muted)'});
      legend.forEach(({i, parts, amount, y:baseline}) => {
        const top = baseline + (sideBySide ? Math.max(0, height - y) / 2 : 0);
        svg.append(el('circle', {cx:legendX + font * .3, cy:top - font * .22, r:font * .28, fill:color(i), 'data-member-key':i}));
        const name = el('text', {fill:'var(--ink)', 'font-size':font * .7});
        parts.forEach((part, row) => name.append(el('tspan', {x:legendX + font, y:top + row * font * 1.05}, part)));
        name.append(el('title', {}, labels[i])); svg.append(name);
        text(compactLegend ? width : legendX + font, top + (compactLegend ? 0 : parts.length * font * 1.05), amount, {fill:'var(--muted)', 'font-size':font * .65, 'data-member-share':i, 'text-anchor':compactLegend ? 'end' : 'start'});
      });
    } else if (data.kind === 'rings') {
      const columns = Math.max(1, Math.min(values.length, 2)), rows = Math.max(1, Math.ceil(values.length / columns));
      const cellWidth = width / columns;
      const labelParts = labels.map(label => wrapped(label, cellWidth - font, font * .95));
      const labelHeight = font * (1.9 + Math.max(1, ...labelParts.map(parts => parts.length)));
      const radius = Math.max(font, Math.min(cellWidth * .35, (font * 15 / rows - labelHeight) / 2));
      const cellHeight = radius * 2 + labelHeight;
      height = Math.max(font * 15, rows * cellHeight);
      const startY = (height - rows * cellHeight) / 2, strokeWidth = Math.min(font * .7, radius * .12);
      const numberSize = Math.min(font * 2.5, radius * .6);
      values.forEach((value, i) => {
        const fraction = data.total ? value / data.total : 0;
        const cx = cellWidth * (i % columns + .5), cy = startY + Math.floor(i / columns) * cellHeight + radius + font * .5;
        const circumference = 2 * Math.PI * radius;
        svg.append(el('circle', {cx, cy, r: radius, fill: 'none', stroke: 'var(--chart-track)', 'stroke-width': strokeWidth}));
        svg.append(el('circle', {cx, cy, r: radius, fill: 'none', stroke: tone(data.colors?.[i] ?? i),
          'stroke-width': strokeWidth, 'stroke-linecap': 'round',
          'stroke-dasharray': `${fraction * circumference} ${circumference}`, transform: `rotate(-90 ${cx} ${cy})`, 'data-value': value}));
        text(cx, cy + numberSize * .35, format(value), {'text-anchor': 'middle', 'font-size': numberSize, 'font-weight': 700});
        labelParts[i].forEach((part, j) => text(cx, cy + radius + font * (1.5 + j), part, {'text-anchor':'middle', 'font-size':font * .95, fill:'var(--muted)'}));
      });
    } else if (['proportional', 'progress'].includes(data.kind)) {
      let y = font;
      labels.forEach((label, i) => {
        const denominator = data.kind === 'progress' ? data.denominators[i] : data.total;
        const fraction = denominator ? values[i] / denominator : 0;
        text(width, y, `${(fraction * 100).toFixed(0)}%`, {'text-anchor':'end', 'font-size':font * .8});
        wrapped(label, width - font * 4, font * .8).forEach(part => {text(0, y, part, {'font-size':font * .8, fill:'var(--muted)'});y += font * 1.05;});
        y += font * .2;
        svg.append(el('rect', {x:0, y, width, height:font * .35, rx:font * .175, fill:'var(--chart-track)',
          ...(data.kind === 'progress' ? {'data-program-row':i + 1} : {})}));
        svg.append(el('rect', {x:0, y, width:width * fraction, height:font * .35, rx:font * .175,
          fill:tone(data.kind === 'progress' ? 0 : i % 2), 'data-value':values[i]}));
        y += font * 1.65;
        // Include the fifth program's full label and bar before scrolling.
        if (data.kind === 'progress' && i === 4 && labels.length > 5) visibleRowsHeight = y - font * 1.05 + padding;
      });
      height = Math.max(y, font * 5);
    } else if (['horizontal', 'stacked'].includes(data.kind)) {
      const totals = labels.map((_, i) => series.reduce((sum, item) => sum + item.values[i], 0));
      const ceiling = scale(maximum(totals)), plot = width - font * 3;
      let y = font;
      labels.forEach((label, i) => {
        wrapped(label, width - font * 4, font * .8).forEach(part => {text(0, y, part, {'font-size':font * .8});y += font * 1.15;});
        let x = 0;
        svg.append(el('rect', {x:0, y, width:plot, height:font * .65, rx:font * .325, fill:'var(--chart-track)', 'data-program-row': i + 1}));
        series.forEach((item, j) => {
          const amount = item.values[i], length = amount / ceiling * plot;
          if (amount) svg.append(el('rect', {x, y, width: length, height: font * .65, rx: font * .325, fill: tone(item.tone ?? j), stroke: 'var(--surface)', 'stroke-width': 1, 'data-value': amount}));
          x += length;
        });
        text(width, y + font * .6, format(totals[i]), {'text-anchor':'end', 'font-size':font * .8, fill:'var(--muted)'});
        y += font * 2;
        // Fit exactly the first five complete rows, including wrapped labels.
        if (i === 4 && labels.length > 5) visibleRowsHeight = y - font * 1.05 + padding;
      });
      height = y;
    } else if (['pie', 'donut'].includes(data.kind)) {
      height = font * 15;
      const cx = width / 2, cy = height / 2, radius = Math.min(width / 2 - font, font * 5.5);
      canvas.dataset.motionCenter = JSON.stringify([cx, cy, radius + font]);
      if (data.total) {
        let start = -Math.PI / 2;
        values.forEach((value, index) => {
          const end = start + value / data.total * Math.PI * 2;
          if (value === data.total) svg.append(el('circle', {cx, cy, r: radius, fill: tone(data.colors[index]), 'data-value': value}));
          else if (value) {
            const a = [cx + radius * Math.cos(start), cy + radius * Math.sin(start)];
            const b = [cx + radius * Math.cos(end), cy + radius * Math.sin(end)];
            svg.append(el('path', {d: `M${cx},${cy} L${a} A${radius},${radius} 0 ${end-start>Math.PI?1:0},1 ${b} Z`, fill: tone(data.colors[index]), stroke: 'var(--surface)', 'stroke-width': 2, 'data-value': value}));
          }
          if (value / data.total >= .035) {
            const angle = (start + end) / 2, distance = radius * (data.kind === 'donut' ? .78 : .65);
            text(cx + Math.cos(angle) * distance, cy + Math.sin(angle) * distance + font / 3, index + 1, {'text-anchor': 'middle', fill: 'var(--chart-label)', 'font-weight': 700});
          }
          start = end;
        });
        if (data.kind === 'donut') {
          svg.append(el('circle', {cx, cy, r: radius * .68, fill: 'var(--surface)'}));
          text(cx, cy, `${(100 * data.closed / data.total).toFixed(1)}%`, {'text-anchor': 'middle', 'font-size': font * 1.7, 'font-weight': 650});
          text(cx, cy + font * 1.6, 'Closed', {'text-anchor': 'middle'});
          text(cx, cy + font * 3, `${format(data.total)} requests`, {'text-anchor': 'middle', 'font-size':font * .8, fill:'var(--muted)'});
        }
      } else {
        text(cx, cy, data.kind === 'donut' ? '0' : 'No matching records', {'text-anchor': 'middle'});
        if (data.kind === 'donut') text(cx, cy + font * 1.6, 'tickets', {'text-anchor': 'middle'});
      }
    } else {
      const left = font * 2.5, right = font, top = font * (growth ? .5 : 1.5), bottom = font * (growth ? 2.4 : 3.6);
      height = font * (growth ? 13.5 : 15);
      const plotWidth = width - left - right, plotHeight = height - top - bottom;
      const ceiling = scale(maximum(data.kind === 'scatter' ? data.points.map(point => point.y) : values));
      const y = value => top + plotHeight - value / ceiling * plotHeight;
      for (let tick = 0; tick <= 4; tick++) {
        const yy = y(ceiling * tick / 4);
        line(left, yy, width - right, yy, {opacity: .35, ...(growth ? {'stroke-dasharray':'3 4'} : {})});
        text(left - font * .5, yy + font * .3, format(ceiling * tick / 4), {'text-anchor': 'end', 'font-size':font * .75, fill:'var(--muted)'});
      }
      if (data.kind === 'scatter') {
        const xMax = scale(maximum(data.points.map(point => point.x)));
        const x = value => left + value / xMax * plotWidth;
        for (let tick = 0; tick <= 4; tick++) text(x(xMax * tick / 4), top + plotHeight + font * 1.7, format(xMax * tick / 4), {'text-anchor': 'middle'});
        // Least-squares description of the observed points; no extrapolation.
        const points = data.points;
        const meanX = points.reduce((sum, p) => sum + p.x, 0) / Math.max(points.length, 1);
        const meanY = points.reduce((sum, p) => sum + p.y, 0) / Math.max(points.length, 1);
        const variance = points.reduce((sum, p) => sum + (p.x - meanX) ** 2, 0);
        if (points.length > 1 && variance > 0) {
          const slope = points.reduce((sum, p) => sum + (p.x - meanX) * (p.y - meanY), 0) / variance;
          const low = Math.min(...points.map(p => p.x)), high = Math.max(...points.map(p => p.x));
          const clipId = `${host.dataset.chart}-plot-clip`;
          const clip = el('clipPath', {id:clipId});
          clip.append(el('rect', {x:left,y:top,width:plotWidth,height:plotHeight}));defs.append(clip);
          line(x(low), y(meanY + slope * (low - meanX)), x(high), y(meanY + slope * (high - meanX)),
            {stroke:tone(0), 'stroke-dasharray':'5 6', 'stroke-width':2, opacity:.8, 'clip-path':`url(#${clipId})`, 'data-trend':'linear'});
        }
        const overlaps = new Map();
        data.points.forEach(point => {
          const dot = el('circle', {cx: x(point.x), cy: y(point.y), r: font * .35, fill: 'var(--surface)', stroke: tone(0), 'stroke-width': 2, 'data-x': point.x, 'data-y': point.y, 'aria-hidden':'true'});
          svg.append(dot);
          const key = `${point.x},${point.y}`;
          const entry = overlaps.get(key) || {point, labels: []};
          entry.labels.push(point.label); entry.dot = dot; overlaps.set(key, entry);
        });
        // Coincident records share one focus target. Details appear on demand,
        // so dense point clusters never produce overlapping number labels.
        canvas.removeAttribute('aria-hidden'); host.setAttribute('role', 'group');
        overlaps.forEach(({point, labels: indexes, dot}) => {
          const label = `${indexes.length === 1 ? 'Program' : 'Programs'} ${indexes.join(', ')} · ${format(point.x)} slots · ${format(point.y)} applications`;
          dot.removeAttribute('aria-hidden');
          dot.setAttribute('role', 'img'); dot.setAttribute('tabindex', '0');
          dot.setAttribute('aria-label', label); dot.setAttribute('data-scatter-point', '');
          scatterTargets.push({dot, label});
        });
        text(left + plotWidth / 2, height - font * .8, 'Slots →', {'text-anchor': 'middle'});
        text(0, font, 'Applications ↑', {'font-size': font * .85});
      } else {
        const isColumns = ['column', 'histogram'].includes(data.kind), count = values.length;
        const x = index => left + (isColumns ? (index + .5) / Math.max(count, 1) : count === 1 ? .5 : index / Math.max(count - 1, 1)) * plotWidth;
        canvas.dataset.motionBaseline = String(y(0));
        if (isColumns) {
          const step = plotWidth / Math.max(count, 1);
          values.forEach((value, i) => {
            const barWidth = step * .55;
            svg.append(el('rect', {x: x(i) - barWidth / 2, y: y(value), width: barWidth, height: value / ceiling * plotHeight, rx: 5, fill: tone(data.kind === 'histogram' ? i % 2 : 0), 'fill-opacity': i === values.indexOf(Math.max(...values)) ? 1 : .7, 'data-value': value}));
          });
        } else if (count) {
          const points = values.map((value, i) => `${x(i)},${y(value)}`);
          const curve = growth ? smoothPath(values.map((value, i) => [x(i), y(value)])) : null;
          if (['area', 'line'].includes(data.kind) && count > 1) svg.append(el('path', {d: curve ? `${curve} L${x(count - 1)},${y(0)} L${x(0)},${y(0)} Z` : `M${x(0)},${y(0)} L${points.join(' L')} L${x(count - 1)},${y(0)} Z`, fill: `url(#${gradientId})`}));
          svg.append(curve ? el('path', {d:curve, fill:'none', stroke:tone(0), 'stroke-width':2.5, 'data-growth-curve':''}) : el('polyline', {points: points.join(' '), fill: 'none', stroke: tone(0), 'stroke-width': 3}));
          values.forEach((value, i) => svg.append(el('circle', {cx: x(i), cy: y(value), r: growth && count > 1 ? 0 : 4, fill: 'var(--surface)', stroke: tone(0), 'stroke-width': growth && count > 1 ? 0 : 2, 'data-value': value})));
        }
        const interval = Math.max(1, Math.ceil(count * font * 4.5 / Math.max(plotWidth, 1)));
        labels.forEach((label, i) => {
          if (i % interval && i !== labels.length - 1) return;
          // Omit a final neighboring tick rather than overlap its preceding label.
          if (i === labels.length - 1 && i % interval && i % interval < interval / 2) return;
          const years = new Set(labels.map(value => value.split(' ').at(-1)));
          const parts = data.kind === 'histogram' || years.size === 1 ? [data.kind === 'histogram' ? label : label.split(' ')[0]] : label.split(' ');
          parts.forEach((part, j) => text(x(i), top + plotHeight + font * (1.7 + j * 1.2), part, {'text-anchor': 'middle', 'font-size': font * .9}));
        });
        if (data.kind === 'histogram') text(width / 2, height - font * .5, 'Age (years) →', {'text-anchor': 'middle', 'font-size': font * .85});
      }
    }
    canvas.setAttribute('height', Math.floor(height + padding * 2));
    canvas.setAttribute('viewBox', `0 0 ${outerWidth} ${height + padding * 2}`);
    host.replaceChildren(canvas);
    // Keep the full plotted area and labels, while removing unused SVG space
    // below short legends or axis labels. The viewport follows this height.
    const bounds = svg.getBBox();
    const fittedHeight = Math.ceil(Math.min(height + padding * 2, bounds.y + bounds.height + padding * 2));
    canvas.setAttribute('height', fittedHeight);
    canvas.setAttribute('viewBox', `0 0 ${outerWidth} ${fittedHeight}`);
    if (['stacked', 'progress'].includes(data.kind)) {
      host.style.height = visibleRowsHeight === null ? '' : `${visibleRowsHeight}px`;
      host.classList.toggle('overview-five-rows', visibleRowsHeight !== null);
      host.parentElement.querySelector('[data-chart-more]').hidden = visibleRowsHeight === null;
    }
    const group = host.parentElement;
    group.querySelector('.overview-point-tooltip')?.remove();
    if (scatterTargets.length) {
      const tooltip = document.createElement('div');
      tooltip.className = 'overview-point-tooltip'; tooltip.hidden = true;
      // Keep overlays outside the scrolling SVG viewport. Measuring or showing
      // a tooltip must never change the plot's available width or height.
      tooltip.setAttribute('role', 'tooltip'); group.append(tooltip);
      scatterTargets.forEach(({dot, label}) => {
        const show = () => {
          tooltip.textContent = label;
          tooltip.style.maxWidth = `${Math.max(0, Math.min(font * 19, host.clientWidth - 16))}px`;
          tooltip.hidden = false;
          const point = dot.getBoundingClientRect(), frame = host.getBoundingClientRect(), bounds = group.getBoundingClientRect();
          const pointX = point.left + point.width / 2, pointY = point.top;
          const tooltipWidth = tooltip.getBoundingClientRect().width, tooltipHeight = tooltip.getBoundingClientRect().height;
          const left = Math.max(frame.left + 8, Math.min(pointX - tooltipWidth / 2, frame.right - tooltipWidth - 8));
          const above = pointY - tooltipHeight - 12;
          const top = Math.max(frame.top + 8, Math.min(above >= frame.top + 8 ? above : point.bottom + 12, frame.bottom - tooltipHeight - 8));
          tooltip.style.left = `${left - bounds.left}px`;
          tooltip.style.top = `${top - bounds.top}px`;
        };
        const hide = () => {tooltip.hidden = true;};
        dot.addEventListener('pointerenter', show); dot.addEventListener('focus', show);
        dot.addEventListener('click', show);
        dot.addEventListener('pointerleave', hide); dot.addEventListener('blur', hide);
        dot.addEventListener('keydown', event => {if (event.key === 'Escape') hide();});
      });
      host.onscroll = () => {tooltip.hidden = true;};
    }
    const scrollable = outerWidth > host.clientWidth || host.scrollHeight > host.clientHeight + 1;
    if (scrollable) host.setAttribute('tabindex', '0');
    else host.removeAttribute('tabindex');
    host.parentElement.querySelector('[data-chart-scroll]').hidden = !scrollable;
  }
  function render(item, first = false) {
    try {
      draw(item.host, item.data);
      item.group.querySelector('[data-chart-fallback]').hidden = true;
      if (first) item.group.querySelector('details').open = false;
    } catch (_) {
      item.host.hidden = true;
      const status = item.group.querySelector('[data-chart-fallback]');
      status.hidden = false; status.textContent = 'Chart could not render. The data table remains available.';
      item.group.querySelector('details').open = true;
    }
  }
  document.querySelectorAll('[data-chart]').forEach(host => {
    const group = host.closest('.overview-chart-group');
    try {
      const data = JSON.parse(document.getElementById(host.dataset.chart).textContent);
      const item = {host, group, data}; nodes.push(item); render(item, true);
    } catch (_) { group.querySelector('details').open = true; }
  });
  document.querySelectorAll('[data-chart-kind="heatmap"] .overview-data').forEach(details => {details.open = false;});
  const dialog = document.getElementById('overview-data-dialog');
  if (dialog && typeof dialog.showModal === 'function') {
    const body = dialog.querySelector('.overview-dialog-body');
    let active;
    document.querySelectorAll('[data-open-chart-data]').forEach(trigger => {
      const group = trigger.closest('.overview-chart-group'), details = group.querySelector('.overview-data');
      const content = details.querySelector('.overview-data-content');
      trigger.hidden = false; details.hidden = true; details.open = false;
      trigger.addEventListener('click', () => {
        if (dialog.open) return;
        active = {trigger, details, content};
        dialog.dataset.chartId = group.dataset.visualization;
        dialog.querySelector('#overview-data-title').textContent = group.closest('section').querySelector('h2').getAttribute('aria-label');
        body.replaceChildren(content);
        document.documentElement.classList.add('dashboard-modal-open');
        dialog.showModal(); body.scrollTop = 0;
      });
    });
    dialog.querySelector('.overview-dialog-close').addEventListener('click', () => dialog.close());
    dialog.addEventListener('keydown', event => {
      if (event.key !== 'Tab') return;
      const targets = [...dialog.querySelectorAll('button,a[href],input,select,textarea,[tabindex]')]
        .filter(node => node.tabIndex >= 0 && !node.disabled && node.getClientRects().length);
      const first = targets[0], last = targets.at(-1);
      if ((event.shiftKey && document.activeElement === first) || (!event.shiftKey && document.activeElement === last)) {
        event.preventDefault(); (event.shiftKey ? last : first)?.focus();
      }
    });
    dialog.addEventListener('click', event => {
      const bounds = dialog.getBoundingClientRect();
      if (event.target === dialog && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) dialog.close();
    });
    dialog.addEventListener('close', () => {
      if (active) active.details.append(active.content);
      document.documentElement.classList.remove('dashboard-modal-open');
      active?.trigger.focus({preventScroll:true}); active = null;
    });
  }
  const filters = document.querySelector('.overview-filters');
  const period = filters?.querySelector('[name="period"]');
  if (period) {
    const showDates = () => {
      const custom = period.value === 'custom';
      filters.querySelectorAll('[data-custom-date]').forEach(field => {field.hidden = !custom;});
      filters.classList.toggle('has-custom-dates', custom);
    };
    period.addEventListener('change', showDates); showDates();
  }
  let frame;
  const redraw = () => {cancelAnimationFrame(frame);frame = requestAnimationFrame(() => nodes.forEach(item => render(item)));};
  // Observe the card's layout, not a viewport whose scrollbars our SVG controls.
  // Internal overflow and tooltip visibility must not trigger a redraw loop.
  if ('ResizeObserver' in window) {
    const widths = new WeakMap();
    const observer = new ResizeObserver(entries => {
      let changed = false;
      entries.forEach(({target, contentRect}) => {
        if (widths.get(target) !== contentRect.width) {widths.set(target, contentRect.width);changed = true;}
      });
      if (changed) redraw();
    });
    nodes.forEach(item => observer.observe(item.group));
  }
  addEventListener('resize', redraw);
  on(document, 'santolan:displaychange', redraw);
  // Also supports browser text scaling and non-widget preference changes.
  new MutationObserver(redraw).observe(document.documentElement, {attributes: true, attributeFilter: ['style', 'data-text', 'data-contrast']});
  const results = document.getElementById('overview-results');
  if (results?.dataset.filtered === 'true') {
    const notice = document.getElementById('overview-refresh') || results.querySelector('[role="alert"]');
    if (notice) {notice.setAttribute('tabindex', '-1');notice.focus({preventScroll: true});}
  }
})();

});
