document.addEventListener('click', (event) => {
    if (event.target.closest('[data-registration-print]')) window.print();
});

// Fit the preview on small screens; keep the original A4 size when printing.
if (document.body.classList.contains('pdao-embedded-preview')) {
    const sheets = [...document.querySelectorAll('.pdao-sheet')];
    let printing = false;
    const fit = () => {
        sheets.forEach(sheet => { sheet.style.zoom = printing ? '1' : Math.min(1,
            Math.max(1, document.documentElement.clientWidth - 16) / sheet.offsetWidth); });
    };
    window.addEventListener('resize', fit);
    window.addEventListener('beforeprint', () => { printing = true; fit(); });
    window.addEventListener('afterprint', () => { printing = false; fit(); });
    fit();
}
