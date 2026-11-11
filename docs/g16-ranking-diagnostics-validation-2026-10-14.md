# G16 — Synthetic ranking diagnostic foundation

Date: 2026-10-14. Repository: Rovic-bot/capstone. Branch: feature/events.
Starting and final HEAD: `949eeda33c6aa5d8ee03962209ae8fedeac58ad1`.
**Development baseline: 70%, unchanged. GO for independent source review only.**

## Scope and preflight

Preflight verified the exact branch/HEAD, clean working tree and empty staging
index. The complete external G16 audit was read, alongside current system
specifications, Guide for Development, Open Decisions and G12/G14/G15 validation
evidence. Existing evidence/readiness, mathematical engines, services, models,
permissions, migrations and regression fixtures were inspected. The current G16
implementation instruction excludes the audit's optional persistence/UI design.

This increment is synthetic-only and migration-free. No existing tracked file was
modified. There are no new models, migrations, database artifacts, routes, forms,
navigation links, operational applicant scores or ranking previews. The four
numerical fixtures contain invented identities and mathematical examples only.
They are not Association policy, reviewed member evidence or beneficiary records.

## Complete new-file inventory

All 16 proposed files are new; no existing tracked source is changed.

| File | Purpose |
| --- | --- |
| `ewaf/ranking_diagnostics.py` | Bounded pure replay/comparison, exact equal-score groups, manifests and G16 digests |
| `ewaf/ranking_fixtures.py` | Read-only, checksum-pinned fixture-name registry |
| `ewaf/ranking_policy.py` | Non-effective documentary policy-completeness diagnostics |
| `ewaf/ranking_readiness.py` | Permission-checked score-free adapter and unconditional ranking guard |
| `ewaf/ranking_testsupport.py` | Invented test-data construction, no ORM or production seeding |
| `ewaf/test_ranking_diagnostics.py` | 35 mathematical, integrity, parser, isolation and runner tests |
| `ewaf/test_ranking_policy.py` | 4 pending-policy and no-authorization tests |
| `ewaf/test_ranking_readiness.py` | 12 permission, provenance, evidence and score-free adapter tests |
| `ewaf/test_ranking_preservation.py` | 3 historical-row, read-only, schema and retired-workflow tests |
| `ewaf/tests_data/g16/README.md` | Fixture provenance, interpretation and runner instructions |
| `ewaf/tests_data/g16/high-first-v1.json` | Explicit high-first, exact ties and illustrative capacity |
| `ewaf/tests_data/g16/low-first-v1.json` | Explicit low-first scenario |
| `ewaf/tests_data/g16/precision-v1.json` | Full-precision G14 weights and distinct 50-digit G15 results |
| `ewaf/tests_data/g16/incomplete-v1.json` | Missing-input example; no partial-pool comparison |
| `scripts/g16_synthetic_diagnostics.py` | Fixed-fixture CLI; no settings/database initialization |
| `docs/g16-ranking-diagnostics-validation-2026-10-14.md` | This report |

Ignored delivery artifacts: `.local/g16-final-review-2026-10-14.zip` and the local
packaging helper under `.local/g16_review/`. The ZIP preserves the paths above and
includes manifest/checksums, validation logs, static preservation evidence and
synthetic trace outputs. The helper is included as a validation utility, not an
application feature. No staging, commit, push or deployment was performed.

## Mathematical contract and reproducibility

The supported numerical entry is `compare_fixture(name)`. It accepts only one of
four names in a read-only source registry, loads at most the bounded byte limit,
checks its pinned SHA-256, then parses and independently validates the fixture.
The CLI accepts these names through explicit argparse choices. There is no file
path, uploaded JSON/CSV, applicant ID, arbitrary score or synthetic=true API.

The private `_evaluate_payload` seam supports source-fixture validation and
adversarial tests. It is not a supported applicant calculator. Python source and
the internal test builder remain accessible to developers; the supported-path
isolation does not claim protection against arbitrary code execution or someone
rewriting the registry. New source fixtures/pins require independent review.

G16 engine `g16-synthetic-comparison-1`, profile `exact-decimal-groups-1`, schema 1
uses the unchanged G14 `g14-ahp-1` / `workbook-five-reference-1` and G15
`g15-minmax-wsm-1` / `synthetic-fixed-bounds-1`. Criterion order is exactly
**SI, ES, PA, ND, PR**. Every candidate is independently recalculated through G15,
which replays G14; G16 additionally compares the entire retained G14 validation
with a fresh replay. Entire G15 results, five ordered traces, full weights,
contributions, settings, completeness and both score scales must match exactly.
Rehashing forged mathematical evidence does not make it acceptable.

The common contract binds definitions, source/unit, explicit normalization
directions, fixed bounds, category encodings, judgments/validation, score
engine/profile/settings, 0–1 comparison scale, synthetic evaluation context,
comparison direction, sorted complete pool IDs and optional illustrative
capacity. Candidate-specific values and digests may differ. A mismatched candidate
contract, missing/duplicate/extra item or altered manifest blocks comparison.
Exact contract representation is intentionally conservative: it does not infer
equivalence between differently represented policy definitions.

The isolated fixture measure is explicitly `synthetic` / `fixture`. This is not
an Association measure/unit. Optional categories must use the `SYN-CATEGORY-*`
namespace; identity fields use `SYN-G16-*`, with no database resolution. The
fixed evaluation label is a scenario epoch, not a claim of live source freshness.

Scores use G15's separate calculated-output parser: up to 50 significant digits,
1100 characters and bounded exponent 999. They never pass through the 40-digit
judgment-input parser. All arithmetic is replayed under the existing explicit
50-digit ROUND_HALF_EVEN contexts. G16 performs direct Decimal comparisons with
reverse sorting for HIGH_FIRST, without floats, negation, quantization, lexical
numeric ordering or epsilon. Full source text remains in the pinned fixture;
canonical unrounded replay output is retained in each item.

HIGH_FIRST and LOW_FIRST are explicit test scenarios, never defaults or policy
authorization. Equal full-precision values share a group and position span.
Synthetic ID order inside a tie only canonicalizes presentation. There are no
operational rank numbers, winners, selections or waitlist decisions. Illustrative
capacity can report overcapacity or a tie crossing its boundary, but cannot drop
candidates, truncate the output or select anyone.

The precision fixture produces these distinct results:

```
0.50000000000000000000000000000000000000010000000002
0.50000000000000000000000000000000000000020000000002
```

Both display as 0.50 under the test's two-place illustration and collapse through
float conversion or low-precision unary negation. G16 preserves two groups and
the correct ordering. Tests also prove equality of 0.50 and 5e-1, ambient-context
independence, permutation-invariant manifests/results and reproducible digests.
No institutional display precision is selected by these tests.

The separate digest domain is `g16-synthetic-content-v1`, with kind-separated
contract, input, calculation, manifest, policy-proposal and result digests.
Canonical JSON uses sorted keys, preserved arrays, ASCII encoding and finite
JSON values. Digests prove content consistency, never institutional authority.
Complete fixture sources plus trace outputs are packaged for replay.

Resource limits are technical: 512 KiB payload, 32 candidates, nesting 16,
30,000 nodes, 256 entries per container and 1100 characters per text value.
They are not application-capacity or admission policies. Duplicate JSON keys,
unexpected fields, JSON floats/constants, invalid types, excessive integers and
nonfinite/extreme scores fail closed. No incomplete subset is compared and no
cohort normalization, clipping, imputation or partial renormalization occurs.

## Diagnostics and policy boundaries

Representative G16 reasons include `FIXTURE_NOT_ALLOWLISTED`,
`FIXTURE_CHECKSUM_MISMATCH`, `DUPLICATE_JSON_KEY`, `UNEXPECTED_FIELDS`,
`PAYLOAD_RESOURCE_LIMIT`, `UNSUPPORTED_FIXTURE_VERSION`,
`UNSUPPORTED_MATHEMATICAL_PROFILE`, `CRITERION_ORDER_INVALID`,
`RANKING_DIRECTION_PENDING`, `SCORE_SCALE_INVALID`, `FIXED_BOUNDS_REQUIRED`,
`EMPTY_POOL`, `POOL_RESOURCE_LIMIT`, `MANIFEST_IDS_INVALID`,
`POOL_MANIFEST_MISMATCH`, `CONTRACT_DIGEST_MISMATCH`,
`MANIFEST_DIGEST_MISMATCH`, `COMPARISON_CONTRACT_MISMATCH`,
`CANDIDATE_DIGEST_MISMATCH`, `G14_REPLAY_MISMATCH`,
`G14_VALIDATION_INCOMPLETE`, `G15_REPLAY_MISMATCH`, `SCORE_MISSING` and
`CALCULATION_INCOMPLETE`. Underlying G15 reasons such as `VALUE_MISSING`,
`MEASURE_OR_UNIT_MISMATCH`, `ENCODING_UNAVAILABLE` and `SCORE_RANGE_ANOMALY`
are retained. A present score with a failed completeness/anomaly verdict never
becomes a comparison. Failed pools return no groups or accepted-subset items.

Every numerical output states **DIAGNOSTIC ONLY — NOT AUTHORIZED FOR BENEFICIARY
PROCESSING**, with effective_authorization and operational_ready false.
All five barriers remain visible:

- `CRITERION_POLICY_UNAPPROVED`
- `CONFIGURATION_AUTHORIZATION_UNAVAILABLE`
- `OPERATIONAL_SCORING_UNAVAILABLE`
- `PROCESSING_GATE_UNAVAILABLE`
- `OPERATIONAL_RANKING_UNAVAILABLE`

The new ranking guard always raises the last code, regardless of supplied user,
approval or completeness arguments. Existing guards and retired entry points are
unchanged. RI=1.12/CR<0.10 remains G14's reference diagnostic, not approval.

`policy_completeness()` accepts only a bounded version-1 schema of optional
documentary references for nine decisions: admission/exclusion, direction
authorization, cutoff, ties, capacity/reservations, exceptions,
recalculation/stale-pool behavior, human decision authority and operational
authorization. It exposes reference-presence flags and a digest, not private
reference text. All decisions remain pending even when every reference exists.
There is no storage, authorization field or policy activation.

## Readiness, permissions, privacy, audit and concurrency

`ranking_readiness()` calls the permission-checked G15 applicant-readiness
interface with the caller and expected program, then revalidates its strict
score-free schema. It returns that readiness/provenance result, pending policy
diagnostics and the unconditional G16 barrier. It never calls synthetic comparison
or extracts reviewed values for arithmetic.

Active authenticated staff, dashboard access and the complete existing G12/G14/G15
private view permissions remain necessary. Services reject anonymous, inactive,
nonstaff, insufficiently permissioned and cross-program callers. No permission
is created or granted automatically. A schema containing a forged applicant score
is rejected rather than forwarded. Applicant output contains no criterion values,
weights, contributions, numerical scores, positions or tie groups.

Current evidence is reevaluated by G15/G12, retaining B1 criterion-specific
supporting evidence, B2 structured PR rubric findings and attestation, and B3
exact reusable-document type relationships. Tests verify missing versus verified
zero, latest rejected/disputed assessments without older favorable fallback,
expiry, revoked documents, changed member context and all-five-verified cases.
Even complete evidence and replayable weights never produce applicant mathematics.

G16 creates no database artifacts or audit entries and takes no write locks.
Readiness is an observation, not a serialized complete candidate-pool snapshot or
future acceptance token. A preservation test rejects every non-SELECT query
during G16 operations and compares all registered application-model rows before
and after, including existing audit, historical EWAF and G12/G14/G15 data.

Existing Terms -> Program -> Application -> Member -> evidence lock contracts,
atomic audit writes, append-only protections and cross-program PA release/void
serialization are unchanged. The existing concurrency and atomic rollback tests
were rerun. No claim is made that a new multi-app pool transaction was tested or
implemented. G06-B2/B3 and PDAO enforcement remain untouched.

## Actual executed validation

All database-backed commands used the unchanged `scripts/g12_test_runner.py`.
Each invocation initialized a fresh native MySQL datadir, verified loopback
port/datadir and an empty instance, created restricted synthetic grants and a
separate DB_TEST_NAME, filtered inherited variables, disabled `.env`, kept PDAO
enforcement off, and shut down its disposable server. No existing application or
production database was opened. Synthetic uploads belong only to test fixtures.

| Executed check | Actual result |
| --- | --- |
| Focused G16 | **54 passed**, 7.493 seconds: 35 engine + 4 policy + 12 readiness + 3 preservation |
| Explicit G12/G14/G15 regression | **198 passed**, 69.809 seconds |
| Complete Django regression | **753 passed**, 214.111 seconds |
| Existing additive migration/preservation cases | **6 passed**, included in the 198 and 753 results; no G16 migration |
| G16 preservation/schema checks | **3 passed**, included in 54 and 753 |
| Django `check --database default` | **0 issues** |
| Migration drift | **No changes detected** |
| Browser/accessibility | **Not run; no UI, route, form or navigation change** |
| Git/static/package checks | Exact inventory, source syntax/whitespace, empty index, baseline preservation and ZIP checksums verified in packaged static evidence |

These suites overlap. Do not add them to claim unique coverage. The complete
suite has 753 tests, 54 more than the recorded 699-test baseline. Counts describe
executed tests, not Association UAT or independent review acceptance.

Commands after `.venv/Scripts/python.exe scripts/g12_test_runner.py`:

```
test ewaf.test_ranking_diagnostics ewaf.test_ranking_policy ewaf.test_ranking_readiness ewaf.test_ranking_preservation --noinput --verbosity 2
test ewaf.test_evidence ewaf.test_readiness ewaf.test_evidence_corrections ewaf.test_evidence_concurrency ewaf.test_evidence_migrations ewaf.test_ahp_validation ewaf.test_configuration ewaf.test_configuration_concurrency ewaf.test_configuration_migrations ewaf.test_normalization ewaf.test_weighted_scoring ewaf.test_scoring_services ewaf.test_scoring_inputs ewaf.test_scoring_concurrency ewaf.test_scoring_migrations --noinput --verbosity 1
test --noinput --verbosity 1
check --database default
makemigrations --check --dry-run
```

Final log directories under the Windows temporary directory:

- Focused: `santolan-g12-tests-dey36_ih`.
- Relevant regression: `santolan-g12-tests-28hx2nrt`.
- Full regression: `santolan-g12-tests-62kzt7lc`.
- Checks: `santolan-g12-tests-fezoh72n`.
- Drift: `santolan-g12-tests-jr3ayo8x`.

Development iterations are disclosed: an initial direct unittest invocation ran
zero tests because Django SimpleTestCase requires configured test settings. No
database was opened. The first isolated-runner attempt was blocked by sandbox
permission for its temporary configuration; the approved rerun verified a fresh
instance. The first actual focused run executed 54 tests with one test-fixture
error (UUID plus integer in a cross-program test). The test now uses a second
synthetic program. Its corrected rerun passed all 54, followed by the successful
regression/check runs above. The first focused log is retained in the ZIP.

## Preservation and delivery package

The EWAF migration leaf remains `0004_scoring_diagnostics`; program terms remain
`programs/0005_approved_terms`. No migrations or models were created or changed.
G15's READINESS_ONLY constraint and required application relations remain intact.
The full suite preserves existing evidence review, audit rollback, revision
concurrency, held release/void races, membership/program behavior, human decisions,
publication and migration preservation cases. Legacy calculation snapshots and
G12/G14/G15 histories remain untouched.

The ZIP is a changed-source review package, not a standalone deployed system.
Rerunning it requires the audited baseline repository, its dependencies and the
local MySQL binary. Root `manifest.json` lists every source and validation artifact
with relative paths and SHA-256 values; `SHA256SUMS` includes the manifest itself.
Only explicit source/log/trace paths are packaged. No `.env`, secrets, database
files, MySQL configuration, private uploads or real PWD records are included.

The validation utility records baseline hashes for protected source/migrations,
unchanged tracked-file and empty-index checks, AST/whitespace checks and fixture
replays. ZIP entries and bytes are reread and verified against checksums. Source
paths remain complete; trace files are separate from applicant readiness tables.

## Remaining decisions and recommendation

Still pending: SI measurement/evidence/period and government-program handling;
ES categories/encoding; ND definition/verification; PA scope/window/direction;
PR rubric/encoding; accepted freshness/correction/dispute rules; actual AHP
judgments and institutional validation/authorization; normalization directions,
bounds and edge cases; classification thresholds; effective program-specific
ranking policy, candidate admission and cutoff; ties/display/rank conventions;
capacity/reservations/overcapacity/waitlists; exceptions; affected-pool
recalculation; human decision authority; G06-B2/B3 suspension/reassessment/resumption;
privacy-approved future outputs. No such policy was supplied by this increment.

**GO for independent source review of G16 only. NO-GO for operational applicant
scoring, ranking, classification, selection, release or public ranking display.**
Nothing is staged, committed, pushed or deployed. Stop after packaging and await
independent review before staging. **Baseline remains 70%.**
