# Checked membership approval and program participation tables — 2026-10-25

The owner explicitly requested a PRPWD checkmark followed by one-click membership approval; one shared workflow for Prepare program results and Publish assistance recipients; and public program-announcement tables listing applicants and selected members with masked names and complete program application reference numbers.

This instruction changes the earlier final-four-reference and selected-only public display policy for this scoped workflow. It does not authorize disclosure of membership/control numbers, access tokens, contact details, evidence, scores or numerical ranks. It does not authorize new scoring rules or convert a private calculation preview into an official selection.

## Membership applications

The pending application review shows the configured PRPWD link, a manual-verification checkbox, and Approve membership. The PRPWD result selector, verification notes, decision selector and decision notes are removed from the normal interface. Admin still performs the external check; the checkbox records that attestation rather than calling a government API.

Approval requires both existing capabilities, refreshed from the database. The service validates the application version, configured verification link, required retained documents, duplicate member constraints and linked-registration guards. It records verification and approval together, creates the official member with its already assigned control number, and writes automatic notes and both native audit entries. Any failure rolls back both steps and member creation. A competing click cannot create a second member.

The existing source writer now has an explicit combined operation: exactly two version increments and two validated native audits in one atomic source batch when the isolated generation boundary is active. Previous submit/verify/decide operations retain their one-event contracts. No scoring or ranking logic changed. The older service/POST interfaces remain compatible, including error reporting, but their extra fields are absent from the screen. The earlier editable online-reference registration workflow remains unchanged.

## Announcements and results

Admin now has one Prepare and publish program results entry. Both old preparation routes use this workflow. Choosing a program and preparing its private preview requires no typed reason or extra preparation confirmation; the server records the reason. The result review shows the two tables, a publication checkbox and a direct Publish program results button. Existing permissions, CSRF, stale-edit checks, publication history and withdrawal controls remain enforced.

New result previews use immutable schema 2 with:

1. Members who applied: all submitted program applications, masked names and complete public program references.
2. Selected members: only confirmed selections validated by the existing final-results workflow, with the same name masking and full references.

For EWAF programs, the existing operational collector validates the current calculation, evidence, configuration, authority and recorded selection decisions. Private demonstration rankings and provisional calculations cannot populate the selected table. No automatic selection, changed tie rule, manual score editing or actual-release creation was introduced. Selected rows are displayed in masked-name order, not as a numerical public ranking.

Already published normal program announcements display a current applicant roster on their detail pages. Selection appears only once the required calculation/reviews and decisions are complete; otherwise the table explicitly says results are pending. Notices remain publicly visible after registration closes, while draft, archived, cancelled and future-publication programs remain withheld. Home and announcement-list previews retain their small projections and do not receive member rows.

All older result and assistance-receipt revisions remain intact, including their original disclosure format and freshness validation. Prepare and publish a new result revision to replace an older result post with the two-table format. The older actual-receipt collector remains available for retained history; selections are never relabeled as confirmed receipt of assistance. Source changes continue to withhold stale published result snapshots.

## Validation

The final targeted run passed **85 tests in 18.400 seconds**, using disposable native MySQL with `.env` disabled:

```powershell
.venv/Scripts/python.exe -B .local/dual-registration-20261024/run_tests.py test membership.test_quick_approval ewaf.test_membership_writers membership.tests membership.test_registration_handoff announcements.test_participation --testrunner scripts.referral_test_runner.ReferralTestRunner --noinput --verbosity 1
```

These include the new approval/form/permission/CSRF, missing-document rollback, audit rollback, linked-intake, simultaneous approval and native source-batch cases; applicant/selection projections, complete references, colliding masked names, unified preparation routes, revision preservation and current EWAF selection checks; and legacy membership/source-writer regressions.

The preceding broader 150-case run passed 149 cases and exposed the combined approval's nested source-transaction problem. The final run above verifies its repair and adds coverage of the existing source-writer suite. That earlier broad run also covered all announcement, result-publication, public Results, announcement-category and operational EWAF regressions. Earlier obsolete UI assertions were updated only for the requested removed fields/button label and for keeping closed program notices visible. Historical disclosure assertions remain in place for legacy revisions.

The synchronized runtime passed `check --database default` and `makemigrations --check --dry-run` with no issues or changes detected. Python syntax and Git/changed-file whitespace checks passed. Browser automation remains unavailable in this environment; no visual/browser acceptance is claimed.

## Runtime and preservation

Twenty-one source/test/template files were synchronized into the identified port-8003 runtime after every original runtime file matched its recorded baseline. Backups, hashes and logs remain under ignored `.local/membership-announcement-workflow-20261025/`; disposable test logs remain under `.local/dual-registration-20261024/temp/`.

No application records were approved or published during implementation, no real email was sent, and no schema migration or hosted deployment occurred. Other unfinished source changes and old calculations/publications remain preserved.

Windows denied the verified restart script permission to stop the development Python process. Run `Restart System.cmd` locally and refresh the pages to load the synchronized code and cached templates.
