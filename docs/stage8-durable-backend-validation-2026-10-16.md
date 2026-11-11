# Stage 8 bounded durable backend — development review

Date: October 16, 2026. Accepted milestone: **70%, unchanged**.
Stage 8 and G18 remain incomplete. No operational EWAF authorization or activation.

## Authority and preserved checkpoint

The owner's current instruction explicitly authorizes new additive EWAF persistence models,
new migration files for their tables/indexes/constraints/relationships, minimal registration
and internal-service integration, and migration/numerical testing **only in freshly created,
explicitly disposable MySQL instances with fictional records and policies**. It removes the
schema-authorization blocker recorded in the preceding proposal. This is development
authorization, not Association scoring-policy approval, a signatory assignment, or signed
institutional authorization. It permits no operational database migration, existing-table
alteration, old migration rewrite, backfill, inferred approval, automatic permission
assignment, live processing, publication, release, deployment or Git publication.

Read authority: repository AGENTS.md; current TARGET specification and development guide;
Open Decisions and the confirmed membership/PDAO amendment; October 10 implementation
impact; current G12–G17 implementation, tests and validation; the October 15 authorization
review; the October 16 non-schema validation and schema proposal. Existing mathematical
engines remain authoritative implementations; workbook examples are not approved policies.

Actual branch: `feature/events`.
Actual HEAD: `949eeda33c6aa5d8ee03962209ae8fedeac58ad1`.
Fresh inventory: **511** tracked/staged/untracked nonignored files, captured before editing
in `.local/ewaf-durable-20261016/baseline.json`, including their SHA-256 hashes, status,
branch/HEAD, index entries, and staged/unstaged summaries. The index had 16 staged G16
additions; there were no unstaged tracked edits. All G17 work and the preceding six files
were present locally. Nothing was pulled, reset, cleaned, stashed or switched.

Five pre-existing files have intentional integration edits, listed below. The other 506
baseline files retain their bytes. The staged manifest remains byte-for-byte identical;
the G16 preservation test's one-line working-tree edit is **not staged**. Original copies
of edited files are retained in the review package. No commit, push, merge or main change.

## Exact source inventory

| File | Change and purpose |
| --- | --- |
| `ewaf/models.py` | Additive registration of six durable models; existing model fields unchanged. |
| `ewaf/weighted_scoring.py` | Extract identity-free `calculate_values` kernel; preserve `calculate_synthetic` output/interface and G15–G17 fixture behavior. |
| `ewaf/test_ranking_preservation.py` | Only expected EWAF migration leaf changes from 0004 to 0005; original staged content preserved in index. |
| `ewaf/test_recalculation_preservation.py` | Only expected leaf changes; synthetic no-write/no-route/no-recalculation-table assertions retained. |
| `ewaf/test_pool_services.py` | Only expected leaf changes; preceding non-schema service and barrier assertions retained. |
| `ewaf/durable_models.py` | New request, attempt, historical run, application result, criterion trace and terminal outcome structures. |
| `ewaf/durable_records.py` | New append-only supported-path guards, canonical content digests and mandatory protected audits. |
| `ewaf/durable_services.py` | New test-only complete-pool capture, current verified-input resolution, numerical orchestration, atomic persistence, retries and interruption recovery. |
| `ewaf/durable_testsupport.py` | Explicit fictional definitions and verified evidence fixtures; never seeded as real policies. |
| `ewaf/test_durable_services.py` | Permission/environment, whole-pool, precision, history, retry, rollback and stale-result tests. |
| `ewaf/test_durable_concurrency.py` | Separate-connection MySQL serialization, duplicate-request and source-writer races. |
| `ewaf/test_durable_migrations.py` | Additive operations, InnoDB and fictional pre-existing-row preservation. |
| `ewaf/migrations/0005_durable_development.py` | New additive migration following the actual local 0004 leaf. |
| `scripts/durable_test_runner.py` | In-process disposable-environment capability established by Django's isolated test runner. |
| `docs/stage8-durable-backend-validation-2026-10-16.md` | This authorization, implementation, validation and limitation record. |

Ignored review evidence includes baseline copies, logs, generated SQL, source diffs, hashes
and the review ZIP. These are listed separately by the package manifest, not presented as
application source changes. The existing `scripts/g12_test_runner.py` is unchanged.

## Durable behavior and schema

Six new tables: `DurableRequest`, `DurableAttempt`, `DurableRun`, `DurableResult`,
`DurableTrace`, `DurableOutcome`. Every artifact protects its actor, program and mandatory
audit association. Requests protect the G15 policy, which in turn protects the exact
configuration/AHP validation/evidence policy. Traces protect the exact G12 assessment.
Source/review identities, digests and payloads are retained privately in canonical JSON.

The migration contains six `CreateModel`, one `AddField` (new request's predecessor) and
seven `AddConstraint` operations. SQL inspection found CREATE TABLE and ALTER TABLE only
for the six **new** `ewaf_durable*` tables, including FK indexes/constraints. No existing
business table is altered. Dependencies are `ewaf.0004_scoring_diagnostics`,
`programs.0005_approved_terms`, and the swappable user dependency. There is no data operation,
seed, grant or old migration edit. The custom processing permission is defined but never
assigned to an actual account/group.

Unique constraints enforce request key per program, attempt ordinal per request, one
successful run per request/attempt, one result per run/application, one trace per
result/criterion, and one terminal outcome per attempt/run. Check constraints enforce
positive ordinals, supported criterion codes and valid completed/failed outcome shape.
Same-program ownership, exact source associations and earlier immutable predecessor chains
are validated on supported writes. Existing records cannot be rewritten to introduce cycles.
Completion validates whole-pool result membership, all five traces, audits and exact replay.
Cross-table completeness is a service/model invariant, not a claimed SQL assertion trigger.

Canonical calculated numbers are **JSON strings**, using the established 50-digit Decimal
profile, ROUND_HALF_EVEN and existing exponent/trap/tolerance settings. No SQL Decimal field
narrows them and no float/early rounding is used. Results retain both score scales, exact
tie counts and numbers of strictly higher scores. `business_rank` remains null: no
classification thresholds, winner among ties, beneficiary selection or waitlist is inferred.

Snapshots include full retained pool accounting and explicit in/out-of-scope status,
eligibility/readiness findings, date/timezone/cutoff, exact policy/configuration/validation
payloads and digests, AHP judgments/replay, verified assessments, source manifests,
input values/types/units, observation/expiry dates (including explicit nulls where no
test rule supplies a date), encodings, directions, fixed bounds, normalized values,
contributions, engine/profile/settings, actor/reason/time and predecessor. The numerical
kernel receives values only, never an application ID through a synthetic-fixture API.

Historical payload save/delete/queryset-update/bulk paths are blocked. Supersession is a
new request/run relationship and processing outcomes are append-only. PROTECT prevents
supported deletion of associated audits/history. This does **not** protect against
privileged direct SQL, arbitrary Python internals or external file alteration.

## Complete-pool contract and live-use barriers

No routes, Admin actions, management commands, jobs, UI or application settings were added.
All existing G12–G17 and non-schema operational barriers remain intact. G15
`READINESS_ONLY` payloads remain score-free. Legacy calculation tables remain untouched.

Numerical service calls require active staff/dashboard/private-source permissions plus
`ewaf.process_durablerequest`, re-read from the user table. Requests are restricted to their
recorded actor and explicit program; cross-program retrieval is refused. Officer scopes
for real use remain undecided. The technical permission never establishes policy authority.

An in-process capability exists only during the custom Django test runner. It verifies the
actual MySQL database, server UUID, loopback connection, port and datadir against the fresh
instance created by the existing runner; verifies an empty harness database before test
database setup; requires the dedicated `test_g12_disposable` database and InnoDB tables;
and verifies temporary fixture media before source access. A request boolean, stored
fictional label or environment flag alone cannot grant this capability. The original
runner's fresh-server/system-schema check and restricted database grants are preserved.

The fictional evaluation contract explicitly supplies scope, timezone-aware cutoff,
pending-case handling, comparison and repeat-test semantics. No operational cutoff or
repeat rule is invented. All retained server-side applications form the manifest; only
explicit cutoff admission determines scope. In-scope unresolved eligibility blocks.
An ineligible status without a current audited ineligible case blocks. Eligible applicants
with missing, disputed, expired, unverified or stale required evidence block the entire
calculation. No caller subset, page or slot limit is accepted. More than the inherited
128-applicant engineering limit returns `WHOLE_POOL_UNSUPPORTED`; it does not truncate.

Current G12 sources and latest G14/G15 artifacts are resolved again; saved readiness
diagnostics are not used as authority. Missing definitions/directions/bounds/units remain
explicit failures. The fictional policy never sets any real effective authorization, and
G12 governance/processing reasons are retained in the private manifest.

## Transaction and locking contract

1. Request creation is one Terms-guarded transaction containing request and required audit.
   The request key is content-bound to actor, stripped reason, expected context, explicit
   test policy and predecessor. Same key/content returns the original request; conflicts fail.
2. Transaction A locks Terms then target Program, validates request/actor, deduplicates a
   completed run or rejects an unfinished attempt, and commits STARTED intent plus audit.
3. Transaction B locks Terms, target Program, **all retained target applications by PK**,
   distinct Members by PK, then EligibilityStatus rows by PK. It resolves fresh config and
   verified inputs, checks expected context, calculates the whole eligible pool, resolves
   the complete source context again under those locks, and rechecks permission. Run,
   every result/trace/audit and COMPLETED outcome commit together. No partial graph is
   published if calculation, validation, audit or commit fails.
4. An ordinary exception exits and rolls back B before a separate Terms/Program transaction
   records a generic FAILED outcome/audit. Raw exception data is not copied to audits.
   If that failure audit also fails, the attempt remains explicitly unfinished; no success
   is reported. A KeyboardInterrupt/process crash can likewise leave STARTED intent.
5. Explicit actor-authorized recovery with a reason appends INTERRUPTED under Terms/Program
   locks. There is no automatic lease/takeover. Retry revalidates the whole original expected
   context. A changed context needs a new request; a successful correction creates a new
   complete run linked to its predecessor, never edits prior scores.

Concurrent processing is serialized by actual InnoDB locks and unique keys. A second caller
can receive the same completed run or the explicit unfinished/in-progress refusal. This
is technical deduplication, **not proof of exactly-once execution across arbitrary crashes**
and not permission for real repeat evaluations.

| Existing writer | Participating locks / finding |
| --- | --- |
| G12 assessments; G14/G15 configuration, validation and proposals; protected terms | Existing Terms/Program contract serializes against capture. Current revision and digest rechecks invalidate old contexts. |
| Member profile/status; document verification | Existing Member lock serializes with full-pool member locks; no writer modifications. |
| Eligibility, photo/application correction and closure | Existing Program/Application (and relevant Member) locks serialize; closure cannot silently remove a pending candidate. |
| Program submission | Existing Terms/Program boundary serializes entry; every later retained row also changes the manifest, even if outside the cutoff. |
| Cross-program assistance release/void | Existing writer locks its own Program/Application then the shared Member. Capture locks that Member; current G12 PA context includes all retained release/void state across programs. No acquisition of another program's lock is added to the writer. |

**Unresolved wider dependencies / promotion blocked:** there is no source outbox, generation
counter or effective institutional authorization control in this subset. Membership-intake
and reference/evidence metadata edits, administration outside the listed services, and
private-file bytes do not all share this complete lock contract. G12's byte-observation
limitation still applies. Additional writer coverage, source invalidation events and
institutional admission/revision rules require another scoped increment. No global
linearizable source snapshot or operational atomic promotion is claimed. Matching reads
are not an acceptance token.

Consequently there is **no current-result pointer**. A COMPLETED outcome means an immutable,
internally complete historical test calculation. The private test inspection service
replays history, validates audits and re-resolves sources under locks; it refuses stale
history and any predecessor with a replacement request, even if replacement failed.
`sources_match_now` is a diagnostic observation; `current_promotion` and
`operational_ready` are always false. `require_operational_result` always rejects.

## Validation commands and evidence

All commands run from the repository root. Never run the normal launcher while this
unapplied migration is pending. No command below connects to the application database.

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py makemigrations ewaf --name durable_development
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py sqlmigrate ewaf 0005
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf.test_durable_services --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 2
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf.test_durable_services ewaf.test_durable_concurrency ewaf.test_durable_migrations --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 2
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 2
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 2
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py check --database default
git diff --check
git diff --cached --check
```

| Executed run | Result | Runtime | Failures / errors / skips | Disposable directory suffix |
| --- | --- | --- | --- | --- |
| Migration generation | Exit 0; additive 0005 created | — | — | `ocghcsfu` |
| Initial focused | 26 run, exit 1 | 20.441 s | 1 / 16 / 0 | `wl7ipphr` |
| Corrected initial focused | 28 passed, exit 0 | 30.833 s | 0 / 0 / 0 | `r15nwnsp` |
| Expanded focused, including incidental G12 discovery | 53 passed, exit 0 | 86.722 s | 0 / 0 / 0 | `yffjyscj` |
| Final focused | 47 passed, exit 0 | 60.816 s | 0 / 0 / 0 | `741ps_ac` |
| Every EWAF test, including G12–G17 and non-schema pool | 403 passed, exit 0 | 179.783 s | 0 / 0 / 0 | `78wuc3fy` |
| Full project suite | 898 passed, exit 0 | 296.693 s | 0 / 0 / 0 | `eckzgmav` |
| Generated SQL | Exit 0; inspected six new table targets only | — | — | `fktafpeb` |
| Migration drift | Exit 0; no changes detected | — | — | `8g3pkyyr` |
| Django/database check | Exit 0; no issues, 0 silenced | — | — | `qmhyew7k` |

Directories use the prefix `santolan-g12-tests-` beneath the Windows temporary directory.
Counts overlap and must not be added together. No separate browser run was performed;
there is no UI change. MySQL **8.4.11**, session isolation **READ-COMMITTED**, and all test
tables **InnoDB** were observed in the numerical runs. Full-suite database identity:
`test_g12_disposable`, loopback port `57189`, server UUID
`16678d8b-c943-11f1-ac44-581122e63603`, fresh datadir
`%TEMP%/santolan-g12-tests-eckzgmav/data/`. These identifiers disclose no credentials.
The normal application's connection settings, .env, datadir and private uploads were not
read or used. Only the existing MySQL executable was reused.

Both Git whitespace checks pass. Python syntax and exact file inventory checks pass.
The three pre-existing test files retain their original newline convention and differ
only in the expected migration leaf. Package verification checks every baseline hash,
permits only the five documented integration edits, checks the unchanged index/HEAD,
verifies test counts/verdicts/no skips, inspects SQL targets, and reads back every ZIP
member against its source bytes. The archive contains no database or connection settings.

The first sandbox migration-generation launch stopped before initialization because the
temporary mysql.ini write was denied. It was rerun with tool escalation, without weakening
the runner. The first actual 26-test run had 1 failure and 16 errors: missing units in the
fictional ES/PR evidence policy caused association mismatches, and a fixture passed an
unsupported expiry argument. Fictional units and a real document-expiry scenario corrected
the fixtures; the source guards were not loosened. The corrected initial run passed 28.

The expanded run passed 53, including nine existing G12 concurrency tests incidentally
discovered through an imported TestCase class. That duplicate discovery was removed and
three additional focused cases added; the final focused run passed 47. Source review also
added validation of attempt/outcome audits on freshness reads; the later regression/full
runs cover that final source revision.

Migration validation reverses only the new empty durable tables in a disposable instance,
then migrates forward with fictional pre-existing business rows present and compares every
prior model's rows. This demonstrates forward preservation, not automatic MySQL DDL
rollback or production failure recovery. Existing G12–G15 migration tests also remain.
Actual separate-connection concurrency tests use event coordination around real writer
transactions; no SQLite or mocked locks substitute for MySQL.

## Remaining decisions and exclusions

Still unresolved for operational use: income basis/reference period, ES categories and
encoding, dependent definition, PR rubric, PA measure/lookback, all directions/bounds,
classification thresholds, business ties, evidence policy, approval authority/effective
dates, officer scope, evaluation cutoff/admission and corrections/repeat/revision rules.
G06-B2/B3 institutional processing dependencies remain. No fixture is an approved policy.

No guided Admin/AHP UI, live scoring/ranking, selection/waitlist, publication, dashboards,
reports, membership/photo/PDAO changes, deployment or migration of actual member data.
The minimalist eight-module Admin Portal is unchanged. The historical 851-test baseline
is not represented as a new run. No 80%, Stage 8 completion or G18 acceptance is claimed.

## Review package

`.local/ewaf-durable-20261016/stage8-durable-review.zip` contains this increment's source,
migration, tests, generated SQL, exact source diffs, validation logs, manifest and SHA-256
hashes. The six preceding non-schema files are included under **baseline-non-schema/**,
using their pre-increment bytes; they are not newly authored work. The original schema
proposal's missing-authorization statements describe that earlier checkpoint and are
superseded only within the development scope recorded above. Supporting G12–G17 source
and validation references are separately labeled baseline dependencies.

The package excludes .env, credentials, MySQL configuration/datadirs, private uploads and
actual member data. Local logs/hashes are review evidence, not signed CI or owner acceptance.
