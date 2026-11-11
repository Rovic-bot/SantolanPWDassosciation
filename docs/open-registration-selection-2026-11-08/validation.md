# Selection while registration is open — November 8, 2026

The owner explicitly requested that the EWAF applicant panel allow **Select for assistance** before the program's registration period ends. This supersedes the preview-only selection restriction recorded in [the November 5 open-registration ranking validation](../open-registration-ranking-2026-11-05-validation.txt).

## Behavior

The approved current-eligible ranking workflow now supports a separate Admin selection while registration is open. The existing current ranking must still pass all integrity, source-freshness, evidence-validity and eligibility checks. Both selection permissions, available slots, exact-tie handling, optimistic concurrency and transactional audit recording remain enforced.

New decisions retain `current-eligible-selection-v1`, whether registration was open at the decision, and the ranking's frozen observation window in their immutable review data. Existing configurations, rankings, scores, decisions, program dates and policy snapshots are not rewritten. A new applicant or changed scoring information still requires recalculation; earlier selections remain in history and continue to reserve capacity until explicitly changed.

The workspace guidance now explains that eligible applicants can be ranked and selected during registration. After closing, the existing requirement to resolve the complete pool and reach the approved final assessment cutoff remains. Public result publication still waits for registration to close and its separate authorized publication action. Selecting an applicant does not record an assistance release or send a message.

No migration or live business-data change was needed. This work enabled the action; it did not choose either applicant from the owner's screenshot.

Follow-up: [same-day receipt validation](../open-registration-receipts-2026-11-08/validation.md) corrects fulfillment handling when recording consecutive deliveries from an open-registration ranking.

## Verification

Verified **39 tests** using isolated native MySQL, including real Chrome browser interaction:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test ewaf.test_rolling_pool.RollingPoolTests ewaf.test_applicant_panel.ApplicantPanelTests ewaf.test_unselect_assistance.UnselectAssistanceTests ewaf.test_ranking_freshness.RankingFreshnessTests scripts.open_registration_selection_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

The initial run passed 37 tests. Two UI assertions needed correction: the old calculation-guide bookmark now redirects to the existing ranking page, and the selected status label is “Selected for assistance.” Both affected tests passed when rerun after correcting those expectations. No application-code changes were made between those test runs.

Coverage includes selection during open registration through HTTP; repeated-submit idempotency; retained scores, dates and audit provenance; capacity and pending-application exclusion; both required permissions; audit-failure rollback; new-applicant staleness and earlier slot reservations; exact boundary ties; final-cutoff controls after closing; publication still blocked before closing; existing applicant-panel behavior, unselection and ranking freshness.

The browser completed the CSRF-protected selection on fictional applicants, verified the selected state and Unselect button after reload, and checked 1440px, 390px and 320px layouts without page overflow or JavaScript errors. Screenshots were visually inspected. No live applicant was selected.

Read-only rendering against the retained database found the reported two-applicant ranking (run 44), returned HTTP 200 and showed enabled selection controls with `selection_waiting=false`. An SQL guard rejected mutation statements, and run/decision counts remained unchanged. The local server on port 8013 was restarted with its existing database and uploads preserved. Django/database checks, JavaScript syntax and `git diff --check` passed.

Evidence:

- [Enabled selection button](open-selection-before.png)
- [Desktop selected state](open-selection-1440.png)
- [Mobile selected state](open-selection-390.png)
- [320px selected state](open-selection-320.png)
- [Browser results](results.json)
- [Read-only local verification](live-verification.json)

Disposable test artifacts: `santolan-g12-tests-65fu73n3` (39-test run) and `santolan-g12-tests-t5c22tl4` (two corrected UI checks) in the Windows temporary directory.
