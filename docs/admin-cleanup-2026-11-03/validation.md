# Admin screens, PDAO reviews and EWAF loading — 3 November 2026

Implemented the owner's requested screen cleanup and workflow repairs in the existing Django application. The October 10 specification, development guide, implementation impact, membership amendment, DEC-027, Open Decisions and relevant dated validation notes were read first. Existing unfinished work was preserved. This change does not alter scoring formulas, membership approval, eligibility, beneficiary selection, issued references or publication rules.

## Screens

- Onsite registration: application status now follows the AMR lookup. Removed the optional “This document will be presented onsite” planning checkbox and its unused JavaScript. Required fields, uploads and physical-document review remain unchanged.
- Member directory: registration action sits above the selected-member card in its right column; row arrows are removed. Full records open in an accessible dialog, with native page links as a fallback. Editing reuses the onsite field cards and existing aligned form/service, with “Update member record” wording and the mandatory correction reason. Original submissions and documents remain retained.
- Assistance inbox: removed its introductory heading/copy and Email settings action. Tickets open in a dialog with concern, contact disclosure, reply composer, evidence and history. Opening still records review through the existing CSRF-protected POST. Reply and status actions retain permissions, current-version checks and audits. Internal notes are not emailed. Gmail composition remains available; the message entered in the composer is included only when the user chooses the Gmail link.
- Moved announcement creation, event actions and the EWAF vault link below their filters. Removed the requested introductory copy from application eligibility, assistance releases, announcements/results, content management, program portfolio and membership reviews. Accessible page headings remain where appropriate.

## PDAO repair

The supplied `/membership/registration/pdao/` URL previously prepared a transient printable form and did not save an application. The retained local instance also had `PDAO_REGISTRATION_ENABLED=False` and contained zero saved PDAO submissions at inspection.

The local setting now enables the already-implemented saved PDAO workflow. The original preparation URL delegates to that workflow when enabled, including session-bound submission tokens, private receipts, idempotency and the review queue. If intake is disabled, the historical print-only route remains available. Staff can review retained submissions regardless of the public intake switch, with all staff permissions still enforced.

Earlier print-only forms cannot be recovered as submissions because they were never stored. No PDAO approval, government ID issuance, automatic forwarding or Association member creation was added.

## EWAF performance

Measured the same nine-program workspace projection against the retained local database without changing its data:

| Measurement | Before | After |
| --- | ---: | ---: |
| List preparation | 9.634 seconds | 0.707 seconds |
| Database queries | 8,030 | 180 |

The list no longer captures every applicant pool or validates every saved run. It shows configuration/recorded-review summaries; “Ready for scoring checks” is explicitly a preliminary queue label. The selected program loads its full readiness checks and validated ranking through a private, uncached endpoint. Generation continues to recheck all sources and permissions through the existing service. Saved rankings, exact ties and stale-run handling are preserved. These timings cover server-side list preparation, not a production latency guarantee or the deferred panel request.

## Email delivery boundary

The reply composer uses the existing durable email queue, delivery attempts and retry history. This local instance has no SMTP credentials and remains on the file-based development outbox. The UI says these messages are not delivered. No real email was sent during this work; browser tests used fictional addresses and the memory-only backend.

For real delivery, configure the Association sender through the existing protected email-settings route and provide the SMTP connection through private environment settings. The retained local launcher accepts `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL` and `EMAIL_TIMEOUT` only when `SANTOLAN_DIRECT_EMAIL=1` is explicitly set, selecting Django's SMTP backend. Without that opt-in, mail credentials are excluded from the launched environment. The launcher intentionally does not load the ordinary `.env`. No secrets belong in source control or this document. Provider acceptance is recorded separately from confirmed inbox delivery.

## Validation

- **101 tests passed** in fresh disposable native MySQL, including PDAO intake/corrections/concurrency, onsite field alignment, member editing/history, directory privacy, EWAF readiness/stale runs/permissions and referral review/mail/rollback/CSRF tests.
- Chrome: ticket concern/reply popup, local email sending, six ticket theme/viewport combinations, onsite status position, PDAO form/review routes; member record popup, update form, 12 directory responsive checks and native fallback; 14 EWAF layouts, lazy readiness and two protected ranking generations.
- Two additional unit tests passed for the explicit mail-environment opt-in and default credential exclusion.
- Django database/system checks, migration drift (`No changes detected`), JavaScript syntax and Git whitespace checks passed. No migrations were introduced or applied.
- The first disposable setup exhausted available memory; the test launcher now bounds its own MySQL buffers/caches. The subsequent native-MySQL runs passed. A screenshot memory failure was resolved by capturing viewport-sized directory screenshots; the lazy-panel test now waits for the asynchronously replaced content. Historical text assertions were aligned with the current templates.
- Updated assets were collected. Only the identity-verified website process was restarted at `http://127.0.0.1:8013/`; the retained database process remained running.

Successful combined run: `santolan-g12-tests-wrsaxk9l`. Screenshots below contain fictional test data only.

[Ticket popup, phone](ticket-light-390.png) · [Member directory](directory-dark-1600.png) · [Member record popup](member-record-dialog.png) · [Member update form](member-update-form.png) · [EWAF](ewaf-selection-dark-1600.png)
