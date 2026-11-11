# EWAF score breakdown — 2026-10-26

The owner requested a separate tab explaining completed EWAF rankings, using Juno Bituinal 02 in **EWAF Lab — Assistance Release** as the example. This change adds a private, read-only presentation of existing operational calculations. It does not change scoring, eligibility, ranking, weights, policy approvals or beneficiary decisions.

## Behavior

- **Score breakdown** appears beside **Results and selection** within a program. Each result score links to that applicant's breakdown. The tab provides saved-calculation and applicant selectors, with the highest-ranked applicant selected initially.
- The criterion table shows Employment Status (ES), Socioeconomic Indicator (SI), Household monthly income (HI), Previous Assistance Received (PA), and Number of Household members (HM), in that display order. Each included criterion shows its recorded input and original category label where available, encoded value, normalization formula and direction, normalized score, weight and points contributed to the total. A separate table compares all scored applicants, paginated at 50 rows. Full-precision values remain available in an expandable section.
- The explanation uses the saved count of strictly higher scores to explain the rank, retains exact ties, identifies all criteria sharing the largest contribution and separately identifies the highest normalized criterion scores. Rounded numbers never determine ranking or tied leaders. Zero totals do not manufacture a leading criterion.
- Historical four-criterion, household five-criterion and exact-rational dataset calculations retain their original definitions and traces. Category labels come from the calculation's retained evidence policy. Applicant display names follow the existing workspace; scoring data always comes from the saved snapshot, not current profile fields.
- The existing integrity replay must pass before a breakdown is shown. Corrupt calculations return an unavailable explanation with HTTP 409. Stale/older calculations remain readable with a renewed-review notice. The empty tab does not generate a calculation.
- Access uses the existing private operational/evidence permissions and no-store caching. The route accepts GET only. Program/run/applicant scope is checked. No public result projection, document URL, mutation action, model or migration was added.

The October 10 requirements, implementation boundary, open decisions and exact workbook formula/cache evidence were reviewed. Workbook defects, disconnected literal copies and proposed policy choices were not imported or repaired. Presentation uses each saved run's own configuration, including its original criterion set.

## Requested example verified

The identified fictional development database contains reference `SPWDA-2026-PRG000012-0000000010`, Juno Bituinal 02. Its latest saved run is ID 23, calculation revision 4, with 20 scored applicants.

| Criterion | Recorded input | Encoded value | Saved normalization | Weight | Contribution |
| --- | --- | ---: | --- | ---: | ---: |
| SI | Income category ₱0–₱5,000 | 5 | (5 − 0) / (5 − 0) = 1 | 25% | 25.00 |
| ES | Retired | 3 | (3 − 0) / (3 − 0) = 1 | 25% | 25.00 |
| PA | 0 confirmed releases in the saved assessment | 0 | (4 − 0) / (4 − 0) = 1 | 25% | 25.00 |
| ND | 4 dependents | 4 | (4 − 0) / (8 − 0) = 0.5 | 25% | 12.50 |

Total: **87.50 / 100**. The saved comparison has zero higher scores and no other equal score, so the rank is **1**. SI, ES and PA share the largest contribution. These are retained fictional lab definitions and inputs, not new Association policy or current member facts.

## Validation

**65 focused tests passed** in a fresh isolated native MySQL instance with `.env` disabled, a distinct test database and private synthetic media. The suite covers the new explanation, operational generation/decisions, household criteria, exact dataset calculations and program navigation. A subsequent focused run passed all **9 breakdown tests** after the display helper and direct result links were finalized; those nine are included in the 65 unique tests.

```powershell
.venv\Scripts\python.exe -B .local\ewaf-score-breakdown-20261026\run_tests.py test ewaf.test_score_breakdown ewaf.test_operational ewaf.test_household_criteria ewaf.test_dataset_policy ewaf.test_program_cards --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
.venv\Scripts\python.exe -B .local\ewaf-score-breakdown-20261026\run_tests.py test ewaf.test_score_breakdown --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

The ignored launcher reuses the existing Windows synthetic-directory ACL compatibility wrapper. Logs are under `.local/ewaf-score-breakdown-20261026/temp/santolan-g12-tests-rozhwabr/` and `santolan-g12-tests-u9q_8w1g/`.

Tests include independently specified 87.50-point arithmetic, category labels, inverse/benefit formulas, joint leading contributions, exact and nearly tied totals, hostile ambient decimal precision, rational values, zero totals, saved totals differing from rounded contribution sums, no automatic generation/selection, authentication/permissions, cross-program identifiers, stale snapshots and tamper rejection. Retained calculation payloads and decision/audit counts remain unchanged by viewing.

Django system checks and `git diff --check` passed. The identified local runtime also passed `check --database default`. Its actual requested breakdown and existing program workspace rendered successfully in a fresh Django process. The rendered breakdown has two tables and no duplicate IDs. Every retained run and decision for that program was compared before/after rendering and remained identical. No browser visual/screenshot pass is claimed; Chromium launch was blocked by Windows permissions earlier in this session.

## Local runtime installation and main development verification

Eight scoped files were installed into `.local/dual-registration-20261024/runtime/`, preserving its separate program-intake hooks and older calculation engines. Existing files were merged by exact context, with original bytes, staged copies and checksums retained under `.local/ewaf-score-breakdown-20261026/`. The runtime templates tolerate the old loaded URL configuration until restart, so the new links do not break the existing running page.

No database records, policies, credentials, environment files or migrations were changed. The completed membership work and pre-existing edits to `templates/ewaf/tabs.html` and `templates/programs/manage_detail.html` were preserved.

The initial port-8003 restart attempt was denied by Windows. The owner subsequently confirmed that **http://127.0.0.1:8000/** is the main development site. Its branch header, launcher and database identity were verified: it serves this source checkout with `.local/ronnel-development-20261026/ronnel_settings.py` and the retained `santolan_lab_ronnel_20261026` fictional database on port 3308.

The Start/Restart shortcuts now target the main port-8000 configuration. The verified server was successfully restarted, and authenticated HTTP checks confirmed the new breakdown route returns 200 with the requested Juno reference and saved **87.50** score. The main database's calculation revision 4 retains the same rank 1 and contributions shown above. The existing workspace and breakdown also rendered in a fresh process with a SQL guard rejecting all writes; every retained run and decision for the program remained identical. Main `check --database default` and migration drift checks passed.

The verification helpers are `.local/onsite-registration-20261026/validate_main.py` and `validate_main_http.py`. The latter uses the normal fictional Admin login, GETs the pages, then signs out; it does not generate scores or submit beneficiary decisions. The result-link template also tolerates an old URL configuration during a server restart. No commit, push or hosted deployment was performed.

## Owner clarification: five displayed criteria

The owner clarified the exact five names and display order: **ES, SI, HI, PA, HM**. This is a presentation order only; versioned engine order, weights, rules, accepted inputs, saved totals and ranks remain unchanged. Both the criterion table and applicant comparison follow that order. The reusable row partial displays full names with their abbreviations.

Older four-criterion runs have no HI or HM scores. Those rows explicitly say **Not included in this calculation**; their comparison cells use a dash, never a fabricated zero. A legacy SI income input remains SI with its original source explanation. Historical Number of Dependents is not relabeled or copied to Household members. Historical factors remain available in a separate expandable table and an identified comparison column so the original total is still explained.

For Juno's retained calculation, ES + SI + PA contribute **75.00** points. HI and HM were not included. The historical ND contribution remains **12.50**, retaining **87.50** and rank **1**. No calculation was generated or converted by this display correction.

All **42 focused tests passed** (70.105 seconds) in a fresh disposable MySQL instance. This run covers the breakdown, five-criterion fixed-bound workflow, and exact dataset workflow, including legacy non-substitution, ordered columns, missing-score treatment, retained contributions, integrity checks, permissions and preserved history. It overlaps the earlier test counts.

```powershell
.venv\Scripts\python.exe -B .local\ewaf-score-breakdown-20261026\run_tests.py test ewaf.test_score_breakdown ewaf.test_household_criteria ewaf.test_dataset_policy --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

Log: `.local/ewaf-score-breakdown-20261026/temp/santolan-g12-tests-fckjkxzw/django.log`. Read-only main-configuration rendering, Django database/migration checks and `git diff --check` passed. The verified port-8000 server was restarted successfully. Authenticated HTTP verification confirmed the five main table rows in the requested order, the two explicitly absent historical scores and the retained Juno total. No browser visual pass is claimed.
