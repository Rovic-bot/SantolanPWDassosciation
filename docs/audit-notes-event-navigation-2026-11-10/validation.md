# Plain audit notes and Home event navigation — November 10, 2026

The owner requested simple descriptions of administrator actions in the recorded notes, a Home event card that opens Events, and removal of the standalone public event detail page.

## Implemented behavior

- Inspect now shows a **What happened** sentence derived from the same recorded action used by the activity list and filters. Examples include membership approval, eligibility, selection, published results, and recorded assistance release. These remain separate outcomes. Program, event, and member edits can name the changed fields without displaying private snapshot values.
- Useful prose from the original note appears under **Additional note**. Hashes, machine payloads, and recognized internal messages are replaced in the presentation by the action description. Native Django change messages remain readable, and report export notes identify the format and record count when recorded. Original audit rows, notes, snapshots, permissions, and historical decisions are unchanged. The summary never reads a current decision to explain an earlier action.
- The entire Home current-event card, including its title and arrow, links to `/events/`. The empty-state card uses the same destination.
- `templates/events/public_detail.html` is removed. Existing published event URLs redirect to the Events list; past events redirect to its past view. The existing `?popup=1` endpoint still serves the event popup after checking publication. Unpublished, archived, future-publication, and missing events remain inaccessible.
- Popup loading failures offer **Try again** within the popup. The simplified audit popup keeps Tab and Shift+Tab inside it even when Close is its only focusable control. Escape and closing restore focus to Inspect.

There are no schema migrations, audit rewrites, event deletions, or changes to eligibility, selection, assistance release, attendance, or registration rules. Annual observance pages and staff event management are outside this change.

## Validation

- All 112 targeted tests passed across the expanded run and focused rerun. The expanded run passed 111 tests; its remaining browser assertion still looked for the original prose in the summary element. After updating it to check the summary and additional note separately, the final browser rerun passed.
- Backend checks cover plain descriptions, escaped administrator notes, digest and private-snapshot suppression, no audit writes, historical selection after a later decision, matching filters, permissions, event publication boundaries, old-link redirects, and retired registration/privacy controls.
- Event browser checks passed at 1440, 390, and 320 pixels in both themes. Home title clicks and keyboard activation open Events, event details stay in the popup, loading retries work, and old links redirect. No-JavaScript navigation reaches Events. No page overflow, browser errors, or mutating requests were recorded.
- The audit browser check passed at 1440, 768, 390, and 320 pixels in both themes, including popup focus containment/restoration, filtering, pagination, search, retry, and the no-JavaScript fallback. Desktop light and 320-pixel dark screenshots were visually inspected. No browser errors or mutating requests were recorded.
- Older assertions in the tested modules were aligned with existing Home guidance cards, the shared close-only dialog form, permission-checked historical registrations, and the event's actual participation wording. No corresponding workflow implementation was changed.
- The running development app returned `/events/` for the Home card, HTTP 302 from an old event detail link to `/events/#scheduled-events`, and a valid event popup fragment. Read-only renders of existing program and native administration audits returned HTTP 200 and issued zero database writes.
- Application/database configuration, JavaScript syntax, and `git diff --check` passed. The local development server was refreshed with the completed changes.

Expanded command:

```powershell
.venv/Scripts/python.exe scripts/g12_test_runner.py test audit events.tests events.test_public_popup events.test_participation events.test_simple_publication events.test_optional_event_details events.test_open_attendance core.tests.test_home_featured_event core.tests.test_public_portal scripts.admin_activity_browser_qa scripts.public_event_navigation_qa --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput
```

Final browser rerun:

```powershell
.venv/Scripts/python.exe scripts/g12_test_runner.py test scripts.admin_activity_browser_qa --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput
```

Tests use fresh disposable native MySQL databases and temporary media, synchronized from models without historical migrations. Expanded-run artifacts are under `santolan-g12-tests-pfe96x7y`; the final browser run uses `santolan-g12-tests-qq6vshpk`. Retained application data is not a test target. Saved screenshots contain fictional records only.
