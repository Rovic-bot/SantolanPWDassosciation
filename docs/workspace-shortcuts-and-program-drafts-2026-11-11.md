# Workspace shortcuts and program drafts — November 11, 2026

Owner-authorized changes: double-click shortcuts in six Admin workspaces (seven destinations), event management in a popup, and program unpublication returning to Draft with Archive restricted to drafts.

## Implemented behavior

| Workspace | Double-click destination |
| --- | --- |
| EWAF program | Existing full ranking URL (`#results`); opening never generates a ranking |
| Assistance Releases program | View Releases popup for that program |
| Announcements notice | Review announcement popup |
| Announcements program results | Review and publish popup |
| Applications & Eligibility program | Review applications, when applications exist |
| Community Assistance Desk concern | Existing View ticket destination |
| Events Calendar event | Manage event popup |

`static/js/workspace-shortcuts.js` delegates gestures to the existing links and is registered through `WorkspacePage` so it survives filtering and sidebar navigation. Ordinary action buttons, form controls, modified clicks, and hidden rows are excluded. Existing single-click links and keyboard access remain available. Every destination retains its existing server permissions.

The Events Calendar reuses `program-dialog.js` and the permission-checked event detail view. Event status review stays inside the popup. Submitted event forms retain their CSRF token, current version, and action; the agenda refreshes after a submission. Requests are never automatically retried after a write failure. Edit event and Open full page retain their normal navigation.

Program cards now contain Open program without Unpublish/Archive controls. The opened program shows **Unpublish to draft** for published programs and **Archive program** for drafts. `programs.services.change_publication` enforces the draft-only archive restriction, including direct service calls. Unpublish retains the original publication timestamp, applications, issued references, and audit history, but withdraws public program visibility and stops new applications.

Drafts can undergo permitted detail corrections and be published again through the existing publication checks. This does not remove approved evaluation-rule locks or restrictions protecting existing ranking, selection, release, or external-approval history. Publication still requires valid program details and approved EWAF configuration.

## Validation

- 15 `ProgramLifecycleTests` passed on the disposable G12 MySQL instance using `scripts.email_test_runner.EmailTestRunner`, which blocks external sockets. Coverage includes unpublish/edit/republish with retained applications, draft-only archive enforcement, permission checks, stale versions, CSRF, reason/confirmation requirements, audit rollback, read-only review, and retained locked configuration.
- Lifecycle fixtures were brought up to the current mandatory EWAF rules: positive slots, applicable disability types, and explicitly fictional approved weights. The old empty/non-EWAF fixtures were incompatible with current setup validation; production requirements were not relaxed.
- Chrome/Playwright checks rendered current templates using fictional in-memory objects. Database cursor access was blocked and every browser request was intercepted. All seven destinations opened correctly; double-clicking EWAF's title also worked. Opening these shortcuts caused only GET requests.
- Event popup Enter/Escape, focus restoration, desktop layout (1366 px), and mobile layout (390 px) passed. No JavaScript errors, unexpected network requests, or horizontal viewport overflow were observed.
- Repeated sidebar navigation produced exactly one detail request per double-click. Opening an event after filter replacement also passed. An intercepted, synthetic event form submission forwarded CSRF/version/action and refreshed the agenda without leaving the popup; no event service was invoked by that browser check.
- JavaScript syntax checks and `git diff --check` passed.

Command:

```powershell
.venv\Scripts\python.exe -B scripts/g12_test_runner.py test programs.test_program_lifecycle.ProgramLifecycleTests --testrunner=scripts.email_test_runner.EmailTestRunner --noinput --verbosity 1
```

No actual member, program, event, assistance, or email record was changed during verification. No migration or real email delivery was performed.
