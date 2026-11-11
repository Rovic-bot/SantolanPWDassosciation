# Program cards and membership review lists - 8 November 2026

## Authorized changes

The owner requested image-led public program cards based on the supplied reference, removal of the Association review inbox's Record printed form entry and its page, removal of the submission-channel filter, and a PDAO review list matching the Association review design.

- Public program cards now use the existing uploaded program image across the card, a readability overlay, translucent category and availability labels, a short description, an expandable application period and a full-width olive action. Programs without an image retain a gradient and title initials. No commercial prices, ratings, example programs or new imagery were added to application data.
- Association reviews no longer show the printed-form action or submission-channel filter. Legacy channel query parameters are ignored and removed from status and pagination links, so a hidden old filter cannot exclude applications. The old printed-intake URL rejects GET and POST with 404 before issuing a context or saving data. Walk-in intake, historical printed records and submitted-form print previews remain available.
- PDAO reviews reuse the Association inbox's search panel, status navigation, table, pagination, dark/light themes and responsive layout. Counts reflect the current search. The labels remain Received, Ready to forward and Forwarded to PDAO, with the existing onsite PDAO action and permissions.

## Validation

The protected disposable MySQL runner passed 50 tests covering:

- Association search, status filtering, exact-reference priority, pagination, channel retirement and permission checks.
- Retired printed-intake GET/POST requests without writes; existing onsite fields and validation.
- PDAO status counts, search over reviewed details, immutable originals, print/forward permissions and concurrency safeguards.
- Existing public catalog visibility, filters and readiness behavior.
- Browser checks at 1600, 1024, 768, 390 and 320 pixels, both admin themes, automatic status/search filtering, full-card imagery, no-image fallbacks, long titles, keyboard schedule disclosure, high contrast and working detail links.

Command:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test membership.test_registration_inbox membership.test_onsite_registration_alignment membership.test_review_inbox_refresh membership.test_pdao_review membership.test_pdao_registration programs.test_public_catalog scripts.program_cards_review_lists_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

The full run was `santolan-g12-tests-bcnx68z6`. After visual inspection, the no-image initials were reduced to avoid overlapping long titles. A second browser-only run, `santolan-g12-tests-grl5kxs7`, passed with an explicit non-overlap check. Attached screenshots and checks.json come from this final run and contain synthetic records only. The uploaded fixture image reuses the repository's public pavilion image.

Django configuration check, JavaScript syntax check and git diff --check passed. The retained development database identity was verified and there were no email deliveries in progress before a code-only restart. HTTP checks confirmed the Programs page and final stylesheet on port 8013. No models or migrations changed; no live applications, program decisions, emails or files were created or edited by these tests.

## Evidence

- [Public program cards on desktop](programs-1600.png)
- [Public program cards on mobile](programs-390.png)
- [Association review list](association-dark-1600.png)
- [PDAO review list](pdao-dark-1600.png)
- [PDAO review list on mobile](pdao-light-390.png)
- [Browser checks](checks.json)
