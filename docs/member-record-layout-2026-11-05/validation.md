# Member record layout — November 5, 2026

The owner requested the attached MedLink dashboard layout for full member records in Member Directory. The record now uses a three-column arrangement with rounded cards, a portrait panel, two small membership statistics, compact document tiles, activity rows, and an administrative timeline. The light theme uses the reference's warm off-white surfaces; dark mode uses the existing workspace palette.

## Scope

- Applies to Member Directory → Open full record and `/members/<id>/`.
- Left: existing photograph or initials, member name/reference, membership date/status, contact information, and association links.
- Center: existing profile facts, protected document links, program applications, assistance history, event activity, and the complete registration profile.
- Right: the existing permission-controlled status form and record history.
- Section shortcuts reveal the full profile and scroll within the popup body. The popup header and X remain visible. Native full-page links remain available.
- Narrow layouts stack the cards. The portrait explicitly stays within its column at 320 pixels.

The photograph is selected only from already-authorized JPEG/PNG membership photo documents, including retained legacy photo records. Its URL uses the existing permission-checked document view. Missing photographs use initials. No personal data is copied to browser storage or third-party services.

Existing status updates, reasons, optimistic version checks, CSRF tokens, protected documents, history pagination, and permission gates remain in place. No model, migration, eligibility, scoring, ranking, selection, publication, or release rules changed. No live status or profile was modified during verification.

## Files

- `members/views.py`: read-only record summary and authorized portrait context.
- `templates/members/detail.html` and `templates/members/record/`: card layout and extracted existing activity, status, and history sections.
- `templates/members/directory/base.html`: loads the shared record stylesheet and section-navigation script for popup use.
- `static/css/member-record.css` and `static/js/member-record.js`: scoped appearance, responsive layout, and section navigation.
- `members/test_record_layout.py`: verifies that portrait, history, manual verification, and administrative actions retain their permission boundaries.

The previous versions of the three edited existing files were saved under `.local/member-record-layout-20261105/before/`. Other unfinished changes were preserved.

## Validation

- **32 tests passed** across `members.tests`, `members.test_directory`, `members.test_registration_edit`, and `members.test_record_layout`.
- Tests used a fresh isolated MySQL instance and temporary synthetic media through `RegistrationIntakeTestRunner`. Its model-synchronized schema does not validate historical migrations. The first run omitted that runner; eight tests were rejected by the disposable-environment guard. The corrected command below passed all tests.
- Django application/database check: zero issues.
- JavaScript syntax and `git diff --check`: passed. Git emitted existing line-ending normalization warnings only.
- Templates compiled and production static assets collected. The local development web process was refreshed; its retained data and uploads remain unchanged.
- Native Brave checks: full-page and popup layouts in light/dark desktop views; 1440-pixel light popup; stacked layout at 390 pixels; final portrait fit and overview/document/activity wrapping at 320 pixels.
- Verified Profile reveals the detailed registration fields within the popup, Overview scrolls within the popup body, X closes it, keyboard focus returns to the opener, Enter reopens it, and Escape closes it. The standalone full record renders the same cards. Dark mode was restored after comparison.
- Screenshots use the existing fictional Ana Testalpha record. The available fixture has no portrait, so browser evidence shows the initials fallback; the protected portrait path is covered by the permission test.

```powershell
.venv\Scripts\python.exe -B scripts/g12_test_runner.py test members.tests members.test_directory members.test_registration_edit members.test_record_layout --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
node --check static/js/member-record.js
git diff --check
```

## Visual evidence

- [Desktop light popup](record-light-desktop.png)
- [320-pixel overview with visible close control](record-light-320-overview.png)

The desktop capture shows the top-of-record appearance; subsequent refinements only constrain the narrow portrait width and keep section navigation inside the popup body.
