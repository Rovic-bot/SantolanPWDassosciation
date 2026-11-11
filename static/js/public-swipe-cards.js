/* Accessible swipe and scroll cards for published public content. */
(() => {
  'use strict';
  const instances = new Map();
  let carouselIndex = 0;
  const initializeScroll = carousel => {
    const viewport = carousel.querySelector('[data-swipe-viewport]');
    const cards = [...viewport.querySelectorAll(':scope > [data-swipe-card]')];
    const hint = carousel.querySelector('[data-scroll-hint]');
    if (!cards.length) return;
    carousel.classList.add('is-scrollable');
    viewport.tabIndex = 0;
    viewport.setAttribute('role', 'group');
    viewport.setAttribute('aria-label', 'Scrollable cards. Use the left and right arrow keys to explore.');
    let measuredWidth = 0, resizeFrame;
    const reveal = target => {
      const card = cards.find(item => item === target || item.contains(target));
      if (!card) return;
      const bounds = viewport.getBoundingClientRect(), item = card.getBoundingClientRect();
      if (item.left < bounds.left) viewport.scrollLeft += item.left - bounds.left;
      else if (item.right > bounds.right) viewport.scrollLeft += item.right - bounds.right;
    };
    const resize = () => {
      const available = viewport.clientWidth;
      if (!available) return;
      measuredWidth = available;
      // Preserve content-sized widths, with natural height and native scrolling.
      cards.forEach(card => {
        card.style.alignSelf = 'flex-start';
        const heightAt = width => {
          card.style.width = `${width}px`;
          return card.getBoundingClientRect().height;
        };
        let low = Math.min(300, available), high = available;
        if (heightAt(low) > 320) {
          if (heightAt(high) <= 320) {
            while (high - low > 2) {
              const middle = (low + high) / 2;
              if (heightAt(middle) > 320) low = middle;
              else high = middle;
            }
          }
          card.style.width = `${Math.min(available, Math.ceil(high))}px`;
        }
        card.style.removeProperty('align-self');
      });
      if (hint) hint.hidden = viewport.scrollWidth <= available + 1;
      if (viewport.contains(document.activeElement)) reveal(document.activeElement);
    };
    const scheduleResize = () => {
      cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(resize);
    };
    resize();
    const resizeObserver = new ResizeObserver(() => {
      if (viewport.clientWidth !== measuredWidth) scheduleResize();
    });
    resizeObserver.observe(viewport);
    const textObserver = new MutationObserver(scheduleResize);
    textObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['style', 'class', 'data-text', 'lang'] });
    document.fonts?.ready.then(scheduleResize);
    viewport.querySelectorAll('img').forEach(img => img.addEventListener('load', scheduleResize));
    // A normal mouse wheel can browse the row; at either end it scrolls the page.
    viewport.addEventListener('wheel', event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || Math.abs(event.deltaX) > 0) return;
      const step = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? viewport.clientWidth : 1);
      const maximum = viewport.scrollWidth - viewport.clientWidth;
      if ((step > 0 && viewport.scrollLeft < maximum - 1) || (step < 0 && viewport.scrollLeft > 1)) {
        if (event.cancelable) event.preventDefault();
        viewport.scrollLeft += step;
      }
    }, { passive: false });
    viewport.addEventListener('keydown', event => {
      if (event.target !== viewport || event.altKey || event.ctrlKey || event.metaKey) return;
      const step = Math.min(viewport.clientWidth, 300) + 18;
      const left = { ArrowLeft: viewport.scrollLeft - step, ArrowRight: viewport.scrollLeft + step,
        Home: 0, End: viewport.scrollWidth }[event.key];
      if (left === undefined) return;
      event.preventDefault();
      viewport.scrollLeft = left;
    });
    const onReveal = event => reveal(event.detail.target);
    document.addEventListener('public:reveal', onReveal);
    try {
      const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (target) reveal(target);
    } catch (_) {}
    instances.set(carousel, () => {
      cancelAnimationFrame(resizeFrame);
      resizeObserver.disconnect();
      textObserver.disconnect();
      document.removeEventListener('public:reveal', onReveal);
    });
  };
  const initialize = root => root.querySelectorAll('[data-about-carousel], [data-swipe-carousel], [data-card-scroll]').forEach(carousel => {
    if (instances.has(carousel)) return;
    const source = carousel.querySelector('[data-about-source]');
    // The visual editor needs its original editable field, without generated cards.
    if (carousel.querySelector('[data-portal-field]')) return;
    if (carousel.hasAttribute('data-card-scroll')) { initializeScroll(carousel); return; }
    const viewport = carousel.querySelector('[data-about-viewport], [data-swipe-viewport]');
    const controls = carousel.querySelector('[data-about-controls], [data-swipe-controls]');
    const previous = controls.querySelector('[data-about-previous], [data-swipe-previous]');
    const next = controls.querySelector('[data-about-next], [data-swipe-next]');
    const status = controls.querySelector('[data-about-status], [data-swipe-status]');
    const dots = carousel.querySelector('[data-swipe-dots]');
    const cards = [];
    if (source) {
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
      const heading = item => item.querySelector('h3')?.textContent.trim().toLowerCase();
      const background = cards.find(item => /^(association )?background$/.test(heading(item)));
      const mission = cards.find(item => /^(our )?mission$/.test(heading(item)));
      if (background && mission) {
        background.append(...mission.childNodes);
        cards.splice(cards.indexOf(mission), 1);
      }
    } else {
      cards.push(...viewport.querySelectorAll(':scope > [data-swipe-card]'));
    }
    if (!cards.length) return;
    carousel.classList.add('public-swipe-carousel');
    viewport.classList.add('public-swipe-viewport');
    controls.classList.add('public-swipe-controls');
    status.classList.add('public-swipe-count');
    previous.parentElement.classList.add('public-swipe-arrows');
    viewport.id ||= `public-swipe-${carouselIndex++}`;
    previous.setAttribute('aria-controls', viewport.id);
    next.setAttribute('aria-controls', viewport.id);
    cards.forEach((item, index) => {
      item.classList.add('public-swipe-card');
      item.setAttribute('role', 'group');
      item.setAttribute('aria-roledescription', 'slide');
      item.setAttribute('aria-label', `${index + 1} of ${cards.length}`);
    });
    viewport.replaceChildren(...cards);
    carousel.classList.add('is-ready');
    carousel.setAttribute('aria-roledescription', 'carousel');
    viewport.tabIndex = 0;
    viewport.setAttribute('aria-label', 'Swipe cards. Use left and right arrow keys to browse.');
    let pageSize = Math.max(0, parseInt(carousel.dataset.swipePageSize, 10) || 0);
    const requestedRows = Math.max(0, parseInt(carousel.dataset.swipeRows, 10) || 0);
    let restoreLastPage = carousel.dataset.swipeInitialPage === 'last';
    const pagination = document.getElementById(carousel.dataset.swipePagination);
    const previousPage = pagination?.querySelector('[rel="prev"]');
    const nextPage = pagination?.querySelector('[rel="next"]');
    const start = parseInt(carousel.dataset.swipeStart, 10) || 1;
    const total = parseInt(carousel.dataset.swipeTotal, 10) || cards.length;
    let current = 0, pages = [], widths = [], offsets = [], tops = [], moving = false, transition = 0;
    const liveDrag = carousel.hasAttribute('data-swipe-live');
    const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches || document.documentElement.dataset.motion === 'reduce';
    let dragOffset = 0;
    let measuredWidth = 0, resizeFrame;
    const gap = 18;
    const visible = (index, page = current) => pages[page]?.includes(index);
    const maximum = () => pages.length - 1;
    const updateControls = () => {
      const group = pages[current];
      controls.hidden = pages.length <= 1 && !previousPage && !nextPage;
      previous.setAttribute('aria-disabled', String(current === 0 && !previousPage));
      next.setAttribute('aria-disabled', String(current === maximum() && !nextPage));
      status.textContent = group.length === 1 ? `Card ${group[0] + start} of ${total}` :
        `Cards ${group[0] + start} to ${group.at(-1) + start} of ${total}`;
      status.setAttribute('aria-label', status.textContent);
      if (dots) {
        dots.hidden = pages.length <= 1;
        if (dots.contains(document.activeElement)) viewport.focus({ preventScroll: true });
        const indices = [...new Set([0, maximum(), current - 2, current - 1, current, current + 1, current + 2])]
          .filter(index => index >= 0 && index <= maximum()).sort((a, b) => a - b);
        const indicators = [];
        indices.forEach((index, position) => {
          if (position && index - indices[position - 1] > 1) {
            const gap = document.createElement('span');
            gap.textContent = '…';
            gap.setAttribute('aria-hidden', 'true');
            indicators.push(gap);
          }
          const button = document.createElement('button');
          button.type = 'button';
          button.dataset.swipePage = index;
          button.setAttribute('aria-controls', viewport.id);
          const items = pages[index];
          const label = items.length === 1 ? `Show card ${items[0] + start} of ${total}` :
            `Show cards ${items[0] + start} to ${items.at(-1) + start} of ${total}`;
          button.setAttribute('aria-label', label);
          button.title = label;
          if (index === current) button.setAttribute('aria-current', 'true');
          indicators.push(button);
        });
        dots.replaceChildren(...indicators);
      }
    };
    const paint = () => {
      cards.forEach((item, index) => {
        item.style.removeProperty('transform');
        item.style.width = `${widths[index]}px`;
        item.style.left = `${offsets[index] - current * (measuredWidth + gap)}px`;
        item.style.top = `${tops[index]}px`;
        item.hidden = !visible(index);
        item.inert = !visible(index);
        item.setAttribute('aria-hidden', String(!visible(index)));
      });
      dragOffset = 0;
      if (liveDrag) viewport.style.removeProperty('height');
      updateControls();
    };
    const resize = () => {
      const available = viewport.clientWidth;
      if (!available) return;
      const anchor = cards.findIndex(item => item.contains(document.activeElement));
      const keep = anchor >= 0 ? anchor : (pages[current]?.[0] || 0);
      transition++;
      cards.forEach(item => item.getAnimations().forEach(animation => animation.cancel()));
      moving = false;
      measuredWidth = available;
      let columns = Math.max(0, parseInt(getComputedStyle(carousel).getPropertyValue('--swipe-columns'), 10) || 0);
      if (requestedRows) {
        const minimumWidth = parseInt(carousel.dataset.swipeMinWidth, 10) || 300;
        const maximumColumns = parseInt(carousel.dataset.swipeMaxColumns, 10) || 4;
        columns = Math.max(1, Math.min(cards.length, maximumColumns, Math.floor((available + gap) / (minimumWidth + gap))));
        pageSize = columns * requestedRows;
      }
      // Give longer copy more width before increasing the shared row height.
      const heightAt = (item, width) => {
        item.style.width = `${width}px`;
        return item.getBoundingClientRect().height;
      };
      widths = cards.map(item => {
        item.hidden = false;
        item.style.height = 'auto';
        if (columns) return (available - gap * (columns - 1)) / columns;
        let low = Math.min(300, available), high = available;
        if (heightAt(item, low) <= 320) return low;
        if (heightAt(item, high) > 320) return high;
        while (high - low > 2) {
          const middle = (low + high) / 2;
          if (heightAt(item, middle) > 320) low = middle;
          else high = middle;
        }
        return Math.ceil(high);
      });
      pages = [];
      let group = [], used = 0;
      widths.forEach((width, index) => {
        if (group.length && (pageSize ? group.length >= pageSize : used + gap + width > available)) {
          pages.push(group); group = []; used = 0;
        }
        used += (group.length ? gap : 0) + width;
        group.push(index);
      });
      if (group.length) pages.push(group);
      let height = carousel.hasAttribute('data-swipe-compact') ? 0 : 320;
      cards.forEach((item, index) => { height = Math.max(height, Math.ceil(heightAt(item, widths[index]))); });
      pages.forEach((items, page) => {
        const row = pageSize ? items.slice(0, columns || 1) : items;
        const total = row.reduce((sum, index) => sum + widths[index], 0);
        const groupWidth = total + gap * (row.length - 1);
        // Keep content-sized cards together in the center, including the last group.
        let left = page * (available + gap) + (available - groupWidth) / 2;
        items.forEach((index, position) => {
          if (pageSize && position % (columns || 1) === 0) left = page * (available + gap) + (available - groupWidth) / 2;
          offsets[index] = left;
          tops[index] = pageSize ? Math.floor(position / (columns || 1)) * (height + gap) : 0;
          left += widths[index] + gap;
        });
      });
      const rows = pageSize ? Math.ceil(Math.min(pageSize, cards.length) / (columns || 1)) : 1;
      viewport.style.setProperty('--swipe-height', `${rows * height + (rows - 1) * gap}px`);
      viewport.style.setProperty('--swipe-card-height', `${height}px`);
      cards.forEach(item => item.style.removeProperty('height'));
      current = restoreLastPage ? maximum() : Math.max(0, pages.findIndex(items => items.includes(keep)));
      restoreLastPage = false;
      paint();
    };
    const scheduleResize = () => {
      cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(resize);
    };
    resize();
    const resizeObserver = new ResizeObserver(() => {
      if (viewport.clientWidth !== measuredWidth) scheduleResize();
    });
    resizeObserver.observe(viewport);
    const textObserver = new MutationObserver(scheduleResize);
    textObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['style', 'class', 'data-text', 'lang'] });
    document.fonts?.ready.then(scheduleResize);
    viewport.querySelectorAll('img').forEach(img => img.addEventListener('load', scheduleResize));
    const show = async (requested, instant = false) => {
      if (!moving && (requested < 0 || requested > maximum())) {
        const link = requested < 0 ? previousPage : nextPage;
        if (link) {
          paint();
          link.dataset.publicBrowseFocus = viewport.id;
          if (requested < 0) link.dataset.publicBrowseLastCards = 'true';
          link.click();
          delete link.dataset.publicBrowseFocus;
          delete link.dataset.publicBrowseLastCards;
          return;
        }
      }
      const index = Math.max(0, Math.min(requested, maximum()));
      if (moving) return;
      if (index === current && !dragOffset) { if (liveDrag) paint(); return; }
      moving = true;
      const token = ++transition, before = current;
      const delta = (index - before) * (measuredWidth + gap) + dragOffset;
      current = index;
      if (cards.some((item, i) => item.contains(document.activeElement) && !visible(i))) viewport.focus({ preventScroll: true });
      const reduceMotion = reducedMotion();
      const animations = [];
      cards.forEach((item, i) => {
        const active = visible(i), wasActive = visible(i, before) || (liveDrag && !item.hidden);
        item.hidden = !(active || wasActive);
        item.inert = !active;
        item.setAttribute('aria-hidden', String(!active));
        item.style.left = `${offsets[i] - current * (measuredWidth + gap)}px`;
        item.style.removeProperty('transform');
        if ((active || wasActive) && !instant && !reduceMotion) {
          animations.push(item.animate([{ transform: `translateX(${delta}px)` }, { transform: 'translateX(0)' }],
            { duration: 300, easing: 'cubic-bezier(.22,.61,.36,1)' }));
        }
      });
      await Promise.all(animations.map(animation => animation.finished.catch(() => {})));
      if (token !== transition) return;
      moving = false;
      paint();
    };
    const reveal = target => {
      const index = cards.findIndex(item => item === target || item.contains(target));
      if (index >= 0 && !visible(index)) show(pages.findIndex(items => items.includes(index)), true);
    };
    const onReveal = event => reveal(event.detail.target);
    document.addEventListener('public:reveal', onReveal);
    try {
      const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (target) reveal(target);
    } catch (_) {}
    previous.addEventListener('click', () => show(current - 1));
    next.addEventListener('click', () => show(current + 1));
    dots?.addEventListener('click', event => {
      const button = event.target.closest('[data-swipe-page]');
      if (!button || !dots.contains(button)) return;
      viewport.focus({ preventScroll: true });
      show(Number(button.dataset.swipePage));
    });
    carousel.addEventListener('keydown', event => {
      if (event.target.closest('.table-responsive,input,textarea,select,[contenteditable="true"],[contenteditable="plaintext-only"]')) return;
      const index = { ArrowLeft: current - 1, ArrowRight: current + 1, Home: 0, End: maximum() }[event.key];
      if (index === undefined) return;
      event.preventDefault();
      show(index);
    });

    let gesture, suppressClick = false;
    viewport.addEventListener('dragstart', event => {
      if (carousel.hasAttribute('data-swipe-linked-cards')) event.preventDefault();
    });
    viewport.addEventListener('pointerdown', event => {
      suppressClick = false;
      if (!event.isPrimary || event.button !== 0 || moving || event.target.closest('.table-responsive,.result-table-scroll,button,input,select,textarea,[contenteditable],summary')) return;
      if (event.target.closest('a') && !carousel.hasAttribute('data-swipe-linked-cards')) return;
      gesture = { id: event.pointerId, x: event.clientX, y: event.clientY, horizontal: false };
    });
    viewport.addEventListener('pointermove', event => {
      if (!gesture || event.pointerId !== gesture.id) return;
      const dx = event.clientX - gesture.x;
      const dy = event.clientY - gesture.y;
      if (!gesture.horizontal && Math.abs(dy) > 12 && Math.abs(dy) > Math.abs(dx)) { gesture = null; return; }
      if (!gesture.horizontal && Math.abs(dx) > 12 && Math.abs(dx) > Math.abs(dy) * 1.3) {
        gesture.horizontal = true;
        viewport.setPointerCapture(event.pointerId);
        carousel.classList.add('is-dragging');
        if (liveDrag) viewport.style.height = `${viewport.getBoundingClientRect().height}px`;
      }
      if (gesture.horizontal) {
        if (event.cancelable) event.preventDefault();
        if (liveDrag && !reducedMotion()) {
          const neighbor = current + (dx < 0 ? 1 : -1);
          // Show the adjacent card under the pointer; resist dragging beyond an end.
          dragOffset = Math.max(-measuredWidth, Math.min(measuredWidth, dx)) * (pages[neighbor] ? 1 : .2);
          cards.forEach((item, index) => {
            item.hidden = !(visible(index) || visible(index, neighbor));
            item.style.transform = `translateX(${dragOffset}px)`;
          });
        }
      }
    });
    const finishGesture = event => {
      if (!gesture || event.pointerId !== gesture.id) return;
      const dx = event.clientX - gesture.x;
      const dy = event.clientY - gesture.y;
      const advance = event.type === 'pointerup' && gesture.horizontal && Math.abs(dx) >= 45 && Math.abs(dx) > Math.abs(dy) * 1.3;
      const dragged = gesture.horizontal;
      gesture = null;
      carousel.classList.remove('is-dragging');
      if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
      if (dragged) suppressClick = true;
      if (advance) show(current + (dx < 0 ? 1 : -1));
      else if (liveDrag) show(current);
    };
    // A drag across a linked event card must not also open its details.
    viewport.addEventListener('click', event => {
      if (!suppressClick) return;
      suppressClick = false;
      event.preventDefault();
      event.stopPropagation();
    }, true);
    viewport.addEventListener('pointerup', finishGesture);
    viewport.addEventListener('pointercancel', finishGesture);
    viewport.addEventListener('lostpointercapture', event => {
      // Touch starts with implicit capture on a child; ignore its capture transfer.
      if (event.target !== viewport) return;
      gesture = null;
      carousel.classList.remove('is-dragging');
      if (liveDrag && !moving) show(current);
    });
    instances.set(carousel, () => {
      transition++;
      cancelAnimationFrame(resizeFrame);
      resizeObserver.disconnect();
      textObserver.disconnect();
      document.removeEventListener('public:reveal', onReveal);
    });
  });
  initialize(document);
  document.addEventListener('public:results-updated', event => {
    instances.forEach((dispose, carousel) => {
      if (!carousel.isConnected) { dispose(); instances.delete(carousel); }
    });
    initialize(event.detail.root);
  });
})();
