# G17 synthetic recalculation/history implementation and validation

Date: 2026-10-15 (Asia/Manila). Branch: `feature/events`.
Baseline HEAD: `949eeda33c6aa5d8ee03962209ae8fedeac58ad1`.

**Bounded G17-A synthetic implementation. Recorded milestone remains 70%.**
G16 formal acceptance, operational G17, G18 and Stage 8 acceptance remain pending.
Passing these diagnostics does not establish the 80% milestone.

## Authorization and contracts reviewed

The owner's implementation request authorizes the isolated synthetic increment in
[the G17 plan](g17-recalculation-history-plan-2026-10-15.md), superseding only that
plan's planning-only restriction for this increment. It does not authorize its
future operational schema, integration or activation proposals.

Reviewed repository instructions, `../../CURRENT_SYSTEM_SPECIFICATION.md`,
`../../Guide for Development.md`, roadmap/API contracts/October 10 impact notes,
active Open Decisions and workbook formula/cache provenance. Reviewed
[G12](g12-verified-evidence-validation-2026-10-13.md),
[G14](g14-configuration-foundation-validation-2026-10-13.md),
[G15](g15-scoring-diagnostics-validation-2026-10-13.md),
[G16](g16-ranking-diagnostics-validation-2026-10-14.md),
[G16 revalidation](g16-revalidation-2026-10-15.md), and their relevant evidence,
readiness, configuration, calculation, ranking and preservation source/tests.

Established safeguards retained: historical records are preserved, incomplete
evidence is not silently substituted, precision/exact ties remain unchanged, real
applicant readiness stays score-free, operational entry points remain disabled,
and human selection/publication/release remain separate. The state machine,
synthetic actor capability, accepted-change categories, event sequencing and retry
deduplication below are proposed behavior demonstrated in fixtures only. Unresolved
institutional policy is not approved by those fixtures.

## Implemented behavior and plan mapping

| Goal | Implementation and evidence |
| --- | --- |
| A: preserved history | Append-only in-memory attempt/result/audit representations; canonical JSON strings with fresh decoded exports protect against nested mutation. Three `history-v1` results preserve original inputs, rules, scores and ties. Previous IDs link 1 -> 2 -> 3. |
| B: traceable versions | Each result captures exact pool payload, input/evidence/configuration/policy versions, pool checksum, context digest, full G14/G15/G16 traces and both score scales. Conflicting version/content reuse is rejected. G17 has a separate digest namespace and engine version. |
| C: explicit conditions | Explicit `OBSERVE`, `BEGIN`, `FINISH` events only. Initial, corrected input, configuration revision, evidence review, date reevaluation and unchanged-context retry are exercised. Changed components must match the illustrative trigger; unresolved policies block. |
| D: stale/incomplete | Observed source change clears simulated currentness. Begin and finish check source generation, complete evidence, evaluation date, inclusive expiry and simulated governance findings. Stale attempts retain captured mathematics without promotion; old results stay historical. Missing inputs never create a successful subset. |
| E: simulated authorization/audit | Active, same-scope synthetic actor with `SIMULATE` plus a reason is required. Denials never invoke the calculator. Audit events retain actor/reason, relevant versions, context/generation and outcome. Every artifact explicitly denies operational/effective authority. |
| F: repeatability | Controlled fixture identifiers/timestamps, no wall clock or UUID. Identical accepted contexts append attempts and reuse results; interleaved same-context completion promotes once. Repeated finish cannot restore old currentness. This is no production retry/concurrency guarantee. |

The supported entry point is `simulate_fixture(name)` for seven pinned names;
the CLI has the same allowlist. The private `_Simulation` test seam supports
controlled synthetic variations, not arbitrary applicant input. It imports no ORM,
application settings, runtime services or operational integration. G14's existing
math dependency on Django's exception class does not initialize Django settings.

G17 reuses G16's unchanged private `_evaluate_payload` source-fixture seam only
after loading its own pinned pool examples. G16's public four-name allowlist and
all staged bytes remain unchanged. This private contract dependency is deliberate:
future changes to G16's payload interface need coordinated review. G17 does not
duplicate or weaken validated math to admit new inputs.

The fixture [README](../ewaf/tests_data/g17/README.md) defines the exact illustrative
transition, version, expiry and repeat contracts. Initial equal-weight scores are
0/50/50/100. Correcting B's SI yields contributions 0.2+0.1+0.1+0.1+0.1 and score
60. A separate configuration revision changes SI:ES from 1 to 2 with fresh G14
validation. Exact B/C ties and 50-digit near ties are tested independently of
ambient Decimal precision. No tie-breaker, rank-number policy or beneficiary
decision is introduced; capacity stays explanatory.

## Files and checkpoint preservation

### New G17 files (outside the index)

- `ewaf/recalculation_diagnostics.py`: bounded in-memory simulation.
- `ewaf/recalculation_fixtures.py`: immutable checksum registries and strict loaders.
- `ewaf/test_recalculation_diagnostics.py`: 50 synthetic behavior tests.
- `ewaf/test_recalculation_preservation.py`: 6 isolation/preservation tests.
- `scripts/g17_synthetic_diagnostics.py`: fixed-name JSON diagnostic CLI.
- `ewaf/tests_data/g17/README.md`: fixture provenance, illustrative contracts and boundaries.
- Five pools: `pool-base-v1.json`, `pool-corrected-v2.json`,
  `pool-configuration-v2.json`, `pool-incomplete-v2.json`, `pool-precision-v1.json`.
- Seven scenarios: `history-v1.json`, `repeat-v1.json`, `stale-v1.json`,
  `incomplete-v1.json`, `unresolved-v1.json`, `unauthorized-v1.json`, `precision-v1.json`.
- This report, `docs/g17-recalculation-history-validation-2026-10-15.md`.

All 12 JSON files are under `ewaf/tests_data/g17/`. Total: 19 new G17 files.
No pre-existing source, test, documentation, dependency or configuration file
was modified. No files were staged, unstaged, committed, pushed, merged or deployed.

### Pre-existing changes retained separately

The 16 staged G16 files remain exactly as captured: the G16 validation report;
`ranking_diagnostics.py`, `ranking_fixtures.py`, `ranking_policy.py`,
`ranking_readiness.py`, `ranking_testsupport.py`; four `test_ranking_*` modules;
the G16 fixture README and four JSON fixtures; and
`scripts/g16_synthetic_diagnostics.py`.

The two pre-existing untracked documents remain byte-for-byte unchanged:
`docs/g16-revalidation-2026-10-15.md` and
`docs/g17-recalculation-history-plan-2026-10-15.md`.

Before implementation, captured SHA-256 for 484 existing tracked/staged and
checkpoint-document files and the exact raw staged diff including full blob IDs.
Final verification details are recorded below. Local manifests/helpers/logs/JSON
diagnostic output reside only under ignored `.local/g17-validation-2026-10-15/`.

## Environment and isolation

Explicit `.venv\Scripts\python.exe`: Python 3.14.5; Django 5.2.17 and mysqlclient
2.3.0 load from this repository's `.venv\Lib\site-packages`. No dependency change,
reinstall or upgrade was required.

All Django commands below use the unchanged `scripts/g12_test_runner.py`. Each
launch creates a fresh temporary MySQL 8.4.11 datadir on a dynamically chosen
loopback port, verifies datadir/port and fresh database inventory, filters inherited
environment, sets `PYTHON_DOTENV_DISABLED=1`, and grants only `g12_empty` and
`test_g12_disposable` to its generated synthetic user. It does not open the
application MySQL datadir or use application credentials. Required temporary
directory access was run with tool approval. Runner shutdown is in its `finally`
block; retained temporary data contains synthetic fixtures only.

Tests apply the repository's **existing** migrations solely inside disposable
test databases. No migration was generated or applied to an application database
for this task. PDAO enforcement remains unchanged in application configuration;
the documented runner's synthetic test override remains as supplied.

## Fresh validation commands and evidence

Every command ran from the repository root in PowerShell, using the current G17
source. The first exploratory G17 run passed 52 tests in 10.264 seconds; four
additional date/pool/stale-retry tests and audit-context refinements were then
added. The final focused run below supersedes that earlier run as final-source
evidence. No failures were suppressed, assertions weakened or tests skipped.

```powershell
.\.venv\Scripts\python.exe scripts/g12_test_runner.py test ewaf.test_recalculation_diagnostics ewaf.test_recalculation_preservation --noinput --verbosity 2
.\.venv\Scripts\python.exe scripts/g12_test_runner.py test ewaf.test_ranking_diagnostics ewaf.test_ranking_policy ewaf.test_ranking_readiness ewaf.test_ranking_preservation --noinput --verbosity 2
.\.venv\Scripts\python.exe scripts/g12_test_runner.py test ewaf.test_evidence ewaf.test_readiness ewaf.test_evidence_corrections ewaf.test_evidence_concurrency ewaf.test_evidence_migrations ewaf.test_ahp_validation ewaf.test_configuration ewaf.test_configuration_concurrency ewaf.test_configuration_migrations ewaf.test_normalization ewaf.test_weighted_scoring ewaf.test_scoring_services ewaf.test_scoring_inputs ewaf.test_scoring_concurrency ewaf.test_scoring_migrations --noinput --verbosity 2
.\.venv\Scripts\python.exe scripts/g12_test_runner.py test --noinput --verbosity 2
.\.venv\Scripts\python.exe scripts/g12_test_runner.py check --database default
.\.venv\Scripts\python.exe scripts/g12_test_runner.py makemigrations --check --dry-run
git diff --check
git diff --cached --check
git diff --exit-code
.\.venv\Scripts\python.exe -B .local/g17-validation-2026-10-15/verify_preservation.py
```

| Validation | Exit | Fresh result | Failures / errors / skips |
| --- | --- | --- | --- |
| G17 focused | 0 | 56 passed; 6.277 s | 0 / 0 / 0 |
| G16 focused | 0 | 54 passed; 8.378 s | 0 / 0 / 0 |
| G12/G14/G15 regression | 0 | 198 passed; 91.706 s | 0 / 0 / 0 |
| Full Django suite | 0 | 809 passed; 224.934 s | 0 / 0 / 0 |
| System/database check | 0 | No issues (0 silenced) | not applicable |
| Non-writing migration drift | 0 | No changes detected | not applicable |
| `git diff --check` | 0 | No whitespace errors | not applicable |
| `git diff --cached --check` | 0 | No whitespace errors | not applicable |
| `git diff --exit-code` | 0 | No changes to tracked working files relative to index | not applicable |
| Preservation helper | 0 | 484 baseline files unchanged; staged manifest identical; 19 new files pass whitespace/conflict-marker, Python AST and JSON parsing checks as applicable | not applicable |

All four final test logs contain `OK`, the expected fresh number of individual
test lines, and no failure/error/skip outcomes. Test timings above are Django's
reported test execution time, excluding disposable server/database initialization.
The additional whitespace scan covers untracked G17 files that ordinary Git diff
checks do not include.

The before/after staged raw manifests each contain 16 entries and have identical
SHA-256 `5036180c963560854148b3192d71b93ccb34695568d60ca61edf6c3a0c21d9da`.
This compares full staged blob IDs and file modes/paths, not just filenames.
The 484-file comparison also confirms staged G16 working copies and both prior
documents remain byte-for-byte unchanged. HEAD and branch remain unchanged.

### Retained evidence

Only `django.log` was copied from each temporary runner directory into ignored
`.local/g17-validation-2026-10-15/`; database files/configuration/credentials were
not copied. Source directories below are under the local Windows `%TEMP%`.

| Local evidence file | Runner directory | SHA-256 |
| --- | --- | --- |
| `g17-focused.log` | `santolan-g12-tests-sd_atre6` | `67b223297e1b2495f6c57df241be266fa0c71005fee1cf854ec8c95931d8b043` |
| `g16-focused.log` | `santolan-g12-tests-20l179k6` | `21ae5689f6e5d0f86bec5bbf570e05744695e14ac05c375b7e6cf1224a6f67a5` |
| `g12-g14-g15-regression.log` | `santolan-g12-tests-kwpv0fsw` | `4484618a2b0775bb3fb968b646d69fc9e8b0284550c721739d8c52eed00c7066` |
| `full-suite.log` | `santolan-g12-tests-vjptkoqj` | `1409128b3aa308828f99543a2e766ea4450681c13508df1a1e7d9d7317b960f2` |
| `system-check.log` | `santolan-g12-tests-ruyujsrm` | `f87ceb15410bde28ff826ce26228e0576558258fa64d145847921a593a61ee63` |
| `migration-drift.log` | `santolan-g12-tests-62_rxp3g` | `93e6e2d5be3c054add80c0f19101608803f7ca8a7df1fa41f76bbb9a1f570f4a` |

`before-files.json`, `before-index.txt`, `preservation.json`, `log-summary.json`,
`diagnostic-results.json` and seven `*-output.json` replay artifacts retain local
comparison evidence. The exploratory 52-test log is `g17-initial-52.log`, from
`santolan-g12-tests-kbc8gkv6`; it is not substituted for the final 56-test run.

Test counts are fresh run output, not reused historical evidence. Tests overlap
between focused/regression/full runs; their counts are not additive coverage.
The full suite's original 753-test baseline gains 56 G17 tests. Browser harnesses
were not separately invoked: this increment adds no UI or browser workflow.

### Standalone diagnostic examples

Executed `.\.venv\Scripts\python.exe -B scripts/g17_synthetic_diagnostics.py NAME`
separately for each fixed name, without Django initialization:

| Name | Actual exit | Result count | Simulated current result |
| --- | --- | --- | --- |
| `history-v1` | 0 | 3 | 3 |
| `repeat-v1` | 0 | 1 | 1 |
| `stale-v1` | 2 | 1 | none |
| `incomplete-v1` | 2 | 1 | none |
| `unresolved-v1` | 2 | 1 | none |
| `unauthorized-v1` | 2 | 0 | none |
| `precision-v1` | 0 | 1 | 1 |

Exit 2 in these four negative examples is the expected explicit diagnostic outcome,
not a failing automated test. Subprocess tests also verify unknown paths are
rejected, and prohibit settings/database imports, network/subprocess calls and
file writes during replay. Disposable database preservation tests prohibit **all**
SQL during simulation and compare every existing model's rows before/after,
including audit/history. They also check existing schema/routes/permissions and
continued G12/G14/G15/G16 and retired EWAF guards.

## Unresolved policy and intentionally blocked behavior

- Candidate-pool/admission/cutoff change: `POOL_CHANGE_POLICY_UNRESOLVED`. No
  automatic exclusions or successful subset; complete manifest is mandatory.
- Cross-program PA release/void dependency: `PA_SCOPE_POLICY_UNRESOLVED`.
  The simulation does not infer an institutional PA window, cutoff or scope.
- Protected terms/authority change: `G06_B2_B3_UNAVAILABLE`. No approval bypass.
- Explicit unresolved admission, cutoff, revisions, evidence, normalization,
  ties, authority or PA scope: `POLICY_UNRESOLVED:<name>`.
- Stale/missing/rejected/disputed/expired findings, incomplete calculations,
  stale expected context or changed generation: named blocked/stale outcomes.
  Missing/corrupt fixture files and conflicting version contents fail explicitly.

Applicable Open Decisions remain those identified in the G17 plan: OQ-06/07/08/
18/19/23, OQ-09/26 and G06-B2/B3, OQ-10/11/12, OQ-13/15, OQ-25, OQ-16/22 and
conditional identity evidence OQ-02/24. The fixture's accepted synthetic flags,
arithmetic examples and passing tests approve none of them.

## Operational G17/G18 work still required

Separate authorization and policy resolution are required for accepted real
inputs, effective configuration/evidence authorization, governed pool membership,
PA scope and cutoff, precision/rank conventions, revisions and post-decision review.
Future persistence needs an additive reviewed schema, private immutable result
graphs, durable requests/invalidation, current-result references and atomic audits.
It must preserve G15 READINESS_ONLY and all legacy history without backfilling
missing provenance.

Real integration needs service-level action permissions and history privacy,
source writers and cross-program dependency rules, locks for complete pools,
authorization rechecks, transactional promotion/rollback, crash recovery and
approved retry semantics. Independent MySQL connection race tests, migration
preservation tests and security/acceptance review would be required. The synthetic
interleaving examples do not implement these guarantees.

G18 needs separate human-controlled decision integration, capacity/tie/exception
policy and currentness enforcement. Selection, waitlisting, public results and
actual release remain distinct workflows. No UI, URL, view, form, API, signal,
worker, scheduler, production audit write or runtime persistence was introduced.

The minimalist light eight-group Admin Portal, onsite membership registration,
verified-member application behavior, offline/external PDAO approval and human
final decisions remain unchanged. **G17 synthetic coverage is implemented;
operational enforcement and persistence are not. Recorded milestone: 70%.**
