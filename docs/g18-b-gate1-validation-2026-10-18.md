# G18-B Gate 1 validation report

Local `feature/events`, 2026-10-18. **Accepted milestone: 70%.**
Migration-free source freshness and complete-pool hardening only. Gate 2 is a
separate proposal; operational EWAF scoring, ranking, beneficiary selection and public
EWAF results remain disabled. The four-criterion configuration remains proposed
and inactive. No policy approval date or program authorization was invented.

## Exact change scope

| File | Change |
|---|---|
| `ewaf/durable_services.py` | Existing file modified: versioned supplemental capture, stale duplicate/replacement request rejection, pre-replay inventory/input checks, final source/permission recheck after graph persistence, historical-only inspection. |
| `ewaf/source_freshness.py` | New read-only dependency observer; no models, signals, source writers or migrations. |
| `ewaf/test_source_freshness.py` | New 26-test fictional MySQL suite, including actual separate-connection interleavings and explicit ABA limitation. |
| `docs/g18-b-gate1-source-coverage-2026-10-18.md` | New source inventory, classifications, locks/audits/scope, test mapping and unresolved boundaries. |
| `docs/g18-b-gate2-proposal-2026-10-18.md` | New unimplemented schema/writer/lock/promotion proposal and required authorization. |
| `docs/g18-b-gate1-validation-2026-10-18.md` | This report. |

No source-writer services, models, migrations, settings, URLs, views, templates,
portal navigation, PDAO enforcement, historical math or prior policy documentation
were changed. Ignored `.local/g18-b-gate1/` contains local hashes/logs only.

## Freshness and complete-pool behavior

The source matrix classifies 34 path groups: 20 COVERED, 6 PROHIBITED and 8
UNRESOLVED. COVERED means supported-path observation coverage, not universal
atomic source invalidation. No unresolved group is represented as complete.

New captures retain the existing five-criterion source manifest, configuration,
validation and numerical replay. An explicitly separate outer snapshot version,
`durable-pool-development-2`, adds `g18-b-source-observation-1` metadata:

- Fresh processor account, effective/direct/group permissions and retained admin
  audit identities, stored as an authority digest rather than raw grants.
- All membership requirement definitions and document-type metadata, including new
  requirements for which no document exists; intake version/requirement snapshot
  digest and membership event identities.
- Linked-event version/status/publication digest; retained member and program
  source audit identities. Durable artifacts' own audits are excluded so a result
  does not invalidate itself.
- Complete ordered retained application IDs. Existing source capture continues
  checking current membership, profile/version, submission, photo/documents,
  eligibility and evidence audit/provenance, exact five assessments, expiry,
  configuration/policy identity, program terms and cross-program receipt history.

Supplementary observations bracket source capture; full capture is repeated after
calculation and after graph persistence. Permission checks use fresh users, not
cached Django permissions. A detected mismatch rolls back the result graph and
records a separate failed outcome under the pre-existing attempt protocol.

Duplicate request keys cannot return a stale request merely because content
matches. A predecessor already named by a replacement request cannot acquire a
second competing replacement request. Explicit recovery/retry of the existing
request remains the supported path; failure never restores an old result as current.

All applications remain in pool accounting. In-scope unresolved eligibility or
incomplete eligible evidence blocks acceptance; ineligible exclusions need a current
audited outcome. Post-cutoff applications are retained in the manifest. There is no
caller-selected subset, pagination or slots truncation; the existing 128-application
limit fails explicitly. The existing read-only pool service still exposes incomplete
inventory for review. Missing result rows, input/assessment keys, criterion traces,
incorrect manifest membership, inconsistent versions or failed exact replay cannot
produce a completed historical outcome.

## Historical preservation

`_capture_legacy` retains the previous capture body; the historical engine label is
unchanged. Old snapshots are not rewritten, normalized or rehashed into a new
format. The canonical hash functions, five-criterion constants/engines, immutable
artifact payloads and database structures remain unchanged. Only NEW outer
snapshots include the explicitly versioned supplement and therefore a new context
digest. An old pending request needs a new context/request; an old completed run
remains replayable but cannot assert Gate 1 freshness.

`inspect_development_history` checks the immutable complete graph with existing
actor/program scope and disposable-harness permission restrictions. It does not
read current evidence or pretend old results are usable: `sources_match_now=null`,
`freshness_basis=not_evaluated`, `atomic_freshness=false`, `current_promotion=false`,
`operational_ready=false`. Current diagnostic inspection also explicitly reports
`atomic_freshness=false`; it remains a momentary observation, not a promotion token.

## Concurrency, rollback and limitations

The 72-test focused run includes 26 new tests plus all 37 existing durable service
tests and 9 existing durable concurrency tests. Evidence includes:

- Actual separate MySQL connections: unshared requirement writer commits during
  calculation and during trace persistence; final observations reject it, all
  run/result/trace rows and their audits roll back, failed attempt outcome remains,
  and the independently committed source change is retained.
- Actual separate connection removes the processor's required permission during
  persistence; completion is refused and the graph rolls back.
- Existing cooperating writer races: member changes, document revocation,
  configuration revision, eligibility exit, cross-program receipt/void; writer
  blocks or completes under the shared row lock and stale capture is refused.
  Duplicate request/process races preserve one request/success graph. A writer
  released after a calculation commits makes its retained history stale.
- Existing graph/audit failure tests preserve atomic historical persistence,
  explicit failed/unfinished attempts, immutable audits and trace completeness.
  New partial-result-map test rejects the whole pool, not just the missing row.
- Supported ABA cases: member deactivate/restore, reject/reverify document,
  receipt/void returning PA count to its original value, and retained actor admin
  audit identity all invalidate the prior context. Stale history still replays.

**No atomic current-result promotion is claimed.** Unversioned requirement changes
followed by restoration between observations are intentionally demonstrated as
undetectable; result diagnostics still deny atomicity and operational readiness.
Silent permission/M2M ABA without retained audit, external file-byte ABA, clock
rollback and changes immediately after the last observation remain unresolved.
File hashes prove bytes observed now, not authenticity at an earlier photo/direct
upload review. A historical signer's later role revocation has no approved
retroactive-invalidity rule. No such policy was introduced.

Supplemental observation conservatively includes all membership requirements and
source audit IDs; unrelated metadata/diagnostic audits may require a new request.
History lists add query/payload cost; this is not a production load/performance
acceptance. Gate 2 generations are proposed to replace reliance on repeated history
observations. No browser/UI QA was needed because there are no UI changes.

## Validation commands and evidence

All commands run through `scripts/g12_test_runner.py`, which creates a NEW local
MySQL instance/datadir with generated credentials, loopback port, limited grants,
`.env` disabled and synthetic-only media. `DurableTestRunner` verifies the actual
test database/datadir/port/server UUID, READ-COMMITTED and InnoDB tables. Existing
migrations are applied only inside the disposable tests. The harness shuts each
temporary server down and Django destroys its test database. No application DB
query, dump, schema migration or member record access was performed.

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf.test_source_freshness ewaf.test_durable_services ewaf.test_durable_concurrency --testrunner scripts.durable_test_runner.DurableTestRunner --noinput
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf --testrunner scripts.durable_test_runner.DurableTestRunner --noinput
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test --testrunner scripts.durable_test_runner.DurableTestRunner --noinput
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py check --database default
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py makemigrations --check --dry-run
git diff --check
```

| Check | Result | Disposable artifact directory suffix |
|---|---|---|
| Focused | 72 passed, 104.668 seconds | `b9daepgn` |
| EWAF regression | 457 passed, 256.340 seconds | `l5hgnpoq` |
| Full project | 999 passed, 432.560 seconds | `4l6qkz1t` |
| Django database/configuration check | No issues (0 silenced) | `2sgi3sxb` |
| Migration drift | No changes detected; no migration generated | `n59aocpr` |
| Diff whitespace | Working/staged diffs and all six changed/new files passed; existing line-ending notices only | local |

All directory suffixes above are under `%TEMP%/santolan-g12-tests-<suffix>`.
All three final test suites exited 0, with no failures, errors or skips. The full
suite increases the prior 973-test baseline by exactly 26 tests; EWAF increases
from 431 to 457. These overlapping runs are not added together as unique tests.
Completed Django logs are copied into ignored `.local/g18-b-gate1/`; no database
files, configurations or credentials are copied. Initial focused attempt `dpp1b8fc`
ran 69 tests with two test errors: unsupported fixture expiry argument and a user-row
update interleaving blocked by FK locks. Those fixtures were corrected; three added
coverage cases brought the final focused set to 72. The final run has no failures,
errors or skips. An initial sandbox-only attempt failed before MySQL initialization
because Windows Temp `mysql.ini` was blocked; approved reruns use the same harness.

## Workspace preservation and stop boundary

Baseline: 560 file hashes including tracked/untracked repository files, `.git/index`
and `.env`; branch `feature/events`, HEAD
`949eeda33c6aa5d8ee03962209ae8fedeac58ad1`. At validation, only the authorized
`ewaf/durable_services.py` baseline file differs; the other **559 entries are
byte-identical**, including all prior G12-G17, G18-A, PR reference, models/migrations,
source writers, settings and the staged index. Staged diff and HEAD are preserved.
Five new repository files are listed above. No staging, commit, reset, clean,
stash, pull, push, merge or deployment was performed.

Review the [complete source matrix](g18-b-gate1-source-coverage-2026-10-18.md) and
[separate Gate 2 proposal](g18-b-gate2-proposal-2026-10-18.md). Gate 2 requires
separate authorization for migrations and shared writer integrations. Outstanding
policy decisions include the proposed four-criterion configuration, measurement
and normalization, PA lookback, classification/ties, program scope/effective date,
approval role, relevance evidence/accessibility/consent and disputed-case review.

**Stop after Gate 1 for independent review. System remains at 70%, not 80%.**
