# Onsite membership validation — GAP-001

> [!warning] OUTDATED / HISTORICAL validation evidence — marked 2026-10-06
> This entire report retains the original implementation, schema, commands and observed test counts for its dated revision. It is not acceptance of [CURRENT_SYSTEM_SPECIFICATION](../../CURRENT_SYSTEM_SPECIFICATION.md). Former current/next/complete labels and obsolete workflows apply only to that historical scope. New acceptance is planned in [[Workflow Acceptance Tests]]; no tests/code/database actions were performed for this documentation revision. Preserve useful nonconflicting security/history evidence without reintroducing public membership intake, open nonmember organizational applications, universal disability rejection, QR/status requirements, fixed EWAF defaults or automatic applicant publication.


Date: 2026-09-30, Asia/Manila. Branch: `feature/events`. Base commit: `96ff02768e08e364f70f4a3e1c26b4a0e99399a7`, with the existing uncommitted workflow implementation preserved. Results apply to the working tree reviewed in this session, not that base commit alone.

## Outcome

**GAP-001 is complete for local acceptance of the existing onsite workflow.** Public visitors read configured guidelines and cannot submit membership applications. An ordinary authorized staff account encodes onsite applicants, reviews private documents, records manual PRPWD verification and explicitly approves/rejects. Approval requires successful verification and original required files, creates exactly one Official Member, and retains evidence/history. Rejection creates no Official Member. No applicant/member user account is created.

Authority: vault `Guide for Development.md` §§16–20, 48–53 and 65, Business Rules and DEC-019. This acceptance does not finalize the association's official role assignments, document list, disability classifications, contact information or PRPWD URL. It does not approve a different physical-document-only evidence scheme, deployment or association UAT.

## Scope and changes

- `membership/tests.py`: four additional regressions for configurable guidelines/retired intake, separate encoding permission at GET/POST/service boundaries, ordinary-staff review with the legacy public-intake flag closed, and retired receipt behavior. The staff review case verifies blocked unverified approval, stale decision rejection, retained document/actor history and unchanged user count.
- `scripts/membership_browser_qa.py`: use an ordinary staff test actor with explicit permissions, a synthetic classification and required/optional/inactive requirements; assert retained evidence, one approved member, rejection without a member and no applicant account creation.
- `scripts/membership_browser_qa.cjs`: replace obsolete public online submission with onsite encoding and public guidelines; exercise document download, manual verification, approval/rejection, logged-out protection, responsive/enlarged-text states and duplicate-ID checks. Store dated screenshots and `results.json` outside the public assets.
- README/current membership plan and vault tracker/progress/roadmap: record the revised operator flow and actual acceptance evidence. Historical public-intake validation remains in `membership-validation.md` unchanged.

No application models, forms, services, views, templates, permissions, environment settings or dependencies were changed in this task. No migrations were created/applied and no real institutional values were seeded. Existing application behavior passed the scoped acceptance; the confirmed gap was the obsolete browser validation procedure.

## Verification

**55 focused automated tests passed**:

```powershell
.venv\Scripts\python.exe manage.py test membership programs.test_workflow_alignment core.tests.test_public_portal --noinput --verbosity 1
```

The run covers onsite membership and retained upload/verification/approval controls, permissions, CSRF, private attachment delivery, duplicate/stale/concurrent decisions, audit/file rollback, requirement snapshots and public portal/workflow regressions. Programs alignment cases were included as existing integration checks; their passing result does not resolve open EWAF or program business decisions.

**One Chrome integration test passed**:

```powershell
$env:PLAYWRIGHT_MODULE = 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'
$env:CHROME_EXECUTABLE = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
.venv\Scripts\python.exe manage.py test scripts.membership_browser_qa --noinput --verbosity 1
```

Use the installed Playwright module/browser locations for another computer. The actor's password is generated for the test, passed only to the browser process, and never written to evidence.

- **35 responsive checks:** seven states at 320/390/768/1024/1440 pixels: guidelines, onsite encoding, queue, pending review, blocked approval, approved review and rejected review. No page overflow or duplicate IDs detected.
- **Seven Largest-text checks** at 390 pixels passed. Desktop pending review, mobile enlarged onsite form and mobile enlarged approved review screenshots were visually inspected.
- **No browser page/console/resource errors** in the successful run.
- Public guidelines display active required/optional requirements and onsite instructions; inactive requirements and online forms are absent. Old receipt redirects to guidelines, anonymous onsite access redirects to staff sign-in, and logout restores private-page protection.
- Browser database assertions confirm two retained applications, exactly one approved Member, correct staff verification/decision actors, retained requirement/document snapshots and expected audit actions; the rejected application has no Member and the user count stays one.
- System/database check passed; `migrate --check` passed; `makemigrations --check --dry-run` reported no changes; JavaScript syntax and `git diff --check` passed.

These are focused results, **not a new full-suite result**. The earlier 228-test log remains historical.

## Isolation and preservation

The project-local MySQL instance was initially stopped; `scripts/local_mysql.py start` started the existing instance on port 3307 without initialization or environment changes. Tests used the separately validated `test_` database and temporary private media. Test databases were destroyed after their runs.

Read-only SHA-256/count fingerprints before and after validation matched across **all 43 application database tables**, including application records, users, permissions, configuration, documents and histories. No synthetic actors, classifications, documents or member/application rows were added to the normal application database. The fingerprints contain hashes/counts, not raw record contents.

Evidence and verified pre-edit copies are in ignored `.local/qa-gap001-20260930/`:

- `browser/results.json` and desktop/mobile screenshots.
- `app-data-before.json` / `app-data-after.json` and the read-only preservation script.
- `before-source/` and `before-notes/` copies.

Do not expose `.local/` or private media publicly. Native MySQL was left running for continued local development.

## Issues encountered

The first sandboxed automated run failed because Windows denied access to temporary upload folders. The approved run outside the sandbox passed all 55 cases; the underlying application behavior was not changed to work around that restriction.

The first updated Chrome run stopped because the new onsite-registration link appeared in both navigation and main content. The selector was scoped to the main dashboard link, and the complete rerun passed. This was a harness selector issue, not a failed membership workflow.

## Evidence process and remaining boundaries

The retained implementation reviews documents supplied onsite and stores their uploaded copies privately. Approval uses each application's original requirements/evidence, not later configuration. Required files still block approval if unavailable. No new evidence representation or paper-only approval bypass was introduced.

Official association configuration remains GAP-016 and disability-list/mapping policy remains GAP-003. Further physical-document-only storage/process changes remain in Open Decisions. Firefox/Safari, real-device assistive technology, association UAT and production checks remain GAP-017/018.

The tracker now records **one locally completed work package and 17 open packages**. These packages have unequal scope, so this is not a completion percentage. Keep the historical 70% baseline; revised-scope progress still needs a defined rebaseline and the remaining milestone acceptance.

Next: **GAP-002, open event attendance**, after the owner resolves the individual-attendees-versus-total-count design recorded in Open Decisions and guide §23. Preserve all historical event records; no attendance schema/workflow change was performed in this membership task.
