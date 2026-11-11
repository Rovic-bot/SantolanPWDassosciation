/* Progressive enhancement: no scroll interception, animation library, or continuous loop. */
(() => {
  'use strict';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const finePointer = matchMedia('(hover: hover) and (pointer: fine) and (min-width: 768px)');
  const hero = document.querySelector('[data-hero]');
  const sculpture = document.querySelector('[data-sculpture]');
  const title = hero?.querySelector('.hero-title');
  const targets = [...document.querySelectorAll('[data-reveal]')];
  let observer;
  let frame = 0;
  let pointerX = 0, pointerY = 0;
  let heroHeight = hero?.offsetHeight || 1;
  let inView = true;
  const canMove = () => !reduced.matches && document.documentElement.dataset.motion !== 'reduce';
  const reset = () => {
    sculpture?.removeAttribute('style');
    title?.removeAttribute('style');
  };
  const paint = () => {
    frame = 0;
    if (!hero || !canMove() || !inView || document.hidden) return;
    const progress = Math.min(1, Math.max(0, window.scrollY / heroHeight));
    sculpture.style.setProperty('--pointer-x', pointerX.toFixed(2) + 'deg');
    sculpture.style.setProperty('--pointer-y', pointerY.toFixed(2) + 'deg');
    sculpture.style.setProperty('--sculpture-y', (progress * 68).toFixed(1) + 'px');
    sculpture.style.setProperty('--sculpture-turn', (-8 + progress * 12).toFixed(1) + 'deg');
    sculpture.style.setProperty('--sculpture-scale', (1 - progress * .1).toFixed(3));
    title.style.setProperty('--copy-y', (progress * -18).toFixed(1) + 'px');
  };
  const schedule = () => { if (!frame && canMove() && inView) frame = requestAnimationFrame(paint); };
  const configure = () => {
    observer?.disconnect();
    cancelAnimationFrame(frame);
    frame = 0;
    pointerX = 0;
    pointerY = 0;
    document.documentElement.classList.remove('motion-ready');
    if (!canMove()) { reset(); targets.forEach(target => target.classList.add('is-visible')); return; }
    if ('IntersectionObserver' in window) {
      observer = new IntersectionObserver(entries => entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      }), { threshold: .12, rootMargin: '0px 0px -20px 0px' });
      targets.forEach(target => observer.observe(target));
      document.documentElement.classList.add('motion-ready');
    }
    heroHeight = hero?.offsetHeight || 1;
    schedule();
  };
  if (hero && sculpture) {
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', () => { heroHeight = hero.offsetHeight; schedule(); }, { passive: true });
    hero.addEventListener('pointermove', event => {
      if (!finePointer.matches || !canMove()) return;
      pointerX = (event.clientX / innerWidth - .5) * 6;
      pointerY = (event.clientY / innerHeight - .5) * -6;
      schedule();
    }, { passive: true });
    hero.addEventListener('pointerleave', () => { pointerX = 0; pointerY = 0; schedule(); });
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(entries => { inView = entries[0].isIntersecting; if (inView) schedule(); }).observe(hero);
    }
  }
  reduced.addEventListener('change', configure);
  finePointer.addEventListener('change', configure);
  document.addEventListener('santolan:displaychange', configure);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) schedule(); });
  configure();
})();
