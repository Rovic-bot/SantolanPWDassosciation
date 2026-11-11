/* Shared stacked cards. Preserve published copy, bookmarks and action routes. */
(() => {
    'use strict';
    document.querySelectorAll('[data-card-stack]').forEach(carousel => {
        // Keep the original editable field available in the visual content editor.
        if (carousel.querySelector('[data-portal-field]')) return;
        const stage = carousel.querySelector('[data-swipe-viewport]');
        const source = carousel.querySelector('[data-about-source]');
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
                    card.className = 'public-swipe-card';
                    card.setAttribute('data-swipe-card', '');
                    if (savedCopy || source.closest('[translate="no"]')) card.setAttribute('translate', 'no');
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
            cards.push(...stage.querySelectorAll(':scope > [data-swipe-card]'));
        }
        if (source && cards.length) stage.replaceChildren(...cards);
        const controls = carousel.querySelector('[data-stack-controls]');
        const dotsContainer = carousel.querySelector('[data-stack-dots]');
        const status = carousel.querySelector('[data-stack-status]');
        const hint = carousel.closest('.public-stack-panel')?.querySelector('[data-stack-hint]');
        const disclosure = carousel.closest('details');
        const maxWidth = Number(carousel.dataset.stackWidth) || 400;
        const minHeight = Number(carousel.dataset.stackMinHeight) || 340;
        if (!cards.length) return;

        let current = Math.max(0, cards.findIndex(card => card.id === carousel.dataset.stackStart));
        let cardWidth = 0, measuredWidth = 0, resizeFrame = 0, printing = false;
        let gesture = null, suppressClick = false;
        const title = card => card.querySelector('h3')?.textContent.trim() || 'Information';
        const dots = cards.map((card, index) => {
            card.tabIndex = -1;
            card.setAttribute('role', 'group');
            card.setAttribute('aria-roledescription', 'slide');
            card.setAttribute('aria-label', `${index + 1} of ${cards.length}: ${title(card)}`);
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'public-stack-dot';
            button.setAttribute('aria-label', `Show ${title(card)} (${index + 1} of ${cards.length})`);
            button.setAttribute('aria-controls', stage.id);
            button.addEventListener('click', () => show(index));
            dotsContainer.append(button);
            return button;
        });

        const paint = () => {
            cards.forEach((card, index) => {
                let offset = (index - current + cards.length) % cards.length;
                if (offset > cards.length / 2) offset -= cards.length;
                const depth = Math.abs(offset);
                const active = offset === 0;
                const distance = depth === 0 ? 0 : depth === 1 ? .66 : 1.16;
                card.style.setProperty('--stack-x', `${Math.sign(offset) * cardWidth * distance}px`);
                card.style.setProperty('--stack-angle', `${active ? 0 : -Math.sign(offset) * 8}deg`);
                card.style.setProperty('--stack-scale', active ? '1' : depth === 1 ? '.84' : '.7');
                card.style.setProperty('--stack-shade', active ? '0' : depth === 1 ? '.17' : '.3');
                card.style.zIndex = String(10 - depth);
                card.style.visibility = depth <= 2 ? 'visible' : 'hidden';
                card.style.opacity = depth <= 2 ? '1' : '0';
                card.dataset.stackActive = String(active);
                card.inert = !active;
                card.setAttribute('aria-hidden', String(!active));
                if (active) dots[index].setAttribute('aria-current', 'true');
                else dots[index].removeAttribute('aria-current');
            });
        };
        function show(index, announce = true) {
            const next = (index + cards.length) % cards.length;
            if (next === current) return;
            const moveFocus = cards[current].contains(document.activeElement);
            current = next;
            paint();
            if (moveFocus) cards[current].focus({ preventScroll: true });
            if (announce) status.textContent = `${title(cards[current])}. Card ${current + 1} of ${cards.length}.`;
        }
        const resize = () => {
            resizeFrame = 0;
            if (printing || matchMedia('print').matches || (disclosure && !disclosure.open) || !stage.clientWidth) return;
            measuredWidth = stage.clientWidth;
            cardWidth = Math.min(maxWidth, Math.max(1, measuredWidth - (measuredWidth < 600 ? 32 : 120)));
            carousel.style.setProperty('--stack-card-width', `${cardWidth}px`);
            carousel.classList.add('is-measuring', 'is-resizing');
            // Measure every card at its reading size, so switching never clips text
            // or shifts the section height. No card has an internal text scrollbar.
            const height = Math.max(minHeight, ...cards.map(card => Math.ceil(card.offsetHeight)));
            carousel.style.setProperty('--stack-card-height', `${height}px`);
            carousel.classList.remove('is-measuring');
            paint();
            // Commit measured geometry before restoring card-switch animations.
            void stage.offsetHeight;
            carousel.classList.remove('is-resizing');
        };
        const scheduleResize = () => {
            if (!resizeFrame) resizeFrame = requestAnimationFrame(resize);
        };

        carousel.classList.add('is-enhanced');
        carousel.setAttribute('aria-roledescription', 'carousel');
        stage.tabIndex = 0;
        stage.setAttribute('role', 'group');
        stage.setAttribute('aria-label', 'Cards. Use the left and right arrow keys to explore.');
        controls.hidden = cards.length < 2;
        if (hint) hint.hidden = cards.length < 2;
        carousel.querySelector('[data-stack-previous]').addEventListener('click', () => show(current - 1));
        carousel.querySelector('[data-stack-next]').addEventListener('click', () => show(current + 1));
        carousel.addEventListener('keydown', event => {
            if (event.altKey || event.ctrlKey || event.metaKey || event.target.closest('input, textarea, select, [contenteditable]')) return;
            const next = { ArrowLeft: current - 1, ArrowRight: current + 1, Home: 0, End: cards.length - 1 }[event.key];
            if (next === undefined) return;
            event.preventDefault();
            show(next);
        });

        stage.addEventListener('dragstart', event => event.preventDefault());
        stage.addEventListener('pointerdown', event => {
            suppressClick = false;
            if (!event.isPrimary || event.button !== 0 || event.target.closest('button, input, select, textarea')) return;
            gesture = { id: event.pointerId, x: event.clientX, y: event.clientY, horizontal: false };
        });
        stage.addEventListener('pointermove', event => {
            if (!gesture || gesture.id !== event.pointerId) return;
            const dx = event.clientX - gesture.x, dy = event.clientY - gesture.y;
            if (!gesture.horizontal && Math.abs(dx) > 12 && Math.abs(dx) > Math.abs(dy) * 1.3) {
                gesture.horizontal = true;
                stage.setPointerCapture(event.pointerId);
                carousel.classList.add('is-dragging');
            }
            if (!gesture.horizontal) return;
            if (event.cancelable) event.preventDefault();
            carousel.style.setProperty('--stack-drag', `${Math.max(-60, Math.min(60, dx * .3))}px`);
        });
        const finish = event => {
            if (!gesture || gesture.id !== event.pointerId) return;
            const dx = event.clientX - gesture.x;
            const dragged = gesture.horizontal;
            gesture = null;
            carousel.classList.remove('is-dragging');
            carousel.style.removeProperty('--stack-drag');
            if (stage.hasPointerCapture(event.pointerId)) stage.releasePointerCapture(event.pointerId);
            if (event.type !== 'pointerup' || !dragged) return;
            suppressClick = true;
            if (Math.abs(dx) >= 45) show(current + (dx < 0 ? 1 : -1));
        };
        stage.addEventListener('pointerup', finish);
        stage.addEventListener('pointercancel', finish);
        stage.addEventListener('lostpointercapture', event => {
            if (event.target !== stage) return;
            gesture = null;
            carousel.classList.remove('is-dragging');
            carousel.style.removeProperty('--stack-drag');
        });
        stage.addEventListener('click', event => {
            if (suppressClick) {
                suppressClick = false;
                event.preventDefault();
                event.stopPropagation();
                return;
            }
            if (event.target.closest('a, button')) return;
            // Preview cards are inert; their exposed sides still act as large
            // pointer targets without exposing hidden links to keyboard focus.
            const active = cards[current].getBoundingClientRect();
            if (event.clientX < active.left) show(current - 1);
            else if (event.clientX > active.right) show(current + 1);
        }, true);

        const reveal = target => {
            const index = cards.findIndex(card => card === target || card.contains(target));
            if (index >= 0) show(index, false);
        };
        document.addEventListener('public:reveal', event => reveal(event.detail.target));
        paint();
        resize();
        disclosure?.addEventListener('toggle', scheduleResize);
        try {
            const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
            if (target) reveal(target);
        } catch (_) {}
        const resizeObserver = new ResizeObserver(() => {
            if (stage.clientWidth !== measuredWidth) scheduleResize();
        });
        resizeObserver.observe(stage);
        const textObserver = new MutationObserver(scheduleResize);
        textObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['style', 'class', 'data-text', 'lang'] });
        document.fonts?.ready.then(scheduleResize);
        stage.querySelectorAll('img').forEach(image => image.addEventListener('load', scheduleResize));
        // Display controls may reveal an action button after this script initializes.
        const contentObserver = new MutationObserver(scheduleResize);
        contentObserver.observe(stage, { subtree: true, attributes: true, attributeFilter: ['hidden'] });
        window.addEventListener('beforeprint', () => {
            printing = true;
            cards.forEach(card => { card.inert = false; card.removeAttribute('aria-hidden'); });
        });
        window.addEventListener('afterprint', () => { printing = false; paint(); scheduleResize(); });
    });
})();
