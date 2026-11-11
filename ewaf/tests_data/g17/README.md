# G17 synthetic recalculation and history fixtures

These are invented, checksum-pinned source examples. They contain no member,
application, release, document or operational database identifiers. `SYN-G16-*`
identifiers are retained from copied G16 mathematical examples; G16 files and
checksums remain unchanged. This directory grants no institutional policy approval.

## Run a diagnostic

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -B scripts/g17_synthetic_diagnostics.py history-v1
.\.venv\Scripts\python.exe -B scripts/g17_synthetic_diagnostics.py stale-v1
```

The command prints JSON to stdout, loads no Django settings or `.env`, and opens
no database or network connection. It creates no history file or application
record. History exists in memory for that replay. The seven fixed names below
are the only CLI inputs; there is no arbitrary path, upload or applicant API.
Exit 0 means the final event promoted/reused a complete **simulated** result with
no pending attempts; exit 2 means blocked, stale, denied or an invalid CLI choice.
`complete` is a replay outcome, never operational readiness or acceptance.

| Scenario | Demonstration | Exit | Results / current result |
| --- | --- | --- | --- |
| `history-v1` | Initial calculation, corrected SI input, revised AHP judgment | 0 | 3 / 3 |
| `repeat-v1` | Identical request and explicit retry retain distinct attempts, reuse result | 0 | 1 / 1 |
| `stale-v1` | Source changes between begin and finish; previous result stays historical | 2 | 1 / none |
| `incomplete-v1` | Missing SI blocks full-pool comparison; no imputation/subset | 2 | 1 / none |
| `unresolved-v1` | Unresolved revision policy blocks replacement | 2 | 1 / none |
| `unauthorized-v1` | Synthetic read-only actor cannot calculate | 2 | 0 / none |
| `precision-v1` | Exact 50-digit near ties remain distinct | 0 | 1 / 1 |

## Mathematical provenance

Five `pool-*.json` files copy G16's strict mathematical payload format. G17's
loader checks its own immutable SHA-256 allowlist before using the unchanged G16
private `_evaluate_payload` **source-fixture** validation seam. G16's public
`compare_fixture` still accepts its original four names only. This narrow internal
dependency requires coordinated review if G16's private payload contract changes.

- Base: equal weights `0.2`; each candidate's five values are respectively
  `0`, `0.5`, `0.5`, `1`. Scores are `0`, `0.5`, `0.5`, `1` (0/50/50/100).
  B and C remain exactly tied across illustrative capacity 2; nobody is selected.
- Corrected: B's SI changes `0.5` to `1`; contributions become
  `0.2 + 0.1 + 0.1 + 0.1 + 0.1 = 0.6`, or 60. All four candidates replay.
- Configuration: corrected inputs with SI:ES judgment `1` changed to `2` and
  a fresh G14 validation artifact. Full weights and contributions are retained.
- Incomplete: B's SI is `null`; G16 returns `VALUE_MISSING` and G17 blocks.
- Precision: byte-identical copy of G16's precision example. No float conversion,
  epsilon, display rounding or identifier tie-breaker is used in calculation.

G14/G15's 50-digit `ROUND_HALF_EVEN` profile, normalization definitions, engine
versions, settings, G16 exact Decimal comparison, both scales and exact groups are
retained in each result. Fixed synthetic normalization bounds, ascending SI/PA
examples, high-first ordering and capacity are illustrative, not approved policy.

## Explicit simulation contract

The proposed G17 plan supplies the history/invalidation/recheck structure. The
following execution choices are **illustrative synthetic policies only**:

1. `OBSERVE` supplies an explicit source snapshot. Changed context increments a
   generation and clears the simulated current pointer immediately. Returning to
   older values does not restore an older pending generation's validity.
2. `BEGIN` requires an active, same-scope invented actor with `SIMULATE`, a reason,
   and the observed context. These are simulated assertions, not application RBAC.
3. Initial/first-retry calculation requires a complete pinned pool. Following a
   prior result, input correction permits changed input/evidence components;
   configuration revision permits configuration/scoring/ranking-policy components;
   evidence review permits evidence/evidence-policy/governance components; explicit
   date reevaluation permits the evaluation date. Mismatched changes are blocked.
   These categories do not authorize changing real sources or approved terms.
4. Missing, declared, rejected, disputed, stale, expired or invalid evidence,
   stale eligibility/terms/binding, simulated B1/B2/B3 findings and unresolved
   policy produce explicit reasons. Missing candidate/criterion manifests fail
   strict validation. No silent favorable fallback, clipping or partial promotion.
5. `FINISH` rechecks context, generation, evaluation date and evidence before
   appending a result. Date/expiry uses controlled UTC instants and Asia/Manila
   local dates; expiry is inclusive (`expires_on < local date` is expired).
   A stale attempt retains its captured calculation, without becoming current.
6. Identical accepted context reuses the current result and appends an attempt.
   Two interleaved completions for that same context promote only once. Repeated
   `FINISH` appends an observation without restoring an old pointer. This is a
   single-process event simulation, not production idempotency or concurrency.
7. Attempts/results/audit entries are canonical immutable JSON strings internally;
   every export is a fresh decoded tree. Initial attempt outcome stays immutable;
   consult terminal audit events and `pending_attempts` for completion status.
   Prior result IDs, exact context contents, versions, digests and checksums remain
   available. A version label cannot denote different contents within one replay.
8. Identifiers and times come from fixtures; result/attempt IDs are local sequence
   numbers within a scenario, not global persistent identifiers. The report's
   source digest and engine version identify replay inputs. No clock/UUID is read.

All artifacts carry `SIMULATION_ONLY`, `effective_authorization=false`, and
`operational_ready=false`. Digests establish content consistency, not institutional
approval, secure audit persistence or protection against a privileged programmer.
Even synthetic successful scenarios leave all operational G12/G14/G15/G16/G17
barriers in place. An empty illustrative `unresolved` list approves no real policy.

The private `_Simulation` seam lets tests vary controlled synthetic cases; it is
not a supported arbitrary-input service or access-control boundary. Limits are
8 actors, 16 contexts and 64 events, plus G16 strict JSON/payload limits. Evidence
flags represent diagnostic findings; the simulation does not verify private files.
Denied attempts do not include a calculation snapshot, but the overall report is
a diagnostic artifact, not a permission-filtered private-history interface.

## Deliberately unavailable

Candidate-pool changes return `POOL_CHANGE_POLICY_UNRESOLVED`; cross-program PA
release/void changes return `PA_SCOPE_POLICY_UNRESOLVED`; protected terms changes
return `G06_B2_B3_UNAVAILABLE`. Explicit unresolved admission, cutoff, revisions,
evidence, normalization, ties, authority and PA scope return named blockers.
No default policy is inferred for these cases.

No models, migrations, runtime persistence, routes, views, UI, signals, workers,
schedulers, production audit writes, ranking previews, selection, waitlisting,
PDAO integration or G18 decisions are added. Crash recovery, atomic database
promotion, authorization revocation during execution and actual competing-writer
locks require separately authorized operational design and tests.

## Tests

Use the disposable MySQL runner, which filters the environment and disables
`.env`; never run tests against application data:

```powershell
.\.venv\Scripts\python.exe scripts/g12_test_runner.py test ewaf.test_recalculation_diagnostics ewaf.test_recalculation_preservation --noinput --verbosity 2
```

Tests cover all scenarios, nested mutation protection, version conflicts, exact
precision/ties, controlled date rollover, simulated permission denials, repeated
and interleaved requests, zero database queries, unchanged rows/audits/schema and
continued disabled operational gates. Subprocess replay forbids settings/database
imports, network operations and file writes. These establish synthetic isolation;
they do not establish operational RBAC, durability or Stage 8 acceptance.
