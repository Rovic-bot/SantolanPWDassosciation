# Public Membership & PWD ID page — 2026-10-25

The owner requested a cleaner, more readable public Membership & Registration for PWD ID page, using the supplied screenshot as visual inspiration. This is a presentation change to the existing dual-registration entry page.

## Changes

The page now has a compact breadcrumb and heading, a pale green onsite guidance banner, and two bordered service cards. Each card has three short steps, its existing online preparation/registration action, its blank PDF download and a requirements anchor. Document checklists appear in separate Association and PDAO columns, followed by a Help Desk contact strip.

Longer process instructions, privacy information, published membership guidance and onsite contact details use native expandable sections. The closed-registration disabled field preview remains available in its own expandable section. The layout stacks at smaller widths, uses visible keyboard focus and labels each checklist checkbox. Checkboxes are personal preparation aids only: they submit nothing, store nothing in the application and do not mark documents verified.

The existing owner-updated checklist in `membership/guidance.py` is retained verbatim, including quantities, alternatives, medical details and renewal-only guidance. The screenshot supplies layout inspiration, not a new document policy. Existing registration gates, reference retrieval, approvals, PDAO print preparation, PDF downloads, protected records and shared admin requirements are unchanged. Published CMS content stays escaped; drafts remain private.

Changed UI files:

- `templates/membership/guidelines.html`
- `templates/membership/guidance_checklist.html`
- `templates/membership/guidance_icon.html`
- `static/css/membership-guidance.css`

No JavaScript, business service, model, migration, private document or registration data was changed.

## Validation

**27 existing focused tests passed** in 1.481 seconds using disposable native MySQL with `.env` disabled:

```powershell
.venv/Scripts/python.exe -B .local/dual-registration-20261024/run_tests.py test membership.test_confirmed_requirements membership.test_registration_entry membership.test_pdf_registration core.tests.test_public_portal --testrunner scripts.registration_handoff_test_runner.RegistrationHandoffTestRunner --noinput --verbosity 1
```

These cover exact requirement lists, privacy and CMS publication boundaries, open/closed registration entry, disabled preview fields, registration printing behavior and public portal navigation. Existing tests were not changed. The synchronized development runtime passed Django's database configuration check, and Git/changed-file whitespace checks passed.

Open and closed page previews were rendered with all database connections prohibited. Both have one main heading, unique IDs, 11 labelled preparation checkboxes, valid in-page anchors and no submitting form. Source/runtime baselines, backups, synthetic previews and rendered-markup checks are retained under ignored `.local/membership-guidance-ui-20261025/`.

The attempted Playwright/Chrome preview failed at process launch with `spawn EPERM`. No visual screenshot comparison, responsive browser measurement or accessibility certification is claimed.

## Runtime

All four UI files were synchronized into `.local/dual-registration-20261024/runtime/` after the existing template matched its recorded baseline. Resulting hashes were verified. Other unfinished work was preserved.

The restart script verified the development website on port 8003, but Windows denied stopping its Python process. Run `Restart System.cmd` locally, then refresh the Membership & PWD ID page to load the updated cached templates. No database migration, GitHub push or hosted deployment was performed for this change.
