# Program unpublish and archive controls — November 10, 2026

## Delivered

The owner requested a button to unpublish and archive a program. Program cards and the Publication panel in Program Details now expose **Unpublish and archive** for published programs and **Archive program** for drafts or retained cancelled programs. Already archived programs do not show an archive button.

Each button opens the existing status form with the intended action fixed, a plain explanation, a required reason, and explicit confirmation. Cancel returns to the program without changing it. The review, cancellation, and submission stay inside the existing Program Details popup when opened there; ordinary links and forms also work without JavaScript.

This uses the existing publication service: unpublishing archives the program, removes public availability, and stops new applications. Applications, issued references, policy authorization, the original publication timestamp, and history remain retained. Existing publishing permission, version checks, CSRF protection, and atomic audit recording still apply. No schema or business-transition changes were needed. Other unfinished repository changes were preserved.

## Verification

- **30 backend tests passed** across program lifecycle, details, and portfolio tests. Coverage includes read-only review, published and incomplete-draft actions, public withdrawal, preservation of application rows and publication history, reason/confirmation, permissions, stale edits, CSRF, and audit rollback.
- **One browser test passed** covering four light/dark desktop/mobile layouts (1440 and 390 pixels), card actions, popup review/cancel/submission, reason focus, public withdrawal, and draft archiving without JavaScript. No horizontal dialog overflow or browser errors were observed. Screenshots were visually reviewed.
- The first browser run passed the popup/layout checks but timed out waiting for the no-JavaScript checkbox to stabilize. The fallback context now explicitly uses reduced motion and an active foreground page; its full submission passed on rerun. No production-code change was required for that harness issue.
- Application configuration, Python/JavaScript syntax, and `git diff --check` passed.
- Existing published and draft records rendered the new buttons and review forms under a database wrapper that rejects writes. The retained local app was restarted. No live program was published, unpublished, or archived during verification.

Backend and initial browser run:

```powershell
.venv/Scripts/python.exe scripts/g12_test_runner.py test programs.test_program_lifecycle programs.test_detail_workspace programs.test_portfolio scripts.program_archive_browser_qa --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput
```

Final browser run:

```powershell
.venv/Scripts/python.exe scripts/g12_test_runner.py test scripts.program_archive_browser_qa --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput
```

Both runs used fresh disposable native MySQL and temporary media. Backend artifacts: `santolan-g12-tests-cck_utaa`; final browser artifacts: `santolan-g12-tests-rv3mxsx6`.

[Browser results](results.json) · [Dark mobile button](button-dark-390.png) · [Light review](review-light-1440.png) · [Dark mobile review](review-dark-390.png)
