# Reported information changes — October 29, 2026

## Owner-confirmed workflow

The owner reported that the current-information review page required supporting
evidence even when no selectable evidence existed. The owner requested displaying
the applicant's report, allowing the administrator to update their information,
and then allowing eligibility review.

The current-information route now shows the original change/uncertainty report
above an editor prefilled from the current Members record. It uses the existing
member fields, choices, validation and audited update service. **Save reviewed
information** saves edits and the report review atomically, then returns to the
application's Eligible / Needs Information / Ineligible actions. Remarks are
optional. An already-correct record can be explicitly reviewed without inventing
a profile edit. The application page's Edit Profile link follows this workflow
when the applicant reported changed or uncertain information.

The separate required evidence picker, evidence attestation checkbox and locked
scoring-configuration prerequisite have been removed from this information-edit
screen. This is an explicit owner amendment to the previous evidence-resolution
step, not automatic acceptance of public input: the admin chooses and saves the
current values. The original application declaration, original membership intake,
issued reference and previous member history are retained. No actual applicant's
employment, information or eligibility was changed during implementation.

Each review records its actor, time, declaration, current member version/profile,
program terms and linked member-change event where applicable. Later changes make
that review stale. Editing an already-eligible application returns it for another
human eligibility decision. Existing photo/document currency, membership,
classification and required submission checks still apply at eligibility review.
Scores, criterion evidence, configuration, selection and releases are not created
or approved by this editor. Historical evidence-based resolution records retain
their original verification behavior.

## Validation

- Nine new tests in `programs.test_information_update` passed, including editing
  employment/contact then marking Eligible with no document verification or
  scoring prerequisite, confirming an already-current record, stale/duplicate
  submissions, invalid fields, permissions/CSRF, final-state protection, atomic
  member/application audit rollback, later-member-change invalidation, editing
  an Eligible application and simultaneous saves. The race saves one member
  change and one report review.
- 27 existing tests passed from `programs.test_direct_review`,
  `members.test_registration_edit.MemberRegistrationEditTests` and
  `programs.test_application_workflow.ConfirmationEvidenceTests`. The latter's
  UI expectation now checks the editor; its historical evidence-resolution and
  scoring-block tests remain. Together these are 36 distinct passing tests across
  focused runs. The full repository suite was not run.
- All tests used `scripts/g12_test_runner.py` with
  `scripts.registration_intake_test_runner.RegistrationIntakeTestRunner`, a separate
  disposable native MySQL database and synthetic private media. Artifacts:
  `santolan-g12-tests-pl8mseqz` (27 existing passes; new fixture setup subsequently
  corrected), `santolan-g12-tests-d5yks3jv` (initial seven new passes), and
  `santolan-g12-tests-owu2zv6a` (all nine new passes).
- The exact reported application was rendered with its authorized admin using
  a read-only SQL wrapper. The editor returned HTTP 200, displayed the reported
  text and employment field, omitted the evidence picker, and validated the
  existing saved field values. All database writes were blocked for this check.
- Chrome/Playwright checked the synthetic form at widths 320, 390, 768 and 1440:
  reported change visible, fields prefilled/editable, optional remarks, no evidence
  picker, valid submission payload and no overflow/JavaScript errors. Browser
  submissions were intercepted; persistence is covered by the Django tests.
  Harness: `scripts/information_update_browser.cjs`.
- Django database check, migration-drift check and `git diff --check` passed.
  No schema migration was needed. The identified web process on port 8013 was
  refreshed with the existing MySQL database and uploads retained.

Synthetic screenshots and browser results:

- [Reported change and current member editor](information-update-2026-10-29/report-desktop.png)
- [Employment edit on desktop](information-update-2026-10-29/edit-desktop.png)
- [Mobile editor](information-update-2026-10-29/edit-mobile.png)
- [Browser results](information-update-2026-10-29/browser-results.json)
