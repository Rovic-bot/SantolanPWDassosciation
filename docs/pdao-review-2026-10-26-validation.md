# PDAO review editing and automatic online channel — October 26, 2026

The owner requested editable PDAO Membership Reviews and removal of “Planned submission channel to PDAO,” clarifying that applicants submit online and are verified onsite. The external specification, development guide, Open Decisions, master index, membership amendment and implementation impact documents were checked and remain absent at the supplied parent paths. This implementation follows the explicit request and preserves other workflows.

## Available behavior

Authorized Admin staff can edit application details directly in Membership Reviews / PDAO Membership and select **Save reviewed details**. The form loads the latest saved details, retains gender/sex dropdowns, validates required fields and number formats, and rejects unexpected fields or uploads. It does not ask staff to impersonate the applicant's original acknowledgement.

The new `correct_pdaoregistration` permission controls editing independently of viewing, printing and forwarding. Superusers have it automatically; other staff require that permission. Fresh permission checks occur before and after correction. Original payloads, receipt bindings, references and applicant acknowledgements remain immutable. Each correction creates an append-only full revision and a processing event with actor, version and time. Admin can inspect the original submission and prior revisions. No-op saves are idempotent; stale/concurrent changes cannot overwrite each other, and audit failure rolls the entire correction back.

The inbox displays and searches the latest reviewed name. Admin printing uses the latest saved revision. An applicant's existing private receipt continues to show their original declaration. Editing a Ready form returns it to Received for another review; already-forwarded forms cannot be edited. Save corrections before printing or forwarding. PDAO records still create no Association Member or MembershipApplication.

The planned-channel field was removed from the shared PDAO form, including the online intake and print-only preparation form. New saved submissions record `intake_channel=online` automatically; applicants cannot override it. Pages explain that onsite verification of information and requirements precedes forwarding. Existing original declarations were not rewritten, including any historical planned-channel answer. The separate manual forwarding confirmation remains required. No automatic forwarding, government approval or PRPWD verification was introduced.

## Verification

47 distinct backend tests passed across disposable native-MySQL runs, covering PDAO review, existing PDAO intake/forwarding, source forms, number validation and short references. The combined regression run `santolan-g12-tests-2tqglzsn` passed 46/47; its remaining applicant-receipt test incorrectly reused the applicant session for Admin login, which rotated that session. After separating the clients, all seven review tests passed in `santolan-g12-tests-mnf6c2ue`.

Earlier testing exposed a MySQL JSON-expression search incompatibility; name extraction now occurs on each JSON column before coalescing the current name. The original intake migration rehearsal was also updated to temporarily remove and restore the new dependent revision table on the disposable instance. The corrected regressions and explicit new migration rehearsal passed. No blanket historical migrations or tests against application data were run.

Coverage includes automatic channel and tamper rejection; editable prefilled fields; correct printed/current-name search results; original payload, acknowledgement and reference preservation; session-bound original receipts and idempotent submission retries after corrections; permission denial/revocation; invalid/duplicate fields; stale edits; concurrent corrections; resetting Ready after changes; locking forwarded forms; immutable history; transactional audit rollback; and absence of Member creation. The new migration rehearsal verifies existing submission rows and event history remain unchanged.

Chrome passed in `santolan-g12-tests-1q4pz3gn`. It submitted both membership forms, approved Association membership, verified short/original searches, edited PDAO name and phone as Admin, reopened the saved review, confirmed corrected details in printing, saved a PDF and recorded forwarding. Backend assertions verified the original name and online channel remain intact. Desktop/mobile overflow checks passed. Screenshots/PDF are in `.local/pdao-review-20261026/browser/`; the PDAO editor screenshot was visually inspected.

Django database checks, migration drift, browser harness syntax and Git whitespace checks passed. Live HTTP verification confirms the public PDAO form omits the channel question and includes online/onsite guidance; anonymous review access still redirects to login.

## Local installation

Only `membership.0010_pdao_review_corrections` was applied. It adds the revision table, correction permission and event action choice without rewriting existing submissions. Reviewed migration SHA-256: `c9e19fde24bb3776d28c7470ed42d8195b424290e2e0e93834f1e52a83990464`.

The helper verified database identity, exact pending migration plan/checksum and stopped-site state, then backed up SQL, environment and private media. Backup: `.local/backups/pdao-review-20261026-20261026-155213/`. SQL SHA-256: `fa2b778ab41c5a4c24c3120dbf373038eb27e692510e75a1b494ca61d12e7325`.

Fingerprints confirmed all 469 existing rows across 119 tables and the private upload were preserved, including one existing PDAO application and all short references. The new revision table starts empty. No pending migrations remain; environment settings and disabled EWAF flags were preserved. The website was restarted hidden at `http://127.0.0.1:8000/`. No changes were committed or pushed.
