# Announcements and Members navigation validation — 2026-10-07

Authority: [[Decisions#DEC-025 — Authorized program announcements and unified Members navigation]], [[CURRENT_SYSTEM_SPECIFICATION]] and the owner's explicit follow-up. This completes the announcement extension for currently supported non-EWAF official decisions, unified Members navigation and sidebar scroll preservation. It extends the accepted seven-stage 70% baseline; no new aggregate percentage is asserted.

## Observed validation

**272 tests passed in 106.321 seconds**, including existing domain/concurrency/security regressions, new announcement lifecycle/privacy/expiry/RBAC/CSRF/audit-rollback tests, concurrent draft/publication attempts, the prior public/Admin application browser workflow and the new publication/navigation browser workflow.

Command: `.\.venv\Scripts\python.exe manage.py test accounts announcements assistance core documents events ewaf members membership programs scripts.revised70_browser_qa scripts.announcements_members_browser_qa --noinput`.

Chrome checked 320, 390, 768, 1024 and 1440 px, with zero JavaScript errors and no page-level horizontal overflow. New browser assertions cover the one Members sidebar entry, onsite registration/review access, retained desktop scroll across custom/native Admin screens, restored mobile-menu position, private masked draft preview and authorized public result visibility. Screenshots of public mobile results and Admin preview were inspected. Synthetic identities/photos and disposable MySQL/media were used; no real program result was published.

Two additive migrations applied locally: `announcements.0003_authorized_program_results` and `0004_preserve_result_source_content`. A native SQL backup and before/after original-column fingerprints confirmed **all 408 original rows across 53 existing tables were preserved**; added schema/permissions/migration records are additive. Django database checks and migration-drift checks passed. Private artifacts are under vault `.local/announcements-20261007/`; screenshots are under application `.local/qa-announcements-members/`. The first sandboxed test attempt could not access temporary uploads; the authoritative passing run used normal temporary-file access. An additional expiry test fixture was corrected before the final passing suite.

## Behavior and operator steps

1. Complete every program application review and official decision after the application period closes. Current verified membership, manual photo, required evidence, eligibility and slot constraints are checked again.
2. Open **Announcements → Prepare program results**, select the program, supply a private reason and confirm preparation. A new private revision is created from authoritative source records; posted names/references/scores cannot override generated rows.
3. Review the exact public projection: program description/date, slots, eligible count, selection method/explanation and selected participants only. Each name token uses an initial plus a fixed `***`; references show only the last four characters. Duplicate display pairs retain their masks with a Help Desk notice. The complete page directs all ambiguous cases to private Help Desk confirmation. Public order is alphabetical by masked display, not score/rank. No personal scores or private eligibility values are displayed.
4. Choose **Publish on the public website**, confirm privacy review including small-group/context risks, then apply the change. Preparation and publication have separate RBAC checks, optimistic versions, program/member transaction locks and atomic audit records. Closing applications does nothing automatically.
5. Withdraw/archive using existing announcement controls. Preparing a later revision withdraws the previous public version until reauthorized. Previous projections, content and publication events remain available as protected history. Corrected/stale/expired source evidence causes public lists/home/detail to withhold the projection; neither a saved draft nor an old approval bypasses current checks. Recording actual receipt retains a valid Selected announcement; voiding it returns processing to review and withholds the stale result.

Program results reuse Announcement/Program and AssistanceCase; `ProgramResultRevision` adds unique per-announcement versions, public projection, private previous-content/source provenance, reason and creator/time. Old applicant rows remain private and old program images cannot be served through public result routes. Public detail receives only the safe projection. Public source validation presently rechecks candidate result announcements and evidence at read time; scale/load tuning remains part of release-readiness testing.

**Members** is now the single sidebar entry for official records, onsite registration and membership reviews, with shared internal links. Existing permissions and manual onsite verification/approval rules are retained. Menu state stores only its offset in browser session storage, scoped by tab/account and desktop/mobile layout. No member data is stored, no content focus is forced, and navigation works without storage.

## Remaining dependencies

- EWAF programs remain blocked from selection/publication until the controlled stage-eight calculation/versioning/recalculation workflow is accepted. This extension does not reactivate legacy fixed-factor calculations or invent an EWAF result.
- Waitlist selection policy, reports/exports, analytics, full institutional/privacy/assistive-technology UAT and production/recovery acceptance remain future scope. Ordinary general announcements remain available.
- Institutional program content/methods/photo instructions and per-publication privacy review remain Admin responsibilities. No new SMS/email/account feature or deployment was introduced.

## Changed files

The inventory below compares against the verified pre-task source/note backup and excludes unrelated earlier changes, credentials, dependencies and generated artifacts.

### Updated

- `00 - Project Overview/Decisions.md`
- `00 - Project Overview/Open Decisions.md`
- `03 - Database/Database Plan.md`
- `05 - Development/API and Workflow Contracts.md`
- `05 - Development/Development Roadmap.md`
- `05 - Development/Feature Implementation Tracker.md`
- `05 - Development/System Development Progress.md`
- `06 - Testing/Workflow Acceptance Tests.md`
- `11 - Defense/Formal User Manual.md`
- `CURRENT_SYSTEM_SPECIFICATION.md`
- `DOCUMENTATION_CHANGELOG.md`
- `ERD and DFD Diagrams.md`
- `Guide for Development.md`
- `UI_Design_Guide_For_Codex.md`
- `santolan-pwd-system/AGENTS.md`
- `santolan-pwd-system/README.md`
- `santolan-pwd-system/announcements/forms.py`
- `santolan-pwd-system/announcements/masking.py`
- `santolan-pwd-system/announcements/models.py`
- `santolan-pwd-system/announcements/program_publication.py`
- `santolan-pwd-system/announcements/services.py`
- `santolan-pwd-system/announcements/urls.py`
- `santolan-pwd-system/announcements/views.py`
- `santolan-pwd-system/static/js/site.js`
- `santolan-pwd-system/templates/announcements/manage_detail.html`
- `santolan-pwd-system/templates/announcements/manage_list.html`
- `santolan-pwd-system/templates/announcements/public_detail.html`
- `santolan-pwd-system/templates/members/detail.html`
- `santolan-pwd-system/templates/members/edit.html`
- `santolan-pwd-system/templates/members/list.html`
- `santolan-pwd-system/templates/membership/detail.html`
- `santolan-pwd-system/templates/membership/encode.html`
- `santolan-pwd-system/templates/membership/list.html`
- `santolan-pwd-system/templates/partials/workspace_header.html`
- `santolan-pwd-system/templates/programs/manage_detail.html`

### Added

- `santolan-pwd-system/announcements/migrations/0003_authorized_program_results.py`
- `santolan-pwd-system/announcements/migrations/0004_preserve_result_source_content.py`
- `santolan-pwd-system/announcements/results.py`
- `santolan-pwd-system/announcements/test_results.py`
- `santolan-pwd-system/docs/announcements-members-plan.md`
- `santolan-pwd-system/docs/announcements-members-validation.md`
- `santolan-pwd-system/scripts/announcements_members_browser_qa.cjs`
- `santolan-pwd-system/scripts/announcements_members_browser_qa.py`
- `santolan-pwd-system/templates/announcements/result_draft.html`
- `santolan-pwd-system/templates/announcements/results_projection.html`
- `santolan-pwd-system/templates/partials/member_navigation.html`

### Removed

None.

Final vault audit: 51 project Markdown notes, 846 local/wiki links checked, no broken links or unbalanced fences.
