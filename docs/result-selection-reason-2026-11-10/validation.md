# Program result selection explanation — November 10, 2026

The owner requested a required explanation of why the members were selected before publishing program results, and a compact popup with Submitted applications and Recorded selections beside each other.

## Implemented behavior

- The popup includes a required, labelled selection explanation (up to 2,000 characters), example text, a character count, and guidance that the explanation is public. The Publish results button stays disabled for blank or whitespace-only input. Native form validation, server form validation, and publication services enforce the requirement independently.
- The explanation is saved in the immutable public result revision, bound to the source digest using a versioned envelope. It appears with the public result details and in the administrative revision history. Private audit reasons remain separate. Text is escaped when rendered.
- Stale submissions refresh the roster and token, preserve the entered explanation, and require another explicit publish action. Existing reasonless historical publications retain their original data and digest rules. Publishing a new revision requires a reason, including direct and legacy generation service paths.
- The two tables use independent-height columns within a maximum 1,060-pixel dialog. Below 850 pixels they stack. References wrap without horizontal clipping, and the body scrolls while the action footer remains visible. Existing applicant search and selected-only filtering remain available.
- The light, dark, and high-contrast palettes reuse existing theme tokens. Keyboard navigation, error focus, Escape, and the no-JavaScript form remain functional.

No schema or migration changes. No changes to eligibility, EWAF scoring/ranking, selection decisions, slot rules, releases, or certificate-delivery policy. No live result publication or emails were performed during validation.

## Validation

Commands used the disposable MySQL runner with model-synchronized test tables, separate database grants, disabled application `.env`, and local-memory email. Certificate queuing was mocked for synthetic publication tests.

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test announcements.test_selection_reason announcements.test_composer scripts.result_reason_fixtures.ResultReasonFixtures --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput
.venv\Scripts\python.exe scripts/g12_test_runner.py test scripts.result_reason_fixtures.ResultReasonFixtures --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput
node scripts/result_reason_browser.cjs
.venv\Scripts\python.exe scripts/current_development.py check
git -c core.safecrlf=false diff --check
```

The 17 selection-reason and composer tests passed. The real EWAF fixture initially attempted two selections in a one-slot synthetic program; it was corrected to one selected member, then passed separately. Final evidence covers missing/blank/overlong input, service bypass attempts, permissions and CSRF, public masking and escaping, stale/replayed submissions, immutable revisions, legacy compatibility, digest tampering, audit rollback, and unchanged real EWAF decisions/calculations/releases.

Disposable run logs: `santolan-g12-tests-kd4cym63` (17 passing focused tests plus the initial fixture capacity failure), and `santolan-g12-tests-ix8y9xcw` (corrected real selection fixture, passing).

An initial broader test discovery also included imported historical RollingPoolTests. Those retain obsolete Student-to-Unemployed scoring and exact-tie expectations from before the owner's employment-score change. The fixture now imports the module rather than exposing that TestCase to discovery. Those historical expectations were not changed as part of this request. A legacy publication fixture also needed its required publication timestamp; that fixture was corrected and passed in the focused run above.

Browser checks passed at 1,440, 1,000, 768, 390, and 320 pixels in light, dark, high-contrast light, and high-contrast dark modes: 20 responsive/contrast checks, zero script errors, zero low-contrast text findings, and no horizontal clipping. Actual form association/FormData, whitespace gating, error recovery, stale reason retention, successful refresh, search, selected-only filtering, keyboard dismissal, public display, and the no-JavaScript fallback were checked. All three browser POSTs were intercepted synthetic responses; only local static GETs reached the running application.

Screenshots and `checks.json` in this directory contain fictional fixtures only. The main development server was restarted at port 8013 without applying migrations or modifying application records.
