// The two visible reason fields edit the same existing eligibility submission.
document.addEventListener('input', event => {
    const field = event.target;
    if (!field.matches('[data-shared-review-reason], #eligibility_notes')) return;
    const other = field.matches('[data-shared-review-reason]')
        ? document.getElementById('eligibility_notes')
        : document.querySelector('[data-shared-review-reason]');
    if (other) other.value = field.value;
    field.setCustomValidity('');
});
document.addEventListener('click', event => {
    const button = event.target.closest('button[form="eligibility-decision-form"][value="review"]');
    if (!button) return;
    const field = document.querySelector('[data-shared-review-reason]');
    if (field && !field.value.trim()) {
        event.preventDefault();
        field.setCustomValidity('Record a reason for this program requirement review.');
        field.reportValidity();
    }
});
