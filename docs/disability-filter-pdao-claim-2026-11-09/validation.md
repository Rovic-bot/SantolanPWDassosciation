# Disability filtering and PDAO collection emails — 9 November 2026

Implemented the owner's request for a disability-type filter in Member Directory and an explicit PWD ID collection email after recording forwarding to PDAO, including bulk selection in the Forwarded to PDAO tab.

## Behavior

- Member Directory combines disability type with the existing name/reference search and member-status filter. Selection survives pagination and browser back/forward; Clear resets it. The normal GET form also works without JavaScript.
- Filtering uses recorded structured disability types. A member with multiple types appears once when any selected type matches. The legacy single-type field is used only when the member has no multi-type records. Inactive recorded categories remain searchable and are labeled inactive. Free text is not inferred or remapped.
- A forwarded PDAO record offers **Send PWD ID claim email** when it has a valid saved email and no previous collection notice. The Forwarded to PDAO tab offers checkboxes, select-all for eligible applications on the current page, a selected count and **Send PWD ID claim emails**. A batch contains at most 25 applications.
- Staff confirm that the selected physical cards are ready at the Barangay Santolan office before sending. The message identifies the applicant and application reference, says the PWD ID is ready for collection, and directs them to the barangay office. It contains no disability, medical or PWD-number details. Each recipient gets a separate email through the existing Association sender.
- Both online and onsite applications can receive this collection email if an email was recorded. Existing onsite Ready/Needs information actions remain email-free.
- Records without valid emails cannot be selected. A crafted batch containing a missing email, a stale version or a non-forwarded application fails without partially queuing it. Existing claim notices are not duplicated, including overlapping batches. Delivery states are visible in the list and the record's **Applicant emails** section.
- Only staff with the existing PDAO view, dashboard and forwarding permissions can request delivery. POST, CSRF validation, fresh permission checks, ordered row locks, immutable message snapshots and audited confirmation protect the action. Submitted recipients and arbitrary redirect URLs are not accepted.
- Claim notices do not change application status, version, issued references, membership, eligibility or government ID decisions. No automatic claim notice is sent by the forwarding action itself.

## Delivery behavior

New notices are durably saved before an after-commit background dispatcher attempts individual delivery. The page returns promptly and offers **Refresh email status**. Known failed or queued notices can be retried from the existing record email controls; accepted, sending or uncertain messages are not automatically resent. A server restart may leave queued notices for explicit retry. Local/test delivery is labeled as a test outbox, rather than claiming inbox delivery.

## Validation

The following focused suite passed **49 tests** against a new disposable native MySQL instance, with fictional applicants and a local test outbox:

```powershell
.venv/Scripts/python.exe scripts/g12_test_runner.py test members.test_directory membership.test_pdao_claim_email membership.test_pdao_claim_migration membership.test_pdao_notifications membership.test_pdao_onsite membership.test_pdao_review scripts.pdao_claim_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

Coverage includes structured disability filtering, legacy fallback, search/status intersections, pagination, invalid categories, permissions, CSRF, stale edits, audit rollback, revoked permissions, missing emails, duplicate and concurrent overlapping batches, known delivery failure/retry, uncertain delivery, immutable snapshots, onsite review behavior and the exact migration.

The Chrome journey exercises both bulk delivery and forwarding a ready record before sending its individual collection email. It also verifies the directory without JavaScript and 16 combinations of light/dark theme, both pages and viewport widths 1440, 768, 390 and 320, without page overflow or JavaScript errors. After adjusting forwarded-table column widths, the browser test was rerun and passed. Screenshots were visually inspected.

- [Browser results](results.json)
- [Directory filter](directory-light-1440.png)
- [Mobile collection controls](claim-toolbar-light-390.png)
- [Forwarded delivery states](delivered-claims.png)
- [Individual collection action](single-claim-action.png)

JavaScript syntax checks, Django database checks, migration drift detection and `git diff --check` passed.

## Local activation and preservation

Migration `membership.0015_pdao_claim_notices` expands the existing email outcome constraint to include `claim_ready` and records the added choices in migration state. It creates no tables or columns and runs no data updates. Its exact forward operation was rehearsed while preserving existing notices, attempts, events and applicants.

The retained local instance is a verified model-synchronized baseline without a Django migration ledger. Its web process was stopped briefly, a complete private SQL backup was written under ignored `.local/disability-pdao-claim-20261109/`, and only the tested migration operation was applied. No historical migrations were replayed or falsely recorded. Fingerprints confirmed all columns and rows in **133 tables** were unchanged; the existing unconfirmed delivery record was preserved. The local server was restarted and checked healthy.

Read-only rendering of the retained Member Directory and forwarded inbox returned HTTP 200 with the new controls, under an SQL wrapper rejecting writes. **No real applicant emails were sent and no application statuses or permissions were changed during activation or validation.**

- [Preservation proof](preservation.json)
- [Read-only local checks](live-read-check.json)

Prior public-portal, PDAO-review and annual-observance work remains in place. Annual observances retain the ordinary responsive grid requested in the preceding change.
