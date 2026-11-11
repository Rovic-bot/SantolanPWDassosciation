# Four-criterion EWAF operational-readiness sprint validation

Accepted milestone: **70%**. Proposed 80% remains unaccepted. Operational scoring, actual beneficiary allocation, application-database migration and deployment were not performed.

## Scope and result

The existing `feature/events` workspace already contained the later four-criterion integration described in `stage8-four-validation-2026-10-19.md` (recorded 1,439-test baseline), in addition to the independently reviewed 1,397-test baseline. This sprint preserved that implementation and completed the authorized saved fictional human-decision workflow. The owner's approval in this conversation covers creation and disposable testing of the proposed two-table migration; it does not approve operational policy or migration of the application database.

The safe development path now combines verified fictional application/evidence records, mandatory PR eligibility, versioned SI/ES/PA/ND configurations and complete-pool calculations, exact descending comparison, four calculation traces, replacement history, and saved reasoned human-review revisions with separate immutable audits. Neither a score nor a saved fictional choice approves an actual beneficiary or release.

## Changes

Twelve existing files changed relative to the captured working-tree baseline:

- `ewaf/development_views.py`, `templates/ewaf/development_program.html`: score-ordered four-criterion comparison, explicit exact-tie counts and SI/ES/PA/ND trace presentation. Historical five-criterion ordering/content is preserved.
- `ewaf/four_views.py`, `templates/ewaf/four_workspace.html`: saved fictional decision forms, stale decision-version tokens, immutable paged history, reason and audit provenance. Existing transient demonstration remains available.
- `ewaf/models.py`: imports the two new development-only models.
- `ewaf/four_testsupport.py`: optional distinct fictional profile values, reviewed through existing evidence services.
- `ewaf/test_generation_migrations.py`: excludes the new descendant tables when reversing to pre-foundation schema, and excludes the newly reapplied migration timestamp from the unchanged older-migration-recorder assertion. Existing preservation assertions remain.
- `core/management/commands/runlocal.py`: exact hash-pinned deferral of the newly approved development migration, so ordinary local startup does not require application migration or query the new feature.
- `ewaf/test_ranking_preservation.py`, `ewaf/test_recalculation_preservation.py`, `ewaf/test_pool_services.py`: latest-migration expectations advance to the explicitly approved `0007`; all existing historical/operational-barrier assertions remain.
- `ewaf/four_decisions.py`: the existing transient preview also accepts the new fictional withdrawal choice; it still saves nothing and has no assistance effect.

New implementation: `ewaf/decision_models.py`, `ewaf/decision_services.py`, `ewaf/four_review.py`, `ewaf/migrations/0007_development_human_decisions.py`. New tests: `ewaf/test_decisions.py`, `ewaf/test_decision_migrations.py`, `ewaf/test_four_review.py`. New browser harness: `scripts/stage8_readiness_browser_qa.py` and `.cjs`. Three new documentation files provide this report, the consolidated policy sheet and acceptance checklist.

No five-criterion mathematical engine, historical source/digest format, source-writer adapter, public result projection, assistance workflow, Admin CSS, environment configuration or previous migration was changed. No reset, stash, clean, stage, commit, push or deployment was used.

## Human-decision transaction and schema

`DevelopmentHumanDecision` retains program/application, exact RunSourceBinding, actor/label/time, reason, decision, revision/predecessor, source/authority/state versions, original run/graph digests, versioned accepted eligibility/calculation payload and a one-to-one audit. `DevelopmentHumanDecisionAudit` retains matching actor/program/time, action, decision digest and its own versioned digest.

The generated migration creates the audit table first, then the decision table with its audit FK, followed by constraints/indexes; no circular FK requires a later AddField. It contains no data migration, seeds, backfill or modification to old tables. Django's generated ordering differs mechanically from the original proposal's suggested AddField ordering while preserving its two-table schema. No default permissions are created and neither model is registered as editable Admin content.

The existing Terms → Authority → Program → SourceState → linked sources fence protects creation. The service requires current decision permission, exact expected source token, current complete four-criterion run and an eligible result. It locks the latest application decision, enforces expected revision/predecessor, and treats an exact retry as idempotent. It records decision and audit atomically, then repeats current-source/deadline/permission checks before commit. A changed source invalidates use of the calculation without erasing prior human evidence. A new calculation requires a fresh reasoned human revision.

Decisions use SELECT_DEMO, DEFER_REVIEW or WITHDRAW_DEMO. They are not a slot-allocation or release mechanism. Previous transient preview remains expressly unsaved. Durable history retains reasons and numerical provenance without changing a calculated value. History pages inspect up to 50 decisions at a time and provide older/newer navigation.

## Executed checks

All Django commands used the existing fresh-instance wrapper:

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py <arguments>
```

All test commands append `--testrunner scripts.durable_test_runner.DurableTestRunner --noinput`. The runner verifies an empty loopback MySQL datadir and restricted disposable grants, disables `.env`, checks InnoDB/READ-COMMITTED, shuts down its server and destroys the Django test database. No real member data or regular application database was opened.

| Run | Test arguments | Result |
|---|---|---|
| Initial required demonstration, before edits | `test scripts.stage8_browser_qa scripts.stage8_four_browser_qa` | 2 passed, 43.186 s |
| Pool/comparison and existing interface | `test ewaf.test_four_review ewaf.test_four_interface` | 9 passed, 129.093 s |
| Decision/interface first run | `test ewaf.test_decisions ewaf.test_four_interface` | 18 tests, 1 assertion failure, 108.763 s; correction explained below |
| Decision safety corrected | `test ewaf.test_decisions` | 12 passed, 68.657 s |
| Final migration expectations / decisions | `test ewaf.test_ranking_preservation ewaf.test_recalculation_preservation ewaf.test_pool_services ewaf.test_decisions` | 55 passed, 101.203 s |
| New and preserved migrations/startup | `test ewaf.test_decision_migrations ewaf.test_generation_migrations ewaf.test_durable_migrations core.test_local_startup` | 12 passed, 150.375 s |
| Combined browser QA | `test scripts.stage8_readiness_browser_qa scripts.stage8_four_browser_qa scripts.stage8_browser_qa scripts.revised70_browser_qa` | 4 passed, 135.603 s |
| Final browser after history pagination | `test scripts.stage8_readiness_browser_qa` | 1 passed, 59.527 s |
| Final browser after cutoff explanation | `test scripts.stage8_readiness_browser_qa` | 1 passed, 58.709 s |
| Concurrent duplicate/successor supplement | `test ewaf.test_decisions.DecisionTests.test_two_connections_conflicting_choices_have_one_winner` | 1 passed, 9.990 s |
| Full project first run | `test` | 1,455 tests, 3 outdated migration-leaf assertion failures, 1,405.318 s; no errors/skips |
| Full project final regression | `test` | **1,455 passed, 1,333.214 s; zero failures/errors/skips** |
| Django/database | `check --database default` | Zero issues |
| Migration drift | `makemigrations --check --dry-run` | No changes detected |
| Whitespace | `git diff --check`; `git diff --cached --check` | Passed; existing Git newline warnings only |

Counts overlap and must not be added as unique coverage. Final logs, including the earlier failed run, are packaged. Durations are Django-reported test execution times, not production performance claims.

The decision test failure was in the assertion: the existing concurrency helper returns `(connection_id, result)`, while the new test initially checked the tuple itself for integer type. The observed database outcomes already showed one saved decision and one `STALE_HUMAN_DECISION_REVISION`. The corrected assertion checks distinct connection IDs and exactly one successful result. No concurrency safeguard was relaxed. A subsequently added test proves a supported source writer waits behind decision insertion, then invalidates the calculation while retaining the saved history.

The first broad run started before three historical migration-leaf expectations were updated for the approved `0007`. Its log is retained separately from the final full run. The source line printed in a traceback can reflect a file edited after that process imported its earlier code; actual assertion results and rerun logs are retained rather than overwritten.

The concurrency supplement adds assertions to the new test after the final full process imported its tests; application code is unchanged. It independently executes simultaneous identical retries and conflicting successor revisions in addition to first-decision contention, checking that one immutable predecessor chain and matching audits remain. The separate log records this additional coverage.

The first migration-generation attempt stopped before generation with an unclosed model constraint-list bracket. Corrected syntax generated the reviewed additive migration. Initial sandbox attempts to write/read the runner's temporary directory were denied and rerun with the required scoped permission. These were tooling/setup failures, not concealed passing test runs.

## Pool and browser evidence

The representative test creates 24 fully verified fictional applicants with differing reviewed income/dependent values and an exact tie. Independent Decimal arithmetic matches every retained score and comparison count; all 96 traces and replacement history are checked. Initial capture plus processing measured 24.280 seconds in that run. This is a bounded development observation, not a production benchmark; the implementation retains its explicit 128-application engineering ceiling and rejects 129 before capture.

The new browser demonstration uses five retained applications, four scored and one late pending record outside the explicit fictional cutoff. The four scores are approximately 60.3350700206, 60.3350700206, 39.2913431119 and 28.4012521847. Exact stored precision is displayed; these arbitrary test measures are not proposed Association income, PA or selection rules. PR contributes no score.

The demonstration creates two complete runs and two reasoned human revisions. Screenshot evidence shows inventory, numerical comparison, four traces, calculation predecessor, saved reasons/audits and mobile layout. Browser tests exercise the real Django forms and server responses, not static mockups. Checks include no-store, CSRF/service privacy tests, labeled inputs, keyboard disclosure, responsive widths and no page errors; no formal WCAG or representative UAT certification is claimed.

## Preservation and package

Before editing, captured 621 source/documentation files, working-tree status, staged patch and index hash under `.local/ewaf-readiness/`. The final manifest distinguishes this sprint's twelve existing-file modifications and added files from earlier unfinished work. The index and every pre-existing migration remain byte-identical. The package includes baseline-relative before/after source, a reviewable diff, final source snapshot, migration SQL, test logs, fictional acceptance JSON, screenshots and SHA-256 manifests. Credentials, `.env`, private uploads, application databases and MySQL datadirs/config are excluded.

## Outstanding operational acceptance

See [the consolidated policy decision sheet](ewaf-operational-policy-decisions-2026-10-19.md) and [acceptance checklist](ewaf-operational-readiness-2026-10-19.md). Development decision persistence is now implemented under the owner's scoped approval. Association scoring/eligibility/selection semantics, actual authority/dates/program scope, operational configuration authorization, actual allocation/reevaluation/consumer integration, application migration and owner acceptance remain pending. The work must not be represented as accepted operational Stage 8 or 80%.

Supported-path transactions do not protect against privileged SQL/unsupported ORM writers, arbitrary external processes or changed-and-restored file tampering. Filesystem/MySQL are not jointly atomic. The test system remains a disposable development capability scoped to its recorded calculation actor; no operational multi-officer role policy or deployment capacity is inferred.
