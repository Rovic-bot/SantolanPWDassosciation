/* Shared public motion, without intercepting navigation or delaying requests. */
(() => {
    'use strict';
    const root = document.documentElement;
    const preference = matchMedia('(prefers-reduced-motion: reduce)');
    const animations = new Set();
    let navigationTransition = false;
    let resultsTransition;
    const enabled = () => root.dataset.motion !== 'reduce' && !preference.matches &&
        !document.querySelector('script[data-portal-page]');
    const track = animation => {
        animations.add(animation);
        animation.finished.then(() => animations.delete(animation), () => animations.delete(animation));
        return animation;
    };
    const enter = (element, { distance = 14, duration = 280 } = {}) => {
        if (!element?.animate || !enabled()) return;
        return track(element.animate([
            { opacity: 0, transform: 'translateY(' + distance + 'px)' },
            { opacity: 1, transform: 'translateY(0)' }
        ], { duration, easing: 'cubic-bezier(.2, .7, .2, 1)' }));
    };
    const finishResults = () => resultsTransition?.skipTransition();
    const changeResults = async update => {
        finishResults();
        if (!enabled() || !document.startViewTransition) {
            const replacement = update();
            enter(replacement?.querySelector('.notice-main'));
            return;
        }
        root.dataset.publicTransition = 'results';
        const transition = document.startViewTransition(update);
        resultsTransition = transition;
        // A superseding filter or reduced-motion preference can skip capture.
        transition.ready.catch(() => {});
        const clean = () => {
            if (resultsTransition !== transition) return;
            resultsTransition = undefined;
            delete root.dataset.publicTransition;
        };
        transition.finished.then(clean, clean);
        await transition.updateCallbackDone;
    };
    window.PublicMotion = { enabled, enter, changeResults, finishResults };

    // Native document transitions retain normal links, history and form behavior.
    window.addEventListener('pageswap', event => {
        if (!enabled()) event.viewTransition?.skipTransition();
    });
    window.addEventListener('pagereveal', event => {
        navigationTransition = Boolean(event.viewTransition);
        if (!enabled()) event.viewTransition?.skipTransition();
    });
    window.addEventListener('pageshow', event => {
        if (!event.persisted && !navigationTransition) enter(document.querySelector('body.public-portal #main-content'));
    });
    const applyPreference = () => {
        if (enabled()) return;
        finishResults();
        animations.forEach(animation => animation.finish());
    };
    preference.addEventListener('change', applyPreference);
    document.addEventListener('santolan:displaychange', applyPreference);

    document.addEventListener('DOMContentLoaded', () => {
        if (document.querySelector('script[data-portal-page]')) return;
        // Keep native disclosures and keyboard activation; animate their height.
        document.querySelectorAll('[data-guidance-card] details').forEach(details => {
            const summary = details.querySelector('summary');
            let animation;
            let expanded = details.open;
            summary.addEventListener('click', event => {
                if (event.defaultPrevented || event.target.closest('a, button, [data-portal-field]')) return;
                event.preventDefault();
                const start = details.getBoundingClientRect().height;
                expanded = animation ? !expanded : !details.open;
                if (animation) { animation.cancel(); animation = undefined; }
                const finish = () => {
                    details.open = expanded;
                    details.style.removeProperty('overflow');
                    animation = undefined;
                };
                if (!enabled() || !details.animate) { finish(); return; }
                details.open = true;
                details.style.overflow = 'hidden';
                const end = expanded ? details.getBoundingClientRect().height : summary.getBoundingClientRect().height;
                animation = track(details.animate([
                    { height: start + 'px' }, { height: end + 'px' }
                ], { duration: 240, easing: 'cubic-bezier(.2, .7, .2, 1)' }));
                animation.onfinish = finish;
            });
        });
    });
})();
