# Phase 3 checkpoint — private review foundation

2026-10-23. **Partial.** Independent staff-only concern/findings storage and internal status projections are implemented and tested with synthetic policy fixtures. Public tracking, applicant confirmation during submission, source-correction integration and evaluation adjudication are **not delivered or activated**. The milestone remains 70%.

## Delivered boundary and files

- `members/review_models.py`, `members/models.py`: two separate review tables, guarded retained originals/history, actual Member and optional ProgramApplication links, UUID retry key and version. No accepted evidence fields or EWAF writes.
- `members/review_services.py`: fresh staff permission checks, fail-closed institutional configuration, own-application validation, idempotent intake, row-locked findings, stale/policy-change rejection, atomic audit, explicit routine-basis requirement; internal staff-authorized minimal Association/program status projection. PDAO is refused.
- `members/review_views.py`, `members/urls.py`, `members/views.py`, `templates/members/detail.html`, `templates/members/reviews/list.html`, `templates/members/reviews/detail.html`: private Member-context concern/history pages, program-specific clarification links, CSRF, sensitive-POST filtering, no-store responses, existing labeled form patterns and pagination. Links appear only when the policy and view permission are available. Direct routes also enforce the gate.
- `members/migrations/0006_private_information_review.py`: two CreateModel and three AddConstraint operations only. Dependencies: members 0005, programs 0005, swappable staff user. SHA-256 `d7202490dceecda7606d7367b2628fd0097d5fbcad55ae01cf03bbacd32812a1`.
- `members/test_information_review.py`, `scripts/remaining_schema_tests.py`, reviewed test-runner allowlist, design/gates, logs/evidence and progress record: tests and traceable checkpoint.

These pages stay within Members and the existing private application review routes. The eight Admin groups/sidebar and minimalist styles are unchanged. No Public Portal destination, member account, tracking route, credential, QR, upload or notification was added in this phase. No dependencies or ordinary settings changed.

## Actual validation

Initial run: **55 tests, four fixture errors**, 63.861s. The synthetic application reference was too long for the existing 40-character column. Only the new fixture was corrected; the retained log records the failure. Final run: **57 passed in 75.574s**, including 12 new review/concurrency cases, the exact additive schema lifecycle test, existing Member tests and **30 unchanged EWAF tests**. Exit 0, no failures/errors/skips in the final run. Counts overlap.

Commands (each via fresh G12 MySQL, `.env` disabled, verified instance/database, separate temporary private media):

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py makemigrations members --name private_information_review --noinput
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test members.test_information_review members.tests ewaf.test_operational ewaf.test_membership_writers --testrunner scripts.remaining_phases_test_runner.RemainingPhasesTestRunner --noinput --verbosity 2
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test members.test_information_review scripts.remaining_schema_tests members.tests ewaf.test_operational ewaf.test_membership_writers --testrunner scripts.remaining_phases_test_runner.RemainingPhasesTestRunner --noinput --verbosity 2
```

The last test rehearses exact reverse/forward operations for the reviewed new membership and members migrations using synthetic model-derived schema/history, retaining an old synthetic Member row. It does not run historical migrations or validate an unknown deployed baseline. Both new schemas are absent from the unchanged startup deferral allowlist; working startup will require a separately reviewed exact migration plan. No working/production database or permissions were changed. Ordinary policy remains absent, so direct routes are unavailable.

Tests cover missing contract fields, unchanged independent verification dates, identical/different retry payloads, retained findings, selected/nonselected/closed application outcome preservation, cross-member denial, routine-basis/date requirements, staff/program permission separation, CSRF, permission revocation, audit failure rollback, immutable history, changed-policy rejection, no public tracking and concurrent duplicate/stale operations. Real-browser, screen-reader and UAT evidence is not claimed here; Phase 5 records available coverage separately.

## Protection, limitations and outstanding decisions

All 267 protected files and all pre-existing migration files are unchanged. Section 8 remains byte-identical (8,384 bytes; SHA-256 `f446ea0be7cf061439293c75f6354bdde77c6e2e4870e69611cc19bd1abec41d`). `verification.json` retains the actual test outcomes and boundary evidence. No score, source freshness, pool membership, decision, publication or release is written by the new service.

The benefit is a retained private place to prepare concerns/findings and test permission/retry behavior. **It is not operationally complete**: a concern does not itself mark accepted evidence unresolved or refresh it. Before operational enablement, an approved procedure must connect material disputes to existing evidence-readiness controls, preserve the exact calculation/version being reviewed, and use authorized source writers without wrapping their top-level transactions. That coupling, exact reviewed-calculation binding, historical/non-operational engine cases and final-case remedies remain blocked. The foundation cannot accept/reject an evaluation, reopen a terminal case or substitute for these controls. Text findings are unaccepted notes, not verified assessment inputs.

IQ-03 still requires approved fields/access/recovery/QR/abuse controls. Applicant confirmation inside protected program submission needs an approved safe integration contract; no protected writer was changed. IQ-12 still requires reviewer authority, deadlines and terminal/published remedies. Association identity/representative procedures, privacy/retention and staff assignments remain outstanding. No sampling rate, review interval or expiry was invented. Additional permissions are defined only, not granted.

Phase 4's public CMS/resources work is independent of these private workflows and may proceed under the owner's authorization. Referral verification/statuses, RSVP rules and event-term interactions must be evaluated separately; none is approved by this checkpoint.
