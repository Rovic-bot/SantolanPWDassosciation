# G18-B Gate 2B — additive persistence foundation validation

2026-10-18. Accepted milestone: **70%**. Gate 2B only; no Gate 2C–2F writer
integration or result promotion. Operational EWAF scoring, ranking, beneficiary
selection and public EWAF publication remain disabled. The four-criterion proposal
is separate and inactive; no policy, effective date or authorized program scope is
inferred from these technical foundations.

## Local checkpoint and preservation

Branch `feature/events`, HEAD `949eeda33c6aa5d8ee03962209ae8fedeac58ad1`.
Before editing, captured the branch, HEAD, staged binary diff, complete porcelain
status, tracked/untracked file hashes, index hash and configuration-file hash.
The baseline has **568 entries**. Configuration was hashed, never loaded into the
test environment. The application database and private member uploads were not read.

Five existing files change: model registration, the precise local startup
compatibility dependency and three migration-leaf test assertions described below.
The remaining **563 baseline entries**,
including every historical migration, source writer, mathematical engine, existing
test except those three assertions, Gate 1 observer, UI asset, four-criterion reference, index and configuration,
remain byte-identical. No baseline file is deleted. Branch, HEAD and staged diff
remain identical. No stage, commit, push, merge, reset, clean, stash, pull or deploy.

## Exact repository change inventory

| File | Change |
|---|---|
| `ewaf/models.py` | Append registration imports for the eight new models only. |
| `core/management/commands/runlocal.py` | Add an exact SHA-256-pinned deferral for reviewed EWAF 0006; preserve startup while it remains unapplied. No migration execution, fake application or table access added. |
| `ewaf/test_pool_services.py` | Change only the expected latest migration from 0005 to authorized 0006. |
| `ewaf/test_ranking_preservation.py` | Change only the expected migration leaf; preserve all existing staged/unstaged test content and numerical/permission guards. |
| `ewaf/test_recalculation_preservation.py` | Change only the expected migration leaf; preserve zero-write, schema/route/permission and operational-denial assertions. |
| `ewaf/generation_models.py` | New eight-table model definitions, protected relationships, checks and indexes. |
| `ewaf/generation_records.py` | New service-owned mutable-state and append-only record guards; versioned UTC-normalized canonical payloads. |
| `ewaf/generation_services.py` | New disposable-only initialization, audit, generation, CAS, consistency and private non-promotable sidecar primitives. |
| `ewaf/migrations/0006_source_invalidation_foundation.py` | New authorized additive migration; eight creates, four deferred links, new-table indexes/checks only. |
| `ewaf/test_generation_foundation.py` | New foundation, permissions, SQL constraints, rollback, concurrency and startup-pin tests. |
| `ewaf/test_generation_bindings.py` | New immutable sidecar, replay, stale intent, expiry, graph and non-promotion tests. |
| `ewaf/test_generation_migrations.py` | New real MySQL forward/reverse/reapply and old-schema/startup preservation test. |
| This report | New validation and review boundary. |

The startup dependency matters: the existing command rejects any pending migration
outside its exact reviewed allowlist. Merely adding 0006 would therefore stop the
previously accepted local startup with deferred development tables. The additional
entry pins **only this reviewed file** and retains all changed-file, reverse-plan,
unknown/future-migration and unrelated-migration denials. Existing startup tests
remain unchanged. No source writer, setting, route, Admin registration or UI changes.

## Eight-model schema

| Model | Persisted purpose and principal safeguards |
|---|---|
| `AuthorityGeneration` | Singleton ID 1; generation and protected last-event tail. Zero is only a transactional bootstrap state. |
| `AuthorityInvalidation` | UUID mandatory authority audit; consecutive globally unique generation, kind/subject allowlists, actor-or-system provenance and native-audit references. |
| `ProgramSourceState` | Program primary key; generation, revision, protected invalidation tail and nullable candidate binding. No pointer is populated by any supported Gate 2B operation. |
| `SourceMutationBatch` | UUID operation audit; source identity, native audit references, sorted complete supplied scope digest/count and reasoned provenance. |
| `SourceInvalidation` | Protected batch/program/cleared binding; consecutive generation/revision; unique program-generation and batch-program pairs. |
| `RequestSourceBinding` | Protected request primary key; expected generations/revision/pointer, exact Gate 1 snapshot, context/inventory/submission digests, protocol/coverage/engine, aware deadline/timezone. |
| `RunSourceBinding` | Protected run primary key and unique request binding; replay-validated ordered graph digest and complete retained/eligible counts. |
| `DevelopmentPromotion` | Future immutable promotion audit schema only; unique new binding and program-revision, consecutive revision, positive generations and distinct prior/new binding. Recording is denied in Gate 2B. |

Every generation/revision uses a PositiveBigIntegerField with explicit SQL bounds
`0..9223372036854775807`; increment at the upper bound is refused, never wrapped.
Request-bound generations/revision and promotion generations must be positive.
All new FK/O2O relationships use `PROTECT`. All eight models have
`default_permissions=()` and no editable Admin registration.

SQL enforces row checks, nullability, foreign-key existence, unique/O2O identities,
sequence arithmetic, counter bounds and declared indexes. Cross-program equality,
audit-tail agreement, complete batch scope, native audit identity/content, graph
replay, expected state and cross-table revision consistency are **service-enforced**.
Raw SQL can create a structurally valid row without a valid service audit/digest;
tests demonstrate that distinction rather than claiming database tamper-proofing.
MySQL creates a supporting index for the AuthorityGeneration FK even though no
additional application index is requested (`db_index=False`); this is required by
InnoDB FK enforcement, not an extra business lookup index.

## Migration and SQL review

Dependencies are exactly EWAF `0005_durable_development`, Programs
`0005_approved_terms`, and the swappable user-model dependency. Other application
migration leaves remain unchanged. The migration has eight `CreateModel` operations
first, followed by exactly these four `AddField` operations:

- RequestSourceBinding.expected_current_binding
- AuthorityGeneration.last_event
- ProgramSourceState.last_invalidation
- ProgramSourceState.current_binding

Then add new-table indexes and constraints. No RunPython/RunSQL, seed, data backfill,
old-table alteration, approved-policy record or automatic bootstrap/promotion.
The nullable candidate-pointer column is part of the approved schema; it is not an
operational current-result pointer or a consumer-facing capability.

Generated SQL was inspected **before the first test applied 0006**. It contains
**71 statements**, eight new table creates, **17 foreign keys**, **38 named CHECK
constraints**, three named composite unique constraints, five explicit secondary
indexes, and implicit PK/unique/FK indexes. Every ALTER targets one of the eight
new tables. No INSERT, UPDATE, DELETE, DROP, TRUNCATE or historical-table ALTER.
The initial generator order was rearranged to match the approved eight-create /
four-link order; the final state passes migration-drift verification.

Normalized migration SHA-256 (also pinned by startup):
`b7a9a78aa36de0fb05c0ca57bce6596caf8d337c56b4394f9411a7c9d6874540`.

SQL evidence SHA-256 after UTF-8 text normalization:
`f01596bdad212af291a17619f24f9dcbd3bc9302d1107f73d34889c196390bef`.
The review package additionally records exact file-byte hashes.

Actual MySQL introspection verifies each declared check/unique constraint, explicit
index columns and FK presence. Direct SQL probes exercise invalid sequences,
bounds, singleton/tail shapes, actor XOR, choices, duplicate audit identities,
request deadlines/protocol/generations, graph counts and promotion row checks.
DDL reverse/reapply is tested only on disposable fictional rows. MySQL DDL is not
represented as rollbackable application-data work or a production recovery plan.

## Services and transaction boundaries

Public foundation helpers first require top-level autocommit and the existing
durable permission set. The existing runner must attest the actual fresh MySQL
database/server identity and temporary fictional media directory. The actor is
reloaded and reauthorized under the fence and before transaction exit; cached
permissions or a caller-provided synthetic flag grant no capability.

Lock order for this bounded foundation is **Terms -> Authority -> all Programs
by PK -> all ProgramSourceStates by Program PK**. No source leaves are mutated.
An internal ContextVar binds record writes to the actual connection and outer
transaction. Arbitrary outer transactions and unowned ORM writes are refused.

- Authority initialization creates zero state, INITIALIZE audit and generation-1
  CAS in one transaction. Existing valid initialization is idempotent; orphaned or
  inconsistent state is not reset or silently approved.
- Program initialization requires the expected current authority generation and
  nonempty valid scope. It creates zero states and a mandatory complete INITIALIZE
  batch/transitions to generation=revision=1, with null pointers, atomically.
- Authority advance writes its immutable event and updates the expected prior
  generation/tail with exactly one affected row. It does not fan out program state.
- Source advance verifies every supplied expected token, writes one batch and one
  transition per supplied program, increments generation/revision and clears the
  expected pointer through exact CAS. Scope/tails are revalidated before commit.
  Missing state, stale authority/source/revision/pointer, duplicate scope or overflow
  denies the whole operation. String and UUID program identities normalize safely.
- Native audit references use an allowlisted model, PK, action and versioned content
  hash; private native text is not copied. Missing, changed, duplicated or previously
  accounted references are rejected. SOURCE_CHANGE requires native audit evidence.
  No existing audit format is rewritten. Generic references are not database FKs.
- Audit insert, state update, second-program transition, final validation or final
  authorization failure rolls back the entire foundation operation. No on_commit
  generation job, asynchronous audit or partial-scope commit exists.
- Append-only history denies supported save/update/delete/bulk/upsert replacement.
  Immutable records use `g18-generation-record-1`; scope, inventory, submission,
  native-audit and graph hashes also have explicit new version tags. Aware timestamps
  normalize to UTC for stable MySQL round trips. Existing digest functions/payloads
  and numerical engines are unchanged.

Private `_bind_request` / `_bind_run` are low-level foundation test primitives,
not generation-aware acceptance/processing workflows. They retain exact old
snapshots, enforce expected tokens and bounded aware deadlines, reject conflicting
retries, validate complete historical graphs and never populate a current pointer.
Coverage is fixed to `g18-2b-foundation-nonpromotable-1`; engine profile is fixed to
`durable-pool-development-2:historical-five-1`. DevelopmentPromotion recording is
unconditionally denied, including inside the private owned context. No current
facade, dispatcher, ranking, selection or publication consumer is added.

## Actual validation results

| Run | Executed tests | Time | Result |
|---|---:|---:|---|
| Initial foundation tests | 42 | 80.067s | Passed; intermediate implementation. |
| Expanded foundation tests | 47 | 76.576s | Passed; intermediate implementation. |
| Final foundation + existing startup regression | 60 | 160.864s | Passed; 52 new tests plus eight existing startup tests. |
| Corrected migration-leaf assertions | 3 | 3.502s | Passed. |
| Initial EWAF regression | 509 | 577.042s | Three outdated migration-leaf assertions failed; corrected below. |
| Initial full project | 1,051 | 846.019s | Same three failures; no additional failures. |
| Final EWAF regression | 509 | 511.357s | Passed; zero failures, errors or skips. |
| Final full project | 1,051 | 784.474s | Passed; zero failures, errors or skips. |

Django/database checks pass with zero issues. Migration-drift verification reports
`No changes detected`; the read-only migration plan succeeds. Both working-tree
and staged `git diff --check` pass, with only pre-existing line-ending notices.
New/untracked files also pass an explicit trailing-whitespace check. No tests were
skipped in the completed runs. Full suite retains all original 999 tests and adds
52 new tests; the earlier 999 baseline is not presented as a newly executed run.

The first complete EWAF run executed **509 tests in 577.042s** with **3 failures**:
`PoolServiceTests.test_schema_unchanged`,
`RankingPreservationTests.test_no_schema_models_or_permissions_added`, and
`RecalculationPreservationTests.test_no_new_models_schema_permissions_or_routes`.
Each expected 0005 to be the latest migration. Only those three expected values
were updated to the explicitly authorized 0006; no test was removed, skipped or
weakened to accept arbitrary future migrations. The new migration tests separately
enforce the exact eight-table/four-link additive boundary. Corrected targeted and
full rerun results are recorded in the table above.
The concurrently running first full-project suite executed **1,051 tests in
846.019s** and reported the same three migration-leaf failures, with no additional
failures or errors. It had imported the old expectations before the edits; its
traceback source lines reflect the subsequently edited files. Both original
failure logs are retained in the package rather than replaced by successful reruns.

All Django/MySQL commands use `.venv\Scripts\python.exe -B scripts/g12_test_runner.py`.
Test commands additionally specify
`--testrunner scripts.durable_test_runner.DurableTestRunner --noinput`.
No `--keepdb` or application settings/credentials are used. Each command initializes
its own empty loopback MySQL instance with isolated grants; tests create/destroy
`test_g12_disposable`, attest server/datadir identity, require InnoDB and use
READ COMMITTED. Servers are shut down by the existing harness.

Executed command scopes:

```text
makemigrations ewaf --name source_invalidation_foundation
sqlmigrate ewaf 0006
test ewaf.test_generation_foundation ewaf.test_generation_bindings ewaf.test_generation_migrations core.test_local_startup
test ewaf
test
check --database default
makemigrations --check --dry-run
migrate --plan
git diff --check
git diff --cached --check
```

The successful read-only migration-plan rerun uses Python `-X utf8` before `-B`.
The first plan attempt encountered a Windows cp1252 console UnicodeEncodeError
while printing an older auth migration description; no DDL was applied. Its UTF-8
rerun exits successfully (the legacy description retains one replacement glyph,
which does not affect migration identities/operations). The initial sandboxed
harness attempt could not write its new temporary MySQL configuration and was
rerun with the required filesystem approval. These are recorded command/environment
failures, not hidden passing tests or application-data operations.

## Concurrency, rollback and historical evidence

Separate real MySQL connections prove concurrent bootstrap converges to one audit
and generation; identical expected source tokens produce exactly one winning
transition; another connection observes neither an uncommitted audit nor its CAS
until commit. These are foundation-fence tests, not tests of future source writers.
Both source and authority stale CAS row-count checks are exercised. Injected failures
at audit, state and final-validation boundaries leave no partial batch or generation.

Forward/reverse/reapply compares complete ordered rows from every pre-existing
model, existing migration-recorder rows, old graph digests/JSON/FKs and both legacy
version-1 and Gate 1 version-2 numerical replay. Old replay works while all eight
foundation tables are absent. New tables start empty and reapply empty. Bootstrap
does not make old results current. Stale sidecars remain immutable and replayable;
old request/run snapshots and digests remain unchanged.

Startup compatibility is exercised with the actual old-schema fixture and a SQL
wrapper admitting only SELECT/SHOW. Existing pending-schema portal/startup tests
remain part of the unchanged full project suite. No listener or application server
is started against the existing application database.

## Limitations and next authorization boundary

1. No shared source writer or account mutation is enlisted. A caller-supplied scope
   is internally checked, but these helpers do not discover the complete business
   impact of a member/document/permission/receipt change. Generation equality alone
   therefore makes no source-freshness or atomic-promotion claim.
2. Native source mutation and its audit will need a separately authorized outer
   writer integration sharing this transaction/fence. Gate 2B only atomically
   commits its own generation and mandatory new audits; it does not retrofit old
   writers through signals or hooks.
3. Full source recapture, policy/permission dependency coverage, generation-aware
   calculation orchestration, automatic expiry/replacement and current-result
   promotion/read services remain later gates. The sidecar deadline primitive does
   not derive an approved earliest source expiry or operational validity period.
4. Privileged SQL/Python, external file tampering, raw management mutations and
   trusted-clock failures are outside the supported ORM/transaction guarantee.
   Coarse Terms serialization and large-scope performance need later integration
   measurements; no measured deadlock-freedom claim is made for unintegrated writers.
5. Association measures, bounds/directions, PA lookback, need classifications/ties,
   approval roles, effective date and authorized program scope remain unresolved.
   PR removal approval does not activate the four-criterion weights or replace
   functional eligibility/evidence, consent, privacy and review requirements.
6. Migration authorization is disposable-only. Application/production deployment,
   applying 0006 there, changing source writers, or starting Gate 2C–2F requires
   separate owner authorization. A code rollback must preserve real audit history;
   disposable schema reverse tests are not permission to drop it.

The allowlisted review package contains source, migration, tests, this report,
Gate 2A design references, SQL, sanitized test/check logs and SHA-256 manifests.
It excludes `.env`, MySQL configuration/credentials, database files, private member
records/uploads and unrelated workspace files. Ignored local preservation evidence
remains in `.local/g18-b-gate2b/`.
The package is a scoped review delta for the preserved local workspace. Its HEAD
identifier does not replace the existing staged/unstaged/untracked G12–G18 work;
it is not a full repository backup or an instruction to restore an older remote.

Final test instance identities (all MySQL 8.4.11, READ COMMITTED, InnoDB; the
runner printed and verified the full temporary datadir/server identity):

| Run | Fresh temporary directory suffix | Loopback port |
|---|---|---:|
| Final focused | `eaa37466` | 61267 |
| Corrected assertions | `3n6jr1cf` | 55779 |
| Final EWAF | `c9er9s83` | 61887 |
| Final full project | `2dbxnf6m` | 61889 |

Review deliverables are in `.local/g18-b-gate2b/`:
`g18-b-gate2b-review-2026-10-18.zip`, `review-package.sha256`, and
`final-manifest.json`. The ZIP contains byte-level SHA-256 hashes and sizes,
`SHA256SUMS`, SQL review assertions, test-result JSON, original failure logs,
successful final logs and the incremental patch against the verified local
baseline. Archive membership and every member hash are checked after creation.

**Stop after Gate 2B for independent owner review. Accepted milestone: 70%.**
