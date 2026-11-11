# Public registration privacy notices — October 27, 2026

Implemented locally on `EWAF-testing` following the owner's requested text removal and privacy pop-ups. No push or deployment was performed.

## Behavior

- Association application: removed the specified introductory paragraphs, PDF/PDAO links, and the document-checklist disclosure. The separate onsite-visit instruction remains because it was not included in the requested removal.
- PDAO application: removed the specified introductory paragraphs, inline privacy block, and requirements/PDF links.
- Each page opens its own privacy notice when the visitor first interacts with an editable registration field, whether by pointer, label, or keyboard. It appears once per page load so subsequent fields can be filled without repeated interruptions.
- A **Privacy information** button reopens the notice. **Continue filling form** or Escape closes it and restores focus. Entered values remain unchanged. Tab and Shift+Tab remain inside the open modal; its notice content is keyboard-scrollable.
- Association notice retains the existing configured privacy text, review/receipt instructions, actual server-provided expiry, and existing conditional upload instructions. The owner's copied timestamp is not hard-coded. The current no-upload policy displays the requested no-upload paragraph.
- PDAO notice retains the existing PDAO privacy text unchanged.
- Without JavaScript or native-dialog support, the notice remains readable inline above the form.

This is a presentation change. It does not record privacy acceptance, add a consent requirement, change declarations, alter form fields, adjust session expiry, or change validation, permissions, submission, or approval logic. The existing required declarations remain in their forms.

## Files

- `templates/membership/registration/apply.html`
- `templates/membership/pdao/apply.html`
- `templates/membership/registration/privacy_notice.html` (new shared partial)
- `static/js/registration-privacy.js` (new; loaded by these two public forms only)
- `static/css/registration.css` (new rules scoped to `.public-portal`)

## Verification

- JavaScript syntax check passed.
- Django database/configuration check passed; template compilation passed; no model changes detected; zero pending migrations. Read-only verification wrapper rejected database writes.
- Fourteen browser scenarios passed across both forms: 1440px, 390px, 320px, and 320px at 200% text; pointer/label/keyboard opening; focus restoration and wrapping; Escape; manual reopening; retained input values and unchanged field metadata; existing required-field validation; no-JavaScript and unsupported-dialog fallback.
- An initial keyboard check exposed focus leaving the dialog; explicit Tab/Shift+Tab wrapping was added and the full focused check passed afterward.
- No application POST was forwarded. Browser checks produced no JavaScript errors.
- Desktop/mobile screenshots were visually reviewed. `git diff --check` passed.

Local browser evidence: `.local/public-redesign/privacy-results.json`; harness: `.local/public-redesign/privacy-qa.cjs`.

## Preview and screenshots

| Form | Local route | Form screenshot | Privacy notice |
| --- | --- | --- | --- |
| Association membership | http://127.0.0.1:8000/membership/registration/apply/ | [Simplified form](public-portal-2026-10-27/membership-form-simplified.png) | [Desktop](public-portal-2026-10-27/membership-privacy-desktop.png), [mobile](public-portal-2026-10-27/membership-privacy-mobile.png) |
| PDAO PWD ID | http://127.0.0.1:8000/membership/registration/pdao/apply/ | [Simplified form](public-portal-2026-10-27/pdao-form-simplified.png) | [Desktop](public-portal-2026-10-27/pdao-privacy-desktop.png), [mobile](public-portal-2026-10-27/pdao-privacy-mobile.png) |

Physical-device and screen-reader user acceptance were not performed. Existing backend test suites were not rerun for this template/CSS/JavaScript-only change.
