# Revised 70% implementation changelog — 2026-10-07

Authority and scope: [[Decisions#DEC-024 — Revised 70% implementation and conservative operating policies]]. See [validation](revised70-validation.md) and [[System Development Progress]].

## Major changes

Added public information CMS, verified-document provenance/reuse, explicit program photo/selection policies, atomic canonical references, private calendar-photo evidence/manual queue, Help Desk corrections with retained proof/history, canonical states and current-photo/eligibility/selection gates. Linked organizational events to the member-only Program Application; new attendance requires selected active verified members. Preserved actual receipt/void history and Admin-only access.

Removed four unreachable legacy status/QR/event registration/form templates and unused QR dependency declaration. Retired fixed-criterion EWAF mutation implementation, automatic closed-program applicant publication and editable eligibility-label workflow. Read-only historical analytics/attendance/reference records remain. No records were deleted to increase the milestone percentage.

## Data, UI and documentation

Five additive migrations reuse existing members/applications/eligibility/audit entities and add CMS, document verification, photo/review/revision/counter/provenance concepts. Every original row passed preservation checks. Public guidance, accessible error summaries, TTS controls, shared navigation, new Admin views and actual workflow descriptions were updated. Full-target ERD/DFD and EWAF requirements remain, with explicit implementation boundaries.

Documentation records the first-seven-stages 70% definition, approved conservative policies, current module/backlog status, actual routes/schema, tests, future-stage limits and operational configuration needs. The restored UI guide remains present. Prior assessments/validation remain clearly historical.

## Remaining questions

Real per-program photo/selection instructions, institutional configuration/UAT and the stage 8–10 EWAF/normalization/tie/masking/retention/exception policies remain in [[Open Decisions]]. No other known current stages 1–7 contradiction remains after the recorded review. This is not a guarantee against undiscovered defects or a production acceptance claim.

## Files changed

The exhaustive source/note manifest below compares against the verified pre-implementation backup, preserving unrelated earlier working-tree changes.

Application paths below are relative to `santolan-pwd-system/`; vault-note paths are relative to the vault root. Existing unrelated changes are excluded by comparing file hashes with the task backup. Local private backups, generated artifacts and credentials are excluded.

### Updated application files

- `AGENTS.md`
- `README.md`
- `announcements/models.py`
- `announcements/program_publication.py`
- `assistance/forms.py`
- `assistance/models.py`
- `assistance/services.py`
- `assistance/tests.py`
- `assistance/views.py`
- `config/urls.py`
- `core/context_processors.py`
- `core/tests/test_public_portal.py`
- `core/urls.py`
- `core/views.py`
- `documents/models.py`
- `events/forms.py`
- `events/models.py`
- `events/services.py`
- `events/test_open_attendance.py`
- `events/tests.py`
- `events/views.py`
- `ewaf/services.py`
- `ewaf/tests.py`
- `ewaf/views.py`
- `members/models.py`
- `membership/views.py`
- `programs/forms.py`
- `programs/management/commands/process_closed_programs.py`
- `programs/models.py`
- `programs/services.py`
- `programs/test_workflow_alignment.py`
- `programs/tests.py`
- `programs/urls.py`
- `programs/views.py`
- `requirements.txt`
- `static/js/accessibility.js`
- `templates/admin_portal/dashboard.html`
- `templates/assistance/action.html`
- `templates/assistance/queue.html`
- `templates/assistance/statuses.html`
- `templates/events/attendance_detail.html`
- `templates/events/attendance_list.html`
- `templates/events/manage_detail.html`
- `templates/events/manage_list.html`
- `templates/events/public_detail.html`
- `templates/ewaf/ranking.html`
- `templates/members/detail.html`
- `templates/membership/guidelines.html`
- `templates/partials/accessibility.html`
- `templates/partials/workspace_header.html`
- `templates/programs/application_detail.html`
- `templates/programs/apply.html`
- `templates/programs/fields.html`
- `templates/programs/manage_detail.html`
- `templates/programs/public_detail.html`
- `templates/programs/submitted.html`
- `templates/public/home.html`
- `templates/public/page.html`

### Added application files

- `assistance/migrations/0003_revised_seventy_workflow.py`
- `core/content.py`
- `core/migrations/0001_revised_seventy_workflow.py`
- `core/migrations/__init__.py`
- `core/models.py`
- `core/tests/test_content.py`
- `docs/revised70-changelog.md`
- `docs/revised70-plan.md`
- `docs/revised70-validation.md`
- `documents/migrations/0003_revised_seventy_workflow.py`
- `documents/services.py`
- `documents/urls.py`
- `documents/views.py`
- `events/migrations/0005_revised_seventy_workflow.py`
- `programs/migrations/0003_revised_seventy_workflow.py`
- `programs/photo_views.py`
- `programs/test_revised_workflow.py`
- `programs/testsupport.py`
- `programs/workflow.py`
- `scripts/revised70_browser_qa.cjs`
- `scripts/revised70_browser_qa.py`
- `templates/content/edit.html`
- `templates/content/list.html`
- `templates/documents/review.html`
- `templates/ewaf/unavailable.html`
- `templates/programs/correction.html`
- `templates/programs/photo_queue.html`
- `templates/programs/photo_review.html`

### Removed application files (originals retained in private backup)

- `templates/events/register.html`
- `templates/events/registered.html`
- `templates/ewaf/form.html`
- `templates/programs/status.html`

### Updated vault notes

- `00 - Project Overview/Decisions.md`
- `00 - Project Overview/Open Decisions.md`
- `00 - Project Overview/System Master Specification.md`
- `03 - Database/Database Plan.md`
- `04 - EWAF/EWAF Specification.md`
- `05 - Development/API and Workflow Contracts.md`
- `05 - Development/Development Roadmap.md`
- `05 - Development/Feature Implementation Tracker.md`
- `05 - Development/System Development Progress.md`
- `06 - Testing/Workflow Acceptance Tests.md`
- `11 - Defense/Capstone Manuscript.md`
- `11 - Defense/Formal User Manual.md`
- `AI/AI Agent Dashboard.md`
- `CURRENT_SYSTEM_SPECIFICATION.md`
- `DOCUMENTATION_CHANGELOG.md`
- `ERD and DFD Diagrams.md`
- `Guide for Development.md`
- `Obsidian_Vault_Structure.md`
- `UI_Design_Guide_For_Codex.md`
- `Welcome.md`

## Final documentation audit

The entire project Markdown inventory was rescanned for the requested legacy terms and additional obsolete workflows. Remaining matches describe prohibitions, explicitly future requirements, or clearly marked historical evidence. Internal links and fenced Markdown were checked; see the local `doc-audit.json` evidence. No unresolved current-workflow contradiction was identified; business-policy questions remain in [[Open Decisions]].
