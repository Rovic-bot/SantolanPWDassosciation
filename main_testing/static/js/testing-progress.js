document.addEventListener('submit', event => {
    const form = event.target;
    if (!form.closest('#calculate')) return;
    if (form.dataset.processing) {
        event.preventDefault();
        return;
    }
    if (form.method.toLowerCase() !== 'post') return;
    form.dataset.processing = 'true';
    const status = document.createElement('p');
    status.setAttribute('role', 'status');
    status.className = 'alert alert-info mt-3';
    status.textContent = 'Processing your request. Larger applicant pools can take time. Please keep this page open.';
    form.appendChild(status);
    setTimeout(() => {
        form.querySelectorAll('button[type="submit"]').forEach(button => { button.disabled = true; });
    }, 0);
});
