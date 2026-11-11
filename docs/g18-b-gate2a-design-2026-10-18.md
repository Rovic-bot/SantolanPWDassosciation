# G18-B Gate 2A finalized implementation proposal

2026-10-18, local `feature/events`. **Design only; owner review required before
implementation. Accepted milestone remains 70%.** Latest completed full-suite
evidence is Gate 1's **999 passing tests**, not a new run during this review.

This document resolves implementation choices left open in the
[Gate 2 outline](g18-b-gate2-proposal-2026-10-18.md), without editing that historical
outline or either Gate 1 report. Read the [verified lock graph](g18-b-gate2a-lock-graph-2026-10-18.md)
and [review record](g18-b-gate2a-review-2026-10-18.md). No model, migration, service,
source writer, setting, Admin UI or database change is made by this proposal.

## 1. Selected authority design: one global generation

Use exactly one installation-wide `AuthorityGeneration` row, fenced by the
existing Terms mutex. Every integrated explicit user/role/permission or credential
mutation advances its monotonic generation with a mandatory immutable
`AuthorityInvalidation` audit. **Do not fan authority changes out into per-program
source generations, and do not introduce per-user/per-group generation counters.**

Rationale: the actual account surface is Django's superuser-only UserAdmin and
GroupAdmin, with direct grants, group membership, group grants, scalar account
state, cascade deletes and distinct password paths. There is no existing complete
reverse dependency registry of all actors/program requests. One global generation
avoids missed scopes on group removal, deletion, superuser changes and ABA. Cost:
even an unrelated account edit invalidates all generation-aware development
requests/results. Accept this conservative cost for a small development backend;
do not optimize into narrower authority scopes without a separate design review.

The exact integration inventory is in the lock document. Increment once per
successful explicit user add/change/delete, group add/change/delete, M2M edit,
admin password set/unset or own-password change. Include actor identity/label
edits; exclude ordinary login/logout/last_login, session refresh, throttle counts
and automatic hash-algorithm upgrades that do not change the credential. Capture
no password, hash, session token or request body in an audit. A successful
no-change form produces no generation event; revoke then restore in separate
transactions produces two, even if effective grants return to their old values.

Admin integrations wrap the entire mutation including `save_related`, native
logging and bulk deletes. Re-fetch and authorize the acting administrator under
T/H, ignoring instance permission caches. Own-password writes retain the existing
non-superuser permission rules. Auth catalog migrations, `createsuperuser`,
`changepassword`, raw ORM and new custom backends are not magically covered by
admin hooks; they require a fenced wrapper or a suspended disposable session and
audited epoch reinitialization before resuming. No broad post-save signal is used
as the correctness boundary.
Where an existing admin form has no reason field, the adapter supplies a bounded
server-generated action description/reason code and links its native change log;
it does not add UI controls or invent a human approval statement. Existing domain
reason requirements remain unchanged. Internal system actions use fixed allowlisted
codes and a private trusted entry point, not a caller-selectable audit bypass.

An authority event invalidates all pointers **logically**, by equality against the
global generation. It does not update every ProgramSourceState row. A stored
`current_binding_id` with an old authority generation is historical/stale and MUST
NOT be returned by the current-result facade. No raw pointer lookup is a valid
current-result API. Its old binding and promotion audit remain immutable. This
rule deliberately removes per-program authority fan-out and its race windows.

## 2. Final additive record design

All proposed models live in `ewaf/generation_models.py`, registered through the
existing `ewaf/models.py` module pattern. No field is added to a historical model.
Use the existing MySQL/InnoDB database alias; no second database or cross-database
transaction. New mutable rows have service-only managers; new historical/audit
rows deny update/delete/bulk update/upsert through supported ORM paths and have no
editable Admin registration. Existing historical engines/constants stay intact.
All eight models use `Meta.default_permissions = ()`; source actions retain their
existing domain permissions, and private development services retain the existing
durable-processing permission set. No new automatic model CRUD grants or Admin
screens are introduced. Audit access remains through explicitly authorized services.

Notation: `PB` = PositiveBigIntegerField (nonnegative; service refuses increment
at the database maximum); `H64` = lowercase SHA-256 CharField(64); `U64` = validated
CharField(64) protocol/source identifier; FK/O2O use `on_delete=PROTECT` unless
explicitly stated. Dates are timezone-aware DateTimeFields. The database stores
integer generations exactly; no JavaScript floating-point token conversion.
Every PB field is additionally bounded to 0..9223372036854775807 by explicit
database checks and service validation; no wraparound, negative generation or
counter reuse is permitted.

### 2.1 AuthorityGeneration (mutable singleton)

- `id`: PositiveSmallInteger primary key, exactly 1, no caller-selected IDs.
- `generation`: PB, default 0; never reduced/reused.
- `last_event`: nullable FK AuthorityInvalidation, default NULL.
- Checks: id=1; `(generation=0 AND last_event IS NULL) OR
  (generation>0 AND last_event IS NOT NULL)`.
- Index: PK only. Last event's `after_generation` must equal this row's generation
  (service validation; cross-row check is not a database CheckConstraint).

### 2.2 AuthorityInvalidation (immutable mandatory global audit)

- `id`: UUID primary key, generated server-side.
- `before_generation`, `after_generation`: PB; after is globally unique.
- `kind`: CharField(24), fixed choices `INITIALIZE`, `USER_CHANGE`, `GROUP_CHANGE`,
  `CREDENTIAL_CHANGE`, `CATALOG_RECONCILE`.
- `subject_kind`: CharField(24), `installation`, `user`, `group`, `catalog`;
  `subject_id`: CharField(64), stable ID or `installation`, never username as key.
- `actor`: nullable User FK; `actor_label`: CharField(150); `system_code`:
  CharField(64), blank default; exactly one actor or approved system code.
- `reason_code`: U64; `reason`: TextField(max_length=2000); `recorded_at`;
  `native_audits`: JSON list of allowlisted model/PK/action/digest references;
  `digest`: H64 over this new versioned immutable payload.
- Checks: after=before+1; kind/subject choice allowlists; actor/system XOR;
  reason_code nonempty. Unique after_generation; index `(subject_kind, subject_id,
  recorded_at)`. Native-audit shape/content and reason limits enforced by service.
- The subject is an ID/label, **not** a target User/Group FK: deleting an otherwise
  deletable target must not be newly blocked by its own deletion audit. Actor FK
  protection is deliberate; existing historical actor protection remains.

### 2.3 ProgramSourceState (mutable one row per program)

- `program`: OneToOne Program, primary key.
- `generation`: PB default 0; `revision`: PB default 0. Generation changes for
  source invalidation; revision changes for invalidation AND pointer promotion.
- `last_invalidation`: nullable FK SourceInvalidation, default NULL.
- `current_binding`: nullable FK RunSourceBinding, default NULL. This is a
  candidate pointer, valid only through the facade and the global authority check.
- Checks: revision>=generation; generation zero requires revision zero, null
  last_invalidation and null current_binding; positive generation requires a
  last_invalidation. No implicit current pointer default/backfill.
- Indexes: PK, ordinary FK indexes. No additional generation-only index needed.
- Services enforce same-program last invalidation/current binding, tail generation,
  current binding's promotion event and revision, and expected pointer CAS. SQL
  cannot enforce those cross-table equalities through the proposed row checks.

### 2.4 SourceMutationBatch (immutable source-operation audit header)

- `id`: UUID PK; `kind`: CharField(24) choices `INITIALIZE`, `SOURCE_CHANGE`,
  `EXPIRY`, `REPLACEMENT`; actor/label/system_code and reason fields as above.
- `source_kind`: U64; `source_id`: CharField(64); `source_audits`: JSON list of
  model/PK/action/digest references; `scope_digest`: H64 over sorted affected
  program IDs; `scope_count`: PositiveInteger; `recorded_at`; `digest`: H64.
- Checks: kind allowlist, actor/system XOR, nonempty reason_code. Index
  `(source_kind, source_id, recorded_at)`.
- Existing MembershipEvent, MemberEvent, ProgramLog, AssistanceLog, EventLog,
  LogEntry and SecurityEvent retain their original formats. Resolve/re-read native
  audit references inside the transaction and freeze their minimal identifiers
  and content digests here; no generic FK masquerading as database-enforced audit
  integrity. Zero-program pending-intake operations may have scope_count=0.
- For `SOURCE_CHANGE`, successful native source audit(s) are mandatory. Initialization,
  expiry and replacement are audited internal actions with explicit system/request
  provenance instead. The new batch is itself a mandatory protected audit, not
  an optional debug log. No raw medical, income, file or credential data in it.

### 2.5 SourceInvalidation (immutable per-program generation transition)

- `id`: BigAuto PK; `batch`: FK SourceMutationBatch; `program`: FK Program;
  `before_generation`, `after_generation`, `before_revision`, `after_revision`: PB.
- `cleared_binding`: nullable FK RunSourceBinding; `recorded_at`; `digest`: H64.
- Checks: after_generation=before_generation+1;
  after_revision=before_revision+1; before_revision>=before_generation.
- Unique `(program, after_generation)` and `(batch, program)`; composite index
  `(program, recorded_at)`; FK indexes retained.
- Invalidation clears the physical program pointer and increments revision even
  when the pointer was already null. One top-level source operation coalesces its
  changes into one transition per affected program; the batch lists every native
  source audit produced. Missing/duplicate/falsely narrow scope fails the operation.

### 2.6 RequestSourceBinding (immutable request acceptance sidecar)

- `request`: OneToOne DurableRequest, PK.
- `source_generation`, `authority_generation`, `expected_state_revision`: PB,
  all >0; `expected_current_binding`: nullable FK RunSourceBinding.
- `protocol`: U64 fixed `g18-generation-development-1`; `coverage_contract`: U64
  fixed supported implementation manifest; `engine_profile`: U64 fixed existing
  historical five-criterion engine/profile combination.
- `accepted_snapshot`: JSON, the exact Gate 1 version-2 snapshot, unchanged;
  `context_digest`: H64 equal to request.expected_context and digest(snapshot);
  `inventory_digest`: H64 of ordered complete manifest.
- `submission_digest`: H64 of caller's expected-token/contract/reason/key/predecessor
  identity; used with existing request content digest for idempotency. This stops
  identical source values under different generations from sharing an intent.
- `valid_until`: non-null aware datetime; `evaluation_timezone`: CharField(64);
  `recorded_at`; `digest`: H64 of this new immutable sidecar payload.
- Checks: positive generations/revision; protocol allowlist; valid_until>recorded_at.
  Index valid_until for stale-request diagnostics. Config, validation and evidence
  policy identities/digests are frozen inside accepted_snapshot and reached by
  request.policy's existing protected FKs; no redundant configurable weight fields.

### 2.7 RunSourceBinding (immutable accepted complete graph sidecar)

- `run`: OneToOne DurableRun, PK; `request_binding`: OneToOne RequestSourceBinding.
- `graph_digest`: H64 over ordered existing run/result/trace/completion-outcome
  digests; `retained_count`, `eligible_count`: PositiveInteger; `recorded_at`;
  `digest`: H64. Checks: eligible_count>=1 and retained_count>=eligible_count.
- Request binding supplies all generations, versions, deadline and exact policy
  identities. Service verifies run.request matches request_binding.request,
  run.context_digest matches its snapshot, program consistency and full replay.
- Indexes: implicit PK/one-to-one indexes only. A binding without a valid immutable
  promotion event is historical, never current.

### 2.8 DevelopmentPromotion (immutable mandatory pointer-transition audit)

- `id`: BigAuto PK; `program`: FK Program; `previous_binding`: nullable FK
  RunSourceBinding; `new_binding`: OneToOne RunSourceBinding.
- `source_generation`, `authority_generation`, `before_revision`,
  `after_revision`: PB; `checked_at`, `recorded_at`; actor User FK (non-null),
  actor_label, reason_code/reason, digest as above.
- Checks: after_revision=before_revision+1; generations>0; previous binding
  differs from new binding when present. Unique `(program, after_revision)`;
  index `(program, recorded_at)`; implicit FK/O2O indexes.
- No same historical binding can be promoted twice. Revision uniqueness across
  promotion and invalidation tables is enforced by the single locked state's CAS,
  not falsely claimed as a cross-table database unique constraint.

All audit payloads use a NEW explicitly versioned canonical digest contract. Do
not add fields to existing `DurableArtifact.payload()` or change `evidence.digest`,
five-criterion engines, configuration digests or old replay. Bulk bypass/raw SQL
is not rendered tamper-proof by these application guards.

## 3. Transaction and atomicity contracts

Use the order in the lock graph: **T -> H -> all P -> all S -> linked Events ->
Applications -> Members -> ordered source leaves**. Public generation entry points
require autocommit/top-level ownership; an internal context proves an outer admin
wrapper already acquired the fence. Reject arbitrary pre-locked outer transactions.
No unawaited jobs, on_commit invalidation or separate database writes participate
in the correctness boundary. Existing read-only diagnostics need not be rewritten.

### Source mutation

1. Acquire T,H; reauthorize actor; resolve complete impact before P locks. Membership
   requirements/DocumentType metadata conservatively affect every registered program
   state. Member sources/receipt/void affect every program with a retained application
   for that member. Inventory and linkage cannot be resolved only from current eligible
   applicants. Shared writer discovery is protected by T after all integrations land.
2. Lock complete scope and native sources in order. Revalidate displayed versions,
   domain guards and business rules. Perform source writes and their native audits.
3. Create SourceMutationBatch. For each scope program create SourceInvalidation,
   advance generation/revision with an expected-value update and set pointer NULL.
   Row count must be exactly one per state; validate complete batch scope and tails.
4. Commit once. Failure of source write, native audit, batch, any scope invalidation,
   CAS or final validation rolls back **all** source/state/audit DB writes. An actor
   cannot opt out of audit/invalidation. File staging/cleanup is addressed separately.

The helper must run inside the source transaction, not in a signal after commit.
Top-level operations collect nested native audit references and invalidate once
per program. Separate transactions that change and restore a source advance twice.
Retry after deadlock restarts the WHOLE operation with re-resolved scope and versions;
no retry of only the generation update. Missing source audit is a failure, not a
reason to write an incomplete successful mutation.

### Authority mutation

T,H -> fresh acting-user authorization -> complete admin/service DB mutation,
M2M/cascade/native audit -> AuthorityInvalidation(g,g+1) -> H update (CAS) -> commit.
Any failure rolls all of these back. Audit target identifiers survive permitted
deletion. No per-program generation changes or physical pointer clearing occur;
every current facade rejects bindings with authority_generation != H.generation.
Old evidence signers' later permissions are not retroactively reinterpreted.

### Initialization and replacement

Migration creates **empty tables only**. A separately guarded disposable-bootstrap
service creates H at zero and an INITIALIZE event to generation 1 in one transaction.
Lazy program-state initialization similarly inserts state 0 then a mandatory
INITIALIZE batch/invalidation to generation=revision=1, null pointer. No historical
run becomes current. Missing state/epoch never means generation zero is approved.

An explicit replacement intent clears the matching prior current pointer by a
REPLACEMENT invalidation before binding the new request, all in one transaction.
Validate the caller's old expected token first; then accept the request against
the advanced generation/revision. Keep the existing single-successor-request rule.
If replacement calculation later fails, the prior binding stays historical; no
fallback or automatic repromotion. If request persistence fails in this initial
transaction, the invalidation also rolls back. A retry of the same request key
compares stored submission_digest and revalidates the accepted generations; it
does not bump again. Changed intent, stale authority/source or an unrelated newer
pointer fails. A completed duplicate uses the current facade, not a blind return.

## 4. Complete-pool promotion protocol

Only the existing authenticated disposable-harness capability may call the new
generation-aware development service. No production enable flag, UI route, public
result, ranking output or beneficiary-selection consumer is added. Foundations
remain non-promotable until the final integration coverage contract is accepted;
unit tests can exercise low-level CAS logic without enabling a current facade.

**Installation boundary:** later writer adapters enlist only inside a verified
generation-test session established by the disposable runner/bootstrap, with the
actual database identity checked at each fence. This is not a request parameter,
production setting or caller-supplied `synthetic=True`. Outside that registered
session, existing application writers retain their old behavior and do not query
the new tables; generation-aware processing is unavailable there. A registered
session with an identity mismatch fails closed, never falls back to an unfenced
write. Old full-suite fixtures do not implicitly activate this session. This keeps
accepted application behavior usable while new tables exist only in disposable
instances. Extending enlistment to the application database would require a
separate migration/deployment design and authorization; no such guarantee is made.
Session registration is tied to the verified server/database identity and shared
across participating worker connections in the test process; it must not be a
thread-local opt-in that silently disappears in concurrency tests. Fence ownership
itself is transaction/connection-local. Unregistered external processes/SQL clients
are outside the integrated-writer guarantee, not invisible cooperating writers.

1. **Accept:** under fence, capture/revalidate the full existing Gate 1 snapshot,
   entire retained inventory, all five latest assessments, configuration/policy,
   source lineage/bytes and processor permissions. Compare caller expected context,
   source generation, authority generation, revision and pointer. Preserve unresolved
   or incomplete applicants in accounting and fail closed. Persist DurableRequest
   and RequestSourceBinding in the same transaction. Its accepted snapshot and
   intent are immutable; caller does not supply scores or authoritative source IDs.
2. **Intent and calculation:** preserve durable attempt/recovery semantics. Numerical
   work can occur outside source locks from accepted_snapshot, using the unchanged
   five-criterion calculator. No current pointer exists merely because work began.
   Old requests without sidecars continue historical Gate 1 behavior only. An old
   processor must refuse a generation-bound request; it cannot complete it through
   the old unbound path. Add that dispatcher guard only in the authorized promotion
   increment, and regression-test both paths.
3. **Reacquire and validate:** T,H,full ordered scope. Re-fetch actor and evaluate
   the complete permission set from the database. Require recognized protocol/
   coverage/engine, matching source and authority generations, expected revision/
   pointer, same complete current inventory and context digest, exact policy/config/
   evidence revisions, readiness/provenance, non-disputed/unexpired current evidence.
   Check every source again; generations complement these checks, not replace them.
4. **Persist complete graph:** use existing immutable durable persistence and outcome
   rules. Reject missing/extra/duplicate results, missing/duplicate criterion traces,
   mismatched assessments/units/inputs, wrong program/request lineage, incorrect
   comparison set, unresolved exclusions or any numerical replay mismatch. Build
   RunSourceBinding only after completion outcome and exact graph digest validate.
5. **Promote once:** final source/permission/deadline check while fence is held.
   Compare-and-swap S using program, generation, revision and expected pointer;
   explicitly handle expected NULL with `IS NULL`. Require exactly one changed row,
   increment revision, set binding, and insert DevelopmentPromotion in the SAME
   graph transaction. Re-read/validate state + audit + graph before exit. Audit/CAS
   failure rolls back the whole graph/promotion; separate existing failure-outcome
   transaction may then record the failed attempt. No partial pool is current.
6. **Read current:** facade reacquires T,H,P,S and source locks, reauthorizes and checks
   coverage, generation equality, promotion audit, graph, current complete dependency
   snapshot and deadline. It returns private development metadata only with
   `operational_ready=false`. Historical inspection remains separately available and
   makes no current claim. Do not cache a pointer as a reusable authority token.

Concurrency linearization is the state CAS under the common fence, committed with
its audits/graph. A participating source writer arriving next clears its program
pointer atomically; an authority writer invalidates it by the global epoch. This
claim is limited to integrated application writers and the tested lock contract.
Repeated hash observations alone still do not prove atomicity.

### Expiry

Require a non-null `valid_until`: the earliest of the next evaluation-day boundary
in the snapshot timezone, exclusive midnight AFTER any inclusive expires_on date,
and any earlier time-sensitive program/event/source boundary used by the accepted
capture. Preserve current development freshness semantics, not invented operational
periods. Any time-sensitive dependency without a defined next transition blocks
promotion until its contract is explicit. No default infinite validity.

Use one aware current time at each acceptance/promotion/read check; require
`now < valid_until`. Crossing the boundary during calculation rejects promotion.
A due current binding is cleared through an EXPIRY batch under the same fence,
once; a delayed worker never makes an expired binding usable because the read
facade checks the clock itself. Once invalidated, clock rollback does not restore
the pointer. The expired-result path must commit this invalidation before returning
a stale status or raising outside the transaction; raising inside the atomic block
would undo it. Trusted clock/timezone remains an assumption: an undetected external
clock rollback before any expiry observation cannot be solved by MySQL row locks.
An instant can expire between final check/CAS and transaction commit; the next
read must reject it. Do not promise a minimum lifetime after commit or wall-clock
atomicity. Each consumer validates at its protected use boundary.

## 5. Exact migration boundary and historical preservation

Proposed single additive file, **not created**:
`ewaf/migrations/0006_source_invalidation_foundation.py`.
Dependencies verified from files, without querying any database:

```python
dependencies = [
    ('ewaf', '0005_durable_development'),
    ('programs', '0005_approved_terms'),
    migrations.swappable_dependency(settings.AUTH_USER_MODEL),
]
```

Create the eight new tables, then AddField for the four cyclic NEW-table links:
AuthorityGeneration.last_event, ProgramSourceState.last_invalidation and
ProgramSourceState.current_binding, plus RequestSourceBinding.expected_current_binding.
Add their checks after fields exist; define
new-table indexes/unique/check constraints with explicit short names below 64
characters. No AlterField/RemoveField/RunSQL against old tables, no data backfill,
no seed of approved settings and no mutation of old migration history. Native audit
references are frozen JSON, so no fictional FK migration dependency on every domain
audit table. Runtime all-app tests still require the actual complete migration graph.

Current file leaves: members 0003; membership 0004; documents 0003; assistance 0003;
events 0006; accounts 0001 (auth 0012); audit 0002. Full exact filenames are in the
review record. These existing unrelated leaves must not be renumbered or merged.
Re-resolve migration leaves before implementation if the workspace changes.

MySQL DDL execution is not treated as rollbackable business-data work. Failures
during installation require a reviewed recovery plan; do not apply this proposal
to the application DB. Schema rollback is tested only on disposable instances;
dropping populated new audit tables is not a production rollback plan. Code rollback
must disable promotion while retaining all new and old history.

No historical five-criterion snapshot, trace, digest, artifact payload or issued
reference is rewritten. The four-criterion math proposal remains inactive and is
not a new engine option here. Existing DurableArtifact tables remain untouched;
new immutable sidecars give new requests/runs generation provenance. Neither a
migration nor initialization makes an old run current. Old numerical replay must
work with and without new tables present, subject to the existing old migration
dependencies. No deletion of old evidence, audits or result graphs is permitted.

## 6. Bounded implementation gates and authorization

| Increment | Exact bounded intent / candidate files (NOT changes in this review) | Stop/acceptance boundary |
|---|---|---|
| **2B: isolated foundation** | `ewaf/generation_models.py`, `generation_records.py`, `generation_services.py`, model registration in `ewaf/models.py`, proposed 0006 migration, focused model/transaction/migration tests | Separate approval to CREATE this migration and APPLY it only in fresh disposable MySQL. Empty tables, bootstrap, audit/state/CAS helpers; no writer integrations, no current facade enabled. Review generated SQL and migration preservation evidence. |
| **2C: authority integration** | `accounts/admin.py`, new `accounts/authority_services.py`, `accounts/views.py` for own-password atomicity, tests; guarded management wrappers only if included in this approval | Whole scalar/M2M/password/delete audit boundary; global epoch ABA/rollback races. Login/UI/security permissions unchanged. No new schema expected; any additional migration requires separate approval. |
| **2D: program and EWAF writers** | `programs/services.py`, `workflow.py`, `approval_services.py`, `binding_services.py`; `events/services.py` only linked-event save/publication; `ewaf/evidence_services.py`, `configuration_services.py`, `scoring_services.py`; targeted tests | Prefix/order/scope and mandatory generation events. Keep conservative diagnostic-audit invalidation compatible with Gate 1 capture. No changes to publication/selection or PDAO enforcement. |
| **2E: shared member/evidence/assistance writers** | `membership/services.py`, `members/services.py`, `documents/services.py`, `assistance/services.py`; metadata admins/reference guards in `documents/admin.py`, `members/admin.py`, `membership/admin.py`, `programs/terms.py` only as needed for fenced approved paths; tests | Cross-program fan-out, metadata add/change, immutable file-version discipline, native audit rollback and scope-completeness tests. Existing source structures/checklists/status rules remain. Split 2E into smaller authorized writer families if desired; partial coverage still cannot promote. |
| **2F: complete-pool development promotion** | New `ewaf/generation_processing.py`, `generation_inputs.py`, `generation_testsupport.py`; minimal dispatcher guard in `durable_services.py`; integration/expiry/current/history tests | All coverage contracts accepted, then private disposable-only request binding, atomic graph+pointer CAS and current facade. Exact graph regression, every writer race, whole-project suite and independent review. No operational consumer or UI route. |

Each row requires its own explicit implementation scope approval. A 2B schema
approval does not authorize 2C-2F, application-DB migrations, deployments or changing
operational policy. Until every participating family is integrated and verified,
the supported build coverage contract denies current-result promotion. No caller
boolean, fixture label or database setting may bypass the existing disposable
identity guard. Foundation CAS tests exercise internals without exposing a current
result capability. All implementation increments preserve staged/unstaged work.

## 7. Explicit limitations and risks

| Risk | Required mitigation / remaining limit |
|---|---|
| Unfenced SQL/ORM, imports, management commands or new admin actions | No CDC/DBA tamper-proof claim. Inventory allowlisted integrations; guarded wrappers or suspension/reconciliation. New paths fail coverage review; no promotion claim before integration. |
| External file replacement/removal/ABA | Keep hash checks and unique new file names; integrated correction never overwrites a referenced object. DB rollback can leave an unreferenced staged file; cleanup must not delete retained evidence. Filesystem tampering between reads remains outside atomic DB guarantee. Earlier photo authenticity is not retroactively established. |
| Global T/H contention, long evidence hashing, large cross-program fan-out | Coarse correctness-first fence; measure duration/lock waits with fictional large pools. Do not truncate program fan-out. Bound resources by failing the operation explicitly; never commit partial invalidation. |
| Deadlocks/FK and admin-hook ordering | Static graph identifies risks; actual two-connection tests are mandatory. Whole-transaction retry only; domain actions that cannot be safely retried fail with no partial commit. |
| Scope drift / new programs for existing member | Resolve under T; registration of new state and application is fenced; future program snapshot captures latest sources even if it did not exist at earlier mutation. Missing initialized state blocks current read. |
| Audit failure / audit references not true FKs | Mandatory atomic new immutable audits plus validated native refs; no successful source mutation if native/new audit fails. Document cross-row checks as service invariants, test bypass rejection. Privileged tampering remains outside guarantee. |
| Expiry and trusted clock | Deadline checks on every protected use; sticky audited invalidation, no implicit resurrection. Clock integrity and policy-defined periods remain explicit assumptions. |
| Global authority invalidates unrelated programs | Accepted conservative behavior, no silent per-user optimization. Old history remains accessible to authorized readers without current claims. |
| Policy authorization missing | Technical development promotion cannot supply Association approval. Four-criterion configuration, measures/bounds/directions, PA lookback, classification/ties, authorized roles/date/program scope remain pending. PR removal alone is not activation authority. |
| Accessible/functional eligibility, home assessment, consent, disputes | Preserve accepted eligibility/readiness and review inventory. No automatic exclusion, label-only functional inference, new PDAO prerequisite or approval defaults. Requires separate policy/implementation scope. |
| Historical signer role changes | Do not reinterpret signed evidence as invalid solely because the signer's later role changed; retroactive revocation policy remains unresolved. Processor authority still revalidated. |
| Misreading development pointer as operational result | Facade private/disposable-only, operational_ready=false, no ranking/selection/publication consumer. Existing hard-denial entry points remain tested. |

## 8. Migration, regression and acceptance plan

No tests below are claimed executed during this design review. Every command that
uses Django/MySQL must run through the existing fresh-instance harness, with
fictional records, `.env` disabled and `DurableTestRunner` where tests use the
development capability. Never use `--keepdb`, an existing app datadir, or migrate
the application database. Each command gets a separate NEW MySQL instance.

**2B migration tests (`ewaf.test_generation_migrations`)**:

1. Use MigrationExecutor at current complete graph including ewaf0005. Seed fictional
   old five-criterion configurations/results, G12-G17 artifacts and Gate 1 v1/v2
   request/run/result/trace/outcome graphs; capture counts, PKs, JSON, hashes, replay,
   old migration recorder rows and FK relations.
2. Forward only proposed 0006; verify eight new empty tables, actual MySQL columns,
   indexes, unique/check constraints, FKs/PROTECT behavior and zero historical
   changes. No bootstrap/current pointer is created by migration.
3. Bootstrap via isolated service, verify audited generation 1, null program pointers,
   missing epoch/state denial and repeated bootstrap idempotency. Validate counter
   overflow refusal and stale CAS. Inject failure at every new audit/state write.
4. Insert duplicate, null-invalid, wrong choice, non-consecutive, mismatched scope
   and orphan references using ORM and direct SQL in the disposable test DB. Distinguish
   enforced SQL constraints from service-only cross-row checks. Assert failures,
   rollback, immutable history and no fake claim of cross-table database checks.
5. On a separate disposable fixture, reverse ONLY 0006 after intentionally exercising
   new records; verify old rows/counts/digests/replay unchanged. This demonstrates
   additive isolation, not permission to discard real audit history. Forward again
   and verify graph installation. Restore latest migration state for following tests.

**Writer and concurrency tests (`test_authority_generation`,
`test_source_invalidation`, `test_generation_concurrency`)**:

- Direct/group/reverse M2M add/remove/set/clear; scalar user edits; group removal,
  single/bulk deletes and PROTECT failures; superuser/active/staff revocation;
  admin/own password paths; no secret in audits; login/last_login excluded. Use
  actual admin requests, not only helper calls. Retain superuser-only admin security.
- Every writer-family row in the lock graph: successful native audit + exactly
  one invalidation per affected program; no-change/failed-domain action; source-audit,
  batch, per-program audit, CAS and final-validation failure all roll back source.
- Two connections, writer-before-capture and capture-before-writer; barriers/events
  at actual locks and commit points. Prove waiting/order and committed states, not
  just mocked `select_for_update`. Include FK user locks, photo join split, event
  restoration, opposite program IDs sharing a member and distinct-member fan-out.
- Pool entry/exit, missing/pending/disputed/expired evidence, changed-restored profile,
  metadata, grants, receipt+void restoring PA count; retained IDs/generations never
  recover an old accepted token. New program/application during fan-out cannot escape.
- Inspect locking SQL for ordered table/PK acquisition; exercise induced 1205/1213
  timeout/deadlock handling and verify entire-transaction rollback/retry semantics.

**Promotion tests (`test_generation_processing`)**:

- Generation/authority/revision/pointer/coverage/version mismatch; partial/extra
  results or traces, broken audit link, wrong actor/program/policy, changed source,
  zero eligible and >128 retained pool. No dropped incomplete applicants or limit
  truncation. Source revalidation still required even if generation matches.
- Concurrent same and distinct requests; exactly one winning CAS at expected
  revision; no duplicate promotions. Idempotent completed retry checks currentness;
  stale replacement, failure, interruption/recovery and audit failure cannot restore
  an earlier binding or leak a partial graph. Low-level foundation tests cannot
  bypass the public coverage/disposable guard.
- Expiry before/during calculation, at equality, after CAS/before next read, delayed
  expiry worker, repeated expiry invalidation, timezone/day change and clock rollback
  after an observed expiry. No validity claim beyond each protected time check.
- Legacy v1/v2 replay without sidecars, historical reads after all source changes,
  old processor refusal of bound requests, immutable old digests and exact five-
  criterion outputs; four-criterion proposal remains mathematical reference only.
- Registered-session identity mismatch denies writes; unregistered application-mode
  behavior on an OLD-schema disposable fixture uses no new tables. Prove the default
  accepted workflow and 999-test baseline still operate without implicit enlistment.

**Command acceptance sequence after authorized code exists** (module names are
proposed and do not exist yet):

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf.test_generation_migrations ewaf.test_source_invalidation --testrunner scripts.durable_test_runner.DurableTestRunner --noinput
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test accounts.tests.test_authority_generation ewaf.test_generation_concurrency ewaf.test_generation_processing --testrunner scripts.durable_test_runner.DurableTestRunner --noinput
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf --testrunner scripts.durable_test_runner.DurableTestRunner --noinput
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test --testrunner scripts.durable_test_runner.DurableTestRunner --noinput
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py check --database default
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py migrate --plan
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py sqlmigrate ewaf 0006
git diff --check
```

Run focused modules only when created by their authorized increment; do not treat
missing tests as passing. Gate 2B additionally reviews generated SQL before tests
apply it. Full-suite baseline must retain all **999** current tests; report actual
new totals, skips, timings, SQL/server identity, concurrency/rollback evidence and
limitations. No new numerical target or invented future passing count. Any UI
touch in a later integration requires review; this plan authorizes no Admin redesign.

**Owner decision requested next:** whether to authorize **2B only**: creation and
disposable-only testing of this eight-model additive foundation and its services.
No migration execution against application/production data, writer integration,
deployment, live EWAF activation or milestone increase is included. Stop here.
