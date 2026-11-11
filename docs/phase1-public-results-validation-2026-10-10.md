# Phase 1 — Public Results, navigation and application receipt

Validated locally on **2026-10-10**. Authority: [CURRENT_SYSTEM_SPECIFICATION](../../CURRENT_SYSTEM_SPECIFICATION.md), DEC-025, DEC-027, [Open Decisions](../../00%20-%20Project%20Overview/Open%20Decisions.md), and [implementation gap analysis](implementation-gap-analysis-2026-10-10.md), G19 / public G01 / G27. The owner-defined **70% development milestone remains unchanged**.

## Implementation status

- **G19 — IMPLEMENTED AND TESTED within this phase:** `/results/` lists current authorized program-result publications, with pagination and a safe empty state. `/results/<publication-uuid>/` renders their existing approved public projection. Older authorized publications remain listed while current; private historical revisions are never archive entries. Broader archive/retention policy remains unresolved.
- **G01, public portion — IMPLEMENTED AND TESTED:** exactly Home, About, Announcements, Events, Programs, Results, Membership, in that order. Results list/detail indicate Results as current. Eight-module Admin regrouping remains unimplemented.
- **G27, receipt guidance — IMPLEMENTED AND TESTED:** retains the existing issued reference and session protection; adds Results and Help Desk links, save/copy/print instructions, conditional authorized-publication guidance and an explicit submission-does-not-guarantee-eligibility-or-selection notice. Copy uses the device's existing copy command; no clipboard library or new tracker was added.

The 28-gap analysis is not fully resolved. EWAF publication/ranking, reports, conditional program-photo alternatives and membership evidence-policy enforcement are not completed by this phase.

## Reused components and behavior

- `AnnouncementQuerySet.published()` remains the shared publication gate for Announcements and Results. Its `results_current()` checks validate revision ownership, current source digest and the regenerated authorized payload. New views do not calculate or select beneficiaries.
- Existing `collect_results()`, `prepare_results()`, `publish_results()`, `ProgramResultRevision`, publication permissions, preview/privacy authorization, immutable history and withdrawal rules remain unchanged.
- Both destinations render the existing `templates/announcements/results_projection.html`. Old announcement URLs retain their existing projection and now link to Results; this is compatible rendering from one publication source, without independent result records.
- Existing shared navigation/context processor, public layout, accessibility controls, pagination and Help Desk route are reused. CMS content/editing/publication was not changed or overwritten.
- `programs.views.submitted`, receipt session binding, reference-generation services, uniqueness/idempotency protections and program application/review/release services remain unchanged.

## Privacy and security

The new views obtain only published, current program-linked result revisions. Draft, withdrawn, archived, deleted, future-dated, stale, wrong-owner and corrupt-payload results are excluded server-side; direct Results and old announcement URLs return 404 for withheld records. Admin login does not make a draft publicly retrievable. EWAF-dependent results remain blocked by the existing engine.

Template context for each result contains only its public publication identifier, publication date and validated `public_payload`; no private ORM record is passed. Output retains initial-based name masks and `****` plus the approved final four reference characters, authorized existing program summary/slots/eligible count/method, and collision warnings. Full names/references, member numbers, birthdates, addresses, contacts, disability/medical information, evidence, financial inputs, scores/ranks, private reasons/digests and audit records are not disclosed. Text is escaped. Masked entries are explicitly not proof of identity.

Results GET/HEAD responses are marked non-cacheable; POST is rejected. No private reference lookup, QR tracker, login/account, notification, government integration or automatic deadline publication was introduced. Full application references remain visible only through the unchanged session-protected private receipt, with `no-store` and `private` cache directives. Status/QR endpoints retain their existing 410 behavior.

## Files changed in this phase

Inventory is relative to the repository; previously dirty/untracked work is not claimed as part of this phase.

New files:

- `announcements/public_results.py` — safe publication queries, public serialization, list/detail views.
- `announcements/test_public_results.py` — 13 focused authorization/privacy/navigation/history tests.
- `programs/test_public_receipt.py` — four focused receipt/privacy/session tests.
- `templates/results/public_list.html` — authorized chronological list, empty state and private clarification guidance.
- `templates/results/public_detail.html` — shared masked projection and compatible announcement link.
- `docs/phase1-public-results-validation-2026-10-10.md` — this report.

Modified existing files:

- `core/context_processors.py` — Results added in the required navigation order.
- `core/urls.py` — Results list/detail named routes.
- `core/tests/test_public_portal.py` — updates the six-section expectation to seven without removing other tests.
- `templates/public/base.html` — Results detail current-page state.
- `templates/announcements/public_detail.html` — official Results link, preserving old URL/projection.
- `templates/programs/submitted.html` — authorized Results and receipt guidance.
- `scripts/public_navigation_browser_qa.cjs` — seven-section acceptance.
- `scripts/announcements_members_browser_qa.cjs` — real publication-to-Results browser acceptance and accessibility checks.
- `scripts/revised70_browser_qa.cjs` — receipt Results/nonselection/copy guidance acceptance.

Vault notes updated:

- [System Development Progress](../../05%20-%20Development/System%20Development%20Progress.md).
- [Development Roadmap](../../05%20-%20Development/Development%20Roadmap.md).

## Commands and actual test outcomes

Run from the repository using the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test announcements.test_results announcements.test_public_results core.tests.test_public_portal membership.test_confirmed_requirements programs.test_public_receipt --noinput --verbosity 1
.\.venv\Scripts\python.exe manage.py test membership members documents core accounts programs announcements assistance --noinput --verbosity 1
.\.venv\Scripts\python.exe manage.py test scripts.public_navigation_browser_qa scripts.announcements_members_browser_qa scripts.revised70_browser_qa scripts.membership_browser_qa --noinput --verbosity 1
$env:NODE_PATH = 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
.\.venv\Scripts\python.exe manage.py test scripts.membership_browser_qa --noinput --verbosity 1
node --check scripts/public_navigation_browser_qa.cjs
node --check scripts/announcements_members_browser_qa.cjs
node --check scripts/revised70_browser_qa.cjs
git diff --check
git diff --stat
git status --short
```

- System check: passed, no issues.
- Final focused run: **49 run, 49 passed, zero failures/skips**.
- Affected-app regression run: **247 run, 247 passed, zero failures/skips**. Includes the focused cases; these counts are not added together as distinct tests.
- First four-workflow browser run: **4 run, 3 passed, 1 failed to start** because the older membership harness could not resolve its installed Playwright module. Navigation, publication/Results and public submission/Admin processing passed.
- Membership browser rerun with command-local `NODE_PATH`: **1 run, 1 passed, zero failures/skips**. All four distinct browser workflows therefore passed across the runs; no environment-dependent test is claimed as passed before rerun.
- Earlier focused run: one new test expected an exact cache-header string and failed despite additional protective Django directives. The assertion was corrected to require `no-store` and `private`; production receipt protections were not changed.
- JavaScript syntax and final whitespace checks: passed.

Tests used Django's isolated disposable MySQL test database and temporary test media with synthetic records. Settings enforce a distinct `test_` database name. No normal development-database migration, cleanup, backfill or content publication was executed.

## Browser and regression evidence

Headless Chrome tested all seven destinations at 320, 390, 768, 1024 and 1440 pixels, current indicators, mobile Escape/focus restoration, existing Home help/FAQ/privacy anchors and no-script information. Results checks exercised the real Admin prepare/privacy-confirm/publish workflow, old announcement compatibility, anonymous masked output, keyboard-focusable result table, Largest text/high contrast, and responsive list/detail layouts. Public submission retained its issued reference through correction, photo review, eligibility, selection and actual release.

The unchanged DEC-027 membership browser workflow passed 35 responsive and seven enlarged-text checks, ordinary authorized staff intake, private download, manual PRPWD review, approval blocked before verification, approval/rejection, duplicate protections and guidance separation. All four workflows reported no captured browser errors. Automated regressions also cover permissions, CMS drafts/publication, private documents, stale/concurrent membership approvals, application safeguards, immutable result revisions and withdrawal/source freshness.

Inspected screenshots: `.local/qa-phase1-public-results/dedicated-results.png`, `dedicated-results-mobile-largest.png`, `results-list-mobile-largest.png`, and `.local/qa-revised70/receipt.png`. Browser artifacts use synthetic disposable-test data; they are not production result records. Automated/browser checks are local evidence, not full accessibility certification or association UAT.

## Preservation and database review

Before editing, Git status/stat/name-only and relevant dirty files were inspected. A verified snapshot of 332 pre-existing nonignored repository files and the two affected vault notes is retained in the vault's `.local/phase1-public-results-20261010/`. Comparison found exactly nine pre-existing repository files modified by this phase, with none missing. All other existing files, including membership guidance/partial, models, migrations, settings, publication/selection services and reference generation, remained byte-identical to the starting working tree. Final Git review distinguishes this phase from earlier uncommitted work; no commit, push, reset or cleanup was performed.

**Schema changes: NONE. New migrations: NONE. Development database changes: NONE.** Only disposable test databases/media were created and removed by test execution. Existing real membership/application/reference/selection/history data were not mutated.

## Remaining decisions and next task

- **OQ-22:** expanded disclosure or a broader historical archive/retention policy needs approval. This phase lists only still-authorized current publications, including older publication dates; it exposes no private revision archive and adds no disclosure fields.
- **OQ-21:** future reference-generation policy remains open. This phase preserves the accepted issued format and existing references.
- **OQ-27:** originals/copies, digital scans versus physical-review recording, civil-document alternative provenance, validity/reverification/resubmission, separately authorized substitutions and any formally established PDAO-ID prerequisite still block full membership checklist enforcement. The five-item list is confirmed; displayed guidance is not evidence receipt/completeness/verification. This phase neither changes enforcement nor invalidates existing members. Separate PDAO scope/current issuing-office confirmation remains as documented.
- EWAF-dependent publication remains unavailable pending its separately authorized mathematics/policy implementation. Admin eight-module navigation and later reporting remain open; no work on them began here.

Next recommended scoped task: **Admin Portal navigation regrouping into eight modules — remaining G01**, preserving existing permissions, routes and validated workflows. Stop after this phase.
