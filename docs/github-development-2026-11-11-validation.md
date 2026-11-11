# Development snapshot publication — November 11, 2026

Destination: `Rovic-bot/SantolanPWDassosciation`, branch `development`. The owner requested the current local development source, with all working features included and a usable setup path for another computer.

## Source and privacy boundary

The source checkout is the current `santolan-pwd-system` working tree, based on local branch `dev-local-8013-2026-11-06`, commit `1514d81958fef2dbd0716f684163a1b72edd0db6`, with all subsequent application changes included. The destination was an empty public repository. Publication uses a separate Git checkout with a single source snapshot, preserving the original branch/index and avoiding publication of the older private Git history.

The selected tree contains every current application Python module, migration, template, stylesheet, script, deployable static asset, certificate template, required downloadable form, dependency manifest, test fixture, and developer tool. Deleted source files remain deleted. Source files were compared byte-for-byte with the prepared snapshot before Git's normal line-ending normalization. No application file was omitted by artifact filtering.

Excluded: `.env`, private runtime manifests, database files/backups, private media/uploads, virtual environments, generated static collections, generated browser screenshots/JSON/PDF evidence, unused original `Assets/`, `new pages/` design references, `output/` previews, and untracked academic/reference papers. These exclusions do not remove an active application feature. Required public images remain in `static/`; the actual certificate template is `announcements/certificate_templates/assistance.docx`; both blank membership PDFs remain included.

Selected files were scanned for high-confidence credential/token/private-key patterns and compared in memory against known local configuration secrets. No real credential match was found. The example environment file contains placeholders only; credential values were not printed. No operational database, private member record, or uploaded personal evidence was used for publication verification.

## Fresh-checkout corrections

- `.env.example` now enables the feature capabilities used in development: the EWAF vault and dataset calculation, application workflow, online Association/PDAO intake, tracking, and the Assistance Desk. Gmail is the certificate provider. The operator supplies credentials separately.
- The allowlisted, non-secret current registration workflow is included as `config/registration_policy.development.json`. `ASSOCIATION_REGISTRATION_POLICY_FILE` explicitly selects it; existing registration validation still applies. This preserves onsite/handoff configuration without distributing the private runtime folder or claiming new institutional approval.
- `manage.py` uses ordinary `.env` settings for a new checkout. If the original managed `.local/development` directory exists, its identity-checked settings remain selected and a missing/invalid manifest still fails closed. Explicit settings overrides retain precedence.
- The Start System launcher checks a fresh checkout and runs it at port 8013 without migrating/seeding/resetting data. The managed local launcher remains intact. Fresh-checkout servers run in the foreground and stop with Ctrl+C; administrator shortcuts support both settings paths.
- `docs/FRESH_CHECKOUT.md` covers MySQL, migrations, account creation, current flags/policy, email setup, LibreOffice, annual observances, empty-state configuration, and deployment boundaries.

## Checks performed on the isolated source copy

- Installed all `requirements.txt` dependencies into a new Python 3.14.5 virtual environment. The application did not depend on the original virtual environment.
- Applied the complete migration graph normally to a new, identity-verified temporary MySQL 8.4.11 instance. Django system checks passed; no pending migrations or model/migration drift were detected.
- Verified all current feature switches and the public/staff/onsite/correction registration policy scopes with the fresh-checkout configuration.
- Successfully loaded **10 public routes and 23 authenticated Admin routes** on the new database. This includes empty-state views, the EWAF vault, program/application/event workspaces, registration queues/onsite forms, Assistance Desk, email settings, and reports.
- Generated CSV, Excel and PDF exports; downloaded both blank membership forms; created and published a fictional annual observance. The bundled 12-entry reference catalogue installed once and retained all entries on a repeat invocation.
- Verified every literal `{% static %}` template asset exists, and ran `collectstatic` successfully.
- Converted the included certificate DOCX into PDF using the separately installed LibreOffice executable. No personalized real-member document or real email was sent.
- **49 focused Django regressions passed**: annual-observance creation/editor, program lifecycle, shared email delivery, and representative-receipt notification suites, including their imported claimant receipt tests. These use their established fixture settings and an isolated test runner that blocks external sockets. The fresh-install checks above separately exercise the enabled feature configuration.
- **14 browser processing checks passed** from the publication copy, including immediate pending feedback, duplicate suppression, rejection/interrupted-response recovery, EWAF replacement only after confirmation, receipt email retries, report downloads, reduced motion, mobile layout, and cleanup.
- All **947 selected Python files** parsed and all **85 static JavaScript files** passed syntax checks.
- The publication changes pass the original repository's `git diff --check`. The root snapshot preserves existing Markdown hard-break whitespace and a few earlier trailing blank lines; these were not reformatted as part of a publication request.

The full historical test suite was not rerun as a release gate; its dated notes remain historical evidence. This is source parity plus fresh-install and focused regression verification, not production deployment, full UAT, load testing, security certification, or proof of real Gmail inbox delivery.

## What Git does not transfer

The application capabilities and annual-observance creation/editor are included. Existing members, programs, saved calendar cards, approved weight configurations, CMS edits, staff accounts, mail connections, and uploaded artwork/documents are database/storage content. A new installation must configure its own services and enter data, or use a separately authorized private backup/restore. GitHub publication does not copy those records or deploy the website.
