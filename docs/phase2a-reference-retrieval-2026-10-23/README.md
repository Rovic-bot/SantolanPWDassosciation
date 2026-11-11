# Phase 2A — Staff-only reference retrieval

Date: 2026-10-23. **Status: Completed within the explicitly authorized Phase 2A scope.** Broader Phase 2 is not complete; Phase 2B has not started. The accepted 70% milestone and historical G-stages remain unchanged. This is a substep of Phase 2 in the existing five-phase plan, not a replacement milestone.

## Delivered behavior and staff instructions

In **Members → Membership reviews**, authorized staff can enter a complete existing application reference and choose **Find reference**. The exact lookup includes pending, approved and rejected applications. The result displays the existing reference as a link to the existing membership application detail screen. It creates no application, Member, identifier, decision or verification finding.

Use the separate **Name or control number / Status** filters for ordinary browsing. Their behavior and the default pending list remain unchanged. **Return to pending applications** exits reference lookup. A reference lookup is independent of the name/status filters, so a completed record is not hidden by the pending default. Full canonical UUIDs, uppercase equivalents and complete 32-character UUID hex input are supported; prefixes, malformed references and extra characters do not broaden the search.

Invalid input receives a labeled error; a well-formed unavailable reference receives a generic empty result. Authentication and permissions are checked before lookup. A reference is never authorization. Staff select the result to review existing information; verification/decision actions and private downloads retain their separate permissions.

**Existing program retrieval is reused unchanged:** Applications & Verification → Program applications → the appropriate program already supports reference/name/control-number search. Existing issued program references, including retained legacy references, were exercised by current regression tests. Phase 2A does not add a universal cross-domain lookup or new reference namespace.

## Exact application and test files changed

| File | Change |
|---|---|
| `membership/views.py` | Adds a read-only exact UUID lookup branch to the existing permission-checked, uncached list view. Invalid input returns an empty queryset; ordinary browsing remains separate. No detail/action service changed. |
| `templates/membership/list.html` | Adds the labeled reference search, associated help/error/status text, reset link and reference link in each existing applicant row. Reuses shared forms, table and layout classes. |
| `membership/test_reference_retrieval.py` | Adds 13 synthetic tests for correct lookup, status coverage, formats/invalid input, access denial/revocation, read-only retries, separate document permissions, audit failure and public-route preservation. |
| `scripts/reference_retrieval_test_runner.py` | Test-only runner reusing the existing fresh-instance isolation checks and temporary media. Disables migrations for test schema creation and blocks migration application/reversal throughout the run. Reuses the existing four-label synthetic fixture helper. |
| `scripts/reference_retrieval_browser_qa.py` | Creates synthetic staff/read-only UI fixtures on the disposable live test server and verifies the browser flow leaves application/history records unchanged. |
| `scripts/reference_retrieval_browser_qa.cjs` | Headless Chrome keyboard, responsive layout, invalid-input semantics and anonymous-access checks; saves synthetic screenshots and findings. |

Only the first two files change application behavior. All other original tracked files, including existing tests/assertions, models, forms, services, routes, migrations, configuration, shared styles and navigation, remain unchanged. [The application diff](application.patch) and [preservation evidence](preservation.json) record this exactly.

Documentation/evidence: this report, `baseline.json`, `validation.json`, `preservation.json`, `application.patch`, retained attempt/final logs, and `ui/` evidence. The existing [single progress record](../added-targets-phase1-2026-10-23/progress-and-decisions.md) receives a new Phase 2A checkpoint; its earlier contents remain intact. No governing source specification or historical validation record was rewritten.

## Existing components and safeguards reused

- `MembershipApplication.reference` and its existing unique constraint; existing statuses, snapshots and review history.
- `membership:list`, `membership:detail` and `membership:document`; no new public route.
- `dashboard_required`, `require_capability`, active/staff/dashboard/membership-view checks, and existing separate document/verify/decide permissions.
- Existing detail rendering, private storage, download audit, cache protection, sandbox/nosniff response headers and source-writer wrappers. Search/detail GETs retain existing read behavior; authorized downloads still record their existing download event.
- Existing Paginator, minimalist Admin template, Members navigation and permission-aware eight-group sidebar. No new group, role, member account, CSS dependency or framework.

## Actual validation

**Final selected regression run: 352 tests passed in 169.882 seconds, zero failures/errors/skips.** This includes the 13 new retrieval tests, 84 existing focused EWAF regressions, membership/member workflows, local/mocked-remote private storage, account permissions/concurrency, program submission/photo/reference/review behavior and one new Chrome integration test. Counts overlap; do not add the earlier targeted 13 passes to 352.

The final command uses the existing launcher and the new test-only runner:

```powershell
$env:PLAYWRIGHT_MODULE = 'C:/Users/rovic/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'
$env:CHROME_EXECUTABLE = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test membership.tests membership.test_reference_retrieval membership.test_onsite_profile membership.test_confirmed_requirements members.tests documents.test_storage accounts.tests.test_accounts accounts.tests.test_authority_generation programs.tests programs.test_revised_workflow programs.test_workflow_alignment ewaf.test_computation_reference ewaf.test_four_criterion_reference ewaf.test_ahp_validation ewaf.test_normalization ewaf.test_weighted_scoring ewaf.test_four_kernel ewaf.test_operational ewaf.test_delivery scripts.reference_retrieval_browser_qa --testrunner scripts.reference_retrieval_test_runner.ReferenceRetrievalTestRunner --noinput --verbosity 2
```

Full output: [final regression log](regression-tests-final.log). Exact attempt commands, timestamps, hashes and isolated instance identities: [validation.json](validation.json). Django system checks reported no issues. Python AST parsing, JavaScript syntax and Git whitespace checks passed. No historical Phase 1 count is presented as a new result.

### Isolation and no-migration boundary

The existing G12 launcher created a fresh loopback MySQL 8.4.11 instance under `C:/Users/rovic/AppData/Local/Temp/santolan-g12-tests-q1hbx12f/`, with `.env` disabled and restricted disposable test credentials. It verified the datadir/port and empty instance before setup. The durable runner reverified database/instance identity, READ-COMMITTED isolation and InnoDB tables. A separate `phase2a-private-media-*` directory held synthetic uploads. Mocked remote storage tests used fake network/storage responses; no live remote service was accessed.

**Zero migrations were generated, applied or reversed.** Django's test-only `TEST.MIGRATE=False` synchronization created temporary tables from existing installed models; the log explicitly reports no migrations to apply. Migration-executor application/reversal was blocked for the final entire run. The four existing eligibility labels were supplied through the existing synthetic fixture helper because the normal data migration was deliberately not run. This is test-fixture preparation, not an approved new institutional policy or working-database configuration.

The final test database was destroyed and the launcher completed. Disposable diagnostic artifacts remain under their printed temporary directories; the interrupted run's synthetic artifacts were retained rather than destructively cleaned. No ordinary launcher, working-database query/check, production access, credential change, migration command against application data or deployment operation ran.

### Earlier attempts retained honestly

| Attempt | Actual outcome / resolution |
|---|---|
| Initial sandbox attempt | Blocked before database initialization by temporary-file access denial; no tests ran. Retained in `targeted-tests.log`. |
| First authorized targeted run | 13 tests attempted, 10 errors. A new test explicitly closed an already-closed streaming response, breaking its TestCase database connection and cascading into later cases. Removed the redundant test cleanup; no application or existing assertion changed. `targeted-tests-authorized.log` retained. |
| Corrected targeted run | All 13 passed in 1.997 seconds. `targeted-tests-rerun.log` retained. |
| Broad app-discovery run | Discovered 354 tests; deliberately stopped before the two migration-history tests ran. Three storage errors had appeared. No final suite result is claimed. `regression-tests.log` retained. |
| Storage diagnostic | The three errors reproduced in 0.309 seconds: missing eligibility-label choices because migration seeding was disabled. Reused `assistance.tests.seed_statuses` in the isolated runner; no engine/service/assertion changes. `storage-diagnostic.log` retained. |
| Final explicit non-migration selection | All 352 passed, including the previously failing storage cases and new browser test. |

Not run: the complete repository suite, `membership.test_profile_migrations`, `members.test_catalog_migration`, migration/upgrade validation, production/working-data checks, screen-reader sessions, measured contrast audit, representative-user UAT, performance benchmarks or backup/restore. The no-migration setup is not evidence of migration correctness.

## Security, privacy and accessibility findings

Authorized staff retrieved the correct existing record in each decision state. Anonymous users were redirected to login; staff lacking required permissions received generic denial before results; inactive/nonstaff/revoked access was denied. View-only staff could not verify/decide, and document access required its separate permission even after successful reference retrieval. Revocation was rechecked. Existing download auditing and failure-before-delivery behavior passed. Public guidance and retired receipts did not expose queried records; program reference/QR routes retained their existing privacy behavior.

Repeated GET/HEAD requests did not change application, Member, document or history snapshots. POST to the search endpoint was rejected. Reference comparison is exact and input is bounded/escaped; invalid input cannot fall back to all records. Existing references, intake forms, snapshots, statuses and review records are not rewritten. No new unauthenticated endpoint or private-file URL was added.

Chrome 156.0.8078.47 checked keyboard lookup and opening the result, associated error semantics, anonymous redirect, and **16 layout checks** across pending list/result/detail/error pages at 320/390/768/1440 pixels. A 390-pixel view with 200% root text size had no document-level horizontal overflow. No page/console errors or duplicate IDs were observed. The existing data table remains a keyboard-focusable horizontal-scroll region on narrow/enlarged screens; these checks do not claim every table column fits simultaneously.

Synthetic evidence was visually reviewed: [desktop result](ui/reference-result-desktop.png), [enlarged mobile result](ui/reference-result-mobile-200percent.png), [browser checks](ui/checks.json). The screenshots contain synthetic people and references only. The sidebar shows the groups allowed to the synthetic view-only staff member; its unchanged implementation retains all eight groups. No WCAG certification or completed UAT is claimed.

## EWAF preservation and acceptance trace

The checkout remains `feature/events`, HEAD `776cac5d1119410717c6a31c044ea85f4d619941`, with the two described application edits and new test/documentation files. No commit, push, merge or deployment occurred.

**All 267 protected files and every existing migration are unchanged.** Only `membership/views.py` and `templates/membership/list.html` differ among the 816 tracked baseline files. Source specifications and Section 8 remain unchanged and byte-identical: Section 8 SHA-256 `f446ea0be7cf061439293c75f6354bdde77c6e2e4870e69611cc19bd1abec41d`.

The 84 freshly executed existing EWAF tests cover criterion/formula references, strict CR validation, bounds/missing inputs, complete-pool and exact-tie controls, stale sources, decisions/capacity, publication and actual-release safeguards. Their assertions were not edited. This is a targeted behavior regression result, not full EWAF acceptance; no-rank/reference tests do not substitute for every unexecuted operational rank/PA/history assertion.

Phase 2A addresses the **existing Association retrieval portion of BF-03 / AC-B02**, BR-A04's authenticated retrieval boundary, and the relevant limited BF-11/AC-B13 checks. The wider AC-B02 also includes future intake categories and is not declared fully implemented. AC-B14 has new targeted regression evidence, not final post-extension acceptance. BF-01/02, receipts/new references, public tracking, new intake and PDAO processing remain undelivered.

## Remaining Phase 2B decisions and stop

No unresolved policy blocks the delivered existing-reference lookup. Phase 2B still requires explicit scope authorization and approval of the additive non-EWAF schema/state/permissions design, minimum intake fields, private uploads, privacy/retention, IQ-10 references/retries/duplicates/submission-context completed-form access, first-time Association identifier allocation and OQ-27 onsite physical/alternative-document treatment. PDAO-dependent behavior requires IQ-09 authority/transfer/checklist decisions and IQ-16 operational ownership, or continued server-side unavailability. Public tracking/access/recovery remains IQ-03 and later scope; no credentials or access periods are invented.

The practical improvement is that staff can find an already retained intake directly from its reference, including completed reviews, and open its existing authorized detail page. No measured speed, capacity or fairness improvement is claimed. The main usage consideration is the distinction between exact reference lookup and the separate name/status filters; the page states this. The larger public-intake/privacy risks remain outside this delivery.

**Stop after Phase 2A. Do not start Phase 2B, apply working-database migrations, deploy or change the accepted milestone without separate authorization.**
