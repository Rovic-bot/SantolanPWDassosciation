/* Page-scoped, bounded animations; the server's exact values stay authoritative. */
'use strict';
WorkspacePage.run(({on, cleanup, requestAnimationFrame, MutationObserver, IntersectionObserver}) => {
  if (!document.body.classList.contains('admin-workspace')) return;
  const preference = matchMedia('(prefers-reduced-motion: reduce)');
  const enabled = () => !preference.matches && document.documentElement.dataset.motion !== 'reduce';
  const pending = new WeakSet(), playedCharts = new WeakSet(), chartTargets = new WeakMap();
  const finishes = new Set(), animations = new Set();
  let serial = 0, scanPending = false;
  const duration = 850, easing = 'cubic-bezier(.22,.75,.25,1)';
  function tween(element, paint, restore) {
    if (!enabled()) return;
    let done = false, start;
    const finish = () => { if (done) return; done = true; restore(); finishes.delete(finish); };
    finishes.add(finish); paint(0);
    function frame(time) {
      if (done) return;
      if (!element.isConnected || !enabled()) { finish(); return; }
      start ??= time;
      const progress = Math.min(1, (time - start) / duration);
      if (progress === 1) { finish(); return; }
      paint(1 - (1 - progress) ** 3);
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
  function animate(element, frames, options = {}) {
    if (!enabled() || !element.animate) return;
    const animation = element.animate(frames, {duration, easing, ...options});
    animations.add(animation);
    animation.finished.catch(() => {}).finally(() => animations.delete(animation));
  }
  function number(element) {
    if (element.childNodes.length !== 1 || element.firstChild.nodeType !== Node.TEXT_NODE) return;
    const node = element.firstChild, original = node.data, match = original.trim().match(/^([\d,]+)(\.\d+)?(%?)$/);
    if (!match) return;
    const target = Number(match[1].replaceAll(',', '') + (match[2] || ''));
    const places = match[2]?.length - 1 || 0;
    tween(element, progress => {
      if (node.parentElement === element) node.data = (target * progress).toLocaleString('en-US',
        {minimumFractionDigits: places, maximumFractionDigits: places}) + match[3];
    }, () => { if (node.parentElement === element) node.data = original; });
  }
  function arc(element) {
    const target = element.getAttribute('stroke-dasharray');
    const values = target?.trim().split(/[ ,]+/).map(Number);
    if (values?.length !== 2 || !values.every(Number.isFinite)) return;
    animate(element, [{strokeDasharray: `0 ${values[1]}`}, {strokeDasharray: target}]);
  }
  function grow(element, vertical = false, baseline = null) {
    const box = element.getBBox?.();
    const origin = box ? `${vertical ? box.x + box.width / 2 : box.x}px ${baseline ?? box.y + box.height}px`
                       : vertical ? 'center bottom' : 'left center';
    animate(element, [
      {transform: vertical ? 'scaleY(0)' : 'scaleX(0)', transformOrigin: origin},
      {transform: 'none', transformOrigin: origin}
    ]);
  }
  function sweep(svg, center) {
    const ns = 'http://www.w3.org/2000/svg', id = `admin-chart-reveal-${++serial}`;
    const clip = document.createElementNS(ns, 'clipPath'), path = document.createElementNS(ns, 'path');
    clip.id = id; clip.setAttribute('clipPathUnits', 'userSpaceOnUse'); clip.append(path);
    svg.querySelector('defs').append(clip);
    const shapes = [...svg.querySelectorAll('[data-value]')].map(shape => [shape, shape.style.clipPath]);
    shapes.forEach(([shape]) => { shape.style.clipPath = `url(#${id})`; });
    const [cx, cy, radius] = center;
    tween(svg, progress => {
      const angle = -Math.PI / 2 + progress * Math.PI * 2;
      path.setAttribute('d', `M${cx},${cy} L${cx},${cy-radius} A${radius},${radius} 0 ${progress > .5 ? 1 : 0},1 ${cx+radius*Math.cos(angle)},${cy+radius*Math.sin(angle)} Z`);
    }, () => { shapes.forEach(([shape, previous]) => { shape.style.clipPath = previous; }); clip.remove(); });
  }
  function play(element) {
    if (element.matches('[data-admin-chart]')) {
      const host = element.closest('[data-chart]');
      if (host && playedCharts.has(host)) return;
      if (host) playedCharts.add(host);
    }
    if (!enabled()) return;
    if (element.matches('[data-admin-chart]')) {
      const kind = element.dataset.adminChart;
      if (element.dataset.motionCenter) sweep(element, JSON.parse(element.dataset.motionCenter));
      else if (kind === 'rings') element.querySelectorAll('circle[stroke-dasharray]').forEach(arc);
      else if (['area', 'line'].includes(kind)) {
        element.querySelectorAll('g > path, polyline, circle[data-value]').forEach(shape => grow(shape, true, Number(element.dataset.motionBaseline)));
      } else if (kind === 'scatter') {
        element.querySelectorAll('[data-scatter-point]').forEach(shape => {
          const box = shape.getBBox(), origin = `${box.x + box.width / 2}px ${box.y + box.height / 2}px`;
          animate(shape, [{scale: '0', transformOrigin: origin}, {scale: '1', transformOrigin: origin}]);
        });
      } else element.querySelectorAll('rect[data-value]').forEach(shape => grow(shape, ['column', 'histogram'].includes(kind)));
      element.querySelectorAll('[data-motion-number]').forEach(number);
    } else if (element.matches('.selection-gauge, .ewaf-score-gauge')) {
      element.querySelectorAll('circle[stroke-dasharray]').forEach(arc);
      element.querySelectorAll('strong, [data-score-total]').forEach(number);
    } else if (element.matches('.ewaf-point-row')) {
      // The swipe controller owns subsequent value-to-value changes on this row.
      if (element.closest('[data-points-animating]')) return;
      const bar = element.querySelector('.ewaf-point-track > span');
      if (bar) grow(bar);
      const value = element.querySelector('[data-points-value]');
      if (value) number(value);
    } else if (element.matches('.overview-heatmap')) {
      element.querySelectorAll('td[data-level]').forEach(cell => animate(cell, [{opacity: 0}, {opacity: 1}], {duration: 600}));
    } else number(element);
  }
  const observer = IntersectionObserver ? new IntersectionObserver(entries => {
    entries.forEach(entry => { if (entry.isIntersecting) { observer.unobserve(entry.target); play(entry.target); } });
  }, {threshold: .08}) : null;
  function scan() {
    scanPending = false;
    document.querySelectorAll('[data-admin-chart], .selection-gauge, .ewaf-score-gauge, .ewaf-point-row, .overview-heatmap, .overview-number').forEach(element => {
      if (element.closest('[data-score-preview]')) return;
      if (pending.has(element)) return;
      pending.add(element);
      const host = element.matches('[data-admin-chart]') && element.closest('[data-chart]');
      if (host) {
        const previous = chartTargets.get(host);
        if (previous) observer?.unobserve(previous);
        chartTargets.set(host, element);
        // Layout/theme redraws preserve the final chart instead of replaying it.
        if (playedCharts.has(host)) return;
      }
      if (observer) observer.observe(element); else play(element);
    });
  }
  function schedule() { if (!scanPending) { scanPending = true; requestAnimationFrame(scan); } }
  new MutationObserver(schedule).observe(document.body, {childList: true, subtree: true});
  function finishAll() {
    [...finishes].forEach(finish => finish());
    animations.forEach(animation => animation.finish());
  }
  function finishMotion() { if (!enabled()) finishAll(); }
  on(document, 'admin-motion:finish', finishAll);
  on(window, 'beforeprint', finishAll);
  on(preference, 'change', finishMotion);
  on(document, 'santolan:displaychange', finishMotion);
  cleanup(() => { [...finishes].forEach(finish => finish()); animations.forEach(animation => animation.cancel()); });
  scan();
});
