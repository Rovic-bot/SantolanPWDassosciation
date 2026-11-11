# G18-B Gate 2D-2A validation and source coverage

2026-10-18. **Accepted milestone: 70%.** Disposable-only development of application
submission and administrative closure. Operational EWAF, ranking, selection,
publication and development-result promotion remain disabled. The four-criterion
proposal remains inactive. Stop at Gate 2D-2A; no later increment is authorized here.

## Checkpoint and preservation

Branch `feature/events`; HEAD `949eeda33c6aa5d8ee03962209ae8fedeac58ad1`.
Before editing, captured status, branch, HEAD, staged binary diff, index hash,
582 baseline file hashes and exact bytes of the three selected existing modules.
Read repository instructions, current specification, development guide, Open
Decisions, Gate 2A design/lock graph and Gate 2B/2C/2D-1 validation. TARGET policy
requirements are not operational authorization. No policy gap was resolved by code.

**579 of 582 baseline entries remain byte-identical.** Only the three existing
modules listed below changed; three repository files are new and none is missing.
Branch, HEAD, staged index and staged binary diff remain identical. Removing the
three integration lines and restoring the original file-list initializer reconstructs
the exact prior `programs/services.py` bytes, including its mixed line endings.
One accidentally altered original CRLF was restored with an AST-equality assertion;
this whitespace-only restoration did not change executable behavior.
Every existing test, model, migration, mathematical engine, Gate 1 observation,
excluded writer and UI asset retains its prior hash. The foundation's only changes
are the narrowly guarded system-provenance extension listed below.

Preserved index SHA-256:
`731c74ba7d747938181fbc4140139120a01c4ac5d676ac9607f3ff30ef718338`.
Preserved staged binary-diff SHA-256:
`64b8c580177e3d43c8c4fa863df77e81193c66a95071b4508f0f25b28e0fded6`.
Migration leaves remain accounts 0001, announcements 0004, assistance 0003,
audit 0002, core 0001, documents 0003, events 0006, ewaf 0006, members 0003,
membership 0004 and programs 0005; the unchanged migration bytes and drift check
support this preservation statement.
The application database and its migration recorder were not queried. The prior
checkpoint reports EWAF 0006 unapplied there; this gate does not independently
query or alter that application state. No remote checkout, private records or
private uploads were accessed. Environment configuration is hashed for preservation,
not loaded by tests or included in the review archive.

## Exact repository inventory

| File | Change |
|---|---|
| `programs/services.py` | One import, two outer decorators and the submission file-list initializer. Original grant/form/business validation, reference allocator, native audits, cleanup and closure body remain intact. |
| `ewaf/generation_records.py` | Add the internal `VERIFIED_MEMBER_SUBMISSION` system code to the existing service-level allowlist. No field/choice/schema change. |
| `ewaf/generation_services.py` | Validate that this new system code describes exactly a submitted application, one matching actorless native ProgramLog, its actual owning program and a SOURCE_CHANGE batch. It cannot label an authority event or unrelated source mutation. All pre-existing code paths and digest formats remain unchanged. |
| `ewaf/application_invalidation.py` | New bounded adapter for the two application writers, separate from the Admin-oriented Gate 2D-1 adapter. |
| `ewaf/test_application_writers.py` | New 47-test fictional submission/closure, audit, rollback, concurrency, history and capability suite. |
| This report | New validation, scope matrix, lock findings, limitations and package inventory. |

Review artifacts are under `.local/g18-b-gate2d2a/`. They are not staged.
No Membership, Members, Documents, Assistance, Events, PDAO, UI, route, settings,
mathematical engine, Gate 1 observer, Gate 2C authority writer or Gate 2D-1 adapter
is changed. No migration or schema is created. All eight foundation models remain
unchanged, with their original constraints, permissions and non-promotable contract.

## Source mutation and native audit coverage

All COVERED entries mean **only inside the existing registered disposable session**.

| Path / outcome | Scope and audit evidence | Result |
|---|---|---|
| New `submit_application` | Program from actual service argument; member from existing server-held verification grant. One actorless `ProgramLog(submitted)` tied to that exact application/program. | COVERED: application, reference counters/public code, initial document/photo/review rows, native audit, one SOURCE_CHANGE batch/invalidation and generation/revision +1 commit together. |
| Newly retained application after a fictional evaluation cutoff | Same actual program; no cutoff-based invalidation filter. | COVERED: advances generation even when not admitted by a historical fictional calculation contract. Pending/incomplete applications stay in retained inventory. |
| Valid duplicate submission | Existing application locked before Member; unchanged application/evidence/case graph, no native audits or saved-file journal entries. | COVERED NO-OP: same reference, no counter increment, new upload or invalidation. A stale generation token still rejects rather than disguising a stale request as a fresh no-op. |
| Expired/wrong-scope grant; changed/inactive member; unavailable program; invalid form, version or evidence; closed duplicate | Existing writer validations retained. | REJECTED: no successful source transition; no retained partial submission or consumed reference. |
| `change_application` to CLOSED without case | Program derived from application ownership before source locks. Fresh authorized staff actor; exact `ProgramLog(application_updated)` status transition. | COVERED: one program invalidation. No eligibility case is created. |
| Closure with existing case | Same ProgramLog plus exact `AssistanceLog(application_cancelled)` with actual before/after case snapshot and matching actor/application. | COVERED: existing review/pending reset, application closure and both native audits commit with one program invalidation. |
| Already closed, non-CLOSED transition, approved case, successful release, stale application version, blank reason or revoked permissions | Existing restrictions retained. | REJECTED: no new status/selection/reopening capability or successful invalidation. |
| Missing/extra token scope, missing state, malformed token, stale source/authority/revision/pointer | Exact four-field foundation token validated against one server-derived program. | REJECTED before successful mutation. No implicit state initialization. |
| Photo correction/review, linked Events, EWAF diagnostic/readiness persistence | Outside this increment. | DEFERRED; existing conservative Gate 1 audit dependencies remain intact. |
| Assistance eligibility/decision/release/void writers; membership/member/document/reference writers | Implementations unchanged. | UNFENCED/DEFERRED for generation coverage. Closure may call existing read/snapshot/audit helpers, not a broader Assistance mutation service. |
| Raw ORM/SQL, shell/imports, external files, other processes | No application integration guarantee. | OUTSIDE CONTRACT. Tests use explicit adversarial fixture writes only to demonstrate denial, not to authorize those paths. |

No account is required for public submission. The new system code is selected by
the trusted adapter, not by request data; actor is null, label/reason are fixed and
native actor remains null. No Admin actor is fabricated. Audit payloads contain
source identities and existing versioned native-audit hashes, not grant tokens,
member names, passwords, upload bytes or request bodies. Original native private
records retain their existing protection. System-code cross-record checks are
service-enforced, not new SQL constraints; the existing actor/system XOR remains
database-enforced. Old digests are not recalculated or reinterpreted.

## Transaction and lock graph

Inspection confirmed that submission already owns Terms -> Program -> Member and
allocates references within its transaction. Closure originally owns Program ->
Application; its Assistance helper calls do not acquire Terms or another Program.
The new adapter owns the complete outer boundary before any original source lock:

```
reject unowned outer transaction
Terms mutex -> AuthorityGeneration -> resolve one actual program
-> Program -> ProgramSourceState -> validate exact expected token
-> existing Application (plain query, no joined photo lock) -> Member
submission: original checks/form -> reference counters -> new application/evidence
closure: EligibilityStatus(review) -> existing AssistanceCase -> original closure
-> native audit set/content/scope and fresh authority/session checks
-> SourceMutationBatch -> SourceInvalidation -> generation/revision CAS
-> final batch/state/authority validation -> root COMMIT
```

Nested original Terms/Program/Application/Member locks re-enter rows already held
by the same transaction; they do not first acquire a lower-order lock after a
higher-order lock. Program scope is resolved before Program locking, never from
the expected-token map. No event row is mutated or locked here; linked availability
is still checked by the original writer under Terms. ReferenceCounter remains
serialized by Program; ProgramCodeCounter follows Member as before. New rows follow
their existing parents. Closure explicitly locks review status before Case so its
existing FK update does not first acquire the status row after Case.

The unchanged Assistance services also lock Program before Application/Member/case
writes and do not subsequently acquire Terms. A real two-connection test holds
closure at invalidation, observes the unchanged eligibility review waiting, then
verifies that review rejects after closure commits. This resolves the bounded
closure integration without editing Assistance services. It does **not** integrate
Assistance release/void generation fan-out or prove global deadlock freedom.

Captured SQL assertions verify the first Terms/H/P/S/A/M locks, no joined photo
lock, the submission counter order and closure's status/case order. Separate
connection IDs and controlled waits prove one winner for two same-token submissions
and two closures. If the first writer fails at invalidation, the waiting writer
commits using the still-valid token. No automatic retry masks a failure.

## Atomicity, files and historical behavior

Native ProgramLog/AssistanceLog actions, actor, application/program and closure
status/case snapshots must match exactly. Missing, duplicate, extra or inconsistent
audit scope rejects the transaction. The batch lists both audit families when a
case exists. Global audit high-water observations conservatively reject unexplained
concurrent new native logs; they are not a general event-capture mechanism.

The submission's existing saved-file list joins a private ContextVar journal only
inside the verified adapter. Original exception cleanup remains; outer cleanup also
runs for native validation, generation audit, CAS, final validation or commit
failure after the original writer returns. Only newly saved files are journaled;
reused protected membership document paths are never added. Database rollback
restores counter/public-code state and removes new application/photo/document rows.
Tests verify actual temporary photo/document files and that the next successful
submission still receives the first available reference. Cleanup remains the
existing best-effort storage deletion: an OS/storage deletion failure or process
crash is not claimed to be an atomic filesystem transaction or recovered by a new
reconciliation worker. Successful files remain private.

Application ABA is tested by closure followed by an explicit adversarial raw fixture
restoration. Restoring status/version does not restore the old generation token.
No supported reopening transition is introduced; raw restoration is not authorized.

Historical durable runs, snapshots, numerical digests and request/run binding
digests survive new submission/closure. Immutable bindings still validate and
historical numerical replay remains available. Such history is never described as
currently usable. No existing result becomes current; source pointers stay null,
operational result access raises, and DevelopmentPromotion remains unavailable.

## Capability and remaining limits

Registration reuses Gate 2C's process-local capability tied to actual fresh MySQL
database/server identity, temporary media and audited bootstrap. No caller boolean,
setting, UI action, request field or source token activates it. The private
`source_expected` argument is a concurrency precondition for development tests,
not a public authorization grant. No Public/Admin token plumbing is added. Ordinary
unregistered calls follow the original writer without foundation-table queries;
supplying a token without registration is denied. Registered calls require tokens.

Member verification, dates, requirements, original PDAO checks, duplicate behavior,
reference format and privacy remain unchanged. There is no member login or online
Association membership registration. Selected writer coverage cannot certify
unfenced mutations, cross-program receipt/void changes, external file tampering,
expiry or full-system freshness. Gate 1's conservative audit dependencies and
`g18-2b-foundation-nonpromotable-1` remain unchanged. Full program graph equality
reads and the global Terms mutex are intentionally coarse; production performance
and deployment are not accepted by this validation.

## Actual validation

Every command below runs through a separately initialized fresh loopback MySQL
8.4.11 instance, READ-COMMITTED, all test tables InnoDB, `.env` disabled, isolated
database grants and fictional temporary media. The test runner verifies actual
database/server/datadir identity before and after test DB creation. No keepdb or
application DB connection is used. Harnesses shut down their own server in finally.

Command prefix:

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py
```

Tests append `test [label] --testrunner scripts.durable_test_runner.DurableTestRunner --noinput`.
Labels: `ewaf.test_application_writers`, `programs`, `ewaf`, or no label for full suite.
Checks append `check --database default` and `makemigrations --check --dry-run`.
Whitespace checks use `git diff --check`, `git diff --cached --check`, plus the new
file whitespace scan in the review builder. Neither Django check command accesses
the regular application database.

| Run | Actual result | Seconds |
|---|---|---:|
| Focused initial | 40 run; 1 failure, 30 errors, 0 skips | 25.136 |
| Focused corrected | 40 passed; 0 failures/errors/skips | 25.577 |
| Focused expanded final | 47 passed; 0 failures/errors/skips | 40.159 |
| Programs | 150 passed; 0 failures/errors/skips | 117.935 |
| EWAF | 592 passed; 0 failures/errors/skips | 566.128 |
| Full project | 1,185 passed; 0 failures/errors/skips | 861.443 |
| Django/database checks | No issues (0 silenced) | - |
| Migration drift | No changes detected | - |

Working and staged `git diff --check` passed. New files have no trailing whitespace.
Git's pre-existing working-copy line-ending warnings are retained as warnings, not
test failures; no broad newline normalization was performed. The full suite includes
all 1,138 previously reviewed tests plus the 47 new tests; no existing test was
removed or edited. Reported durations are test-runner timings, excluding MySQL
initialization/migration setup. Independently isolated regression/full runs may
overlap in wall time; they never share database instances or fixture media.

Initial failures were an implementation assumption that the application PK was
`id` (it is `reference`), missing eligibility-status fixtures after TransactionTestCase
flush, and a dependent concurrency timeout before invalidation was reached. The
adapter now reads the model PK attname; fixtures explicitly seed their fictional
statuses. New helpers no longer perform an unnecessary token inspection when an
explicit test token is supplied. No original test/permission/version guard was
weakened. The corrected 40-test rerun passed; seven additional security/audit/race
cases were added and all 47 passed. These are manual corrected reruns, not hidden
automatic retries. Initial logs are included in the package.

## Review package

The ZIP is a scoped delta, not a replacement checkout. Retain all existing local
staged/unstaged/untracked work; HEAD alone does not represent the baseline. It
contains exact changed/new source and tests, this report, unchanged foundation/
lock/session/runner references, sanitized fictional logs, baseline-relative diff,
preservation evidence, per-file manifest and SHA256SUMS. A separate SHA-256 file
covers the ZIP. Credentials, environment content/hash, database/configuration
files, private records and uploads are excluded by explicit allowlisting.

No staging, commit, push, merge, reset, clean, stash, pull, deployment, application
database migration or later-gate implementation was performed. **70% remains the
accepted milestone. Stop for owner review after Gate 2D-2A.**
