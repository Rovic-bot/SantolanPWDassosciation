# G16 local environment recovery and fresh validation

Date: 2026-10-15 (Asia/Manila). Branch: `feature/events`.
HEAD: `949eeda33c6aa5d8ee03962209ae8fedeac58ad1`.
**Baseline: 70%, unchanged. Stage 8 and the 80% target remain incomplete.**

## Environment diagnosis and actions

The supplied failed attempts loaded Django from global Python 3.14 and could not
import MySQLdb. The existing project `.venv` is healthy. The global traceback,
combined with the successful project imports below, supports an interpreter/path
selection error, not a missing project dependency. The old failures were not
reproduced against an unverified database.

Explicit interpreter: repository `.venv\Scripts\python.exe`, Python **3.14.5**.
`sys.prefix` is the project `.venv`; `sys.base_prefix` is the existing Python
installation; `include-system-site-packages = false`. Both `django.__file__` and
`MySQLdb.__file__` resolve beneath `.venv\Lib\site-packages`.

Installed versions match every `requirements.txt` pin: Django 5.2.17,
mysqlclient 2.3.0, python-dotenv 1.2.3, Pillow 12.3.0, asgiref 3.12.1,
sqlparse 0.6.0 and tzdata 2026.4. Import verification succeeded, including dotenv
and PIL. No dependencies, Python version, settings, credentials or activation
scripts were changed. Use the explicit virtual-environment executable for future
commands; bare `python` is not evidence of using this environment.

Final standalone interpreter probe (exit 0):

```powershell
.\.venv\Scripts\python.exe -c "import sys, django, MySQLdb; from importlib.metadata import version; print(sys.executable); print(sys.version.split()[0]); print(django.__file__); print(MySQLdb.__file__); print('Django='+version('Django')+' mysqlclient='+version('mysqlclient')); assert sys.prefix != sys.base_prefix"
```

## Isolation verified before Django execution

Inspected `scripts/g12_test_runner.py`, `config/settings.py`, dependency pins and
the G12/G14/G15/G16 test documentation before running Django commands. The local
MySQL 8.4.11 binary exists. Every database-backed command below used the unchanged
documented runner, which:

- Creates a fresh temporary datadir and loopback port, verifies actual datadir/
  port identity and the absence of application schemas before setup.
- Filters inherited environment variables, disables dotenv with
  `PYTHON_DOTENV_DISABLED=1`, sets `config.settings` explicitly and keeps
  `PDAO_ENFORCEMENT_ENABLED=0` in the disposable child environment.
- Generates ephemeral synthetic credentials with grants limited to `g12_empty`
  and the separate `test_g12_disposable` database.
- Launches Django with its own `sys.executable`, destroys the test database after
  tests and shuts down its disposable server in cleanup.

No `.env`, local operational credentials, application datadir, production settings
or remote service was opened. Test setup applies the repository's existing
migrations only inside disposable databases; preservation tests also exercise
historical migration transitions there. No new migration was generated or applied
to an operational database. This was not a migration workaround for the import
failure.

The first sandboxed check and focused invocation each exited **1** before MySQL
startup because writing the temporary `mysql.ini` was denied. Their temporary
directories were `santolan-g12-tests-4t5aqirt` and
`santolan-g12-tests-_9idzuv8`. No tests ran in those two attempts. Approved
escalated reruns of the same runner resolved that sandbox restriction. A later
sandboxed attempt to read the retained test logs was also denied; an approved
read copied only the five `django.log` files into ignored local evidence.
These permission failures are separate from the supplied global-Python error.

## Fresh commands and results

Commands were run from the repository root. Results below are from this task,
not copied from the October 14 report. The three suites overlap; do not add their
counts as unique coverage.

| Command | Exit | Tests run/passed | Failures/errors | Skips | Reported test time/result |
| --- | ---: | ---: | ---: | ---: | --- |
| A: system/database check | 0 | N/A | 0 issues | N/A | 0 silenced |
| B: focused G16 | 0 | 54 / 54 | 0 / 0 | 0 | 9.570 s |
| C: complete Django suite | 0 | 753 / 753 | 0 / 0 | 0 | 259.605 s |
| D: migration drift, check only | 0 | N/A | 0 | N/A | No changes detected |
| E: explicit G12/G14/G15 regression | 0 | 198 / 198 | 0 / 0 | 0 | 75.043 s |

```powershell
# A
.\.venv\Scripts\python.exe scripts/g12_test_runner.py check --database default
# B
.\.venv\Scripts\python.exe scripts/g12_test_runner.py test ewaf.test_ranking_diagnostics ewaf.test_ranking_policy ewaf.test_ranking_readiness ewaf.test_ranking_preservation --noinput --verbosity 2
# C
.\.venv\Scripts\python.exe scripts/g12_test_runner.py test --noinput --verbosity 2
# D
.\.venv\Scripts\python.exe scripts/g12_test_runner.py makemigrations --check --dry-run
# E
.\.venv\Scripts\python.exe scripts/g12_test_runner.py test ewaf.test_evidence ewaf.test_readiness ewaf.test_evidence_corrections ewaf.test_evidence_concurrency ewaf.test_evidence_migrations ewaf.test_ahp_validation ewaf.test_configuration ewaf.test_configuration_concurrency ewaf.test_configuration_migrations ewaf.test_normalization ewaf.test_weighted_scoring ewaf.test_scoring_services ewaf.test_scoring_inputs ewaf.test_scoring_concurrency ewaf.test_scoring_migrations --noinput --verbosity 2
```

All suites reported `OK` and zero system-check issues. Verbose logs contain no
skips, failures or errors. Two full-suite tests print management-command output
between their test name and `ok`; these are passing tests, not missing results.
No browser suite was run: this task and G16 introduce no UI changes. This evidence
does not establish browser/accessibility acceptance or Association UAT.

Retained runner directories are under `C:/Users/rovic/AppData/Local/Temp/`.
Only Django logs were copied to `.local/g16-revalidation-2026-10-15/`; no MySQL
configuration, credentials, database files or uploads were copied.

| Local log | Runner directory | SHA-256 of copied log |
| --- | --- | --- |
| `check.log` | `santolan-g12-tests-7wmv6_ll` | `f87ceb15410bde28ff826ce26228e0576558258fa64d145847921a593a61ee63` |
| `focused.log` | `santolan-g12-tests-53r3wy91` | `f9ca4cc0f69bb4002bdb9332e958cef435c1cec857d3e976178340e853faaf38` |
| `full.log` | `santolan-g12-tests-j6_8havn` | `e8e715dbb4f8e6efb4b79ef13c89325e442c9027259ebfbee42be2730527ac80` |
| `drift.log` | `santolan-g12-tests-mwfgz8aa` | `93e6e2d5be3c054add80c0f19101608803f7ca8a7df1fa41f76bbb9a1f570f4a` |
| `g12-g14-g15.log` | `santolan-g12-tests-c03h8ub2` | `e3bdad17dd6809aeb8bccfdbb1e92c02c21ffb71dff01b7fac7abf8762b34065` |

## Source and preservation review

Reviewed G16 source bodies, test assertions and fixture contracts, with unchanged
G12/G14/G15 dependencies and historical-preservation helpers. Working copies of
the staged files match the index (`git diff --exit-code`, exit 0). The staged raw
diff including full blob IDs was captured before work and compared afterward:
identical. It still contains exactly 16 added files, 4,438 inserted lines, with
no model, migration, template, static, route or settings changes.

- `ranking_fixtures.py` accepts only four fixed names and checks bounded file
  bytes against immutable registry checksums. The CLI exposes those names only;
  it accepts no applicant IDs, upload, arbitrary path or score submission.
- `ranking_diagnostics.py` checks the entire manifest/common contract and replays
  G14/G15 evidence, including traces, weights, score scales and completeness.
  Incomplete pools return no accepted subset comparison. The private evaluator
  and test builder are developer seams, not a security boundary against arbitrary
  Python execution; they must not be exposed as applicant endpoints.
- Decimal sorting uses direct values and reverse order, with no float, unary
  negation, quantization or epsilon. Exact equal-score groups retain ties;
  synthetic IDs only stabilize their presentation. Tests cover equivalent decimal
  spellings, distinct 50-digit values with identical display rounding, changed
  ambient context, permutation stability and tampered/rehashed calculations.
- `ranking_policy.py` reports all nine decisions pending even with documentary
  references. `ranking_readiness.py` calls the permission-checked G15 score-free
  adapter, validates its schema and leaves operational authorization false.
  `require_operational_ranking` rejects unconditionally.
- Capacity is illustrative diagnostics only. G16 creates no actual applicant
  score/rank, selection, waitlist, operational activation, persistence/audit write,
  new ranking table, migration or UI. Existing operational guards are unchanged.
- The 54 focused tests comprise 35 numerical/integrity/isolation cases, 4 policy,
  12 readiness and 3 preservation cases. Preservation initializes synthetic
  historical EWAF rows, G12/G14/G15 artifacts and related business histories;
  compares all registered model rows before/after; rejects non-SELECT SQL during
  G16 calls; verifies EWAF leaf `0004_scoring_diagnostics`; and exercises all five
  retired mutation/ranking guards. No production rows were inspected to do this.
- The explicit regression and full suite exercise existing audit rollback,
  concurrent source/terms/release/void behavior and six G12/G14/G15 preservation/
  migration cases. These do not prove a new G17 multi-applicant pool transaction:
  none exists. Source inventory supplements the deliberately bounded schema test.

No blocking G16 source defect or corrective code change was identified in this
review. Fresh local validation closes the reported execution gap for the current
synthetic increment. It does not approve institutional policy or operational EWAF.
G16 remains suitable for owner review/acceptance as a synthetic foundation only;
formal acceptance is not inferred from staging or from this report.

## Files and preservation

Pre-existing staged files, all unchanged:

```text
docs/g16-ranking-diagnostics-validation-2026-10-14.md
ewaf/ranking_diagnostics.py
ewaf/ranking_fixtures.py
ewaf/ranking_policy.py
ewaf/ranking_readiness.py
ewaf/ranking_testsupport.py
ewaf/test_ranking_diagnostics.py
ewaf/test_ranking_policy.py
ewaf/test_ranking_preservation.py
ewaf/test_ranking_readiness.py
ewaf/tests_data/g16/README.md
ewaf/tests_data/g16/high-first-v1.json
ewaf/tests_data/g16/incomplete-v1.json
ewaf/tests_data/g16/low-first-v1.json
ewaf/tests_data/g16/precision-v1.json
scripts/g16_synthetic_diagnostics.py
```

Added by this task, left unstaged:

- `docs/g16-revalidation-2026-10-15.md` (this report).
- `docs/g17-recalculation-history-plan-2026-10-15.md` (planning only).

Ignored evidence: five copied logs in `.local/g16-revalidation-2026-10-15/`.
Disposable runner artifacts remain in the listed temporary directories.
`git diff --cached --check` and `git diff --check` passed. No reset, unstage,
commit, push, merge, deployment, operational migration or application-code change
was performed. The October 14 report remains a dated record: its old statements
about an empty index describe that earlier task, not today's 16 staged files.

## Remaining work and milestone

See [G17 plan](g17-recalculation-history-plan-2026-10-15.md) for trigger conditions,
immutable history and version association, incomplete/stale evidence handling,
permissions/audit, proposed files/tests/acceptance and separate authorization
boundaries. G17 runtime behavior was not implemented. G18 remains pending.

Open measurement/direction/bounds/precision/classification/tie policies, effective
configuration authorization, G06-B2/B3 governance, complete current applicant
runs and human-selection integration remain unresolved dependencies. Preserve
the light eight-group Admin Portal, onsite membership, verified-member applications,
offline PDAO decisions, private evidence and human final decisions.

**Current milestone remains 70%. The 80% target is not yet achieved.**
