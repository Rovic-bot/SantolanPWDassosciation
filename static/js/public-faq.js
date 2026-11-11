/* Native FAQ disclosures, enhanced with reversible height animation. */
(() => {
    'use strict';
    const list = document.querySelector('[data-faq-list]');
    if (!list || document.querySelector('script[data-portal-page]')) return;
    const preference = matchMedia('(prefers-reduced-motion: reduce)');
    const controllers = new Map();
    const motion = () => document.documentElement.dataset.motion !== 'reduce' && !preference.matches;
    list.querySelectorAll('[data-faq-item]').forEach(details => {
        const summary = details.querySelector('summary');
        let animation, expanded = details.open;
        const finish = () => {
            details.open = expanded;
            details.style.removeProperty('overflow');
            animation = undefined;
        };
        const set = open => {
            const start = details.getBoundingClientRect().height;
            animation?.cancel();
            animation = undefined;
            expanded = open;
            if (!motion() || !details.animate) { finish(); return; }
            details.open = true;
            details.style.overflow = 'hidden';
            const border = details.offsetHeight - details.clientHeight;
            const end = open ? details.getBoundingClientRect().height : summary.getBoundingClientRect().height + border;
            animation = details.animate([{height: start + 'px'}, {height: end + 'px'}],
                {duration: 260, easing: 'cubic-bezier(.2,.7,.2,1)'});
            animation.onfinish = finish;
        };
        controllers.set(details, {set, finish: () => { animation?.cancel(); finish(); }});
        summary.addEventListener('click', event => {
            if (event.defaultPrevented || event.target.closest('a, button, [data-portal-field]')) return;
            event.preventDefault();
            const open = animation ? !expanded : !details.open;
            if (open) controllers.forEach((other, item) => {
                if (item !== details && item.open) other.set(false);
            });
            set(open);
        });
    });
    const applyPreference = () => {
        if (!motion()) controllers.forEach(item => item.finish());
    };
    preference.addEventListener('change', applyPreference);
    document.addEventListener('santolan:displaychange', applyPreference);
    let printState;
    window.addEventListener('beforeprint', () => {
        printState = [...controllers.keys()].map(details => [details, details.open]);
        controllers.forEach((control, details) => { control.finish(); details.open = true; });
    });
    window.addEventListener('afterprint', () => {
        printState?.forEach(([details, open]) => { details.open = open; });
        printState = undefined;
    });
})();
