/* Display only: the server still enforces registration and application readiness. */
(() => {
    'use strict';
    const clocks = new WeakMap();
    let timer;
    function update() {
        clearTimeout(timer);
        let next = Infinity;
        for (const note of document.querySelectorAll('[data-public-deadline]')) {
            if (!clocks.has(note)) clocks.set(note, {
                start: Date.parse(note.dataset.noticeStart),
                end: Date.parse(note.dataset.noticeEnd),
                server: Date.parse(note.dataset.noticeNow),
                observed: performance.now(),
            });
            const clock = clocks.get(note);
            const now = clock.server + performance.now() - clock.observed;
            if (![clock.start, clock.end, now].every(Number.isFinite)) { note.hidden = true; continue; }
            note.hidden = now < clock.start || now >= clock.end;
            if (now < clock.start) next = Math.min(next, clock.start - now);
            else if (now < clock.end) next = Math.min(next, clock.end - now);
        }
        // Server-relative elapsed time avoids depending on the device's clock setting.
        if (Number.isFinite(next)) timer = setTimeout(update, Math.max(1, Math.min(next, 60000)));
    }
    document.addEventListener('public:results-updated', update);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) update(); });
    window.addEventListener('pageshow', update);
    window.addEventListener('pagehide', () => clearTimeout(timer));
    update();
})();
