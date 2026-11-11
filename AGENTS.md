# Repository Guidelines

## Current documentation authority

Read `../CURRENT_SYSTEM_SPECIFICATION.md` first (October 10 TARGET master), then `../Guide for Development.md` and relevant domain notes. `../00 - Project Overview/System Master Specification.md` is the master index.

Source priority: `../00 - Project Overview/admin portal.docx` (Admin V2) → `public portal.docx` → `Computation - final.xlsx` for mathematics → existing requirements not superseded → historical background. The owner confirmed these actual paths/names. Extracted sources, formulas/caches and provenance are in `../00 - Project Overview/Workflow References/2026-10-10/Workflow Source Register.md` and linked notes; originals stay unchanged.

Membership-specific amendment: read `../00 - Project Overview/Workflow References/2026-10-10/Confirmed_Membership_and_PDAO_Requirements_2026-10-10.md` and DEC-027. Association onsite membership has five confirmed items (2×2 picture, Birth OR Marriage, Voter's Certificate and physical long envelope alongside its form); separate PDAO guidance uses 1×1/calendar/medical/residency and renewal-only old-ID rules. Keep Association completeness/manual PRPWD distinct, no inferred PDAO-ID prerequisite or forced envelope upload; OQ-27 governs unresolved handling. Approved program identity/selection/EWAF and validated code stay preserved; documentation is not implementation authorization.

TARGET requirements are not CURRENT implementation. Preserve the owner-defined 70% milestone (DEC-024), DEC-025 validated publication/unified-Members/sidebar work and all unfinished Git changes. Read `../05 - Development/October 10 Implementation Impact.md` plus dated `docs/*validation.md` before claiming availability. Seven public sections, eight Admin groups, conditional photo/approved alternatives, dedicated Results and controlled workbook EWAF require later scoped implementation; documentation alone approves no code changes.

Before changing business logic, check `../00 - Project Overview/Open Decisions.md`. Do not silently decide RSVP/public audience, accessible evidence, income/PA direction, unverified-input assessment, thresholds/bounds/ties, future reference policy or disclosure. Gemini is PROPOSED. Preserve onsite/manual PRPWD, no member accounts, secure verification, immutable issued references, private evidence, distinct eligibility/ranking/human selection/actual release, locked versioned rules and protected audits. Never manually edit scores/ranks or restore a public QR/status tracker without a separate decision.

Read the workbook's exact formulas AND stored values: it has broken row-average cells and disconnected literal copies. Do not treat cached values as recalculated output or sample values as approved policy. Preserve validated working controls and old calculation/source/publication history during future authorized changes.

## Project Structure & Module Organization

This application uses Django 5.2, native MySQL, and server-rendered Bootstrap templates. `config/` owns settings and root routing. Domain apps include `membership/`, `members/`, `documents/`, `announcements/`, `events/`, `programs/`, and `assistance/`; `core/` includes public content management. `ewaf/` preserves read-only historical calculations while its revised workflow remains stage 8. `analytics/` and `reports/` remain later-stage shells.

Keep business operations in app-level `services.py`, validation in forms/models, and request handling in `views.py`. Store migrations in each app’s `migrations/`, templates in `templates/<app>/`, and CSS/JavaScript/images in `static/`. Tests live in app-level `tests.py` or `tests/`; browser harnesses live in `scripts/`. Record milestone plans and validation evidence in `docs/`.

## Build, Test, and Development Commands

Run from the repository root in PowerShell:

- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1`: start project MySQL, check configuration/migrations, and serve locally. `Start System.cmd` provides the same workflow.
- `.venv\Scripts\python.exe manage.py check --database default`: validate application/database configuration.
- `.venv\Scripts\python.exe manage.py makemigrations --check --dry-run`: detect model changes lacking migrations.
- `.venv\Scripts\python.exe manage.py migrate`: apply migrations; back up existing data first.
- `.venv\Scripts\python.exe manage.py test --noinput`: run Django tests.
- `.venv\Scripts\python.exe manage.py collectstatic --noinput`: collect deployment assets.

## Coding Style & Naming Conventions

Use four-space Python indentation, `snake_case` functions/variables, and `PascalCase` classes. Follow neighboring files’ conventions. Use named, app-namespaced URLs, such as `programs:manage_detail`. Reuse shared templates and design tokens; preserve accessible labels and keyboard navigation. No repository-wide formatter or linter is configured. Run `git diff --check` before submission.

## Testing Guidelines

Use Django `TestCase` and `TransactionTestCase`; name tests `test_<behavior>`. Cover permissions, validation, privacy, audit rollback, stale edits, and relevant concurrency. No numeric coverage threshold is configured.

Tests require a separate disposable `DB_TEST_NAME`; never target application data. Run focused tests with `.venv\Scripts\python.exe manage.py test programs --noinput`. Current browser checks use Playwright/Chrome: run `manage.py test scripts.revised70_browser_qa --noinput` with the virtual-environment Python and configure `PLAYWRIGHT_MODULE` and `CHROME_EXECUTABLE`. Older milestone harnesses retain historical expectations and are not current workflow acceptance.

## Commit & Pull Request Guidelines

History uses imperative descriptions, such as “Implement membership registration and manual approval workflow.” Keep commits focused. PRs should explain changed behavior, migrations, test results, and limitations. Link relevant issues or milestone notes; include screenshots for UI changes.

## Security & Scope

Never commit `.env`, `.local/`, credentials, or private uploads. Serve documents only through permission-checked attachment views; never expose unrestricted `/media/`. Preserve existing work and business rules. Implement only authorized milestone scope and document workflow decisions.
