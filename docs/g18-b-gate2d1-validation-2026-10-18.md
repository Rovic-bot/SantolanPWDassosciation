# G18-B Gate 2D-1 source-writer integration validation

2026-10-18. **Accepted milestone remains 70%.** Disposable-only development.
No Gate 2D-2/2E/2F, operational EWAF, ranking, selection, public results or
development-result promotion. The four-criterion proposal remains inactive.

## Checkpoint, authorization and preservation

Branch `feature/events`; HEAD `949eeda33c6aa5d8ee03962209ae8fedeac58ad1`.
Captured branch, HEAD, complete porcelain status, staged binary diff, index hash,
579 baseline file hashes and exact bytes of the six selected writer modules before
editing. Read the current specification, development guide, Open Decisions, Gate 2A
design/lock graph and Gate 2B/2C validation. TARGET requirements are not current
operational approval; this increment supplies no policy decisions.

**573 baseline entries remain byte-identical.** The six edited files have only
19 inserted lines: six imports and 13 outer decorators. Removing precisely these
lines reconstructs their original bytes, including pre-existing mixed line endings.
Every existing function body, permission check, transaction decorator, validation,
audit call and return path is retained. No baseline file is missing. Branch, HEAD,
staged index and staged diff remain identical. No remote checkpoint was retrieved.

Migration leaves remain accounts 0001, announcements 0004, assistance 0003,
audit 0002, core 0001, documents 0003, events 0006, ewaf 0006, members 0003,
membership 0004 and programs 0005. All migration bytes are unchanged. Application
migration state was not queried; the existing checkpoint reports EWAF 0006 as
unapplied there. The application database, member records and private uploads were
not accessed. No settings, PDAO enforcement, schema or migration changes.

## Exact repository inventory

| File | Change |
|---|---|
| `programs/services.py` | Import plus three decorators: save program, change publication, save requirement. |
| `programs/approval_services.py` | Import plus approval-record decorator; original PDAO rules unchanged. |
| `programs/binding_services.py` | Import plus terms-capture and approval-binding decorators. |
| `ewaf/evidence_services.py` | Import plus evidence-policy and criterion-assessment decorators. Readiness function untouched. |
| `ewaf/configuration_services.py` | Import plus configuration, validation, review and authority-evidence decorators. |
| `ewaf/scoring_services.py` | Import plus scoring-policy decorator. Applicant diagnostic function untouched. |
| `ewaf/source_invalidation.py` | New disposable-session adapter: scope derivation, generation tokens, transaction ownership, native-audit checks and invalidation. |
| `ewaf/test_source_writers.py` | New 36-test fictional integration/concurrency/history suite. |
| This report | New validation, source coverage, lock findings and review boundary. |

Artifacts under `.local/g18-b-gate2d1/` are unstaged. Existing G12-G18-B Gate 2C
sources, eight foundation models, foundation services, all existing tests,
historical engines/digests, Gate 1 observations, inactive four-criterion mathematics,
Admin UI and excluded domain writers remain preserved.

## Verified source-coverage matrix

All COVERED entries apply only inside the already verified disposable session.
Each scope is derived from the actual service argument or database ownership,
never from caller-selected affected-program lists.

| Entry point | Scope, native audit and integration finding |
|---|---|
| `programs.services.save_program` | COVERED. Existing program from `pk`; new creation obtains its server-generated ID from the original writer. `created`/`updated`, plus the existing `disability_types_configured` audit when applicable. One invalidation even when two native logs are required. |
| `programs.services.save_requirement` | COVERED. One owning program from `pk`; `requirement_added`/`requirement_updated`. Existing submitted/protected requirements and limits remain enforced. |
| `programs.services.change_publication` | COVERED. One program; original status-action audit or `policy_authorized`. Existing binding, approval, status, version and confirmation rules unchanged. This is program availability, not EWAF-result publication. |
| `programs.approval_services.record_pdao_approval` | COVERED. One program; `pdao_recorded`. Manual approval evidence and both expected versions still required. Does not toggle PDAO enforcement or confer new authorization. |
| `programs.binding_services.capture_terms` | COVERED. One program; `terms_recorded`; existing control explicitly locked after SourceState. Same digest, version, immutable revision and duplicate/protection checks. |
| `programs.binding_services.bind_approval` | COVERED. One program; `approval_bound`; control locked after SourceState. Same cross-program, current-revision, latest-approval and manual-confirmation checks. |
| `ewaf.evidence_services.record_policy` | COVERED. One program; `g12_evidencepolicyrevision`. Original policy/provenance/context validation and private historical digest preserved. |
| `ewaf.evidence_services.record_assessment` | COVERED. Resolve actual application ownership under Terms/H before Program lock. `g12_criterionassessment`. Existing Program -> Application -> Member order can follow the new prefix without rewriting member/document locking. |
| `ewaf.configuration_services.record_configuration` | COVERED. One program; `g14_configurationrevision`; current policy/context checks and historical five-criterion mathematics unchanged. |
| `ewaf.configuration_services.record_validation` | COVERED. One program; `g14_configurationvalidation`; original configuration lock follows the new prefix. Even numerically identical newly retained validations remain dependency changes. |
| `ewaf.configuration_services.record_review` | COVERED. One program; `g14_configurationreview`; original Configuration -> Validation locking retained. No operational approval inferred. |
| `ewaf.configuration_services.record_authority_evidence` | COVERED. One program; `g14_configurationauthorizationevidence`; exact artifact lineage and attestation remain mandatory; no activation. |
| `ewaf.scoring_services.record_scoring_policy` | COVERED. One program; `g15_scoringpolicyrevision`; proposed definitions, current references and old profile preserved. No calculation or scoring activation is introduced. |
| `record_readiness`, applicant diagnostic/trace persistence | DEFERRED to separately authorized Gate 2D-2 review. These remain audit dependencies; this increment does not narrow them or claim they advance source generations. |
| Application submission, photo/correction/closure, linked event writers | DEFERRED to Gate 2D-2/appropriate writer increment. Existing application/member/photo locks and cross-source relationships require their own review. No changes made. |
| Membership, Members, Documents, Assistance; reference metadata/Admin writers | DEFERRED to Gate 2E or separately authorized scope. No changes made, including receipt/void cross-program fan-out and PDAO enforcement. |
| Raw ORM/SQL, unwrapped imports/commands, external file tampering | UNFENCED / outside the contract. Prohibited during claimed integrated source mutation use. No CDC, trigger, signal, SQL-tamper or complete-system freshness claim. |

Deferred/unfenced paths are not silently considered covered. The foundation retains
`g18-2b-foundation-nonpromotable-1`; no complete-pool promotion or current-result
consumer exists. Existing Gate 2C global authority integration is reused unchanged,
without per-program authority fan-out.

## Lock-order and transaction findings

Inspected each selected original function before editing. Every selected writer
already owns Terms before its program/source rows. None calls another selected
top-level writer; helpers such as `persist` remain internal to that transaction.
The adapter is installed **outside** the existing Terms and atomic decorators:

```
reject arbitrary existing transaction
Terms mutex -> AuthorityGeneration
-> resolve actual single-program scope
-> Program -> ProgramSourceState
-> optional existing ProgramApprovalControl (capture/bind only)
-> original writer's locks and validation
-> original business write + native ProgramLog
-> fresh actor/session validation + native audit/scope validation
-> expected-token recheck -> SourceMutationBatch -> SourceInvalidation
-> expected-value state CAS -> final batch/state/authority validation -> COMMIT
```

Criterion assessment retains Program -> Application -> Member after the new prefix;
the repeated Program lock is already held. No joined photo lock, new member lock
ordering or broad source-writer refactor is needed here. Configuration validation
retains its Configuration lock; review/authority recording retain Configuration ->
Validation. Binding control's existing get/create/save is now preceded by an
explicit lock when the row exists. New rows are inserted under their existing
parent/global fence; there is no existing row to prelock.

Original nested Terms decorators re-enter the **already held** mutex on the same
connection and root transaction. They do not first acquire Terms after a source
lock. A caller already holding an arbitrary transaction is rejected before entry.
The original service atomic blocks become savepoints under the new owned root;
returning from one does not commit the source before its invalidation.

SQL capture verifies the Terms/H/Program/SourceState prefix and assessment's later
Application/Member locks, plus control ordering. Two actual MySQL connection IDs
exercise waiting under the shared mutex. These are bounded runtime proofs, not a
claim of deadlock freedom for deferred or privileged writers.

## Tokens, native audits, no-ops and initialization

Existing-program mutations require `source_expected={str(program_id): token}`.
The exact token contains source generation, global authority generation, revision
and current-binding identity. Missing state, missing/extra scope, stale generation,
authority, revision or pointer rejects the operation. Existing business versions
and context digests are independently validated by the unchanged writer.

New program creation requires only the expected current global authority generation,
because its program ID does not exist yet. The original writer creates the program
and native audit(s); its new state is initialized from 0 to generation/revision 1
with one INITIALIZE batch/invalidation in the same root transaction. No historical
program is silently initialized by an update, no policy is seeded and no result
becomes current. A failed audit/transition removes the entire uncommitted creation.

The adapter compares private before/after values for the selected source families
and all newly observed ProgramLog rows. These equality observations are not stored,
not new historical digests and not an atomic promotion mechanism. Every committed
change must have the exact expected native action set, actor and program; immutable
artifact results must reference that exact native audit. Missing, duplicated or
out-of-scope native logs reject the transaction. Foundation validators retain
native reference hashes, enforce consecutive bounded generations, require exact
CAS row counts and validate the complete one-program batch before commit.

There is **one invalidation per program per successful top-level call**, including
calls with multiple original native audits. Failed business validation creates none.
A protected unchanged save that writes neither a source nor an audit creates none.
Unprotected legacy saves that increment Program.version and retain a new audit are
real dependency changes even if visible form values match; their invalidations are
deliberately retained. Likewise, another validation/review/assessment revision is
not discarded because its numerical or descriptive content matches an earlier one.
This preserves Gate 1's conservative audit-dependency rules without changing its
observer, digest formats or comparison envelope.

Actors are freshly reloaded before the original permission checks. Their current
identity/status/effective grants are checked again before invalidation. A cached
superuser instance cannot bypass revocation. No role definitions or grants change.
Authority state must still match at final validation. No invalidation/audit is
asynchronous or deferred to on_commit. Native audit, invalidation, CAS and final
validation failures roll back business state and both audit layers together.

## Development boundary

The existing Gate 2C private registration supplies verified process-local disposable
identity, shared across its test connections. Every integrated write rechecks it.
Neither a caller token nor an ordinary Admin operation can register the session.
Outside it, the original service executes unchanged and queries no new foundation
tables. Supplying a token while unregistered fails rather than activating anything.
Registered calls without tokens fail closed. No UI token plumbing, configuration
flag, public endpoint, operational protocol or session-resume shortcut was added.

## Executed validation

Each Django invocation uses a new disposable MySQL datadir and loopback port through
`.venv/Scripts/python.exe -B scripts/g12_test_runner.py`, with `.env` disabled,
isolated grants and fictional temporary media. Tests use
`--testrunner scripts.durable_test_runner.DurableTestRunner --noinput`. The runner
attests the actual database/server identity, MySQL 8.4.11, READ-COMMITTED and InnoDB.
No SQLite, keepdb, application/production DB or regular manage.py migration command.

| Run | Tests | Seconds | Actual result |
|---|---:|---:|---|
| Initial focused | 33 | 32.403 | One test-helper error; corrected below. |
| Final focused | 36 | 50.378 | Passed; zero failures/errors/skips. |
| Program regression | 150 | 120.198 | Passed; zero failures/errors/skips. |
| EWAF regression | 545 | 507.019 | Passed; zero failures/errors/skips. |
| Full project | 1,138 | 829.153 | Passed; all 1,102 existing tests plus 36 new tests; zero failures/errors/skips. |

The initial approval test used an old helper that folded arbitrary keyword arguments
into form data. It placed `source_expected` there instead of passing it to the
service, so the adapter correctly rejected incomplete scope. The new test calls
the actual approval service with the token as a service argument. No original test
helper, scope check or production permission check was weakened. The final focused
run adds out-of-scope audit rejection, control lock evidence and waiting-writer
success after rollback, plus retained request/run binding digest verification.

Executed commands after the harness prefix:

```
test ewaf.test_source_writers --testrunner scripts.durable_test_runner.DurableTestRunner --noinput
test programs --testrunner scripts.durable_test_runner.DurableTestRunner --noinput
test ewaf --testrunner scripts.durable_test_runner.DurableTestRunner --noinput
test --testrunner scripts.durable_test_runner.DurableTestRunner --noinput
check --database default
makemigrations --check --dry-run
```

Django/database checks pass with zero issues. Migration-drift verification reports
`No changes detected`. Working-tree and staged `git diff --check` pass, as does
the explicit new-file whitespace scan; only pre-existing line-ending notices remain.
The review packager verifies the source delta, baseline preservation, ZIP integrity
and each payload hash. All final run evidence is included in the package.
No automatic transaction retry is implemented. The initial error and all completed
run logs are retained; no failed test is hidden, removed or skipped.

Focused evidence covers all 13 successful writer entries, genuine protected no-ops,
conservative same-value audit changes, program ABA, stale source/business/authority
tokens, incomplete scope, missing state, fresh permissions, native audit errors,
duplicate/out-of-scope audits, failed batch/audit/CAS/final authorization/final
validation, complete creation rollback and private capability denial. Two-connection
tests prove one winner for a shared expected token after commit, and a valid waiting
writer after the first transaction rolls back. Historical durable graphs and
request/run bindings retain identical digests and replay after source invalidation;
operational access remains denied and all current pointers remain null.

## Limitations and stopping boundary

- This is single-program integration for the 13 named paths. Deferred application,
  member/document/assistance/event/reference writers still require separately
  authorized work. No complete-system freshness or atomic current-result claim.
- Privileged SQL/ORM and external files can bypass the protocol. Unfenced concurrent
  native audit insertions may conservatively reject a source call; the global audit
  check does not silently certify an unexplained extra scope.
- The shared mutex and full selected-history equality observations favor correctness
  over throughput. Large-history performance and all future lock interactions have
  not been accepted. Lock errors must roll back; retry must restart the whole call.
- No expiry worker, authority reconciliation, dispatcher/current facade or promotion
  implementation. Existing historical processing and replay stay available within
  their previous development restrictions, without a currently usable result claim.
- No PDAO enforcement, Admin UI, production configuration or database migration.
  Remaining Association scoring, normalization, PA-window, classification/tie,
  authority/date/program-scope and four-criterion activation decisions remain open.

Stop after Gate 2D-1 for independent review. Do not proceed to Gate 2D-2. **70%**.

## Review package

`.local/g18-b-gate2d1/g18-b-gate2d1-review-2026-10-18.zip` contains the nine exact
changed/new files, unchanged foundation/session/design references, sanitized test
logs, baseline-relative patch, preservation summary, migration leaves, actual test
results and per-file hashes. `manifest.json`/`SHA256SUMS` cover payload bytes;
`review-package.sha256` records the ZIP hash. ZIP integrity and hashes are verified.

It is a scoped review delta, not a replacement checkout. Keep the local baseline
with all its staged/unstaged/untracked work. Explicit allowlisting excludes
credentials, environment files, application databases, MySQL data/configuration,
real member records and private uploads. Nothing is staged, committed, pushed,
merged, reset, pulled, cleaned, stashed or deployed.
