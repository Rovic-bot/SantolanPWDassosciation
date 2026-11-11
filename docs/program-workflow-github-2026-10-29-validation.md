# Program workflow GitHub snapshot — October 29, 2026

The owner requested pushing the current work to GitHub and authorized updating `fix-UI` or creating `System90%` if needed. The existing `fix-UI` branch was synchronized with `origin/fix-UI` at `8175951` before preparing this snapshot, so no additional branch was needed.

## Included behavior

- The ten owner-requested Association disability labels retain their controlled catalog IDs and map correctly into approved member classifications.
- The active local settings treat PDAO approval as an external process while retaining the existing program publication and application requirements.
- Application review opens while scoring rules are pending, shows the submitted information, and provides Eligible / Needs Information / Ineligible actions with audit, permission, stale-edit, and concurrency safeguards.
- Reported member changes have an optional administrator editor. Marking Eligible does not require changing the member record or falsely resolving the report. Changed/uncertain applicants receive the barangay-office confirmation instruction on their reference/QR receipt.
- The previous light dashboard design is retained. Its template asset version was refreshed after reverting the experimental dark design; the dashboard CSS, JavaScript, and chart markup match the pre-experiment branch contents.

The dated disability mapping, direct review, information update, and receipt validation notes describe the detailed behavior and prior browser checks. The final eligibility-and-change-receipt note supersedes earlier descriptions that required resolving information changes before the direct eligibility action.

## Current verification

The focused combined run used a new native MySQL 8.4.11 instance, isolated `test_g12_disposable` database, and synthetic media. **204 of 205 tests passed** in 80.700 seconds. Temporary artifacts are in `C:/Users/rovic/AppData/Local/Temp/santolan-g12-tests-zhutl2ak`; the disposable database was destroyed after the run.

```text
.venv/Scripts/python.exe scripts/g12_test_runner.py test members.test_disability_mapping members.test_registration_edit membership.test_onsite_registration_alignment programs.test_direct_review programs.test_information_update programs.test_change_receipt programs.test_application_workflow programs.test_checklist_navigation programs.test_inline_document_review programs.test_one_click_publication programs.test_reference_ui programs.test_ui_cleanup programs.test_tracking ewaf.test_intake_policy analytics assistance.tests --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

The remaining failure is `programs.test_application_workflow.ConfirmedApplicationTests.test_admin_can_create_ewaf_draft_and_open_settings_before_publication` at the assertion that the EWAF settings page contains an evidence-policy link. The existing workspace does not display that link. The failing test method was compared with `HEAD` using its Python syntax tree and is unchanged; the EWAF workspace view and templates are also unchanged from `8175951`. This snapshot does not change that navigation or weaken the assertion. The full repository suite was not run.

Django database/configuration checks and migration-drift checks passed; no schema migration is needed. `git diff --check` passed. The restored dashboard was checked with current data through a read-only render and Chrome: original light background, full desktop sidebar, three-column metrics, all ten chart sections, mobile layout, and no JavaScript errors. That verification created no application data.

## Files kept local

`.env`, `.local/`, databases, private uploads, and credentials are excluded from the commit. New browser screenshots included in this snapshot use synthetic fixtures; the disability-choice screenshot contains only the generic field. Unused `Assets/` source images and the reverted dark-dashboard previews remain local. The already tracked application images under `static/images/` remain available.

No deployment, merge to `main`, or live-data migration is part of this push.
