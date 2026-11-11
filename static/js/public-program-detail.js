/* Cap long eligibility lists at the overview height; short lists size naturally. */
(() => {
    'use strict';
    const root = document.querySelector('.public-program-detail');
    if (!root || !window.ResizeObserver) return;
    const overview = root.querySelector('.program-detail-overview');
    const eligibility = root.querySelector('.program-detail-eligibility');
    const heading = eligibility?.querySelector('h2');
    const list = eligibility?.querySelector('.program-eligibility-list');
    const actions = eligibility?.querySelector('.program-detail-actions');
    if (!overview || !heading || !list || !actions) return;

    let frame = 0;
    const number = value => parseFloat(value) || 0;
    const outerHeight = element => {
        const style = getComputedStyle(element);
        return element.getBoundingClientRect().height + number(style.marginTop) + number(style.marginBottom);
    };
    const update = () => {
        frame = 0;
        root.classList.add('program-detail-sized');
        const cardStyle = getComputedStyle(eligibility);
        const listStyle = getComputedStyle(list);
        // Keep the title, actions and at least one full item usable at large text sizes.
        const minimum = outerHeight(heading) + outerHeight(actions)
            + number(cardStyle.paddingTop) + number(cardStyle.paddingBottom)
            + number(cardStyle.borderTopWidth) + number(cardStyle.borderBottomWidth)
            + number(listStyle.marginTop) + number(listStyle.marginBottom)
            + (list.firstElementChild?.getBoundingClientRect().height || 0);
        root.style.setProperty('--program-overview-height', `${overview.getBoundingClientRect().height}px`);
        root.style.setProperty('--program-eligibility-min-height', `${Math.ceil(minimum)}px`);
        if (list.scrollHeight > list.clientHeight + 1) list.tabIndex = 0;
        else list.removeAttribute('tabindex');
    };
    const schedule = () => {
        if (!frame) frame = requestAnimationFrame(update);
    };
    const observer = new ResizeObserver(schedule);
    [overview, heading, actions].forEach(element => observer.observe(element));
    window.addEventListener('resize', schedule, { passive: true });
    document.fonts?.ready.then(schedule);
    schedule();
})();
