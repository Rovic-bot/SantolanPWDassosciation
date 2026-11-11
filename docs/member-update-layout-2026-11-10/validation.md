# Member update layout aligned with onsite registration

November 10, 2026. The owner requested the onsite registration design when updating member records.

## Change

The member editor now uses the same onsite workspace grid: numbered field cards in the main column, a sticky guide/status/help column on desktop, and a single column on smaller screens. Its existing fields still render through the shared onsite section and field templates, with the same controls, spacing, surfaces and theme colors.

A compact identity card identifies the member being updated. Current documents, earlier recorded information and the required update reason use consistent card styling. The sticky action bar contains Cancel and Update member record; its buttons share a row on narrow screens when they fit and can wrap with enlarged text.

The guide describes updates to an existing record. It does not use new-registration status, reference lookup, intake review or PRPWD actions. The existing update POST, field validation, version, CSRF protection, archived-record guard, document replacement, audit/history and save redirect remain in place. The legacy form fallback renders its hidden fields once through its existing partial.

Only the member template, a small scoped stylesheet and one outdated test assertion changed. No form definitions, services, models, migrations or stored member data changed.

## Verification

Twenty distinct focused Django tests passed across the initial run and one targeted rerun, using fresh disposable MySQL databases:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test members.test_registration_edit.MemberRegistrationEditTests membership.test_onsite_registration_alignment --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput
```

The initial run passed 19 tests. Its remaining assertion incorrectly assumed that email has the same required state in current member corrections and new onsite registration. Existing member editing already permits an empty email, while new onsite intake requires it. The test now explicitly preserves this existing difference. That test passed when rerun alone; neither form's validation was changed.

The checks cover fields/prefills, actual corrections, retained originals and classifications, validation, duplicate identifiers, permissions, stale edits, archived records, no-op rejection and audit-failure rollback, plus the existing onsite alignment checks. Both disposable databases were destroyed afterward.

Chrome inspected synthetic, unsaved records rendered through the real templates under a SQL write blocker. Browser POST requests were also blocked. All 24 layout checks passed: 1440, 1280, 1024, 768, 390 and 320px in light, dark and high contrast with both theme preferences. There was no horizontal overflow, clipped input or duplicate ID. The field values, choices, required states and hidden markers matched the pre-change template; input styling matched onsite registration.

Additional checks passed for the sticky guide, independent column heights, retained-information disclosure, file selection/removal feedback, keyboard access to actions, server-error links and retained inputs, archived state, 200% root text, forced colors and the no-JavaScript POST form. No JavaScript errors or write requests occurred. Desktop dark, mobile light and high-contrast screenshots were visually inspected.

The local application was restarted with its database and uploads retained. `git diff --check` passed. Evidence: `backend-initial.log`, `backend-rerun.log`, `results.json` and synthetic screenshots in this directory. No real member record was edited.
