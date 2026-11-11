# Membership review layouts — November 8, 2026

The requested review pages now reuse the existing Member record and onsite registration designs.

- PDAO application review uses the Member record theme, initials/profile panel, received/status cards, overview, keyboard-accessible application tabs and processing sidebar. Editing and retained submission/review history sit below the primary cards; expanding the editor does not stretch the contact and submission cards. All eight application categories remain available, including without JavaScript.
- Association membership review uses the onsite registration stylesheet and shared field component, numbered section cards, section navigation, status, protected documents and print link. Pending review retains every editable field, hidden version/CSRF/acknowledgement/PRPWD control and existing decision button. Approved and declined reviews display saved submission labels and values in the same card layout. The decision bar stays in normal flow on small screens.

No service, view, model, migration, decision rule, forwarding rule or live application data was changed. PDAO remains separate from Association membership. The new layout does not load the onsite submission controller or introduce a new intake action. Existing permission gates, manual PRPWD verification, private document URLs, original submissions, corrections and processing history remain in place.

## Validation

- 41 tests passed across registration decisions, PDAO registration, PDAO browser workflows and the new Association review browser check.
- The Association browser check passed again after the final saved-value display refinement.
- Browser checks cover dark/light themes at 1600, 1024, 768, 390 and 320 pixels, without horizontal page overflow; all eight PDAO keyboard tabs; no-JavaScript content; unstretched PDAO side cards; saved correction and ready/forwarded transitions; forwarded edit lock; complete Association review fields; PRPWD gating and reset after changing the number; permission-protected documents; original history; view-only, approved and declined states; and validation errors.
- Tests ran on fresh disposable native MySQL instances with temporary synthetic uploads. The model-synchronized test baseline does not validate historical migrations.
- An existing PDAO-suite Association approval fixture was updated to supply the already-required PRPWD permission, synthetic registry setting and lookup number. No approval check was weakened. The first run also caught an overly specific browser expectation of seven editable sections; the harness now verifies that every actual editable field and section remains available without JavaScript.
- Django configuration/database check, JavaScript syntax checks and `git diff --check` passed.

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test membership.test_registration_decisions membership.test_pdao_registration.PDAORegistrationTests scripts.pdao_record_browser_qa scripts.association_review_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
.venv\Scripts\python.exe scripts/g12_test_runner.py test scripts.association_review_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
.venv\Scripts\python.exe scripts/current_development.py check
git -c core.safecrlf=false diff --check
```

## Synthetic screenshots

- [PDAO desktop](pdao-dark-desktop.png)
- [PDAO mobile](pdao-light-mobile.png)
- [Association desktop](association-light-desktop.png)
- [Association mobile](association-dark-mobile.png)
- [Association validation](association-validation-mobile.png)
