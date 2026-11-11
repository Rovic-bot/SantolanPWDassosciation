# Public registration UI alignment — 2026-10-24

Scope: match the applicant form's UI to Admin Onsite Member Registration. Online activation, field contracts, institutional policies, membership handoff and other phases are unchanged. Accepted milestone remains 70%.

The public preview and full submission form now reuse `member-profile.css`: bordered profile sections, two-column desktop fields, one-column mobile fields, a two-column disability checklist, full-width disability information, and the middle-name checkbox alongside its field. The public editor matches the Admin 58rem maximum width and padding. Onsite guidance sits below the preview so it no longer squeezes the application into a narrow sidebar layout. Active submission reuses the existing `member-profile.js` for no-middle-name and custom-suffix controls; disabled preview fields remain disabled. Staff-only control numbers, verification and approval controls are not added to the public form.

Files changed in this UI task:

- `templates/membership/guidelines.html`: wider form placement, shared profile stylesheet and renderer, guidance below the form.
- `templates/membership/registration/apply.html`: shared profile CSS/JS and Admin-sized editor panel.
- `templates/membership/registration/profile_sections.html` (new): grouped public applicant layout using the existing profile classes and accessible field labels.
- `templates/membership/registration/fields.html`: explicit public-layout option; existing Admin rendering retained.
- `static/css/registration.css`: scoped public editor dimensions and fieldset sizing.
- `scripts/registration_prefill_browser.cjs`: compare public/Admin geometry, check conditional fields, retain full synthetic submission/retrieval checks and save new evidence separately from earlier reports.
- This report, evidence files and the existing progress record.

Validation:

`tests.log`: 17 tests passed in 15.337s using fresh verified disposable MySQL, synthetic data and separate private media. Command:

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test membership.test_registration_entry core.tests.test_public_portal membership.test_registration_prefill scripts.registration_prefill_browser --testrunner scripts.remaining_phases_test_runner.RemainingPhasesTestRunner --noinput --verbosity 2
```

The browser compared actual computed public/Admin geometry: 928px maximum width, 24px panel padding, 9.6px section corner radius, 20px/28px grid gaps and two desktop columns. The complete synthetic flow still submitted once, issued a reference, showed it in the inbox and loaded the same retained application through staff retrieval. Private-access denial and Finish revocation checks passed. See `ui/checks.json` and the public/Admin screenshots. Existing evidence in prior dated directories was not overwritten.

Read-only live public preview checks passed at 320/390/768/1440px (one/two columns as appropriate), with no horizontal overflow, browser errors or enabled preview fields. A 200% narrow-screen reflow check also passed. The local web server was refreshed through its unchanged startup guard. No real application was submitted. Full screen-reader/contrast/UAT testing was not performed or claimed.

All 267 protected files and original/integrated Section 8 are unchanged. The original onsite template, profile stylesheet and script retain their starting hashes (`preservation.json`). No EWAF behavior suite rerun is claimed for this UI-only task. No backend services, models, migrations, working records, configuration, permissions or credentials changed. No commit, push or deployment.

Public submission remains disabled by the existing operating-policy gate. This task changes presentation, not authorization or registration readiness. Final isolated browser rerun after reusing the existing conditional-field script: **1 test passed in 11.502s** (`browser-final.log`), including custom-suffix visibility/requiredness, no-middle-name behavior and the full pending submission/reference/retrieval journey. This overlaps the earlier 17-test suite; it is not a new distinct test count. The live preview was refreshed and its four-width/200% checks repeated successfully after the final adjustment.
