# G18-B Gate 2D-2C linked-event validation

Work began 2026-10-18; validation continued 2026-10-19 (Asia/Manila).
**Accepted milestone remains 70%.** This increment integrates only
`events.services.save_event` and `change_publication` in verified disposable
development sessions. Operational EWAF, scoring/ranking, selection, public EWAF
results and development-result promotion remain disabled. The four-criterion
proposal remains inactive. Stop after Gate 2D-2C for independent review.

## Checkpoint and exact inventory

Branch `feature/events`, HEAD `949eeda33c6aa5d8ee03962209ae8fedeac58ad1`.
Before editing, captured branch, HEAD, status, staged binary diff, index hash,
588 baseline file hashes and original `events/services.py` bytes. Read AGENTS,
current specification, development guide, Open Decisions, October 10 impact,
Gate 2A design/lock graph and Gate 2D-2B validation. Documentation target rules
and unresolved OQ-05/OQ-16/OQ-26 policies were not treated as new authorization.

| File | Changes |
|---|---|
| `events/services.py` | One import, two outer decorators, one new-upload journal call, and a condition retaining old images only inside the adapter. Original Terms/atomic decorators, forms, guards and native audit calls remain. |
| `ewaf/event_invalidation.py` | New bounded transaction adapter, trusted old/new link scope, ordered locks, exact audit validation, multi-program batch validation and image journal. |
| `ewaf/test_event_writers.py` | New fictional integration, audit/rollback, file retention, SQL/concurrency and durable-history tests. |
| This report | New scope matrix, transaction/file findings, test evidence and limitations. |

Only one pre-existing file changes. Registration, attendance and annual-observance
functions in that file remain byte-identical. No models, migrations, URLs, views,
templates, Admin controls, CSS, PDAO enforcement, numerical engines, digest
implementations or pre-existing tests change. Foundation and earlier gate adapters
remain byte-identical. Review artifacts are under `.local/g18-b-gate2d2c/`.

## Source coverage matrix

COVERED below means only within the existing registered disposable capability.

| Path / outcome | Scope and result |
|---|---|
| Create event with validated program link | COVERED. Existing Program state required; one EventLog(created), one SOURCE_CHANGE batch/invalidation. No silent foundation initialization or program approval. |
| Edit linked event without changing link | COVERED. One owning program; exact EventLog(updated), source generation/revision +1. |
| Permitted relink from A to B | COVERED. Union of stored old link and validated proposed link; both Programs then both SourceStates locked in ascending PK order. One shared batch, exactly one invalidation per program. |
| Permitted unlink | COVERED. Old program invalidated once; no invented new program. Existing applications and protected terms still prohibit disallowed unlinking. |
| Link an unlinked event | COVERED. Proposed Program validated with the existing form field and current actor permission. Original full form/terms checks still run. |
| Unlinked create/edit/publication | Native business/audit transaction retained; zero program batches or invalidations. Empty expected scope required inside registration; global authority still checked. |
| Publish, cancel, withdraw, archive | COVERED. Existing transitions/reasons/versions remain. Exact EventLog(status action). No program state, approval, selection or PDAO record is changed. |
| Same visible form values | Original writer still increments Event.version and retains a new EventLog. This is a real conservative dependency change, so one invalidation remains appropriate. No native behavior is silently narrowed. |
| Failed form, stale event/token, missing source state, wrong/missing/extra scope | REJECTED with no successful generation transition. No partial fan-out. |
| Unauthorized/protected link or major terms change | REJECTED by existing permissions/guards. No new link/unlink authority, reapproval route or public RSVP. |
| Ordinary unregistered requests | Original accepted writer behavior and image retirement remain. No development-generation table queries, automatic registration, feature flag or UI token plumbing. |
| Registration, attendance, annual observances | UNCHANGED; no fabricated EWAF invalidation. Regressions include these modules; a separate-connection registration restoration contention test exercises the existing Event-to-Member path. |
| Other member/document/assistance writers, raw ORM/SQL, external file tampering | Not integrated by this increment. Full writer coverage and usable-result promotion remain unavailable. |

Scope is never taken from the expected-token map. Under Terms and Authority,
the adapter reads the actual current Event link, constructs the existing EventForm
for the current actor, and validates its Program ModelChoiceField against trusted
records. An actor lacking program-view permission cannot supply a new link; an
absent form field preserves the existing link. Full form/image/model validation
occurs once in the original writer. A later stored/proposed link mismatch fails.
One-to-one constraints, retained-application restrictions and protected-program
guards continue to apply. Direct link dependency is conservatively covered even
when the linked program currently uses a non-EWAF selection method.

## Transaction and lock evidence

Baseline inspection confirmed both services use Terms before Event, but acquired
no preceding Program/source-state locks. Event locking selects only Event (no
joined Program lock). Their forms/guards read linked programs afterward. The new
outer decorator owns the transaction before invoking either original service:

```
reject unowned outer transaction
Terms -> Global AuthorityGeneration -> fresh actor and trusted old/proposed scope
-> every affected Program, ascending PK
-> every affected ProgramSourceState, ascending Program PK; exact token checks
-> Event (existing row only)
-> original Terms/atomic writer, original validation, event and EventLog writes
-> fresh actor/session check, exact persisted result and native audit validation
-> SOURCE_CHANGE batch -> each invalidation and expected-value CAS
-> complete batch/tail/authority validation -> one root commit
```

Creation inserts its new Event after existing parents; there is no Event row to
prelock. Original nested Terms and atomic blocks re-enter already held locks and
savepoints. No new Program lock occurs after Event. Implicit EventLog/Event/User
FK writes remain inside the same fence. Actor authorization is re-fetched rather
than trusted from a cached permission result. Tokens are concurrency preconditions,
not activation flags; no caller-owned affected-program list is accepted.

Captured actual MySQL SQL asserts T,H,all P,all S,Event, including a permitted
high-PK-to-low-PK relink. The capture excludes separate preflight token inspection.
Separate MySQL connections establish:

- Two editors and two publishers with the same token: one commit, one stale rejection.
- Two same-intent relinks: one complete union commit; the waiter rejects the now
  inconsistent old scope. A changed scope is rejected before stale token comparison.
- First image writer rolls back; waiter succeeds with the still-valid token and
  no orphan from the failed writer.
- A connection holding Program can acquire Event NOWAIT while the integrated
  writer waits on Program. Event is not locked early.
- Existing registration restoration holds Event, then acquires registration and
  Member; it completes while an integrated event editor waits. Both commits retain
  their own audit, without changing the registration writer or inventing a generation
  for attendance/registration itself.

Connection IDs and lock-order messages are retained in the logs. These are bounded
runtime proofs, not a claim of deadlock freedom for every workload or unfenced
writer. No automatic retries conceal lock errors. Whole-operation retry, if later
introduced, must re-resolve scope and versions rather than retry only CAS.

## Native audit, rollback and historical preservation

The adapter requires exactly one new EventLog for the actual event, with no
registration association, and the precise actor/label, action, notes, address and
before/after changes. Missing, duplicate, foreign-event/cross-program or forged
records reject the transaction. Previously observed EventLog rows must remain
unchanged. The returned Event is compared field-for-field to the persisted row;
its identity, link, version, creator/updater and publication behavior are checked.
Affected Program rows must remain unchanged.

Native datetime spellings remain intact: form values may use Philippine offsets
while database reloads use UTC. Actual datetimes are compared by value, then the
validated original representation is used for native audit equality. IPv6 audit
addresses use the existing model field's normalization. No historical EventLog
digest format changes; the existing `g18-native-audit-1` reference is reused.

The batch references the exact EventLog through its existing canonical content
hash. Its scope digest/count, all program tails and generation/revision increments
are validated after CAS. A failure on the second program rolls back the first
program as well as the Event and EventLog. Partial-scope injection, native audit
failure, invalidation/CAS/final-validation failure and final permission revocation
are tested. No successful transition survives a failed transaction.

Global EventLog observations deliberately remain conservative; an unrelated
unfenced audit arriving during observation can abort an otherwise valid edit.
This does not narrow Gate 1 audit dependencies or assert all audit writers are
fenced. Historical records are protected by this workflow and digest replay,
not new SQL triggers or universal ORM guards.

A fictional historical five-criterion durable run and its request/run bindings
are retained across linked-event publication. Digests and snapshots remain
unchanged and replayable; historical access reports operational_ready false,
source pointers remain null and no DevelopmentPromotion exists. The fixture link
predates the audited development epoch; it is not permission to link a protected
program through a production workflow.

## Image lifecycle and storage limits

The original Event writer uses UUID image paths, validates decoded images and alt
text, records old/new paths in native audit changes and deletes the old image on
commit after replacement/removal. In registered sessions only, the adapter retains
that old file, preserving the audit's historical reference. Ordinary requests keep
their accepted retirement behavior. No new image-serving route or public historical
image access is introduced; existing protected/status-aware serving remains.

Only exact non-overwriting local FileSystemStorage is accepted in the registered
adapter. A forced filename collision verifies another name is allocated without
overwriting retained bytes. Custom or overwriting stores fail closed before mutation.

Newly saved uploads enter a ContextVar journal immediately after saving. Failures
inside the original writer still use its cleanup; late audit, CAS or final-validation
failures also clean that journal after database rollback. Only new paths are removed,
never the prior retained image. Tests hash real temporary file bytes before/after
replacement, removal, collision and rollback. Missing current images block registered
acceptance, and original publication/alt-text validation remains in force.

**Filesystem writes are not atomic with MySQL.** Cleanup is the existing best-effort
deletion contract. Process crash, OS deletion failure, external tampering, missing
historical bytes, durable orphan recovery and remote immutable storage remain explicit
limitations. Retention here does not establish an approved institutional retention
policy or a new immutable storage-version schema. Those need separate authorization.

## Workspace and migration preservation

587 of 588 baseline entries remain byte-identical; only `events/services.py` changes.
Three repository files are added; none is removed. The original service file can be
reconstructed byte-for-byte by removing only the import/decorators/upload journal
call and registered-session retention condition. This includes all annual-observance,
registration and attendance functions and the complete pre-existing local changes.

Branch/HEAD, staged index and staged binary diff remain unchanged. Index SHA-256:
`731c74ba7d747938181fbc4140139120a01c4ac5d676ac9607f3ff30ef718338`.
Staged binary-diff SHA-256:
`64b8c580177e3d43c8c4fa863df77e81193c66a95071b4508f0f25b28e0fded6`.

All model/migration bytes remain unchanged. Local per-app migration leaves were
inspected from dependency AST without accessing a database: accounts 0001,
announcements 0004, assistance 0003, audit 0002, core 0001, documents 0003,
events 0006, ewaf 0006, members 0003, membership 0004, programs 0005.
The application migration recorder was not queried. Prior application migration
status is preserved by not accessing that database. No production configuration,
private upload, real member record or application database was opened for this work.

## Actual test execution

All Django invocations use fresh independently initialized loopback MySQL 8.4.11
instances, generated credentials, isolated database grants, disabled `.env` loading
and fictional temporary media. DurableTestRunner verifies server/datadir/database
identity and all-InnoDB test tables; the reported isolation is READ-COMMITTED.
No keepdb. Test databases are
destroyed and their own servers shut down by the harness. No regular application
database command or migration was run.

Command prefix:

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py
```

Tests append `test [labels] --testrunner scripts.durable_test_runner.DurableTestRunner --noinput`.
Labels are `ewaf.test_event_writers`, `events programs`, `ewaf`, or omitted for full.
Checks append `check --database default` and `makemigrations --check --dry-run`.
Working/staged `git diff --check` and new-file whitespace checks are also run.

| Run | Actual result | Test-runner seconds |
|---|---|---:|
| Initial focused | 42 run; 42 errors, 0 failures/skips | 5.870 |
| Corrected/expanded focused | 47 run; 3 failures, 1 error, 0 skips | 48.896 |
| Corrected focused | 48 passed; 0 failures/errors/skips | 61.597 |
| Final focused | 49 passed; 0 failures/errors/skips | 55.412 |
| Events + Programs | 239 passed; 0 failures/errors/skips | 144.806 |
| EWAF | 692 passed; 0 failures/errors/skips | 667.309 |
| Full project | 1,285 passed; 0 failures/errors/skips | 991.105 |
| Django/database checks | No issues (0 silenced) | - |
| Migration drift | No changes detected | - |
| Whitespace | Working/staged diffs passed; new files checked during packaging | - |

Initial failures were fixture construction: the existing program factory already
sets status/publication fields, and the first historical fixture changed terms after
capturing its policy. The second run exposed missing fixture actor fields, an SQL
capture accidentally including preflight token-inspection locks, a relink rejection
assertion expecting stale-generation instead of changed scope, and an overbroad
query assertion matching the existing `ewaf_applicable` column rather than generation
tables. These were corrected without weakening business guards. The 48-test run
passed. A final IPv6 native-normalization test was then added. Initial logs and all
reruns are retained; no existing test changed. Test durations exclude initialization
and migrations; independent invocations may overlap without sharing databases/media.
Earlier focused runs loaded intermediate test versions while corrections and added
coverage were being prepared, so traceback line snippets can differ from the final
source. The final 49-test run and subsequent regression runs use unchanged final
implementation/test source; only reporting and package artifacts changed afterward.
The full suite contains all 1,236 baseline tests plus 49 new tests. The Events/
Programs, EWAF and full-project processes exited successfully and recorded test
database destruction. All requested checks completed; no skips or automatic retries
occurred in the final successful runs.

## Review package and stop boundary

The ZIP contains the exact four-file delta, unchanged dependency references,
baseline-relative patch, sanitized fictional logs, test results, preservation hashes,
manifest and SHA256SUMS. A separate checksum covers the ZIP. It is a scoped review
delta, not a replacement checkout. Credentials, environment content/hash, MySQL
configuration, databases and private uploads are excluded.

No staging, commit, push, merge, reset, stash, clean, pull or deployment occurred.
No Gate 2E work began. Complete writer coverage, time-based invalidation and atomic
usable-result promotion remain future authorized work. **Stop after Gate 2D-2C;
accepted milestone remains 70%.**
