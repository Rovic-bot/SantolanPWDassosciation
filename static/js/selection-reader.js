/* Read the user's selected visible text only after an explicit click or shortcut. */
'use strict';
WorkspacePage.run(({on, cleanup, setTimeout}) => {
    const isAdmin = document.body.classList.contains('admin-workspace');
    if (!document.body.classList.contains('public-portal') && !isAdmin) return;
    const reader = document.querySelector('[data-selection-reader]');
    const hint = document.querySelector('[data-selection-hint]');
    if (!reader) return;
    if (typeof window.speechSynthesis?.speak !== 'function' || typeof window.SpeechSynthesisUtterance !== 'function') {
        if (hint) {
            hint.textContent = 'Selected-text reading is not supported by this browser.';
            hint.hidden = false;
        }
        return;
    }
    if (hint) hint.hidden = false;
    const button = reader.querySelector('[data-selection-read]');
    const label = reader.querySelector('[data-selection-read-label]');
    const status = document.querySelector('[data-selection-status]');
    const speech = window.speechSynthesis;
    const forbidden = 'input, textarea, select, [contenteditable]:not([contenteditable="false"]), [inert], [aria-hidden="true"], [data-display-widget], [data-selection-reader], [data-tracking-dialog], [data-concern-dialog], [data-portal-field]';
    const privateSource = 'input, textarea, select, [contenteditable]:not([contenteditable="false"]), [inert], [data-display-widget], [data-selection-reader], [data-tracking-dialog], [data-concern-dialog], [data-portal-field]';
    let text = '', range = null, dismissed = false, reading = false, interacting = false, timer = 0, generation = 0;
    const resetPlayback = () => {
        label.textContent = 'Read aloud';
        reader.removeAttribute('aria-busy');
        reading = false;
    };
    const cancel = () => {
        generation++;
        if (reading) speech.cancel();
        resetPlayback();
    };
    const hide = () => {
        cancel();
        reader.hidden = true;
        text = '';
        range = null;
        dismissed = false;
    };
    const position = () => {
        if (!range || dismissed || !range.startContainer.isConnected) { reader.hidden = true; return; }
        const viewport = window.visualViewport;
        const left = viewport?.offsetLeft || 0, top = viewport?.offsetTop || 0;
        const width = viewport?.width || innerWidth, height = viewport?.height || innerHeight;
        const rect = [...range.getClientRects()].filter(r => r.width && r.height && r.bottom > top && r.top < top + height && r.right > left && r.left < left + width).at(-1);
        if (!rect) { reader.hidden = true; return; }
        reader.hidden = false;
        reader.style.maxWidth = `${Math.max(1, width - 20)}px`;
        const box = reader.getBoundingClientRect(), gap = 10;
        let y = rect.bottom + gap;
        if (y + box.height > top + height - gap) y = rect.top - box.height - gap;
        reader.style.left = `${Math.max(left + gap, Math.min(rect.left, left + width - box.width - gap))}px`;
        reader.style.top = `${Math.max(top + gap, Math.min(y, top + height - box.height - gap))}px`;
    };
    const update = () => {
        const selection = window.getSelection();
        if (interacting || reader.contains(document.activeElement)) return;
        if (!selection?.rangeCount || selection.isCollapsed || !selection.toString().trim()) { hide(); return; }
        const next = selection.getRangeAt(0);
        const parent = node => node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
        const start = parent(next.startContainer), end = parent(next.endContainer);
        if (!start || !end || start.closest(forbidden) || end.closest(forbidden) || document.activeElement?.matches('input, textarea, [contenteditable]:not([contenteditable="false"])')) { hide(); return; }
        // Read visible page copy, never editable form values or hidden evidence.
        const source = isAdmin ? 'main, #content, .workspace-navigation' : 'main, .bento-footer, .portal-navigation, [data-public-popup-content]';
        if (!start.closest(source) || !end.closest(source)) { hide(); return; }
        const ancestor = parent(next.commonAncestorContainer);
        // Native paragraph selection can cross adjacent decorative icons. Those
        // do not invalidate the selection, but editable/private sources do.
        if ([...ancestor.querySelectorAll(privateSource)].some(node => next.intersectsNode(node))) { hide(); return; }
        const selected = selection.toString().trim();
        const changed = selected !== text || !range || next.startContainer !== range.startContainer || next.startOffset !== range.startOffset || next.endContainer !== range.endContainer || next.endOffset !== range.endOffset;
        if (changed) { cancel(); dismissed = false; }
        text = selected;
        range = next.cloneRange();
        position();
    };
    const schedule = () => {
        window.clearTimeout(timer);
        timer = setTimeout(update, 120);
    };
    const speak = () => {
        if (!text || !range) return;
        cancel();
        const token = generation;
        const chunks = [];
        let chunk = '';
        for (const word of text.match(/\S+\s*/gu) || []) {
            if (chunk && chunk.length + word.length > 280) { chunks.push(chunk); chunk = ''; }
            chunk += word;
        }
        if (chunk) chunks.push(chunk);
        const lang = document.documentElement.lang || 'en';
        const voices = speech.getVoices();
        const voice = voices.find(item => item.localService && item.lang.toLowerCase().startsWith(lang.toLowerCase().split('-')[0])) ||
            (isAdmin ? voices.find(item => item.localService) : undefined);
        if (isAdmin && !voice) {
            status.textContent = 'On-device reading is unavailable. Enable a local speech voice in your browser or device settings.';
            return;
        }
        reading = true;
        label.textContent = 'Reading…';
        reader.setAttribute('aria-busy', 'true');
        status.textContent = 'Reading selected text. Press Escape or close Read aloud to stop.';
        const next = index => {
            if (token !== generation) return;
            if (index >= chunks.length) {
                resetPlayback();
                status.textContent = 'Finished reading the selected text.';
                return;
            }
            const utterance = new SpeechSynthesisUtterance(chunks[index]);
            utterance.lang = lang;
            if (voice) utterance.voice = voice;
            utterance.onend = () => next(index + 1);
            utterance.onerror = event => {
                if (token !== generation) return;
                generation++;
                resetPlayback();
                if (!['interrupted', 'canceled'].includes(event.error)) status.textContent = 'Reading is unavailable right now. Please try again or check your browser voice settings.';
            };
            try { speech.speak(utterance); }
            catch (_) { generation++; resetPlayback(); status.textContent = 'Reading is unavailable in this browser right now.'; }
        };
        next(0);
    };
    const dismiss = () => {
        const wasReading = reading;
        cancel();
        dismissed = true;
        reader.hidden = true;
        if (wasReading) status.textContent = 'Reading ended.';
    };
    on(reader, 'pointerdown', event => {
        // Preserve the highlighted range when the floating button is pressed.
        interacting = true;
        event.preventDefault();
    });
    on(document, 'pointerup', () => { interacting = false; schedule(); });
    on(document, 'pointercancel', () => { interacting = false; schedule(); });
    on(button, 'click', speak);
    on(reader.querySelector('[data-selection-dismiss]'), 'click', dismiss);
    on(document, 'selectionchange', schedule);
    on(document, 'keyup', schedule);
    on(document, 'keydown', event => {
        if (event.key === 'Escape' && (!reader.hidden || reading)) { event.preventDefault(); dismiss(); }
        if (event.altKey && !event.ctrlKey && !event.metaKey && event.key.toLowerCase() === 'r') {
            update();
            if (text && range) { event.preventDefault(); dismissed = false; position(); speak(); }
        }
    });
    on(window, 'scroll', position, true);
    on(window, 'resize', position);
    if (window.visualViewport) {
        on(window.visualViewport, 'resize', position);
        on(window.visualViewport, 'scroll', position);
    }
    on(window, 'pagehide', hide);
    cleanup(hide);
});
