# Assistance selection without page navigation — November 8, 2026

The owner requested that selecting an applicant for assistance should neither refresh the page nor automatically scroll it.

The ranking workspace now submits selection, unselection and selection-review forms in the background through the existing CSRF-protected server routes. It replaces the affected ranking and applicant-panel content with the server-rendered result. The page URL and document remain in place; document, applicant-panel and horizontal-table scroll positions are retained. A shorter selected state retains enough panel height to avoid clamping the existing scroll position. Keyboard focus follows the updated action without scrolling, and a live status message reports success or validation errors.

Search/decision filters and pagination remain in effect. Cached applicant panels are refreshed together with the table so switching away and back shows the current selection. While saving, controls prevent duplicate submissions and competing filter/ranking actions. A network failure reports an unconfirmed result without automatically repeating the POST or navigating away. Ordinary forms remain the fallback when JavaScript is unavailable.

Only the workspace JavaScript and its template assets changed. Permissions, eligibility, ranking freshness, capacity, completed-recipient restrictions, decision audits and receipt services are unchanged. No model, migration, scoring formula or live selection/receipt data was changed by this work.

## Verification

Disposable native MySQL and headless Chrome were used for the browser journeys:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test scripts.selection_inline_browser_qa scripts.open_registration_selection_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
node scripts/ewaf_applicant_switch_dom_test.cjs
```

The new browser journey measures document, panel and table offsets before and after selection/unselection at 1440px and 390px. It checks that the same document and URL remain, the updated action retains keyboard focus, each action sends one POST, rapid repeated submission cannot duplicate the write, filters survive, cached applicant switching stays current, stale revisions display validation feedback, failed requests do not replay, and the saved decision survives a later explicit reload. Database assertions verify seven expected selection/unselection revisions, valid audits, unchanged scores/ranking, and no assistance release created. The existing open-registration journey also checks selected state at 1440px, 390px and 320px.

An initial browser failure caught a hidden field named `action` shadowing the form's DOM `action` property. The request URL now reads the actual HTML attribute. Both browser journeys subsequently passed in `santolan-g12-tests-1ku_zko8`. The final run, `santolan-g12-tests-__fr2not`, passed both tests in 32 seconds and additionally verified keyboard focus after disabling/replacing the original submit button. Every measured scroll offset remained unchanged.

The local development server was restarted with its database and uploads preserved. Its versioned JavaScript asset returned HTTP 200 with the new selection and focus handlers. Django/database checks, JavaScript syntax and `git diff --check` passed. The existing synthetic DOM regression passed 100 cached applicant switches with no fetches and retained its stale-response and history checks.

Evidence: [browser results](browser-results.json), [desktop](selected-desktop.png), [mobile](selected-mobile.png). Screenshots use fictional disposable applicants only.
