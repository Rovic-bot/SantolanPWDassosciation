# G18-B Gate 2D-2B validation and source coverage

2026-10-18. **Accepted milestone remains 70%.** Photo review and application
correction integration in verified disposable sessions only. Operational EWAF,
ranking, selection, publication and development-result promotion remain disabled.
The four-criterion proposal remains inactive. Stop after this gate for review.

## Checkpoint and exact inventory

Branch `feature/events`; HEAD `949eeda33c6aa5d8ee03962209ae8fedeac58ad1`.
Before editing, captured branch, HEAD, status, staged binary diff, index hash,
585 baseline file hashes and exact original bytes of the two edited modules.
Read repository instructions, current specification, development guide, Open
Decisions, October 10 implementation impact, Gate 2A lock graph and Gate 2D-2A
validation. No unresolved policy was treated as approved implementation.

| File | Exact scope |
|---|---|
| `programs/workflow.py` | Import, two outer decorators, correction file-journal initializer, and minimum split of Application/Photo locking around Member. Existing forms, permissions, deadline/status rules, storage/revision helpers, case invalidation and native audit calls remain. |
| `ewaf/generation_services.py` | Permit PhotoVerification and ProgramDocumentRevision native references. Add a separate digest version for those newly admitted audit types; factor old native hashing without changing its version or fields. |
| `ewaf/photo_invalidation.py` | New disposable-session transaction, source-scope/token, ordered lock, evidence/audit validation and outer file-cleanup adapter. |
| `ewaf/test_photo_writers.py` | New 51-test fictional integration, filesystem retention, SQL/concurrency, rollback and historical replay suite. |
| This report | New validation, coverage, lock/file findings, limits and review inventory. |

Review artifacts reside in `.local/g18-b-gate2d2b/`; they are not staged. No
Membership, Members, Documents, Assistance or Events service implementation is
changed. No view, URL, template, CSS, authentication, PDAO setting, model definition,
migration, numerical engine, four-criterion reference or Gate 1 observer is changed.
The eight foundation models, Gate 2C authority integration, Gate 2D-1 adapter and
Gate 2D-2A adapter/services/tests remain preserved.

## Source coverage matrix

COVERED means inside the existing registered, identity-verified disposable session.

| Entry point / outcome | Native records and source result |
|---|---|
| `review_photo`: VERIFIED | COVERED. Exactly one new PhotoVerification with matching current photo, actor/label, member version, reason, category and outcome; exact ProgramLog(photo_verified); conditional AssistanceLog(evidence_invalidated). One program batch/invalidation and generation/revision +1. |
| `review_photo`: NEEDS_RESUBMISSION | COVERED. Existing Needs Information transition retained. Later correction must provide the requested replacement; the prior photo/review and file remain. |
| `review_photo`: REJECTED | COVERED. Existing Verification Failed terminal behavior retained; correction cannot reopen it. No ineligibility, selection or score is inferred. |
| `correct_application`: new/replacement photo | COVERED. New ApplicationPhoto under its existing application plus exactly one new PENDING PhotoVerification; original photo row/file/reviews retained. Existing reference unchanged. |
| Correction: replace existing program document | COVERED. Exactly one ProgramDocumentRevision containing the old file/content type/size/source document/source verification and actual actor/reason. Current document changes without changing its application/requirement/label identity. |
| Correction: newly supplied program document | COVERED. Current document belongs to the actual application and requirement's program; no fictitious previous revision. |
| Correction: retained/reused evidence | COVERED. Existing files are not journaled as new uploads. Reused source must belong to the member's intake, match its verification document, and pass the existing current-document check. |
| Correction without file replacement | COVERED. Existing version/source-snapshot/native-audit changes remain source dependencies even when visible values match. No invented photo review or document revision. |
| Existing eligibility case | COVERED within these two workflows. Existing review/pending reset and exact AssistanceLog before/after snapshot commit together. No case is created when absent. No Assistance service implementation changes. |
| Stale/malformed token, extra/missing scope, missing state, stale application/photo version, missing current evidence, unauthorized action | REJECTED. No successful source transition; source/authority/revision/current-pointer expectations are independently checked. |
| Repeated successful review of the same outcome | COVERED. Distinct native review/audit is a real conservative dependency change, with a new monotonic generation. |
| Ordinary unregistered requests | Original accepted workflow, with the safer split locking helper. No generation-table queries or automatic registration. A supplied non-null source token cannot activate the protocol. |
| Private photo-view audit (`photo_viewed`), other read-audit paths, readiness/diagnostic persistence | DEFERRED for generation coverage. Their conservative Gate 1 audit dependencies are not narrowed or ignored. |
| Linked Events, member/membership/document writers, Assistance eligibility/selection/release/void, reference metadata | DEFERRED to separately authorized integrations. No claim of complete-system writer coverage. |
| Raw ORM/SQL, external file edits, custom storage, separate processes/imports | OUTSIDE the integrated contract. No triggers, CDC, broad signals or privileged-tamper immunity. |

Existing manual-review confirmation, reasons/categories, role permissions, active
membership, authorized photo policy, correction deadlines and permissible statuses
are preserved. Current universal calendar-photo behavior is not silently replaced
by a no-photo or accessible-alternative route. OQ-02/OQ-03/OQ-24 and any separate
consent/home-assessment policy remain unresolved where already unresolved. This
gate adds neither a consent claim nor an automatic verification/waiver rule.

## Actual lock-order findings

The original helper issued:

```python
ProgramApplication.objects.select_for_update().select_related('current_photo').get(pk=reference)
```

A focused test executes that exact prior query on fictional MySQL rows and captures
the SQL: Application LEFT OUTER JOIN ApplicationPhoto, with FOR UPDATE. The photo
is in the locking query before the original subsequent Member query. Python line
order alone therefore did not establish the required source order.

The helper now uses an Application-only locking query, then Member, then an explicit
Photo query constrained to that application. Only these two authorized workflows
call this helper. The split also applies outside registration; valid business
outcomes remain unchanged and foundation tables are not accessed there.

The disposable adapter's measured first-acquisition order is:

```
top-level transaction boundary check
Terms -> AuthorityGeneration -> resolve actual Program from Application
-> Program -> ProgramSourceState -> exact expected token
-> Application (no photo join) -> Member
-> EligibilityStatus(review) -> ordered ProgramRequirements
-> ordered member MembershipApplicationDocuments -> their DocumentVerifications
-> ordered ProgramDocuments -> ApplicationPhotos -> PhotoVerifications
-> AssistanceCase
-> original workflow -> native/evidence validation -> immutable batch/invalidation
-> expected-value CAS -> final state/batch/authority validation -> root COMMIT
```

The two verification leaf queries use MySQL `FOR UPDATE OF` to lock only their
own rows, not joined parent tables. All leaf rows are ordered by primary key.
Unused earlier levels are omitted. Original Program/Application/Member/Photo
queries re-enter locks already held by the outer fence; they do not first acquire
a lower-order lock after a higher-order row. Original atomic blocks become nested
savepoints. No source lock precedes Terms. Arbitrary caller-owned outer transactions
are denied in registered sessions.

Separate-connection evidence includes two same-token reviewers, two same-token
corrections and a failed correction followed by a waiting successful correction.
One successful transition results; the other request rejects stale generation,
or proceeds with the still-valid token after rollback. Actual different MySQL
connection IDs and controlled waiting are recorded in the sanitized logs.

A dedicated two-connection probe holds Member on connection A while the integrated
writer on B waits for Member. A can then acquire the current Photo with NOWAIT;
the writer has not locked Photo early. Releasing A lets B finish. Captured SQL also
asserts each first lock level and that Application's locking query has no JOIN.
These are bounded runtime proofs, not a claim of global deadlock freedom for
unfenced writers, privileged SQL or all possible workloads. No retry hides a failure.

## Exact native and historical-record validation

Before each write, the adapter retains private in-memory row observations, never
publishing them or changing historical evidence digests. Previously retained photos,
photo reviews and document revisions must remain byte-for-value identical in the
database observation. All newly observed rows must be exactly the expected set.
Existing current documents cannot disappear; changed documents require matching
old-value revisions and cannot cross application/program ownership.

ProgramLog must match the exact action, actor/label, reason, application, program
and status/photo-review or correction snapshot. PhotoVerification must refer to the
actual current/new photo and exact submitted review data; a replacement needs its
PENDING review. Document revisions must match old file/source values and actor/reason,
with no omissions, duplicates, forged snapshots or unrelated rows. AssistanceLog
must match the actual case before/after snapshot and existing reset semantics.
The returned artifact must match the validated application/review. Global audit
high-water observations reject unexplained newly observed native audits rather
than silently narrowing scope. This can conservatively abort on an unrelated
unfenced audit, such as private photo access; no complete audit fence is claimed.

The batch references ProgramLog, conditional AssistanceLog, new PhotoVerification
and any ProgramDocumentRevision through model/PK/action/content-hash references.
The latter two have no `action` column, so the existing reference convention uses
the string `None`; their model and hashed fields provide the record semantics.
They use **`g18-native-evidence-audit-1`**, representing a revision FileField by
its retained storage name. No file bytes or private filename are copied into the
batch; the filename participates only in the digest input.

Every previously supported native audit retains exactly **`g18-native-audit-1`**
and the original concrete field payload. A dedicated test independently reconstructs
old ProgramLog/AssistanceLog hashes, validates new evidence references, then shows
that an adversarial revision edit is detected by native-reference replay. Historical
five-criterion and existing evidence/calculation digest formats remain unchanged.
The new records still use the original foundation generation digest contract.

Mandatory native, evidence, case and generation records and the business mutation
share one database commit. Failures in native audits, evidence validation, generation
audit insertion, CAS, fresh authorization or final validation roll back all database
writes. One top-level operation advances exactly one owning program, not per-record
increments. No generation state is silently initialized.

## File lifecycle and limits

The actual installed Django local storage implementation was inspected. Existing
photo/document upload paths use fresh UUID names, and FileSystemStorage defaults
to no overwrite, including exclusive creation/collision handling. Registered
operations require that exact local storage class with overwrite disabled;
unsupported custom/overwriting storage fails closed before mutation. No storage
configuration is changed. A forced existing-photo filename collision test verifies
that Django allocates another filename and preserves the original bytes.

| Lifecycle | Retention / cleanup result |
|---|---|
| New photo | New path/row and PENDING review; original application reference retained. |
| Replacement photo | Current pointer changes; every old photo row, review and file remains. |
| Document replacement | Old path/source attribution retained in ProgramDocumentRevision; new UUID path becomes current. |
| Reused membership document | Original protected source path remains; replacement revision retains its source document and verification IDs. It is never added to the new-upload cleanup journal. |
| Failed review | No file deletion or new file expected; rejection/resubmission outcome remains reasoned history on successful review. |
| Failed correction before original writer returns | Existing cleanup runs; original retained files remain. |
| Failure after original writer returns, including invalidation/CAS/final validation | Outer ContextVar journal triggers the same cleanup for only newly written files, while the database transaction rolls back. Existing cleanup may attempt the same new-file deletion first; local deletion is idempotent for an absent file. |

Tests hash actual temporary files before/after successful replacement, forced
collision and rollback; both uploaded old evidence and reused membership evidence
are retained. Successful current photos/documents must exist; reused evidence must
pass the existing current verification/hash checks. Previously missing historical
files cannot be recreated by database invalidation. A new replacement may address
an unavailable current photo while preserving its historical record; that does not
restore the missing old bytes or certify them as available.

**MySQL and filesystem writes are not automatically atomic.** Cleanup retains the
existing best-effort deletion contract. Storage/OS deletion failure, process crash,
external tampering and durable orphan recovery remain limitations. No old file is
deleted merely because it is no longer current. No custom remote immutable-object
versioning is implemented; such storage requires separate design/authorization.
No schema change was necessary for the existing non-overwriting local paths.

Historical rows are retained by these workflows and checked by the adapter and
native-reference digests. This does not add SQL append-only triggers or universal
ORM guards to the pre-existing photo/revision models. Privileged edits remain
outside contract and can cause later integrity checks to fail closed.

## Preservation, capability and deferred work

583 of 585 baseline entries remain byte-identical: only the two existing modules
listed above change. Three repository files are new; none is removed. Branch,
HEAD, staged index and staged binary diff remain unchanged. Original workflow
bytes reconstruct after removing only this gate's import/decorators/journal and
split-lock edits. All existing tests are unchanged. The index hash remains
`731c74ba7d747938181fbc4140139120a01c4ac5d676ac9607f3ff30ef718338`;
staged binary-diff hash remains
`64b8c580177e3d43c8c4fa863df77e81193c66a95071b4508f0f25b28e0fded6`.

All model/migration bytes and leaves remain unchanged: accounts 0001,
announcements 0004, assistance 0003, audit 0002, core 0001, documents 0003,
events 0006, ewaf 0006, members 0003, membership 0004, programs 0005.
The application migration recorder was not queried. The prior checkpoint's
unapplied development migration status is preserved by not accessing that database.

The existing process-local disposable registration validates actual database,
server and temporary-media identity. A token is a development concurrency
precondition, not activation or authorization. No UI token plumbing, caller flag,
production setting, member login, online membership registration or current-result
interface is added. Registration/foundation permissions are unchanged.

The historical durable graph and request/run binding digests remain reproducible
after an evidence correction in the fictional tests. Old snapshots are not made
current or described as usable; source pointers remain null, operational access
raises and development promotion remains disabled. Gate 1 conservative dependencies
and the non-promotable coverage contract remain unchanged. Full writer coverage,
cross-program assistance invalidation, expiry, linked events, storage reconciliation,
production performance and operational policy remain separate work. Full-history
observations and the global Terms mutex are deliberately coarse in this gate.

## Executed tests and checks

Each harness invocation initializes its own fresh loopback MySQL 8.4.11 instance,
uses READ-COMMITTED and verifies that all test tables are InnoDB. `.env` is disabled;
credentials are generated and grants confined to empty/disposable test databases.
The runner verifies actual server/database/datadir identity. Only fictional records
and temporary media are used; no keepdb. Existing migrations are tested only in
these disposable databases. Harnesses shut down their own servers in finally.

Command prefix:

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py
```

Tests append `test [label] --testrunner scripts.durable_test_runner.DurableTestRunner --noinput`.
Labels: `ewaf.test_photo_writers`, `programs`, `ewaf`, or omitted for full suite.
Checks append `check --database default` and `makemigrations --check --dry-run`.
Whitespace checks use working/staged `git diff --check` and a scan of new files.

| Run | Actual result | Test-runner seconds |
|---|---|---:|
| Focused initial | 42 run; 2 failures, 5 errors, 0 skips | 49.205 |
| Focused corrected/expanded | 50 passed; 0 failures/errors/skips | 34.897 |
| Focused final | 51 passed; 0 failures/errors/skips | 65.038 |
| Programs | 150 passed; 0 failures/errors/skips | 119.788 |
| EWAF | 643 passed; 0 failures/errors/skips | 655.236 |
| Full project | 1,236 passed; 0 failures/errors/skips | 980.104 |
| Django/database checks | No issues (0 silenced) | - |
| Migration drift | No changes detected | - |
| Whitespace | Working/staged diffs passed; new files have no trailing whitespace | - |

The initial error was the new document-revision audit type's FileField reaching
the old hasher as a FieldFile object. Five errors include subtest errors; the two
correction race failures were dependent waits because that serialization error
prevented reaching invalidation. The fix introduced the separate evidence-audit
digest contract and explicit storage-name serialization, preserving old native
hashes. The corrected 50 tests passed; final coverage added old/new hash replay
and the final result-scope guard, then all 51 passed. No pre-existing test or
business guard was weakened. Initial logs and both corrected runs are retained;
there is no hidden automatic retry. Durations exclude MySQL initialization and
migration setup; independent runs may overlap without sharing instances/media.
The full run comprises all 1,185 pre-existing tests plus 51 new tests. Both the
EWAF and full-project regression processes exited successfully, and their logs
record destruction of their respective disposable test databases.

## Review package

The review ZIP is an explicit scoped delta, not a replacement checkout. It contains
the five changed/new files, relevant unchanged design/foundation/session/storage/
writer references, sanitized fictional logs, actual test results, baseline-relative
diffs, preservation hashes, manifest and SHA256SUMS. A separate checksum covers the
ZIP itself. Credentials, environment content/hash, application/test database files,
MySQL configuration and private uploads/records are excluded. Keep the complete
existing staged/unstaged/untracked baseline; HEAD alone is not the working checkpoint.

No staging, commit, push, merge, reset, clean, stash, pull, deployment, application
database access, PDAO enforcement change or later-gate implementation occurred.
**Stop after Gate 2D-2B for owner review. Accepted milestone remains 70%.**
