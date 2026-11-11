# G18-B Gate 2C authority integration validation

2026-10-18. Accepted milestone: **70%**. Gate 2C only. No Gate 2D, 2E or 2F,
operational scoring, ranking, selection, publication or development promotion.
The separate four-criterion proposal remains inactive.

## Checkpoint and preservation

Local branch `feature/events`; HEAD `949eeda33c6aa5d8ee03962209ae8fedeac58ad1`.
Before editing, recorded branch, HEAD, porcelain status, staged binary diff,
index hash and 576 baseline file hashes. No remote checkout was fetched.
The application database, member records and private uploads were not accessed.
Configuration was hashed for preservation, not loaded into test processes.

Final verification: **574 of 576 baseline entries remain byte-identical**. Only
the two existing account files listed below changed; no baseline file is missing.
Three repository files are new. The complete staged binary diff, staged index,
branch and HEAD remain identical. Every existing test file, historical migration,
Gate 2B foundation, numerical engine, Gate 1 observer, source writer outside the
authorized account files, UI asset and inactive four-criterion reference is preserved.

## Exact repository file inventory

| File | Change |
|---|---|
| `accounts/admin.py` | Existing file: outer add/change/delete/action boundaries, fresh authority fencing, and registered-session password path with post-commit session rotation. Existing labels, permission rules and styling preserved. |
| `accounts/views.py` | Existing file: own-password POST fence before form validation; credential, SecurityEvent and invalidation atomic; session rotation after commit in the registered path. Unregistered behavior retained. |
| `accounts/authority_services.py` | New: private disposable registration, authority lock/transaction adapter, before/after comparison, native-audit verification, monotonic invalidations and forward/reverse M2M adapters. |
| `accounts/tests/test_authority_generation.py` | New: fictional actual Admin and password requests, M2M, audit/CAS rollback, capability boundaries and separate-connection MySQL concurrency. |
| This report | New: scope, coverage, transaction evidence, validation and review limitations. |

Review artifacts are under `.local/g18-b-gate2c/` and are not staged. No schema,
migration, model registration, settings, URL, template, CSS, role definition or
permission catalog changes. No changes to any EWAF foundation/engine/digest code,
membership/member/document/program/event/assistance writer or PDAO enforcement.

## Installation and capability boundary

This follows the Gate 2A disposable-session contract. Normal application requests
do not query AuthorityGeneration or other new tables. Migration 0006 remains an
unapplied development dependency of the application checkpoint; this task did not
query the application's migration recorder or run migrations there.

Only the private test bootstrap can register a generation-integrated session.
It requires the existing DurableTestRunner capability, actual database/server
identity, temporary fictional media, existing foundation initialization and the
existing durable bootstrap permissions. No request parameter, setting, database
label or public boolean enables it. Registration is process-local and shared with
the separate connections used by concurrency tests. Each writer revalidates the
actual disposable identity; mismatch or missing authority state fails closed.

A closed registration cannot resume the same initialization audit. A new isolated
fixture/bootstrap is required; no reconciliation service is exposed. This avoids
silently certifying unfenced changes made during suspension. Initialization and
existing foundation services remain unchanged. Old test/application workflows do
not implicitly enlist merely because the foundation tables exist.

## Authority mutation coverage matrix

Coverage below means **within a registered, verified disposable session**.

| Path | Coverage and mandatory native audit |
|---|---|
| User add | COVERED: outer `add_view` precedes UserAdmin's own transaction; scalar save, related save and ADDITION LogEntry commit with invalidation. |
| User edits, activation/deactivation, staff/superuser, identity fields | COVERED: full change form; current actor re-fetched under locks; one CHANGE log per changed target. |
| User direct permissions and group membership via Admin | COVERED: `save_related` and all M2M changes remain inside the complete outer transaction, followed by native log validation. |
| Group add/edit/permission changes | COVERED: ADDITION/CHANGE log and GROUP_CHANGE invalidation. Group permission changes invalidate the global authority epoch without per-program fan-out. |
| Single user/group delete | COVERED: collector, PROTECT checks, DELETION log and delete share the fence. Subject ID is retained without a target FK. |
| Bulk `delete_selected` for users/groups | COVERED: changelist boundary starts before native logging. Each deleted target gets its own native log and consecutive authority event; all events and all deletes commit together. Confirmation alone creates no event. |
| Administrator password set/unset | COVERED: installed Django form and usable-password checks retained; native CHANGE log plus CREDENTIAL_CHANGE event. Session rotation/success response follow successful commit. |
| Staff own password | COVERED: fresh active staff user, existing old-password validation, PASSWORD_CHANGED SecurityEvent and credential invalidation; own session retained after commit. No superuser/durable-processing permission is added to this action. |
| M2M `add/remove/set/clear` through internal adapter | COVERED: User.groups, User.user_permissions, Group.permissions and reverse Group.user_set, Permission.user_set, Permission.group_set. Per changed root, native CHANGE log plus invalidation. No HTTP endpoint. |
| Valid unchanged forms / unchanged M2M sets | COVERED NO-OP: no authority event. Django's normal empty change log may remain. |
| Revoke followed by restore | COVERED: separate monotonic generations and immutable events even if effective grants return to their original set. |
| Login/logout, last_login, session refresh, throttles, automatic hash upgrade | EXCLUDED maintenance: no authority event or new fence. Concurrent login-failure audits are excluded from the password operation's audit set. |
| Unknown future admin actions | FAIL-CLOSED in registered sessions; only the existing delete action is allowlisted. New actions need integration review. |
| Direct raw ORM/M2M, shell/imports, createsuperuser/changepassword, post_migrate permission catalog changes | UNFENCED / PROHIBITED during a registered generation-aware session. No broad signals or monkey patches claim to cover these paths. Fixture/catalog setup precedes registration; deliberate raw fixture writes in tests are explicitly adversarial/test setup, not integrated services. |
| Privileged SQL, another process, custom backends, external tampering | OUTSIDE CONTRACT. No CDC, database trigger or DBA-proof guarantee. Default-disabled promotion prevents these foundations from supplying consumable results. |

Historical native Django audits retain their existing protections; no schema-level
immutability is added to LogEntry or SecurityEvent. New AuthorityInvalidation rows
are append-only through the foundation's supported interfaces and freeze native
audit identities/content hashes. Privileged native-audit tampering is outside the
writer contract and can invalidate historical reference verification.

## Transaction and lock evidence

Installed Django 5.2.17 source was inspected before editing: UserAdmin.add_view,
user_change_password, ModelAdmin.changeform_view/delete_view/changelist_view,
save_related, native logging, delete_selected, PasswordChangeView/Form and
update_session_auth_hash. In particular, add_view has an outer transaction and
bulk deletion logs before delete_queryset. Late save_model/audit hooks would miss
the required boundary. No installed Django source was modified.

The implemented registered writer order is:

```
top-level autocommit check
Terms mutex -> AuthorityGeneration
-> all existing Users by PK -> Groups by PK -> Permissions by PK
-> User.groups through rows by PK -> User.user_permissions through rows by PK
-> Group.permissions through rows by PK
-> re-fetch and authorize actor -> before snapshot
-> inherited scalar/M2M/delete work and native audit
-> validate exact changed targets and native audits
-> append immutable authority event(s) -> expected-value CAS -> validate tail
-> commit
```

This deliberately coarse lock scope covers the small disposable authority catalog.
It avoids discovering lower-key auth rows during cascades/reverse M2M. All existing
auth roots are locked, not just the actor. New rows are inserted under the global
fence. Snapshot password hashes are transient equality inputs only; snapshots,
hashes, credentials, tokens and request bodies are never generation audit payloads.
Audits contain a fixed server-generated action reason and native reference hashes,
not a claim of human policy approval.

Ownership uses Gate 2B's actual connection/outer-transaction guard. Nested inherited
Admin calls join only the same request's owned transaction. Arbitrary pre-existing
transactions are refused before Terms acquisition. Actor checks use a fresh User,
not cached has_perm results. Deliberate self-revocation can commit if the actor was
authorized at the protected mutation boundary; it does not retain future authority.

Every changed target must have exactly one newly created native audit of the
correct type, actor, target and action. Missing/duplicated audits reject the entire
operation. Foundation validation also rejects missing/changed/reused native audit
references, inconsistent generations and overflow. Bulk events advance sequentially
inside one transaction; failure on the second event rolls back the first and every
deleted target. No audit/invalidation is deferred to on_commit or a background job.

Password session rotation is deliberately after successful source/audit/generation
commit, matching Gate 2A. A post-commit session-store failure does not undo a committed
credential; it cannot produce a partial authority audit. Failed DB auditing leaves
the old credential and existing session intact. Superuser-only Django Admin checks,
password secrecy decorators, form validation, messages and destinations are retained.

Authority changes do not update ProgramSourceState. Old authority tokens fail the
existing expected-token checks while historical source state, request/run bindings,
digests and calculations remain unchanged. No current-result interface is created.

## Test execution and evidence

All Django/MySQL commands use `.venv/Scripts/python.exe -B scripts/g12_test_runner.py`.
Each invocation initializes a new temporary MySQL datadir with loopback-only access,
an empty `g12_empty` base, isolated test grants, `.env` disabled and fictional media.
Tests additionally use `--testrunner scripts.durable_test_runner.DurableTestRunner
--noinput`, which verifies database/server identity, InnoDB and the test database.
No SQLite, keepdb, regular manage.py test/migrate or application DB is used.

Commands executed (each line through that harness prefix):

```
test accounts.tests.test_authority_generation --testrunner scripts.durable_test_runner.DurableTestRunner --noinput
test accounts audit --testrunner scripts.durable_test_runner.DurableTestRunner --noinput
test ewaf --testrunner scripts.durable_test_runner.DurableTestRunner --noinput
test --testrunner scripts.durable_test_runner.DurableTestRunner --noinput
check --database default
makemigrations --check --dry-run
```

| Executed run | Tests | Seconds | Result |
|---|---:|---:|---|
| Initial focused authority tests | 42 | 48.789 | One assertion failure; corrected below. |
| Expanded focused authority tests | 49 | 65.405 | Passed. |
| Intermediate account/security | 68 | 83.848 | Passed. |
| Account/security with login-audit exclusion | 69 | 98.193 | Passed. |
| Final account/security, including session re-entry denial | 70 | 93.353 | Passed; all 51 new Gate 2C tests plus 19 existing account tests. |
| EWAF regression | 509 | 519.761 | Passed, including Gate 2B migration/binding/history preservation. |
| Intermediate full project | 1,100 | 858.246 | Passed; before the final two additional safeguards/tests. |
| Final full project | 1,102 | 801.887 | Passed; all 1,051 existing tests plus 51 new Gate 2C tests. |

The initial failure was a test expectation: Django's test client correctly returned
HTTP 403 for PermissionDenied on a mismatched registered identity, whereas the
test expected an uncaught exception. The test now asserts 403 and preserved state.
No production authorization check was weakened. Subsequent additions covered
post-commit password-session updates, unrelated login-audit exclusion and refusal
to resume a suspended initialized session. These refinements caused the additional
account/security and final full-suite runs; no failing test was skipped or deleted.

All completed passing runs have zero failures, errors or skips. No automatic test
retry or authority transaction retry is implemented. MySQL reports **8.4.11,
READ-COMMITTED, all test tables InnoDB**. Each sanitized log retains the distinct
disposable datadir suffix, server UUID and port attestation. No historical 1,051-test
baseline is presented as a newly executed result.

Django/database checks: zero issues. Migration-drift check: `No changes detected`.
Working-tree and staged `git diff --check` pass; only pre-existing line-ending
warnings for unrelated preserved files appear. All five Gate 2C files separately
pass a trailing-whitespace scan, including new files not visible in git diff.

Actual MySQL concurrency tests use distinct connection IDs. Two real Admin POSTs
wait at Terms and commit consecutive generations. A waiting request whose actor is
revoked by the first request returns 403 after acquiring the fence, without changing
the group. SQL capture confirms Terms/H/Users/Groups/Permissions/through-table order.
A separate connection holding Terms induces real MySQL error **1205** with a
one-second session lock timeout; the request rolls back and is not retried. No
claim of induced 1213 deadlock testing is made in Gate 2C.

Rollback tests include missing/duplicate native logs, native audit exceptions,
generation-audit failures, CAS failure, a second CAS failure after the first bulk
delete event, missing password SecurityEvent and password invalidation failure.
They verify restoration of account state, M2M rows, all deletion targets, password,
old session and generation/native audit counts. Revoke-and-restore yields distinct
events. Source generations/revisions remain unchanged while old authority-bound
tokens are rejected. Unregistered requests are captured to prove no foundation-table
queries, and registered missing-state/identity mismatch cases deny before writes.

## Remaining limitations and review boundary

- No Gate 2D/E source writer integration, complete-pool promotion, current facade,
  operational consumer or release/publication capability. Foundation coverage stays
  `g18-2b-foundation-nonpromotable-1`; DevelopmentPromotion recording remains denied.
- Global locks serialize authority mutations and can contend with login/last-login
  FK/user writes. SQL lock order and separate-connection waiting are tested; this is
  not a proof of deadlock freedom for every future writer. Lock errors abort without
  automatic retries. Any retry must restart the complete request with current state.
- Unfenced privileged writes and permission catalog maintenance cannot be certified
  by Admin hooks. Do not resume the same registered epoch after suspension. A future
  catalog reconciliation/writer integration requires separate authorization.
- Normal application mode deliberately remains unintegrated until an authorized
  installation/deployment plan exists. It neither requires nor probes migration 0006.
- Historical actor PROTECT relationships can block deletion; this preserves audit
  provenance rather than silently removing history.
- Scoring definitions, bounds/directions, PA lookback, classification/ties, approving
  role/effective date/program scope and revised four-criterion activation remain
  unresolved policy matters. This technical increment supplies none of those approvals.

Stop after Gate 2C for owner review. Accepted milestone remains **70%**.

## Review package

`.local/g18-b-gate2c/g18-b-gate2c-review-2026-10-18.zip` contains the five exact
Gate 2C files, unchanged design/foundation/runner references, sanitized fictional
logs, actual test-result JSON, migration-leaf inventory, baseline-relative patch,
preservation summary and preserved-file hashes. `manifest.json` and `SHA256SUMS`
cover payload bytes; `.local/g18-b-gate2c/review-package.sha256` records the ZIP hash.
The packager verifies ZIP integrity and every payload hash after writing it.

This is an incremental review package, not a replacement checkout or complete
repository backup. Retain the local staged/unstaged/untracked baseline. Explicit
allowlisting excludes credentials, environment files, application databases,
MySQL data/configuration, private member records and private uploads. No file was
staged, committed, pushed, merged, reset, pulled, cleaned, stashed or deployed.
