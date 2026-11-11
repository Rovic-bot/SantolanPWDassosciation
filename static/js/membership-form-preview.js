(() => {
  const paper = document.querySelector('.association-print-form');
  if (!paper) return;
  let printing = false;
  const fit = () => {
    if (!printing) paper.style.zoom = Math.min(1, Math.max(1, document.documentElement.clientWidth - 32) / paper.offsetWidth);
  };
  window.addEventListener('resize', fit);
  window.addEventListener('beforeprint', () => { printing = true; paper.style.zoom = '1'; });
  window.addEventListener('afterprint', () => { printing = false; fit(); });
  fit();
})();
