# Unlimited non-EWAF programs and automatic eligibility selection

Historical validation: superseded by the owner's later November 10 reversal in [Mandatory EWAF validation](../mandatory-ewaf-2026-11-10/validation.md). Its non-EWAF behavior and browser/test expectations are no longer current acceptance requirements.

Date: November 10, 2026.

## Scoped owner decision

The owner requested required beneficiary slots for EWAF programs, eligibility-only processing for non-EWAF programs, and no certificate email when publishing non-EWAF results. The owner explicitly resolved the capacity question:

> All non-EWAF programs are unlimited, and every eligible applicant is selected automatically.

This authorizes the non-EWAF selection change below. It supersedes the earlier requirement for a separate human selection decision and a finite slot count only for non-EWAF programs. It does not change EWAF formulas, ranking, approved configuration, or actual-receipt rules. Earlier specifications and validation remain historical evidence; no milestone percentage is changed.

## Implemented behavior

- EWAF programs require a positive beneficiary slot count before publication. Incomplete private drafts may still be saved. Existing EWAF configuration, ranking, selection, and publication checks remain in place.
- Non-EWAF capacity is always unlimited. New non-EWAF programs store no slot limit. The form disables the count when EWAF is off and ignores submitted counts. Old stored counts remain intact for signed terms and history, but cannot cap selection or appear as current available capacity.
- An authorized eligibility review that confirms a non-EWAF applicant as Eligible also records the approved selection, reviewer, timestamp, and policy marker in the same transaction. This works while registration is open and beyond any retained historical count. No ranking is generated.
- Active membership, required evidence, current source versions, and resolved information changes are still required. Needs Information and Ineligible do not select applicants. Stale reviews, missing permissions, failed audits, and repeat submissions cannot partially apply a selection.
- Automatic selection appears in Administration changes as “Member marked eligible and automatically selected,” with a simple explanation and the matching Approvals filter.
- Publishing results remains an explicit action. It does not record actual assistance received. Non-EWAF publication creates no certificate document, email job, or certificate delivery callback. Retry and background delivery also skip retained non-EWAF jobs. Old private documents and delivery attempts remain available to authorized staff.
- EWAF certificate publication and both supported email-provider paths are preserved. Ordinary application decision emails remain separate from selection certificates; their non-EWAF Eligible message explains automatic selection.
- Current program capacity labels, public program guidance, review previews, and portfolio totals distinguish unlimited programs from EWAF programs missing a count. Existing publication payloads and hashes are retained.

## Data and verification boundaries

No schema migration or bulk application-data change is required. A read-only inspection of the retained local database found five non-EWAF programs and 27 non-EWAF applications, all already Completed; no pending legacy Eligible applications required transition. No real application, selection, result publication, or email was created during verification.

Tests use fresh native MySQL instances under the disposable G12 launcher, isolated private media, and mocked/locmem email transport. Browser checks use synthetic staff and applicant records. The local application database is never used as a test database.

## Validation

113 focused tests verified across the completed regression run and corrected native-source assertion:

- Main run: 112 passed; one new test expected generation 1 even though the disposable source bootstrap already creates generation 1. The action correctly advanced it to 2. The test was corrected to assert an increment from the actual starting generation; no production change was required.
- Follow-up run: the corrected registered-source test passed, including native audit history and source-generation validation.
- Scope: non-EWAF creation and publication, unlimited legacy counts, automatic selection beyond old counts, open registration, EWAF eligibility, pending/ineligible outcomes, unresolved information, permissions, stale/repeated reviews, concurrency, rollback, audit labels/filters, capacity pages, explicit result publication, protected delivery history, EWAF certificate delivery through Resend and Gmail, and browser behavior.
- The browser exercised desktop (1440 px) and mobile (390 px), light and dark themes, EWAF toggle/readiness, saving an unlimited draft, Eligible selection, and result publication. No JavaScript errors or viewport overflow were observed. Certificate PDF generation and delivery were not invoked for the non-EWAF program.

Main artifact directory: `C:\Users\rovic\AppData\Local\Temp\santolan-g12-tests-xa5alamm`.
Registered-source follow-up: `C:\Users\rovic\AppData\Local\Temp\santolan-g12-tests-s5v1kwmo`.

The main run used:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test programs.test_non_ewaf_selection programs.test_direct_review programs.test_one_click_publication programs.test_portfolio programs.test_detail_workspace announcements.test_recorded_results announcements.test_certificate_delivery announcements.test_gmail_certificates audit.test_activity scripts.non_ewaf_browser_qa --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput
```

The follow-up used the same launcher and runner with `programs.test_non_ewaf_selection.NonEWAFRegisteredSourceTests`.

Browser evidence: [results](results.json), [desktop dark capacity](capacity-dark-1440.png), [mobile light capacity](capacity-light-390.png), [published non-EWAF results](published-results.png).

- Django `check --database default`: passed.
- `makemigrations --check --dry-run`: no changes detected.
- JavaScript syntax checks and `git diff --check`: passed.
