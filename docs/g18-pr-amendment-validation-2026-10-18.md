# G18 PR-removal amendment — configuration design and validation

Recorded 2026-10-18 (Asia/Manila), existing local `feature/events` workspace.
**Accepted milestone remains 70%. This increment does not begin G18-B.**

## Authority and scope

The owner confirms that the Association President approved removing Program
Relevance (PR) from EWAF scoring and requiring program-specific relevance before
EWAF as an eligibility condition. The owner describes the prior five-criterion
computation as historically Association-approved; its configurations, evidence,
digests and numerical replay remain historical and unchanged. That description
does not retroactively activate software, assign missing dates or approve sample data.

The amendment's approval date is unknown. The record date above is not its approval
or effective date; approximately May 2026 is not substituted. The amendment applies
only to specifically authorized programs. No program identifiers have been supplied,
so no program is marked as bound, effective or authorized by this increment.

Computation.docx remains a proposed reference and is not automatically promoted to
an approved replacement of the workbook. The six retained pairwise judgments supply
the mathematical proposal below; the resulting matrix/weights still require explicit
Association confirmation. President approval of PR removal is distinct from approval
of the recalculated configuration, evidence rules and operational use.

## Recalculated proposed reference

Both axes are selected by criterion name from Computation.docx table 2. Source order
PA/SI/ES/ND/PR is mapped into **SI/ES/PA/ND**; the PR row and column are removed.
There is no renormalization of the old five-criterion weights.

| | SI | ES | PA | ND |
| --- | --- | --- | --- | --- |
| SI | 1 | 2 | 3 | 5 |
| ES | 1/2 | 1 | 2 | 4 |
| PA | 1/3 | 1/2 | 1 | 3 |
| ND | 1/5 | 1/4 | 1/3 | 1 |

Six independent comparisons: SI:ES=2, SI:PA=3, SI:ND=5, ES:PA=2, ES:ND=4, PA:ND=3.
For n=4, sum each column, divide each matrix entry by its column total, average
each normalized row, calculate WSV=A·w, CV=WSV/w, mean CV for the lambda estimate,
CI=(lambda−4)/3, and CR=CI/0.90. RI **0.90**, not the historical five-criterion 1.12.

Version **`g18-four-ahp-reference-1`** uses an explicit 50-significant-digit Decimal
context, ROUND_HALF_EVEN, Emin=-999/Emax=999 and arithmetic-error traps. Exact output
text below means all digits of that finite Decimal profile, not infinitely exact
real arithmetic. An independent Fraction oracle verifies all stages within 1e-47;
that bound is a mathematical test tolerance, not an approved business rule.

```text
SI = 0.47085905179088958208889183867613548372823610097122
ES = 0.28401252184686179509302891528948474591270104643702
PA = 0.17148293179354439061082719408862635782394194818699
ND = 0.073645494568704232207252051945753412535120904404772
weight_sum_residual = 0

lambda_estimate = 4.0513654728589442612068089407860696967972113290515
CI = 0.017121824286314753735602980262023232265737109683833
RI = 0.90
CR = 0.01902424920701639303955886695780359140637456631537

WSV(SI) = 1.9215603637087675051436915112497511117010685604302
WSV(ES) = 1.1569898896042122961881374305878188535651866109157
WSV(PA) = 0.69137869368671784547539508712934079629506721827689
WSV(ND) = 0.29598141265311239426856337986622714836692403560393
CV(SI) = 4.0809672372235508591242899362410904324047492635073
CV(ES) = 4.0737284471846482806432641488122826218194139893206
CV(PA) = 4.0317638989231774864967144872191832662469467093267
CV(ND) = 4.0190023081044004185629671908717224667177353540511
```

These match all supplied ten-decimal verification targets. CR is below the 0.10
reference threshold, which establishes consistency only, not fairness, authority,
eligibility or permission to score. The fixture retains column totals, the expanded
matrix, normalized matrix, weights, WSV and CV with every calculated digit.

The independently constructed fixture is
`ewaf/tests_data/g18/four-criterion-reference-v1.json`. Its input is transcribed by
name from the previously inspected source; its expected Decimal calculations were
constructed separately from the new replay module. Tests additionally recompute
the method entirely with exact fractions and compare the owner targets.
Source DOCX SHA-256 remains
`f91591c4df9e9b3ca15aaf86b457f53da214e2c6844111203749e54849108668`;
workbook SHA-256 remains
`060dee928997f913127e4ba1644416c2a6b0f2df54b066dd93cd3c5f2df3d31f`.
Neither original was changed or recalculated in its authoring application.

## Implemented reference boundary versus future versioned configuration

Implemented now: a fixed, zero-argument reference replay with no applicant input,
ORM, settings, file/network access during replay, persistence or operational caller.
Outputs always include pending configuration confirmation, unknown approval/effective
dates, an empty authorized-program list and false effective/operational flags.
No scores, ranks, thresholds, live configuration object or eligibility decision are
created. Proposed values are recorded in source fixtures/documentation only.

Separately versioned implementation design, **not implemented or activated here**:

1. Introduce a distinct four-criterion configuration/calculation family with an
   explicit version, exact criterion list SI/ES/PA/ND, matrix, method, RI=0.90,
   numeric profile, source provenance and immutable approval/program binding.
   Never infer a version from array length or silently accept a five-criterion
   payload in the four-criterion path. Unknown/missing associations fail closed.
2. Keep historical five-criterion engines, schema interpretations, canonical digests,
   trace cardinality and replay dispatch intact. Historical records never lose PR
   traces or receive recalculated four-criterion values. Any future revised run
   is a new immutable artifact with explicit lineage, not an update to an old run.
3. Four-criterion scoring requires four separately verified scoring inputs. PR belongs
   to a separate, versioned program-eligibility finding with evidence, reviewer,
   review date, applicability and amendment/configuration authority provenance.
   Do not turn an old PR category or verified PR score into a new eligibility pass.
4. Bind only explicitly authorized program versions after the unknown approval/effective
   dates, approving roles and program identifiers are resolved. No global switch,
   date default, automatic copying, blanket EWAF-flag activation or automatic weight seed.
5. A future new calculation adapter must validate eligibility and complete inventory,
   then dispatch by explicit version. The existing durable backend remains five-criterion
   development-only. Its five-trace validation is neither relaxed nor reused by
   substituting a four-element array. Missing storage/version support blocks execution.
6. Any persistence, new migration, eligibility-service integration, source invalidation,
   current-result promotion, UI replacement or operational authorization requires a
   separate reviewed increment. Existing preparations and historical screens remain
   five-criterion groundwork; they do not implement the revised policy.

No new schema is proposed as already approved, and no migration is authored here.

## Updated eligibility design

For an explicitly authorized program, confirm these independently before admitting
an application to a future revised EWAF candidate pool:

| Gate | Required finding |
| --- | --- |
| Membership | Active, verified Association membership with retained manual provenance. No member account or new universal PDAO-ID requirement. |
| Program qualifications | The actual approved disability/qualification requirements; a matching label alone cannot establish functional need. |
| Documents and evidence | Applicable required documents and identity/accessible-alternative evidence reviewed, current and verified. |
| Functional need / relevance | Documented actual need against program-specific approved criteria; mandatory eligibility, never a PR weight or scoring bonus. |
| Additional assessment | Any separately approved assessment required by the program, with authorized reviewer and evidence. |

Hospital-bed assistance must document the relevant functional need; no disability
label is automatically sufficient. This increment does not invent clinical criteria,
an assessment checklist, medical thresholds or an automatic eligibility rule.

If an authorized home assessment is required, its approved workflow must define
informed consent and withdrawal handling, purpose/minimum data, authorized assessors,
private storage/access, verification provenance, validity/expiry, retention and
approved accessible alternatives. Do not require a home visit universally or treat
refusal/inaccessibility as an automatic ineligibility decision. Unresolved assessment
handling remains review-needed until the approved procedure supplies an outcome.

Keep all retained applications in the evaluation inventory. Missing or disputed
evidence remains visible with reasons and a review/correction path; it must not be
silently removed, given a zero value, or automatically labeled ineligible. Only
confirmed eligible applicants enter scoring. While in-scope reviews or the pool
admission/cutoff policy remain unresolved, no complete-pool result may be promoted.
Confirmed ineligible outcomes retain reasons/evidence and stay separate from missing
information. Eligibility, ranking, human selection, publication and actual release
remain different decisions.

## Files and preservation

One existing file intentionally updated:

- `docs/g18-a-computation-crosswalk-2026-10-17.md`: dated amendment, authority distinctions,
  revised matrix/weights, eligibility design and qualified historical checkpoint.

Four new files:

- `ewaf/four_criterion_reference.py`: versioned fixed mathematical replay only.
- `ewaf/test_four_criterion_reference.py`: eleven isolated reference/isolation/preservation tests.
- `ewaf/tests_data/g18/four-criterion-reference-v1.json`: proposed matrix and independent full expected outputs.
- `docs/g18-pr-amendment-validation-2026-10-18.md`: this design and validation report.

All existing application code, G12–G17, G18-A tests/fixtures/UI, durable code, migration
files and numerical engines are preserved byte-for-byte. No global CRITERIA constant,
G14 RI, historical digest, five-trace contract or operational barrier is changed.
Existing PR-scoring UI wording is retained as historical preparatory tooling; it is
not an implementation of the newly approved eligibility amendment.

## Remaining decisions

- Explicit confirmation of the recalculated four-criterion configuration and numeric profile.
- Amendment approval date; effective date; designated configuration approving role;
  explicit authorized program/version scope. No approximately May 2026 substitution.
- SI/ES/PA/ND definitions, measurement, evidence, freshness and normalization directions/bounds.
- PA measure, included release types/programs, lookback/cutoff and reversal handling.
- Cohort/fixed-bound choice, pool admission/cutoff, missing/equal/outlier behavior.
- Exact classification boundaries, rank/tie/capacity/exception and revision rules.
- Program-specific functional-need/relevance criteria, supporting evidence, reviewer
  duties, home-assessment consent/privacy/accessible alternatives and correction/dispute handling.
- Separate schema/integration authorization and institutional acceptance before live use.

Open Decisions continues to govern these gaps. The approved PR-removal and mandatory
eligibility role override earlier unresolved PR-scoring placement only for authorized
programs; unrelated policies and historical facts remain unchanged.

## Validation

The unchanged `scripts/g12_test_runner.py` initializes a fresh temporary MySQL
instance for each invocation. It verifies datadir/port and initially empty schema,
filters the environment, disables dotenv, generates temporary restricted credentials,
uses `g12_empty` plus `test_g12_disposable`, and shuts its server down after the command.
Existing migrations run only inside disposable test databases. No application
connection, real member data, production settings or private uploads are used.

The numerical suites use `scripts.durable_test_runner.DurableTestRunner`, which
requires the actual disposable database/server identity and temporary fixture media.
Observed MySQL 8.4.11, READ-COMMITTED and all test tables InnoDB. Full-suite instance:
port 51603, UUID `e8c2f349-cad1-11f1-bdd9-581122e63603`, datadir
`%TEMP%/santolan-g12-tests-9qg4519g/data/`.

Commands:

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf.test_four_criterion_reference ewaf.test_computation_reference ewaf.test_ahp_validation ewaf.test_policy_reference --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 2
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 1
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 1
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py makemigrations --check --dry-run
git diff --check
git diff --cached --check
```

Focused execution: **44 tests passed in 2.288 s**, including all eleven new tests,
eight G18-A reference tests, sixteen historical G14 mathematics tests and nine
G18-A policy-review tests. Directory suffix `tfnr8zom`.

Complete EWAF execution: **431 tests passed in 209.149 s**, including G12–G17,
G18-A, the new reference, existing separate-connection concurrency, rollback,
historical-migration preservation and durable development barriers. Directory
suffix `aqma0laa`. No failures, errors or skips in either completed suite.

Migration drift returned **No changes detected**, exit 0 (`syrejp17`). Django system
checks reported no issues (0 silenced) during suite setup. Browser QA was not rerun:
no template, form, view, route or static asset changed. Earlier G18-A browser evidence
is retained as historical evidence, not presented as a new run.

Complete project execution: **973 tests passed in 387.032 s**, exit 0, with zero
failures/errors/skips (`9qg4519g`). This is the freshly run prior 962-test local suite
plus eleven new tests. All three suites passed on their first execution in this
increment. Existing application regressions and source-preservation checks passed.

The four Django logs, baseline/staged-diff/hash evidence and full reference output
are retained in ignored `.local/g18-pr-amendment/`. Copying the temporary logs used
tool approval for the known temporary-directory sandbox restriction; only Django
logs were copied, not MySQL configurations, credentials or database files. All
directories above have the prefix `santolan-g12-tests-` beneath `%TEMP%`.

Preservation preflight captured 556 hashes (554 repository files, `.env` and the
index), staged binary diff, dirty-file inventory and HEAD. Only the intentionally
amended crosswalk differs among baseline files; the other **555 hashes match**.
Staged diff, index, HEAD, original DOCX/workbook/handoff and all existing code are
unchanged. `.env` was hashed solely for preservation, not loaded or printed.
New Python/JSON syntax and whitespace checks pass; Git whitespace checks pass with
only pre-existing unrelated line-ending notices. Exact proposed values in both
documents match the fixture/replay output.

All results are local test evidence, not Association acceptance. Suite counts overlap
and must not be added as unique coverage. No tests were removed or relaxed, no new
migrations generated, and no application database changes, staging, commit, push,
merge, deployment or real-data access occurred.

**Stop after this amendment for review. G18-B Gate 1 is not started. Operational
EWAF scoring, ranking, beneficiary selection and public results publication remain
disabled; the accepted milestone remains 70%.**
