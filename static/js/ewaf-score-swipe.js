'use strict';
WorkspacePage.run(({on, requestAnimationFrame, cleanup, MutationObserver}) => {
  const root = document.querySelector('.ewaf-breakdown');
  const card = root?.querySelector('[data-score-swipe]');
  const picker = document.getElementById('breakdown-applicant');
  const deck = root?.querySelector('[data-score-deck]');
  const panel = root?.querySelector('.ewaf-contributions');
  const details = root?.querySelector('[data-score-details]');
  if (!card || !picker || !deck || !panel || !details) return;
  function readMembers(page) {
    try {
      const rows = JSON.parse(page.getElementById('score-deck-members').textContent);
      return Array.isArray(rows) && rows.length === page.querySelectorAll('#breakdown-applicant option').length ? rows : null;
    } catch (_) { return null; }
  }
  let members = readMembers(document);
  if (!members?.length) return;
  const form = picker.form, preview = deck.querySelector('[data-score-preview]');
  const dots = deck.querySelector('[data-score-dots]');
  const media = matchMedia('(prefers-reduced-motion: reduce)');
  const reduced = () => document.documentElement.dataset.motion === 'reduce' || media.matches;
  const indexOf = value => (value + members.length) % members.length;
  let current = picker.selectedIndex, gesture = null, moving = false, previewIndex = -1;
  let pointGeneration = 0, finishPoints = null;

  function showPreview(index) {
    if (previewIndex === index) return;
    previewIndex = index;
    const member = members[index], copy = card.cloneNode(true);
    for (const attribute of ['id', 'tabindex', 'data-score-swipe', 'aria-describedby', 'aria-keyshortcuts', 'aria-busy']) copy.removeAttribute(attribute);
    copy.querySelectorAll('[id]').forEach(node => node.removeAttribute('id'));
    copy.querySelector('[data-score-rank]').textContent = `Rank ${member.rank} of ${members.length}`;
    copy.querySelector('[data-score-name]').textContent = member.member_name;
    copy.querySelector('[data-score-member]').textContent = `Member · ${member.member_number}`;
    copy.querySelector('[data-score-total]').textContent = member.score;
    copy.querySelector('[data-score-comparison]').textContent = `${member.higher} higher · ${member.tied_others} tied · ${member.lower} lower`;
    copy.querySelector('.ewaf-score-gauge').setAttribute('aria-label', `Total EWAF score: ${member.score} percent`);
    const arc = copy.querySelector('.ewaf-score-gauge-value');
    arc.setAttribute('stroke-dasharray', `${member.score} 100`);
    arc.style.visibility = Number(member.score) === 0 ? 'hidden' : '';
    preview.replaceChildren(copy);
  }
  function refreshDeck() {
    const enabled = members.length > 1;
    deck.classList.toggle('is-deck', enabled);
    card.classList.toggle('ewaf-score-swipable', enabled);
    card.setAttribute('aria-label', enabled ? 'Applicant score summary. Swipe left or right, or use arrow keys to change member.' : 'Applicant score summary');
    deck.querySelector('[data-score-navigation]').hidden = !enabled;
    const focusedDot = dots.contains(document.activeElement) ? document.activeElement.dataset.scoreIndex : null;
    dots.replaceChildren();
    const start = Math.max(0, Math.min(current - 3, members.length - 7));
    for (let index = start; index < Math.min(members.length, start + 7); index++) {
      const dot = document.createElement('button');
      dot.type = 'button'; dot.className = 'ewaf-deck-dot';
      dot.dataset.scoreIndex = index;
      dot.setAttribute('aria-label', `Show member ${index + 1} of ${members.length}`);
      if (index === current) dot.setAttribute('aria-current', 'true');
      dots.append(dot);
      if (String(index) === focusedDot) dot.focus({preventScroll: true});
    }
    previewIndex = -1;
    if (enabled) showPreview(indexOf(current + 1));
    else preview.replaceChildren();
  }
  function clearDrag() {
    deck.classList.remove('is-dragging');
    for (const property of ['--deck-x', '--deck-tilt', '--deck-opacity', '--deck-reveal']) deck.style.removeProperty(property);
  }
  function reset() {
    gesture = null; moving = false;
    clearDrag();
    picker.selectedIndex = current;
    card.removeAttribute('aria-busy');
  }
  function copyChildren(live, fresh) {
    if (live && fresh && live.innerHTML !== fresh.innerHTML) live.replaceChildren(...[...fresh.childNodes].map(node => document.importNode(node, true)));
  }

  function updatePoints(freshPanel) {
    document.dispatchEvent(new Event('admin-motion:finish'));
    const generation = ++pointGeneration;
    finishPoints = null;
    const freshRows = [...freshPanel.querySelectorAll('[data-points-criterion]')];
    const liveRows = [...panel.querySelectorAll('[data-points-criterion]')];
    if (freshRows.map(row => row.dataset.pointsCriterion).join('|') !== liveRows.map(row => row.dataset.pointsCriterion).join('|')) copyChildren(panel, freshPanel);
    const targets = new Map(freshRows.map(row => [row.dataset.pointsCriterion, row]));
    const updates = [];
    panel.querySelectorAll('[data-points-criterion]').forEach(row => {
      const fresh = targets.get(row.dataset.pointsCriterion);
      const value = row.querySelector('[data-points-value]'), bar = row.querySelector('.ewaf-point-track > span');
      const target = fresh.dataset.pointsFinal, to = Number(target), from = 0;
      row.dataset.pointsFinal = target;
      delete row.dataset.pointsFrom;
      copyChildren(row.firstElementChild.firstElementChild, fresh.firstElementChild.firstElementChild);
      row.querySelector('strong .visually-hidden').textContent = fresh.querySelector('strong .visually-hidden').textContent;
      bar.className = fresh.querySelector('.ewaf-point-track > span').className;
      if (!reduced() && Number.isFinite(from) && Number.isFinite(to) && from !== to) {
        row.dataset.pointsFrom = String(from);
        value.textContent = from.toFixed(2);
        bar.style.width = `${from}%`;
        updates.push({row, value, bar, from, to, target});
      } else {
        value.textContent = target;
        bar.style.width = `${to}%`;
      }
    });
    delete panel.dataset.pointsAnimating;
    if (!updates.length) return;
    panel.dataset.pointsAnimating = 'true';
    const finish = () => {
      if (generation !== pointGeneration) return;
      ++pointGeneration;
      updates.forEach(({row, value, bar, to, target}) => {
        value.textContent = target;
        bar.style.width = `${to}%`;
        delete row.dataset.pointsFrom;
      });
      delete panel.dataset.pointsAnimating;
      finishPoints = null;
    };
    finishPoints = finish;
    const started = performance.now();
    function frame(now) {
      if (generation !== pointGeneration) return;
      const progress = Math.min(1, Math.max(0, (now - started) / 700));
      if (progress === 1 || reduced()) { finish(); return; }
      const eased = 1 - Math.pow(1 - progress, 3);
      updates.forEach(({from, to, value, bar}) => {
        const valueNow = from + (to - from) * eased;
        value.textContent = valueNow.toFixed(2);
        bar.style.width = `${valueNow}%`;
      });
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
  function updateDetails(freshDetails) {
    const open = new Map([...details.querySelectorAll('details')].map(node => [node.querySelector('summary')?.textContent.trim(), node.open]));
    const scroll = new Map([...details.querySelectorAll('.table-responsive')].map(node => [node.getAttribute('aria-label'), node.scrollLeft]));
    copyChildren(details, freshDetails);
    details.querySelectorAll('details').forEach(node => {
      const key = node.querySelector('summary')?.textContent.trim();
      if (open.has(key)) node.open = open.get(key);
    });
    details.querySelectorAll('.table-responsive').forEach(node => { node.scrollLeft = scroll.get(node.getAttribute('aria-label')) || 0; });
  }

  // Keep the shell, controls, card and chart mounted. Only authorized response
  // content is applied, so theme initialization and asset loading never repeat.
  on(document, 'workspace:render', event => {
    const update = event.detail, page = update.page;
    const nextCard = page.querySelector('[data-score-swipe]');
    const nextPanel = page.querySelector('.ewaf-contributions');
    const nextDetails = page.querySelector('[data-score-details]');
    const nextPicker = page.getElementById('breakdown-applicant');
    if (update.url.pathname !== location.pathname || !nextCard || !nextPanel || !nextDetails || !nextPicker || nextCard.dataset.scoreRun !== card.dataset.scoreRun) return;
    const nextMembers = readMembers(page);
    if (!nextMembers?.length || !nextMembers.some(member => member.application === nextCard.dataset.scoreApplicant)) return;
    if ([...nextPanel.querySelectorAll('[data-points-criterion]')].some(row => !row.querySelector('[data-points-value]') || !Number.isFinite(Number(row.dataset.pointsFinal)))) return;
    update.render = () => {
      const focusCard = details.contains(document.activeElement);
      deck.classList.add('is-updating');
      clearDrag();
      copyChildren(card, nextCard);
      card.dataset.scoreApplicant = nextCard.dataset.scoreApplicant;
      card.dataset.scoreRun = nextCard.dataset.scoreRun;
      copyChildren(picker, nextPicker);
      picker.value = nextCard.dataset.scoreApplicant;
      current = picker.selectedIndex;
      members = nextMembers;
      document.getElementById('score-deck-members').textContent = page.getElementById('score-deck-members').textContent;
      refreshDeck();
      updatePoints(nextPanel);
      updateDetails(nextDetails);
      for (const selector of ['.ewaf-page-header', '.ewaf-tabs', '.ewaf-calculation-label', '[data-score-notice]', '#breakdown-run']) copyChildren(root.querySelector(selector), page.querySelector(selector));
      form.querySelector('[data-auto-filter-feedback]')?.replaceChildren(document.createTextNode('Applicant updated.'));
      gesture = null; moving = false;
      card.removeAttribute('aria-busy');
      // Commit the revealed card at rest rather than animating it back in.
      void card.offsetWidth;
      deck.classList.remove('is-updating');
      if (focusCard) card.focus({preventScroll: true});
    };
  });

  function moveTo(index, direction) {
    if (moving || index === current || document.getElementById('main-content')?.getAttribute('aria-busy') === 'true') return;
    moving = true;
    showPreview(index);
    deck.classList.remove('is-dragging');
    deck.style.setProperty('--deck-x', `${-direction * card.offsetWidth * 1.15}px`);
    deck.style.setProperty('--deck-tilt', `${-direction * 12}deg`);
    deck.style.setProperty('--deck-opacity', '0');
    deck.style.setProperty('--deck-reveal', '1');
    card.setAttribute('aria-busy', 'true');
    picker.selectedIndex = index;
    form.requestSubmit();
  }
  on(deck, 'click', event => {
    const step = event.target.closest('[data-score-step]'), dot = event.target.closest('[data-score-index]');
    if (step) moveTo(indexOf(current + Number(step.dataset.scoreStep)), Number(step.dataset.scoreStep));
    else if (dot) {
      const index = Number(dot.dataset.scoreIndex);
      moveTo(index, index > current ? 1 : -1);
    }
  });
  on(card, 'keydown', event => {
    if (event.target !== card || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      const step = event.key === 'ArrowRight' ? 1 : -1;
      moveTo(indexOf(current + step), step);
    } else if (event.key === 'Escape' && gesture) reset();
  });
  on(card, 'pointerdown', event => {
    if (!event.isPrimary) { if (!moving) reset(); return; }
    if (moving || members.length < 2 || document.getElementById('main-content')?.getAttribute('aria-busy') === 'true' || event.button !== 0 || event.target.closest('button, a, input, select, textarea')) return;
    gesture = {id: event.pointerId, x: event.clientX, y: event.clientY};
    card.setPointerCapture(event.pointerId);
  });
  on(card, 'pointermove', event => {
    if (!gesture || gesture.id !== event.pointerId || moving) return;
    const dx = event.clientX - gesture.x, dy = event.clientY - gesture.y;
    if (Math.abs(dx) < 8 || Math.abs(dx) <= Math.abs(dy) * 1.2) return;
    showPreview(indexOf(current + (dx < 0 ? 1 : -1)));
    deck.classList.add('is-dragging');
    const progress = Math.min(1, Math.abs(dx) / (card.offsetWidth * .65));
    deck.style.setProperty('--deck-x', `${dx}px`);
    deck.style.setProperty('--deck-tilt', `${Math.max(-12, Math.min(12, dx / 25))}deg`);
    deck.style.setProperty('--deck-opacity', '1');
    deck.style.setProperty('--deck-reveal', String(progress));
  });
  on(card, 'pointerup', event => {
    if (!gesture || gesture.id !== event.pointerId || moving) return;
    const dx = event.clientX - gesture.x, dy = event.clientY - gesture.y;
    gesture = null;
    if (card.hasPointerCapture(event.pointerId)) card.releasePointerCapture(event.pointerId);
    const threshold = Math.max(50, Math.min(100, card.offsetWidth * .22));
    if (Math.abs(dx) >= threshold && Math.abs(dx) > Math.abs(dy) * 1.5) {
      const step = dx < 0 ? 1 : -1;
      moveTo(indexOf(current + step), step);
    } else reset();
  });
  on(card, 'pointercancel', () => { if (!moving) reset(); });
  on(card, 'lostpointercapture', () => { if (gesture && !moving) reset(); });
  on(document, 'workspace:navigated', event => { if (!event.detail?.partial) card.focus({preventScroll: true}); });
  on(media, 'change', () => { if (reduced()) finishPoints?.(); });
  cleanup(() => { ++pointGeneration; });
  const main = document.getElementById('main-content');
  if (MutationObserver) {
    new MutationObserver(() => { if (reduced()) finishPoints?.(); })
      .observe(document.documentElement, {attributes: true, attributeFilter: ['data-motion']});
    new MutationObserver(() => {
      if (moving && card.isConnected && main.getAttribute('aria-busy') !== 'true') reset();
    }).observe(main, {attributes: true, attributeFilter: ['aria-busy']});
  }
  refreshDeck();
});
