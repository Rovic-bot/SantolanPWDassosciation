# Stage 8 pool backend: non-schema fallback and validation

Date: October 16, 2026. Workspace: current local Rovic checkpoint.

**Delivered scope: complete retained-application inventory, current score-free pool readiness, freshness recheck, disabled recalculation service contracts, and tests. Permanent calculation/recalculation/history is unfinished.**

The user's explicit fallback applies because no recorded authorization for this increment's new additive migrations was identified. This report does not claim an operational backend, accepted live calculation, G18 acceptance, full Stage 8 completion, or 80%. Accepted milestone remains **70%**.

## 1. Preflight and preserved checkpoint

- Branch: `feature/events`.
- HEAD: `949eeda33c6aa5d8ee03962209ae8fedeac58ad1`.
- Pre-existing index: 16 G16 additions, 4,438 inserted lines. No tracked unstaged difference from that index.
- Pre-existing untracked files: G16 revalidation, G17 plan/validation, October 15 operational proposal, G17 code/tests/fixtures/CLI, and the October 16 EWAF explanation guide. They remain separate from this task.
- Captured SHA-256 hashes for **505 existing tracked/staged/untracked nonignored files**, plus branch, HEAD, porcelain status and the complete staged raw manifest, before editing. Evidence: `.local/ewaf-pool-backend-20261016/baseline.json`.
- No pull, reset, clean, stash, branch switch, staging, commit, push, merge, deployment or changes to `main`.

The original 809-test October 15 result is historical evidence. New commands/results are recorded below and are not substituted with that historical number.

Final comparison verified all **505 pre-existing file hashes unchanged**, the exact branch/HEAD and staged raw manifest unchanged, and exactly the six new repository files listed below. Existing G16/G17 staged/untracked work remains untouched. All new files remain untracked; nothing was staged.

## 2. Authority actually used

The current user request explicitly authorizes: **“Application-code development and testing may proceed within this backend task.”** It also explicitly says: **“If schema authorization is absent, implement the non-schema-changing service contracts, validation, and tests; prepare the additive schema change proposal separately.”** Those instructions authorize this delivered fallback, including isolated tests and documentation.

Read/reviewed repository AGENTS, the current master/development guide and relevant Open Decisions, DEC-024–027, membership amendment, impact notes, current G12–G17 implementations/tests and validation, the October 15 operational proposal, source-writer lock boundaries, and the complete isolated runner before execution.

No covering new-schema authorization was identified in current decisions, repository/development notes or relevant local Markdown/text authorization records. The [October 15 proposal](stage8-operational-authorization-review-2026-10-15.md), section 7, expressly records creation of migrations and their disposable application as not authorized by that earlier review. Earlier G12/G14/G15 migrations were scoped to those foundations; they do not authorize this increment's dedicated result/history schema. Neither the current conditional instruction nor technical sandbox approval is treated as institutional or schema approval.

**No new migration or registered model was created.** Existing migrations were applied only by the isolated test runner to freshly created disposable databases, as necessary for the currently authorized tests. No migration was applied to the application database. The separate [durable schema proposal](stage8-persistence-schema-proposal-2026-10-16.md) records the unimplemented records and tests.

## 3. Files added by this increment

| File | Purpose |
| --- | --- |
| `ewaf/pool_contracts.py` | Explicit policy/storage barriers, engineering ceiling and context-token validation; reuse G15's bounded proposal/Decimal policy validation. No defaults or numerical applicant payload. |
| `ewaf/pool_services.py` | Permission-checked whole-program inventory and two-observation source/readiness comparison, current-source recheck, unconditionally disabled request/process/current-result contracts. |
| `ewaf/test_pool_services.py` | 34 contract/service tests covering accounting, policy gaps, permissions, privacy, evidence, preservation and disabled writes. |
| `ewaf/test_pool_concurrency.py` | Eight tests: seven real separate-connection MySQL source-change observations and one source-audit rollback check. |
| `docs/stage8-persistence-schema-proposal-2026-10-16.md` | Dedicated additive schema, orchestration, source-event/lock/retry/audit requirements and authorization boundary. Documentation only. |
| `docs/stage8-pool-backend-validation-2026-10-16.md` | This development checkpoint, evidence and completion limitations. |

No existing source, migration, template, route, setting, engine, fixture, test, checkpoint note or sidebar is modified. Ignored `.local/` evidence is not application code or a proposed commit.

## 4. Behavior delivered

`inspect_program_pool(program_id, *, user)` derives all retained applications for one program from server-controlled records, in deterministic PK order. It takes no subset, pagination, cutoff, “synthetic” or score arguments. Available slots never restrict its inventory.

It distinguishes:

- The complete retained-record inventory, including ineligible, pending and other retained states.
- The applications currently marked `ELIGIBLE`, including those with invalid/stale provenance.
- Current G12 eligibility readiness, criterion completeness, G14 weight-evidence completeness and G15 policy findings.
- Unknown approved evaluation scope/cutoff, effective authority, and calculation completeness.

**Retained inventory is not an approved evaluation pool.** Both `evaluation_scope` and `evaluation_cutoff` remain `None`; documented policy-pending reasons remain present. The application closing date is not silently adopted as the evaluation cutoff. Noncandidate admission remains a separate unresolved finding, not an implicit exclusion policy.

Missing, rejected, disputed, expired or stale required evidence does not remove an eligible-status application. Its entry and blocking reasons remain visible. Verified numeric zero remains different from a missing assessment. Actual membership/eligibility/source review still comes from G12; the existing G15 adapter replays current G14 weight evidence. Old diagnostic snapshots are not current authority.

The private manifest records application ID/version/status/submission timestamp and source/readiness digests. The program policy-context digest covers the current evidence/configuration/validation/review/scoring-proposal context. G12 source digests cover member/profile, documents and current bytes/reviews, photo, eligibility audit/checklist, approval/terms and cross-program release-state dependencies. The output retains no raw income, employment text, names, documents, scores, weights, contributions or numeric ranks.

Two independent autocommit observations must match, including evaluation date/timezone. The service rechecks fresh staff/account permissions and rejects an outer transaction to avoid a caller's old repeatable-read snapshot. A changed observation returns `POOL_CONTEXT_CHANGED`, empty ready/manifest/item lists, and no context token. At **128 retained applications**, inspection is supported; above that engineering ceiling the whole inventory is explicitly unsupported, without returning a successful page. This is not a business population limit.

`recheck_program_pool` resolves current sources again and compares the diagnostic context. A wrong-program, changed, missing or malformed digest cannot become authority. Stable diagnostics remain `calculation_complete=False`, `effective_authorization=False`, `operational_ready=False`, `persisted=False`.

`request_recalculation`, `process_recalculation` and `current_pool_result` check the existing private-read permission baseline, then unconditionally raise `DURABLE_POOL_STORAGE_UNAVAILABLE` before program/result queries or writes. They are reserved, disabled service contracts, not functional durable request APIs. No new action permissions are invented or granted. Setting `EWAF_OPERATIONAL_BACKEND_ENABLED=True` cannot bypass them; no runtime enable flag was added.

## 5. Persistence, concurrency, rollback and privacy limits

**Not delivered:** accepted numerical applicant input resolution, whole-pool numerical runs, permanent requests/attempts/results/traces, predecessor chains, source outbox, current pointer, durable invalidation, retries/deduplication, crash recovery, generation-based promotion, atomic result-graph audits or an operational consumer.

The new services execute no INSERT/UPDATE/DELETE and do not create a mutex/control row on reads. Tests compare all registered model rows before/after and reject non-SELECT SQL. Existing G15 `READINESS_ONLY` storage and legacy history remain unchanged; source/audit writers are not extended.

Seven tests coordinate **real separate MySQL connection IDs** around the two observations. Committed member status changes, document revocation, new evidence, new configuration validation, pool entry, cross-program actual release, and cross-program void all prevent a stable diagnostic capture. These are source-change detection tests, **not** concurrent durable promotion/idempotency tests.

Two equal observations do not guarantee that no write occurs immediately afterward. A changed-then-restored context (ABA) may also evade observation without a durable generation/event. Accordingly no readiness digest is an operational acceptance token. The service installs no new source locks or generation mechanism and does not claim those guarantees.

The existing Member-first audit failure path is tested: a failed required member audit rolls back its status/version change, and the pool context stays unchanged. A failed/interrupted read creates no partial records. This is not evidence of result-graph atomicity; there is no new result graph to commit. Repeated calls to disabled processing produce no successful effects, but durable retry semantics remain unimplemented.

Permission checks occur in services, before private reads, and fresh permissions are checked again during inspection. Raw exception messages are suppressed for recognized evidence-read failures. Output is private because it contains internal record IDs and readiness information; it must never be logged wholesale or exposed publicly. No API/view/button/job/management command was added. Actual private uploads and application database records were not read by this task; test evidence files are fictional and temporary.

## 6. Test isolation and exact commands

Inspected `scripts/g12_test_runner.py` before use. It uses the existing MySQL **binary only**, creates a fresh temporary datadir, binds an unused loopback port, verifies `@@datadir`/`@@port` and an initially empty instance, and restricts the synthetic account to `g12_empty` and `test_g12_disposable`. The child environment is allowlisted, `PYTHON_DOTENV_DISABLED=1`, the application `.env` is not loaded, and PDAO enforcement remains disabled in the isolated child. It starts hidden processes and shuts down the disposable server in `finally`. Existing application credentials/datadir are not opened or changed.

Commands executed from the repository root:

```powershell
# Initial development run, before fixing the new helper:
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf.test_pool_services --noinput

# Corrected focused tests and real MySQL observation races:
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf.test_pool_services ewaf.test_pool_concurrency --noinput --verbosity 2

# Every EWAF test, including current G12–G17 and historical preservation:
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf --noinput --verbosity 2

# Complete suite:
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test --noinput --verbosity 2

# Both checks also use new isolated instances; neither touches application data:
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py check --database default
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py makemigrations --check --dry-run

git diff --check
git diff --cached --check
```

The initial sandbox attempt stopped before MySQL initialization because writing its temporary `mysql.ini` was denied. It was rerun with the required tool escalation; the runner was not weakened or replaced. The first actual 34-test run had **5 errors**: the new test helper incorrectly passed `status` to an existing fixture that did not accept it. The helper was corrected to set the fictional application's status separately; no production guard or assertion was weakened.

| Run | Result | Runtime | Failures/errors/skips | Disposable artifact directory basename |
| --- | --- | --- | --- | --- |
| Initial actual focused | 34 run, exit 1 | 14.211 s | 0 / 5 / 0 | `santolan-g12-tests-gm_xb6qu` |
| Corrected focused | 42 passed, exit 0 | 21.596 s | 0 / 0 / 0 | `santolan-g12-tests-x868n26r` |
| All EWAF | 356 passed, exit 0 | 124.929 s | 0 / 0 / 0 | `santolan-g12-tests-0la0e6hy` |
| Complete suite | 851 passed, exit 0 | 240.716 s | 0 / 0 / 0 | `santolan-g12-tests-dvll9ai1` |
| System/database check | No issues, exit 0 | — | 0 silenced | `santolan-g12-tests-1n3mz4kc` |
| Non-writing migration check | No changes detected, exit 0 | — | Not applicable | `santolan-g12-tests-98d0hrnv` |

Directories are under the Windows temporary directory printed by the runner. Only Django logs, hashes and preservation evidence are retained in the task's ignored evidence directory; no connection configuration or datadir is copied into a review deliverable. Counts overlap and must not be added together. Existing Decimal/precision/exact-tie tests remain in the EWAF/full regressions; no new mathematical algorithm was added.

These are actual new test runs. The new full-suite count is the historical 809-test suite plus 42 new tests, but the result above comes from executing all 851 tests. Existing migration-preservation/concurrency tests ran in the disposable database. There are no new-schema migration/promotion tests because those features were not implemented. No browser suite was separately run; no UI was changed.

Both Git whitespace checks passed. All four new Python files parse successfully. Documentation links resolve. An auxiliary link-check first used Windows' default text encoding and failed to decode UTF-8 punctuation; rerunning it with explicit UTF-8 passed. This was a verification-tool issue, not an application/test failure.

Final evidence: `.local/ewaf-pool-backend-20261016/delivery-evidence.json` contains source and log SHA-256 hashes and the observed command exit codes. The verification helper also checks all pre-existing hashes/index identity, the exact new-file inventory, Python syntax, trailing whitespace/conflict markers and test log counts/verdicts. The parser was corrected for Windows CRLF and two existing tests that print management-command output before their `ok` line. These packaging corrections did not change test source or results. Temporary log access required tool escalation; no database configuration/datadir was copied.

Full-suite log SHA-256: `a96f418bfc4dafd8d915919ed210a6064ac5fdd74ba6e05b4d4e170f4aa88e62`. Focused log: `718c9b56bc7b4868c560343f408b7b9373bb407911fee30fa4354d5f94c6b0a8`. EWAF regression log: `90e98e9241215f41fbb9070292f92475d8d5efeac7419ab1c892325111fdb8a0`. Local logs and hashes are review evidence, not signed CI attestation or owner/client acceptance.

## 7. Remaining work and development position

The accepted 70% milestone is preserved. Stage 8 is still incomplete. G12/G14/G15 foundations, G16 synthetic ranking and G17 synthetic history retain their existing limits. This new checkpoint adds read-only complete-inventory diagnostics, not another accepted percentage or real recalculation history.

To continue the durable increment, identify/record explicit authorization for new additive schema creation and applying it only to disposable test databases, then implement the separate proposal. Application-database migration, live activation and deployment remain separate. The existing G06-B2/B3 processing dependency remains intact.

Association policy decisions remain explicit: income basis/period; ES definitions/encoding; dependent definition; PR rubric; PA measure/window/cutoff/direction; all criterion directions/bounds and evidence rules; classification; true ties; authority/effective dates/officer scope; admission/cutoff; correction/repeat/revision rules. No example or fixture was seeded as approved policy. Classification, waitlist, guided Admin UI, selection, Results publication, reports, membership/photo/PDAO changes and production work remain outside this increment.

This is the user's schema-absent fallback delivered for review. **Permanent calculation and recalculation/history remain unfinished; live use remains disabled.**
