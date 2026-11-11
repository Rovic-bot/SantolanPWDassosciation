/* Progressive enhancement of the published About text; no copy is discarded. */
(() => {
  'use strict';
  const carousel = document.querySelector('[data-about-carousel]');
  if (!carousel) return;
  const source = carousel.querySelector('[data-about-source]');
  // The visual editor needs its original editable field, without generated cards.
  if (!source || source.querySelector('[data-portal-field]')) return;
  const viewport = carousel.querySelector('[data-about-viewport]');
  const controls = carousel.querySelector('[data-about-controls]');
  const previous = controls.querySelector('[data-about-previous]');
  const next = controls.querySelector('[data-about-next]');
  const status = controls.querySelector('[data-about-status]');
  const savedCopy = source.querySelector('.portal-saved-copy');
  let nodes = [...source.childNodes];
  if (savedCopy) {
    // Saved visual-editor copy is plain text, including any Markdown headings.
    nodes = savedCopy.textContent.trim().split(/\n\s*\n/).filter(Boolean).map(paragraph => {
      const lines = paragraph.split(/\r?\n/);
      if (lines.length === 1 && lines[0].startsWith('## ')) {
        const heading = document.createElement('h3');
        heading.textContent = lines[0].slice(3);
        return heading;
      }
      if (lines.every(line => line.trim().startsWith('- '))) {
        const list = document.createElement('ul');
        lines.forEach(line => {
          const item = document.createElement('li');
          item.textContent = line.trim().slice(2);
          list.append(item);
        });
        return list;
      }
      const text = document.createElement('p');
      text.textContent = paragraph;
      return text;
    });
  }
  const cards = [];
  let card;
  nodes.forEach(node => {
    if (!node.textContent.trim()) return;
    if (!card || node.nodeName === 'H3') {
      card = document.createElement('article');
      card.className = 'about-background-card';
      cards.push(card);
    }
    card.append(node);
  });
  if (!cards.length) return;
  viewport.id = 'about-background-cards';
  cards.forEach((item, index) => {
    item.setAttribute('role', 'group');
    item.setAttribute('aria-roledescription', 'slide');
    item.setAttribute('aria-label', `${index + 1} of ${cards.length}`);
    item.hidden = index !== 0;
    item.inert = index !== 0;
    item.setAttribute('aria-hidden', String(index !== 0));
  });
  viewport.replaceChildren(...cards);
  carousel.classList.add('is-ready');
  if (cards.length < 2) return;
  carousel.setAttribute('aria-roledescription', 'carousel');
  viewport.tabIndex = 0;
  viewport.setAttribute('aria-label', 'Association background cards. Use the left and right arrow keys to browse.');
  controls.hidden = false;
  let current = 0;
  let moving = false;
  const updateControls = () => {
    previous.setAttribute('aria-disabled', String(current === 0));
    next.setAttribute('aria-disabled', String(current === cards.length - 1));
    const title = cards[current].querySelector('h3')?.textContent.trim();
    status.textContent = `Card ${current + 1} of ${cards.length}${title ? ': ' + title : ''}`;
  };
  updateControls();

  const show = async index => {
    if (moving || index < 0 || index >= cards.length || index === current) return;
    moving = true;
    const direction = index > current ? 1 : -1;
    const outgoing = cards[current];
    const incoming = cards[index];
    if (outgoing.contains(document.activeElement)) viewport.focus({ preventScroll: true });
    outgoing.inert = true;
    outgoing.setAttribute('aria-hidden', 'true');
    incoming.hidden = false;
    incoming.inert = false;
    incoming.setAttribute('aria-hidden', 'false');
    current = index;
    const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches || document.documentElement.dataset.motion === 'reduce';
    if (!reduceMotion) {
      const options = { duration: 300, easing: 'cubic-bezier(.22,.61,.36,1)' };
      const animations = [
        outgoing.animate([{ transform: 'translateX(0)', opacity: 1 }, { transform: `translateX(${-direction * 110}%)`, opacity: 0 }], options),
        incoming.animate([{ transform: `translateX(${direction * 110}%)`, opacity: 0 }, { transform: 'translateX(0)', opacity: 1 }], options),
      ];
      await Promise.all(animations.map(animation => animation.finished.catch(() => {})));
    }
    outgoing.hidden = true;
    moving = false;
    updateControls();
  };
  previous.addEventListener('click', () => show(current - 1));
  next.addEventListener('click', () => show(current + 1));
  carousel.addEventListener('keydown', event => {
    if (event.target.matches('input,textarea,select,[contenteditable="true"]')) return;
    const index = { ArrowLeft: current - 1, ArrowRight: current + 1, Home: 0, End: cards.length - 1 }[event.key];
    if (index === undefined) return;
    event.preventDefault();
    show(index);
  });

  let gesture;
  viewport.addEventListener('pointerdown', event => {
    if (!event.isPrimary || event.button !== 0 || moving || event.target.closest('a,button,input,select,textarea')) return;
    gesture = { id: event.pointerId, x: event.clientX, y: event.clientY, horizontal: false };
  });
  viewport.addEventListener('pointermove', event => {
    if (!gesture || event.pointerId !== gesture.id) return;
    const dx = event.clientX - gesture.x;
    const dy = event.clientY - gesture.y;
    if (!gesture.horizontal && Math.abs(dx) > 12 && Math.abs(dx) > Math.abs(dy) * 1.3) {
      gesture.horizontal = true;
      viewport.setPointerCapture(event.pointerId);
      carousel.classList.add('is-dragging');
    }
    if (gesture.horizontal && event.cancelable) event.preventDefault();
  });
  const finishGesture = event => {
    if (!gesture || event.pointerId !== gesture.id) return;
    const dx = event.clientX - gesture.x;
    const dy = event.clientY - gesture.y;
    const advance = event.type === 'pointerup' && gesture.horizontal && Math.abs(dx) >= 45 && Math.abs(dx) > Math.abs(dy) * 1.3;
    gesture = null;
    carousel.classList.remove('is-dragging');
    if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
    if (advance) show(current + (dx < 0 ? 1 : -1));
  };
  viewport.addEventListener('pointerup', finishGesture);
  viewport.addEventListener('pointercancel', finishGesture);
  viewport.addEventListener('lostpointercapture', event => {
    // Touch starts with implicit capture on a child; ignore its capture transfer.
    if (event.target !== viewport) return;
    gesture = null;
    carousel.classList.remove('is-dragging');
  });
})();
