# Direct application eligibility review — October 29, 2026

## Owner authorization and behavior

The owner requested removal of the separate Requirements, Association Membership,
Disability Qualification, Photo / Identity Verification and Program Fit / Consent
panels. The requested replacement is the complete submitted information followed
by one-click **Eligible**, **Needs Information** and **Ineligible** decisions.

The application-review page now displays member information, submitted identity
and contact details, the applicant's information confirmation and change report,
the submitted photograph, written answers, acknowledgements, program documents
and member documents on file. Private files retain their permission-checked
preview/download routes. The five separate panels and checklist inputs are absent.

All three decisions accept optional remarks. The service records a default audit
description when remarks are blank, retains the reviewer and timestamp, and
displays the result and reviewer in Application History. Eligible explicitly
attests the administrator's review of the displayed photo and required submission
in one transaction. Needs Information and Ineligible can be recorded before
photo verification and do not create a successful identity review. Ineligible
records the administrator's overall finding without inventing a failed item.

This owner-authorized direct decision supersedes the separate PR finding as a
prerequisite for this page's eligibility action. It does not create a PR assessment,
approve scoring rules, calculate scores, rank, select a beneficiary or release
assistance. Existing scoring and selection controls and historical reviews remain
intact. The legacy endpoints retain their validation and display errors from
previously opened forms without restoring the removed controls.

Eligibility still checks actual required submissions, current reused documents,
active approved membership, applicable disability classifications and unresolved
change reports. Released/final/closed records retain existing return-for-review
controls. Permissions, CSRF, application/member/program versions, source-context
tokens, locking and audit rollback remain enforced. No migration is required.

## Verification

- Focused MySQL run: `programs.test_direct_review`, `assistance.tests`,
  `programs.test_reference_ui`, `programs.test_ui_cleanup`,
  `programs.test_checklist_navigation`, `programs.test_inline_document_review`
  and `ewaf.test_intake_policy` using `scripts/g12_test_runner.py` and
  `scripts.registration_intake_test_runner.RegistrationIntakeTestRunner`.
  **79 of 80 tests passed on that run.** The remaining test used a synthetic
  tomorrow-dated submission but reviewed it today. Its new decision portion was
  corrected to review after submission with an authenticated session at that time;
  the focused rerun **passed**. Thus all 80 distinct selected tests passed across
  these runs. No production time or session rule was changed.
- Ten new direct-review tests cover displayed submissions, each decision with
  blank remarks, no automatic selection/release, required missing evidence,
  missing photo, stale and duplicate actions, permissions, CSRF, closed states,
  full transaction rollback on audit failure and simultaneous clicks. The race
  saves one decision, one eligibility audit and one new successful photo review.
- The pending-scoring regression proves that the page opens and the direct
  Eligible action works with approved intake weights and pending scoring rules.
  Configuration content remains unchanged; no criterion assessment, calculation
  or selection is created, and the scoring configuration remains unavailable.
- Chrome/Playwright checked the synthetic rendered page at widths 320, 390, 768
  and 1440 with no horizontal overflow or JavaScript errors. All three clicks
  submitted the correct action/outcome and refreshed the page content. Browser
  POSTs were intercepted; backend persistence is covered by the Django tests.
  Harness: `scripts/direct_application_review_browser.cjs`.
- The exact reported Saklay application route returned HTTP 200 and displayed
  all three actions and submitted details in an authorized view invocation with
  SQL mutations blocked. No actual member/application decision was made.
- Django database checks, migration-drift checks and `git diff --check` passed.
  The identified development web process on port 8013 was refreshed; the retained
  MySQL service and uploaded files remained in place.

Disposable test artifacts: `santolan-g12-tests-wyw6we0r` (80-test run),
`santolan-g12-tests-wpaz0gb5` (passing pending-scoring regression). Earlier focused
clock/session diagnosis is in `santolan-g12-tests-9ju43j4_` and
`santolan-g12-tests-cua64sej`. All use separate disposable MySQL databases and
synthetic private media. The full repository suite was not run for this change.

Screenshots contain synthetic data only:

- [Submitted information](direct-application-review-2026-10-29/submitted-information-desktop.png)
- [Desktop decision actions](direct-application-review-2026-10-29/decision-desktop.png)
- [Mobile decision actions](direct-application-review-2026-10-29/decision-mobile.png)
- [Browser results](direct-application-review-2026-10-29/browser-results.json)
