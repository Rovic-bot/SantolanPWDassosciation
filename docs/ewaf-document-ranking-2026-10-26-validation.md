# EWAF document calculation and ranking — 26 October 2026

The owner requested removal of Revised EWAF preview, use of `EWAF_Computation_Download/Computation_Updated_HI_SI_ES_PA_HM.docx` for calculation, editable criterion weights in the Configuration Vault, and generation after all applicant information is entered. The owner then explicitly confirmed SI: 5 for both 4Ps membership and a Certificate of Indigency, 2.5 for either one, and 0 for neither. This authorizes the implementation below; it does not change the credited 70% milestone or approve unrelated requirements.

## Behavior

- EWAF navigation now leads to **EWAF Ranking** and **Configuration Vault**. The former `/ewaf/revised/` entry redirects to ranking and rejects POST. Private retained demonstration records and exports remain available without exposing a new preview or deleting history.
- The latest owner-confirmed weight editor uses full-scale 0–100% sliders with Saaty-compatible final weights. Increasing one criterion reduces those below it proportionally while earlier weights stay fixed; the last receives the remainder. Priority arrows let every criterion move higher. Feasible values preserve positive weights, descending priority and the 9:1 proposal limit. New proposals start from 34.21 / 23.60 / 17.74 / 12.23 / 12.22 when no usable saved vector exists. AHP can produce equal weights for equal comparisons; the editor does not force equal weights or invent a ban on equal importance.
- The earlier `approved-percentage-weights-v1` method, its document-specific ranges, exact remainder (including zero HM), saved records and already-open submissions are retained. New slider approvals use the existing `slider-ratio-projection-v1` method: convert proposal ratios to supported discrete comparisons, calculate column-normalized row-average weights, and require consistency to pass. The generated-comparison provenance does not claim independently elicited judgments. All versions retain their original validators and precision; existing program configurations do not silently adopt newer weights.
- The Vault links to calculation-rule review and the ranking flow. New policy drafts use the supplied document method and confirmed SI rubric. Historical policy content and proposal provenance remain unchanged; legacy SI assessments are still replayed with their original rule.
- Accepted-input review records separate Yes/No findings for 4Ps membership and Certificate of Indigency. Missing or disputed findings block acceptance rather than becoming zero. SI is computed by the service; staff cannot type a final SI result, overall score or rank. Evidence ownership, freshness, supporting-document verification and permissions remain enforced. Previously saved findings are prefilled for renewed review without fabricating acceptance.
- The program ranking page shows ready/pending counts, per-applicant review problems, accepted values and links to enter/verify information. These display fields are not added to the persisted pool manifest. **Generate EWAF Ranking** uses every eligible, current, accepted applicant under the same locked program policy, after closing and cutoff. An unresolved application blocks the pool; verified ineligible outcomes remain outside it.
- Existing exact-rational dataset min–max and weighted-sum code is reused: HI and PA inverse; SI, ES and HM increasing; score = 100 × sum(weight × normalized value). Full precision determines order and ties. Constant columns stop as specified by the supplied document. Human beneficiary decisions, publication and actual releases remain separate.

No model change, migration, automatic policy approval, member-data backfill, real-data scoring, beneficiary selection or public-result change is part of this installation. The Word source and historical workbook/calculation engines remain unchanged.

## Validation

Tests run only through the existing fresh-instance MySQL harness with `.env` disabled, a verified disposable datadir, separate `test_g12_disposable` grants and synthetic private media. No working database was used as a test target.

The broad run covered 142 tests across document ranking, Vault, dataset policies, retained previews, operational generation/decisions, household criteria, breakdowns, intake policy, program cards and document arithmetic. Its sole failure was an assertion for the replaced heading; the assertion was updated. A subsequent 16-test focused run passed, including that test and two additional policy/input-form submission tests. The union covers 144 distinct tests. The final **17-test targeted run passed** (25.631 seconds), checking the display-only inventory change and retained-policy/current-run behavior. Counts overlap; they are not additive.

Independent fixture expectations include all four SI combinations and rejection of missing/boolean-lookalike values; exact default and edited weights; negative and zero HM; stale approval tokens; unauthorized writes; audit rollback; immutable older weights; incomplete-pool rejection; and HTTP generation with scores **100**, **0**, and **6379/120 = 53.158333…**, ranks **1, 3, 2**, with no automatic selection. The original DOCX example remains covered by the existing exact arithmetic tests.

Commands:

```powershell
.venv\Scripts\python.exe -B .local\ewaf-score-breakdown-20261026\run_tests.py test ewaf.test_document_ranking ewaf.test_vault ewaf.test_dataset_policy ewaf.test_revised_preview ewaf.test_operational ewaf.test_household_criteria ewaf.test_score_breakdown ewaf.test_intake_policy ewaf.test_program_cards ewaf.test_revised_math --testrunner scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

Broad log: `.local/ewaf-score-breakdown-20261026/temp/santolan-g12-tests-o_ugbpx8/django.log`. The passing 16-test log is in `santolan-g12-tests-oy5r2ysx/django.log` under the same temp root. The final targeted run is in `santolan-g12-tests-dpowvqdp/django.log`.

Django database checks and migration drift checks passed against the identified main development configuration. JavaScript syntax and `git diff --check` passed. Five private pages rendered with a SQL wrapper rejecting writes, and all rows of **72** inspected EWAF, program, assistance, migration and audit tables were unchanged. Sixteen retained runs replayed successfully. Seven older lab runs already lack required PR eligibility definitions in the unchanged legacy validator; those records were preserved, not repaired, reinterpreted or counted as successful replays.

Browser visual testing was attempted but Chrome process creation failed with Windows `spawn EPERM`. No screenshot, browser layout or keyboard-navigation pass is claimed. Ignored verification helpers and rendered HTML are under `.local/ewaf-document-ranking-20261026/`.

## Local operation and remaining setup

The approved feature is enabled in the identified main development settings for port 8000. The source defaults make dataset policy/scoring available when the Vault is enabled, while respecting explicit environment overrides. Existing startup guards remain unchanged; no migrations are applied or faked.

The existing restart script verified port 8000 and process 9752, but Windows denied `Stop-Process` access. The running process was not stopped or replaced. **A manual restart is still required to load the backend changes.** The Vault template detects the old editor context and shows a restart notice instead of submitting an incompatible form. Main-config checks use a fresh Django process, not a claim that the running process has reloaded. Run `scripts/restart-current-development.ps1` from the user's normal PowerShell session, or stop and restart the local system with the existing shortcuts.

There is currently **no approved dataset scoring policy** in that development database. An authorized Admin must complete the remaining assessment definitions, periods, evidence types/procedures, PA scope/history coverage, tie handling and effective scope, approve the policy, and assign it to an eligible new or weights-only program. Existing scored/historical programs retain their policy. The confirmed SI rule and document formulas are preselected for new drafts; missing institutional details are not invented. Generation becomes available only after configuration and all required applicant reviews are complete, within the retained timing and mathematical constraints.

No commit, push, merge or hosted deployment was performed. Pre-existing membership, receipt, QR, launch-script and other unfinished work was preserved.

## Weight-slider follow-up

The owner's initial volume-style request was implemented by pairing each HI/SI/ES/PA percentage box with a native range slider. That intermediate editor retains its exact-percentage submission method for already-open forms. The subsequent cascading/Saaty confirmation below supersedes it as the default editor.

JavaScript syntax, rendered slider labels/ranges/step values, Django checks, migration-drift checks and `git diff --check` passed. The five-page read-only rendering check again retained all 72 inspected tables unchanged. No new backend test suite was needed for this presentation-only follow-up. Browser visual verification remains subject to the recorded Windows restriction, and the running server still needs the previously described restart.

## Cascading Saaty sliders — confirmed follow-up

The owner explicitly selected **Full-scale sliders with Saaty-compatible final weights** after clarification that a saved 100% weight would leave zero for every other criterion. This authorizes replacing the document-specific display ranges for new edits while retaining the document's dataset normalization and ranking formula.

The default Vault editor reuses the existing cascading allocation and ratio-to-Saaty projection. All five sliders display 0–100% in 0.01 percentage-point steps and disclose their current feasible ranges. Earlier weights stay fixed during lower-row edits; the last row is automatic and can be moved higher to edit. The proposed total and rounded calculated-weight total both display exactly 100%. Saved weight strings retain the existing engine's precision.

Calculated AHP weights refresh after each adjustment, with approval disabled until the current calculation succeeds. Responses for superseded edits cannot re-enable approval or replace the current result. The server independently recalculates and validates on approval, requires a reason and the existing authority/token/audit checks, and retains an immutable new version. Reopening an AHP slider version restores its original proposal so calculated weights are not repeatedly re-quantized. Retained exact-percentage versions are replayed with their original method.

The Node cascade checks passed 1,500 cases across historical four-criterion and current five-criterion proposals, including fixed earlier weights, proportional tail changes, moving HM to first priority, positive weights, exact totals and saturation at Saaty limits. All **49 focused Django tests passed** (49.251 seconds), covering document ranking, Vault, weight input and household criteria. Coverage includes calculated/displayed versus saved results, reopening without drift, replacing a direct-percentage version without rewriting it, changed priority, invalid and stale submissions, permissions and audit rollback. The first run's test user lacked portal/workspace access; correcting the fixture required no permission-rule change. Final log: `.local/ewaf-score-breakdown-20261026/temp/santolan-g12-tests-8i4z7j_t/django.log`.

The read-only main-configuration check again rendered five private pages, confirmed no model migration drift and left all 72 inspected tables unchanged. Browser visual verification and loading the changes into the already-running process remain limited by the Windows restrictions described above.
