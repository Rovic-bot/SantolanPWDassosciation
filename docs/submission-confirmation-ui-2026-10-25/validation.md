# Membership submission confirmation UI — 2026-10-25

The owner supplied a screenshot and requested that the public membership submission confirmation follow that layout. The receipt now has a success banner, prominent reference number with Copy number, pending onsite guidance, numbered next steps, a requirements checklist, a visit-information card, Print / Save as PDF, and five expandable sections for the submitted Association form. The layout adapts to narrow screens; native details elements support keyboard access and work without JavaScript.

The page reuses the application's existing Association requirements for the submitted form format. The screenshot's inconsistent checklist wording is not adopted as a new requirement. Original policy instructions remain available in an expandable section. Help Desk contact details link to the existing contact page; no new address, schedule or contact number is invented. Next steps describe the already authorized Admin correction and approve/decline workflow.

## Privacy, data and printing

The receipt still requires its original session-bound access and displays the original submitted revision. It does not query staff decisions or expose review notes, private evidence or later corrections. Assessment-only household fields remain excluded from this public/print projection. Pending onsite wording is submission guidance, not a live public status tracker.

Copy number copies the issued reference without altering it. If clipboard access is unavailable or denied, the page selects the reference and displays manual-copy guidance. View submitted form opens the retained sections and moves keyboard focus to the summary. Printing opens older form sections temporarily and restores their previous state after printing. The separate A4 Association print template, original Word file and print styles remain unchanged.

The existing CSRF-protected Done action remains available below the summary. It closes access to the private form and retains only the reference and barangay instructions. The finished page shares the new confirmation design and copy control; it contains no applicant details or link to reopen the form.

No model, migration, membership decision, application data or approval service was changed. The only view change supplies the matching existing checklist to the receipt template. All other changes are templates, scoped CSS, JavaScript and one existing test assertion updated to the uppercase signature label already present in the preserved print template.

## Verification

**78 focused tests passed** in fresh disposable MySQL with `.env` disabled and isolated synthetic media:

```powershell
.venv/Scripts/python.exe -B .local/dual-registration-20261024/run_tests.py test membership.test_registration_finish membership.test_pdf_registration membership.test_registration_intake membership.test_registration_prefill --testrunner scripts.registration_handoff_test_runner.RegistrationHandoffTestRunner --noinput --verbosity 1
```

The initial 70-test run found the old title-case on-screen signature assertion. The final test checks the existing uppercase signature in the original print template. The final run passed all 78 tests in 4.892 seconds, including receipt ownership, original-revision projection, digital-field exclusion, form prefill and Finish revocation/privacy.

The identified development runtime passed `manage.py check --database default --settings=config.full_registration_settings`. JavaScript syntax and `git diff --check` passed. Synthetic receipt and finished HTML previews were rendered with all database connections prohibited; they verified five expandable sections, unique element IDs, digital assessment-field exclusion and no private form after Finish.

Chrome/Playwright launch was blocked with `spawn EPERM`. No browser screenshot, visual comparison, responsive browser pass or new print-pagination verification is claimed. The prepared synthetic HTML previews and render checks are retained under ignored `.local/submission-confirmation-ui-20261025/`.

## Development runtime

Eleven UI files were synchronized to `.local/dual-registration-20261024/runtime/` after checking each existing file against its recorded baseline. Source backups, before hashes and the synchronized-file manifest are retained under the ignored validation directory. Existing unfinished work was preserved.

The restart script verified the development website on port 8003, but Windows denied stopping its Python process. Run `Restart System.cmd` locally to load the updated Python and cached templates, then refresh the registration confirmation page. No database migration, GitHub push or hosted deployment was performed.
