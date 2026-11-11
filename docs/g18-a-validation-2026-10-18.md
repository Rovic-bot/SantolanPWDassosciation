# G18-A implementation and validation report

Started 2026-10-17; completed 2026-10-18 (Asia/Manila).
Branch: `feature/events`. HEAD: `949eeda33c6aa5d8ee03962209ae8fedeac58ad1`.
**G18-A is ready for owner review. The accepted milestone remains 70%; Stage 8
is incomplete and 80% is not claimed. Stop before G18-B.**

## Scope delivered

Implemented the first bounded increment in the supplied Stage 8 handoff:

1. Read the new Computation.docx text/tables and all eight embedded formula images;
   inspect the existing workbook's exact formulas, literal copies and stored caches.
   Preserve the originals. The [computation crosswalk](g18-a-computation-crosswalk-2026-10-17.md)
   records source fingerprints, locations, conflicts, canonical arithmetic and the
   complete specified-versus-pending policy inventory.
2. Add a portable named-criterion matrix fixture and eight isolated mathematical
   tests. Compare G14's full canonical matrix, normalized matrix, weights, WSV, CV,
   lambda estimate, CI and CR with an independently constructed Decimal fixture and
   an exact rational oracle. Preserve G14 arithmetic and parser limits unchanged.
3. Add a private, read-only policy checklist linked from existing configuration
   diagnostics and preparation forms. Clarify the ten comparison fields with full
   criterion names and importance direction. Inputs remain blank. All twelve policy
   areas remain pending; no example becomes a default or approval.
4. Add nine permission/privacy/no-write/workflow tests and an opt-in headless
   browser scenario covering the new page and existing preparation workflow.

The review flow uses the existing draft, mathematical validation, review/correction
and **non-effective** authority-record services. No separate policy schema or saved
approval form was added. The read-only checklist rejects POST; existing review
explanation/correction fields can record unresolved policy questions through the
existing audited services. This is groundwork, not G18-C's full guided workflow.

## Computation findings

- Both sources use the same named pairwise matrix in PA/SI/ES/ND/PR source order.
  G14 requires SI/ES/PA/ND/PR. Tests map both axes by name and prove source dictionary
  order cannot affect the result; a consistency pass alone cannot detect mislabeled criteria.
- Exact canonical `CR = 0.017826279545329435154397479041353552931098572185357`,
  below 0.10. This establishes reference consistency only.
- Document ES 0.2483/24.83% and CI 0.0199 differ from direct rounding of the canonical
  values (0.2482/24.82% and 0.0200). The handoff's abbreviated weights also have minor
  final-digit discrepancies. No displayed coefficient is consumed as an input.
- Workbook C29:C33 still contain broken row-average references with stored `#DIV/0!`;
  downstream copies are not live dependencies. No repair or Excel recalculation is claimed.
- Dataset-derived min–max in the document conflicts with the current explicit
  fixed-bound synthetic contract. Directions, all-equal/missing/outlier treatment,
  exact pool/cutoff, band endpoints, ranking/ties and effective authority remain pending.
- No member accounts, new PDAO-ID prerequisite or score-based eligibility path was introduced.

## Exact file inventory

Five pre-existing files modified by **this increment only**:

| File | Change |
| --- | --- |
| `ewaf/configuration_forms.py` | Full criterion labels and plain-language comparison guidance; no defaults or validation/service change. |
| `ewaf/configuration_views.py` | Permission-checked GET/HEAD-only policy review, no writes or applicant queries. |
| `ewaf/urls.py` | Named `policy_review` route before the existing generic action route. |
| `templates/ewaf/configuration_detail.html` | Link to the policy review. |
| `templates/ewaf/configuration_form.html` | Link and source-example warning in existing preparation forms. |

Ten new files, all left unstaged:

| File | Purpose |
| --- | --- |
| `ewaf/policy_reference.py` | Immutable review-item records containing prose only; no score-policy parser or activation state. |
| `ewaf/test_computation_reference.py` | Eight reference/mapping/precision/isolation tests. |
| `ewaf/test_policy_reference.py` | Nine UI permission/privacy/no-write/preparation-barrier tests. |
| `ewaf/tests_data/g18/computation-reference-v1.json` | Original named fractions, ten G14 pairs and complete independent expected arithmetic. |
| `ewaf/tests_data/g18/README.md` | Fixture provenance, precision and non-operational contract. |
| `templates/ewaf/policy_review.html` | Existing Admin styling, twelve pending areas and links into existing review/history flow. |
| `scripts/g18_browser_qa.py` | Fictional live-server setup with temporary private media. |
| `scripts/g18_browser_qa.cjs` | Headless Chrome checks and screenshots. |
| `docs/g18-a-computation-crosswalk-2026-10-17.md` | Reconciliation and owner decision inventory. |
| `docs/g18-a-validation-2026-10-18.md` | This report. |

No models, migrations, settings, dependencies, durable backend, numerical engines,
source writers, navigation groups or operational guard code were changed. Existing
G12–G17 tests and fixture sources remain unchanged. The user's pre-existing
`ewaf/migrations/0005_durable_development.py`, annual-observance migration/work,
launcher changes and other staged/unstaged/untracked files remain preserved.

## Isolation and commands

Every database-backed command used the unchanged `scripts/g12_test_runner.py` and
the project `.venv` interpreter. The runner creates a fresh loopback MySQL instance
and datadir, checks actual datadir/port and empty system-only initial schemas,
filters inherited environment, disables dotenv, uses ephemeral credentials with
grants only for `g12_empty` and `test_g12_disposable`, and shuts its server down.
No application credentials, datadir or real private uploads were loaded.
The `.env` file was hashed solely for unchanged-byte verification, not executed or
printed. Fictional test media stays in temporary fixture storage.

Numerical test runs also used the existing `DurableTestRunner`: actual server UUID,
port, datadir, test name and temporary media must match the fresh-instance capability.
Observed **MySQL 8.4.11, READ-COMMITTED, all test tables InnoDB**. The final full-suite
instance used loopback port 64185, server UUID
`957bb0e9-ca43-11f1-b54f-581122e63603`, and datadir
`%TEMP%/santolan-g12-tests-39kk_15k/data/`.

Existing migrations were applied only to disposable test databases. Historical
migration-preservation tests exercised their existing down/up transitions there.
No new migration was generated, no application migration was run, and the normal
system launcher was not invoked.

Exact commands from the repository root:

```powershell
# Initial focused run: one test assertion corrected as described below.
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf.test_computation_reference ewaf.test_policy_reference --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 2

# Final focused tests plus the explicit browser scenario.
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf.test_computation_reference ewaf.test_policy_reference scripts.g18_browser_qa --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 1

# All EWAF: G12–G17, pool, durable, migrations/concurrency and new G18-A tests.
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test ewaf --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 1

# Complete project regression.
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test --testrunner scripts.durable_test_runner.DurableTestRunner --noinput --verbosity 1

# Non-writing schema drift and configuration checks on separate fresh instances.
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py check --database default

git diff --check
git diff --cached --check
node --check scripts/g18_browser_qa.cjs
```

## Fresh results

Each directory below has prefix `santolan-g12-tests-` under `%TEMP%`. Counts overlap
and must not be added together as unique coverage.

| Run | Result | Runtime | Failures / errors / skips | Directory suffix |
| --- | --- | --- | --- | --- |
| Initial G18-A | 17 run, exit 1 | 1.454 s | 1 / 0 / 0 | `uq9sdygs` |
| Final G18-A + browser | **18 passed**, exit 0 | 12.837 s | 0 / 0 / 0 | `ke63ah2a` |
| Complete EWAF regression | **420 passed**, exit 0 | 186.096 s | 0 / 0 / 0 | `53nqim74` |
| Complete project regression | **962 passed**, exit 0 | 359.295 s | 0 / 0 / 0 | `39kk_15k` |
| Migration drift | No changes detected, exit 0 | — | — | `0ubnps1w` |
| Django/database check | No issues, 0 silenced, exit 0 | — | — | `mu8l57tp` |
| Git whitespace, Node syntax, Python/JSON syntax and file preservation | Passed | — | — | `.local/g18-a/` |

The full suite discovered the current local work, including observance/startup
changes. The handoff's 898 and the later observance note's 942 are historical
reported counts, not substituted for this run. The 17 new tests are included in
both the 420 and 962; the opt-in browser scenario is included only in the focused 18.
No test was skipped, deleted or weakened to bypass a business-rule failure.

The initial failure asserted there was no `<form>` anywhere in the page; the shared
Admin shell correctly contains a logout POST. The test now checks the review's
`<main>` content. The read-only/no-SQL-write/POST-rejection assertions remain intact.
No runtime code change was required for that failure.

Before the first actual run, the sandbox blocked writing the disposable temporary
`mysql.ini` (`2wdh62gh`); no server or tests ran in that attempt. The identical
harness was rerun with tool approval. Later copying temporary test logs was also
sandbox-blocked; approved copying retained only the six Django logs and three
fictional screenshots, without MySQL configuration, credentials or database files.

## Coverage and visual verification

- Pure math: exact named pairs, both-axis/source-order independence, full canonical
  arithmetic equality, exact rational error bound, source rounding discrepancies,
  hostile ambient Decimal settings, immutable inputs, no scores/ranks/authority.
- UI/server: every existing configuration-view permission required; anonymous,
  dashboard-only, inactive and nonstaff rejection; no-store; no member/application
  values; GET permits SELECT only and preserves all registered model rows; POST
  cannot save or activate; blank judgments; reference validation plus review and
  attestation still leaves all effective/operational gates closed.
- Existing regressions: G12 evidence/provenance; G14 configuration/audit/staleness;
  G15 READINESS_ONLY and arithmetic; G16 exact comparisons; G17 simulations;
  pool/durable barriers, atomic audit rollback, separate-connection MySQL races,
  retries/history, historical-migration preservation; project membership, events,
  assistance, publication, permissions and startup tests.
- Browser: eight private pages, widths 320/390/768/1440, one main heading, visible
  control labels, no page overflow or JavaScript errors, no-store responses,
  keyboard confirmation/navigation, all four existing draft/validate/review/
  authority POST workflows, no preselected comparisons and twelve pending areas
  still shown after documentary attestation. No activation or score/rank/file controls.

Visually inspected the generated policy mobile/desktop and draft mobile screenshots:
[policy mobile](../.local/g18-a/g18-policy-mobile.png),
[policy desktop](../.local/g18-a/g18-policy-desktop.png),
[draft mobile](../.local/g18-a/g18-draft-mobile.png).
The existing light Admin layout is retained; text wraps without clipping/overlap.
This is focused Chrome/keyboard/responsive QA, not full WCAG/screen-reader or
Association UAT acceptance. Optional full-matrix entry retains its existing `null`
presentation; the ten comparison inputs are blank.

## Preservation evidence

Before edits, captured 546 SHA-256 entries: **544 repository files plus `.env`
and the Git index**, the full staged binary diff, and the dirty-file inventory.
Final comparison found only the five intentional existing-file edits listed above;
the other **541 entries remain byte-identical**, including all pre-existing dirty
G16/G17/durable/observance files, `.env`, and the index. The staged binary diff is
also byte-identical. No reset, clean, stash, pull, branch switch, staging, commit,
push, merge or deployment was performed.

All three supplied source hashes match the initial capture. All migration files,
numerical engines, business services and operational guards retain their initial
bytes. Git whitespace checks passed; unrelated pre-existing line-ending notices
are not rewritten. Syntax/JSON/whitespace checks include the ten new files,
which ordinary `git diff --check` does not cover.

Ignored `.local/g18-a/` retains baseline/status/staged-diff evidence, source
extractions/formula images, source hashes, final preservation/manifest evidence,
six Django logs and three screenshots. These are review evidence, not committed
source or signed CI. No real applicant data, database dump or credential is packaged.

## Review decisions and limits

**Owner decision needed before a later increment:** is Computation.docx a draft
reference or an Association-approved replacement for the workbook? If approved,
identify the approving role, documentary reference, effective date and program scope.
The crosswalk enumerates the remaining criterion/evidence/direction/bounds/bands/
ties/locking/revalidation choices without selecting defaults.

This increment does not establish wider source-writer invalidation or atomic
current-result promotion (G18-B), full guided operational Admin configuration
(G18-C), human selection integration (G18-D), or institutional acceptance (G18-E).
The durable backend's documented wider-source limitations and absent current-result
pointer remain. Mathematical consistency does not prove equity or fairness.

Live EWAF scoring/ranking, selection, public outcomes and real-data migration stay
unavailable. No application database was modified. **Stop at G18-A for review;
accepted milestone remains 70%.**
