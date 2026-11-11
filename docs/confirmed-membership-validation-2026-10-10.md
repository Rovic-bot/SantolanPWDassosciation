# Confirmed membership guidance — implementation and validation

Date: 2026-10-10. Authority: DEC-027 and the owner's subsequent scoped Django implementation instruction. The owner-defined **70% baseline and DEC-025 extension remain unchanged**.

## Implemented and tested

- Public Membership displays exactly five Association requirements, in order: Membership Application Form; one (1) 2×2 ID Picture; Birth Certificate OR Marriage Certificate; Voter's Certificate; one (1) Long Envelope. Civil documents are alternatives; the envelope is a physical onsite item, not a required digital upload.
- The five-step procedure requires an in-person Association Help Desk visit, authorized review/applicable verification and administrative approval. No public form, member account, government ID application or automated approval is introduaced.
- Separate owner-supplied Pasig City PDAO guidance lists six items, including its 1×1 picture, whole-body updated-calendar proof of life, four Medical Certificate details and its civil/residency alternatives. Old-ID surrender is renewal only. The notice asks visitors to confirm the latest requirements directly with PDAO; no independently verified government-policy claim is made.
- Admin onsite intake and membership review show the same five-item guidance. Existing uploaded evidence, submission-time requirement snapshots, manual PRPWD outcomes and membership decisions remain separate. The membership CMS editor displays that same guidance while editing additional instructions through existing draft/publication/history controls.
- Published membership and Help Desk CMS snapshots are reused and escaped. Drafts stay private. The central guidance module and shared partial avoid independent public/Admin checklists. Arbitrary private-upload configuration is no longer published as the authoritative Association list; existing configurable uploads, validation and approval gates remain intact.

## Partial implementation and policy boundaries

This delivers **presentation and compatible integration**, not complete five-item backend enforcement. `MembershipDocumentRequirement` represents one document type and a required/optional file upload; it has no approved physical-receipt or accepted-civil-alternative provenance fields. Its existing upload configuration is retained unchanged rather than reinterpreted or automatically seeded. Guidance alone neither records receipt/verification nor establishes completeness. Existing profile fields, PWD control-number validation, successful manual PRPWD prerequisite and required-upload checks are unchanged; their presence does not establish a new institutional PDAO-ID prerequisite.

OQ-27 still governs originals/copies, necessary scans versus physical review, validity/reverification, missing/correctable-document procedures, any separately authorized voter-certificate substitution and any explicit PDAO-ID prerequisite. The owner authorized informational renewal guidance in this task; government renewal processing remains outside scope and issuing-office currency remains unverified. Before implementing receipt/alternative enforcement, approve the handling policy and assess a versioned additive representation that preserves old evidence and decisions. No migration was needed or created for guidance.

A read-only query of the development database found **no saved membership CMS row and no active configured upload requirements**. It queried published membership metadata and requirement configuration only, not personal member records. No approved content/configuration was written, seeded, replaced or published. If administrators later publish membership instructions, review them against the shared confirmed list through the existing CMS authorization workflow.

## Tests executed

Commands ran from the repository using its existing virtual environment:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test membership.test_confirmed_requirements --noinput --verbosity 1
.\.venv\Scripts\python.exe manage.py test membership members documents core.tests accounts programs.test_workflow_alignment programs.test_revised_workflow announcements.test_results --noinput --verbosity 1
$env:PLAYWRIGHT_MODULE = 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'
$env:CHROME_EXECUTABLE = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
.\.venv\Scripts\python.exe manage.py test scripts.membership_browser_qa --noinput --verbosity 1
node --check scripts/membership_browser_qa.cjs
git diff --check -- membership/views.py membership/tests.py core/content.py templates/membership/guidelines.html templates/membership/encode.html templates/membership/detail.html templates/content/edit.html programs/test_workflow_alignment.py scripts/membership_browser_qa.cjs
```

- System check: **no issues**.
- Focused guidance/preservation tests: **8 passed**.
- Regression suite: **141 passed**, including those same eight; counts are not additive.
- Chrome integration: **1 passed**, using ordinary authorized staff, two synthetic applications, one approved Member and no additional user account. **35 responsive checks** at 320/390/768/1024/1440 pixels and **seven Largest-text checks** passed; no overflow, duplicate IDs or page/console/resource errors. Keyboard display-panel focus/return and high contrast were checked; reading controls were exercised where the browser supports speech synthesis. Public desktop/enlarged-mobile and enlarged-mobile intake screenshots were visually inspected.
- JavaScript syntax and scoped diff whitespace checks passed. No tests were skipped and no failures remain in the final runs.

The first focused attempt hit sandbox access errors while cleaning temporary media and two new test-expectation errors (literal template apostrophe versus escaped dynamic text, and a nonstaff session rejected by the existing StaffBackend). Assertions were corrected to test actual protected behavior; access controls were unchanged. The focused and regression runs then passed with authorized access to disposable test media. These initial failures are not counted as passes. The earlier one-off environment probe also had a shell-command syntax error; it did not change project files or settings.

All Django tests used the **separate disposable `test_santolan_pwd` MySQL database**, created and destroyed by the test runner, with temporary test media. Existing migrations were applied only inside that test database. No migration, reset, data update or fixture load ran against the owner's development database.

Browser evidence: repository `.local/qa-confirmed-membership-20261010/browser/results.json` and screenshots. Verified source backups and diffs against the original dirty working files are under vault `.local/confirmed-membership-implementation-20261010/`. Neither evidence directory is public content.

## Regressions preserved

The passing suite covers onsite permission separation/CSRF, pending intake, private downloads, manual PRPWD actor/time/reason, required/missing files, successful official Member creation, duplicate and concurrent approvals, stale edits, requirement snapshots, audit/file rollback, member corrections/status/history, CMS draft/publication/withdrawal/history/escaping and authorization, public navigation, program verification/photo/eligibility/reference safeguards, verified-document reuse and masked non-EWAF result controls. Existing service/model/form/configuration/URL/CSS/JavaScript behavior outside the membership browser harness was not changed. Existing tests about arbitrary configured public document lists were updated to assert the superseding confirmed checklist and preservation of private configuration; their no-online-intake and history protections remain.

This is local acceptance, not full screen-reader/PWD UAT, production readiness or government-policy confirmation. No commit or push was made.

Final Git status/stat/whitespace review and SHA-256 comparison against **328 pre-existing repository files** found only the nine intended existing source/test/template edits, four intended new repository files and no lost pre-existing Git change entries. **319 existing files remain byte-for-byte unchanged**, including all models, forms, services, settings, routes, migrations and static assets. Verified byte backups cover all nine edited existing source files. Prior completed checkboxes remain intact; the roadmap additionally credits the newly completed scoped inspection without changing a milestone percentage.

## Files in this implementation scope

Source and tests:

- `membership/guidance.py` (new)
- `membership/views.py`
- `membership/tests.py`
- `membership/test_confirmed_requirements.py` (new)
- `core/content.py`
- `templates/membership/association_requirements.html` (new)
- `templates/membership/guidelines.html`
- `templates/membership/encode.html`
- `templates/membership/detail.html`
- `templates/content/edit.html`
- `programs/test_workflow_alignment.py` (membership-only expectations)
- `scripts/membership_browser_qa.cjs`

Documentation: this validation note (new), `../05 - Development/System Development Progress.md` and `../05 - Development/Development Roadmap.md`. Historical validation notes, source requirements and gap-analysis findings are retained as dated evidence.

**Development database modified: NONE. Schema changes: NONE. New/modified migrations: NONE.** Unrelated unfinished Git work, membership history, issued references, approved program/selection decisions and EWAF calculations are preserved. Implementation stops here.
