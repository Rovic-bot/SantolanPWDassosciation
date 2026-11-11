# Baseline and protected boundary evidence

Audit date: 2026-10-23. This report distinguishes source/document preservation, actual synthetic behavior tests and unavailable verification. None proves institutional acceptance or working-database readiness.

## Actual checkout and preserved work

- Branch: `feature/events`; HEAD: `776cac5d1119410717c6a31c044ea85f4d619941`.
- One worktree, the current repository. It was already on a feature branch; no checkout/branch/reset/stash/clean/stage/commit/merge/push operation was used.
- Initial status before new audit files: only `?? OVERALL_SYSTEM_SPECIFICATION.md`. That owner file was not added by this task or modified. The owner supplied the integrated PDF later; it is separately hash-recorded and remains untracked/unchanged.
- Initial `git diff` and staged diff were empty. `baseline.json` was written once, after adding the two initial audit/test helper files but before running tests. Its status therefore includes those audit artifacts; this does not indicate pre-existing application changes. All 816 original tracked files are hashed. No files were reset to the document's checkpoint.
- The 267-file protected subset includes the whole `ewaf/` tree, EWAF templates, **all app migrations**, startup guard, ordinary settings and key program/publication/release consumers. The broader 816-file comparison additionally covers every other existing tracked source/test/document. Existing assertions are unchanged.

Evidence: [baseline.json](baseline.json), [preservation-check.json](preservation-check.json), [source-supplement.json](source-supplement.json). Final check: **zero changed tracked files, zero changed protected files, zero changed original source documents; HEAD/branch/staged diff unchanged**. No protected-file patch exists because the diff is empty. Newly authored audit files are listed in [report](README.md).

## Section 8 and original workbook

| Evidence | SHA-256 / result |
|---|---|
| Entire baseline `OVERALL_SYSTEM_SPECIFICATION.md` | `6b9fcf60d8ce8d6b67c2c2bbd13c75472fa44997078d59339efc8b75ff75fa29` |
| Exact baseline Section 8 bytes, from `## 8.` up to but excluding `## 9.` | `f446ea0be7cf061439293c75f6354bdde77c6e2e4870e69611cc19bd1abec41d` |
| Integrated PDF | `8edf61623376da53169405446d175c02fb5daaa317dcb4462de82a5e14b7d8a7` |
| Normalized Section 8 text, both baseline and integrated PDF pp. 23–25 | `897244f7766d34bb6cbb7ef80d656dc613302cfad716a1812c375a484c14c0e1`; exact match, no differences |
| Integrated Markdown byte identity | **Blocked/unverified:** that Markdown master is unavailable. PDF's own preservation statement is not independent verification. |

Comparison removed only running page headers/footer, Markdown structural/emphasis/table/list/fence syntax and whitespace. It retained wording, digits and mathematical operators. See [section8-comparison.json](section8-comparison.json) and `scripts/added_targets_phase1_sources.py`. Source pages 23, 24, 25, 38 and 39 were rendered and visually inspected for Section 8 and AC/IQ table context; temporary renders/extracted text stay in ignored `.local/added-targets-phase1/`. These are source-document images, **not application UI evidence**.

The workbook was read twice with the bundled runtime's openpyxl, formula mode and stored-value mode. [workbook-read-evidence.json](workbook-read-evidence.json) retains all 422 populated cells and 84 formulas with caches. C29:C33 still contain empty-range averages and cached `#DIV/0!`; disconnected literal matrices/weights and the 0–1 H86 value remain source evidence. No workbook save/recalculation, mathematical repair, direction choice, threshold adoption or policy inference occurred. Synthetic test policy is not Association policy.

## Isolated test environment

The existing `scripts/g12_test_runner.py` creates a **new** temporary MySQL datadir on a free loopback port, disables dotenv, creates an empty base database and synthetic user with grants restricted to the disposable base/test names, and verifies datadir/port/empty-instance identity before use. The unchanged `DurableTestRunner` verifies identity again before test database setup/migrations, then validates the resulting test database, server UUID and InnoDB tables. It does not fall back to the ordinary database. The new `PhaseOneTestRunner` only supplies a separate temporary private-media root and requires this launcher context.

Completed run:

- Python 3.14.5; Django 5.2.17; MySQL 8.4.11; READ-COMMITTED; all test tables InnoDB.
- Base database: `g12_empty`; test database: `test_g12_disposable`.
- Host `127.0.0.1`, port `53765`; instance UUID `a3e17706-cece-11f1-adce-581122e63603`.
- New datadir: `C:/Users/rovic/AppData/Local/Temp/santolan-g12-tests-y1p5kdre/data/`.
- Separate synthetic media: `.../santolan-g12-tests-y1p5kdre/phase1-private-media-0twtogwf/`; individual existing tests may also use their own fresh temporary fixture media.
- `DJANGO_SETTINGS_MODULE=config.settings` with `.env` disabled and fresh synthetic environment. No ordinary credentials, `.env`, working tables or real-member files were read. Optional `program_intake` was not installed/activated.
- **62 existing baseline migrations** built only the fresh disposable test schema, including existing EWAF `0008`; **zero new migrations** generated/applied. This is test setup for existing code, not application of the proposed additive schema or enablement in ordinary settings. Startup migration deferral/guard stayed unchanged.
- Log completion timestamp: `2026-10-23T10:45:55.600731+00:00` (18:45:55 Asia/Manila; retained log modification time). Exact execution output and settings/identity are retained below. No production timing claim is made.

Exact successful command, from the repository root:

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf.test_computation_reference ewaf.test_four_criterion_reference ewaf.test_ahp_validation ewaf.test_normalization ewaf.test_weighted_scoring ewaf.test_four_kernel ewaf.test_operational ewaf.test_delivery --testrunner scripts.added_targets_phase1_test_runner.PhaseOneTestRunner --noinput --verbosity 2
```

**84 tests passed in 72.183 seconds; zero reported failures/errors/skips.** Django system checks reported zero issues. The test database was destroyed by the runner and its temporary server shut down. A read-only process check found no remaining MySQL process for this run or the earlier interrupted audit instance. The initialized temporary datadir/logs are retained as harness artifacts, not committed, and contain only synthetic data. Do not publish its config or credentials.

Evidence: [baseline-tests.log](baseline-tests.log), [test-results.json](test-results.json). Log SHA-256: `f8a1d40ff0c6f8470bc316d062d0666b74e692c0935f7100008e87603719c447`.

## Behavior coverage and limits

| Protected behavior | Executed existing test evidence | Further existing tests identified, not executed in this audit |
|---|---|---|
| Five/four criterion formulas, PR/RI separation, exact replay | `test_computation_reference`; `test_four_criterion_reference`, including historical five replay and independent Fraction oracle; `test_four_kernel` | `test_four_workflow`, `test_four_acceptance`, `test_four_development` |
| Strict CR boundary and structural validation | `AHPValidationTests.test_reference_boundary_uses_unrounded_strict_comparison` tests below .10, exactly .10, above .10 and negative; operational policy replacement/consistency tests | Broader configuration/migration/authority suites |
| Bounds, directions, precision and missing inputs | All `test_normalization`, `test_weighted_scoring`, `test_four_kernel`; operational missing bounds/classification policy | `test_scoring_inputs/services`, `test_onsite_sources` |
| Stale/missing evidence and current authority | Operational stale source, expiry/revoked permission and final freshness rollback tests | Full evidence/source freshness and writer-adapter suites |
| Complete pool and exact ties; numerical-rank boundary | `OperationalPoolTests.test_pending_applicant_blocks_complete_pool_and_hold_blocks_ties`, `test_exact_ties_slot_capacity_and_concurrent_decisions`, pool limit. Executed reference tests assert no rank output. Source inspection confirms `operational_policy.calculations` sets `business_rank=None`; the operational subset does not directly assert that field. | `test_four_workflow.test_four_persistence_and_historical_five_replay` and `test_four_review` explicitly assert unset business rank; `test_pool_services/concurrency`, `test_ranking_preservation`, `test_operational_volume` |
| History, explicit replacement and separate human decisions | `OperationalTests.test_exact_calculation_predecessor_reasoned_decisions_and_separation`; concurrent calculation successor; immutable/tamper/rollback checks | `test_four_workflow`, `test_decisions`, `test_recalculation_preservation` |
| Publication authorization/masks/freshness | `OperationalTests.test_publication_explicit_masked_and_withheld_after_recalculation` | Full `announcements` result tests, public-navigation/browser suite |
| Actual releases, no selection bypass, unchanged scores | Three `OperationalDeliveryTests`: successful delivery once, each selected member delivery, stale/unselected/audit-failure blocking | `assistance.tests` (void/release/PA counting, dates, concurrent release); full PA window/cross-program source suites |

The static [test-inventory.json](test-inventory.json) lists 1,538 discovered method definitions with source path/class/line. It is **not** a Django discovery count, unique-coverage total or pass claim. The 84-test execution establishes a focused baseline only. It does not accept new intake/tracking/ticket/RSVP behavior, prove full PA/release semantics, certify all writer adapters, or certify the whole application.

## Failed, interrupted and unperformed checks

| Check | Actual outcome |
|---|---|
| First focused command inside sandbox | Failed before test execution: permission denied writing fresh `...santolan-g12-tests-jni2l8xp/mysql.ini`; no app DB fallback. |
| First escalated attempt, `...santolan-g12-tests-k6h_4zqw` | Daemon interruption. Initialization/server-start logs existed; no `django.log` result was found. Not counted as a pass or behavior failure. Follow-up session ID was unavailable after restart. |
| Fresh repeated focused command | Completed: 84/84, as above. No assertion/engine fix was needed. |
| `git diff --check` and `git diff --cached --check` | Passed; existing tracked/staged diff empty. New audit files are separately checked for syntax/whitespace/references. |
| Source hashing / Section 8 text comparison / workbook read | Passed as described; integrated Markdown byte comparison and original Brainstorm/log provenance remain unavailable. |
| Full Django suite, all migration-preservation suites, full source-writer/concurrency/performance coverage | Not run. No historical test count reused as a new pass. |
| New application UI/browser, screen-reader, contrast/mobile/print journeys, representative UAT | Not run; no Phase 1 UI changes and no private/working data used. Source-PDF inspection is not UI acceptance. |
| Working DB check/migrations, ordinary launcher, `makemigrations`, deployment, backup/restore | Not run. Phase 1 proposed schema only. Disposable baseline setup is separately stated above. |

## Security, privacy and accessibility source findings

Current membership staff detail/download routes enforce dashboard/capabilities, private responses and audited retrieval. Program reference search exists; membership list reference search is absent. Existing result projection excludes private records, uses fixed masks and checks publication freshness. Old program tracking/QR returns 410; direct event registration and new event creation also return 410. These source observations do not prove every deployment setting or stored permission.

The main extension risks are identifier-only private access, accidental PDAO powers, first-time identifier misuse, all-file checklist assumptions, stale updates, duplicate cross-channel Members, optional-intake activation and source changes bypassing existing invalidation. The proposed gates, service integration, typed states, atomic audits and acceptance tests directly address these risks; implementation is pending.

Upload signature/type/size checking is reusable but is not malware scanning. Anonymous intake broadens abuse and storage exposure and requires bounded requests, payload validation and private-file retention review before activation. Existing UI controls can be reused; they do not prove new forms/receipts/tracking are accessible. No WCAG certification, legal-compliance certification, fairness improvement or performance gain is claimed.
