# EWAF one-click configuration — 25 October 2026

The owner requested removal of the authority/selection, dates, assessment periods, criterion definitions, ranges, category mappings and document-type controls from the Configuration Vault. Approval is now a single **Approve configuration** action after adjusting the existing weights. The separate reason, attestation and AHP-preview acceptance steps are removed from this screen. Historical program editors retain their existing behavior.

The screen lists the confirmed sources: member-registration household monthly income, supporting documents and optional 4Ps membership for SI, Employment Status, household-member count, and confirmed non-voided system assistance releases. It does not accept replacement applicant values or configurable source overrides. Existing registered-input review, private evidence and actual-release services are preserved.

The approval service validates weights server-side, records actor/time and an automatic explanation, and creates an immutable audited revision. Stale submissions, missing authorization and audit failure remain protected. Unchanged saved weights retain their original comparisons. Existing active approved scoring definitions are copied on the server; posted policy fields cannot change them. Earlier configurations and calculations remain intact.

No approved numerical scoring policy existed in the identified local vault. A first approval therefore locks the confirmed weights and sources with an explicit `weights_and_sources` scope. It does not invent income/PA directions, category scores, bounds, thresholds or an evidence rubric. The page reports scoring as pending, and operational validation/publication still reject incomplete calculation rules. Optional 4Ps or document presence is not silently converted into a score. A clarification about these missing rules was requested; no answer arrived during implementation.

New programs inherit the approved source/weight version as a draft. Complete existing approved policies retain their original publication, review, calculation and human-selection behavior. The source-only approval does not authorize incomplete EWAF program publication or beneficiary selection.

## Validation

- Initial isolated MySQL regression run: 49 cases across vault, household criteria, weight input and operational EWAF; 45 passed and four existing registered-review cases exposed a UTC-versus-Manila date error in their synthetic assessment-period fixture.
- Corrected the fixture to use the same `timezone.localdate()` convention as the review. All five registered-input tests passed on rerun, covering the four failed cases, source changes, evidence/audit protections and confirmed-release/void counting.
- A follow-up vault run also passed all 12 configuration tests and the concurrency test after preserving unchanged saved comparisons. Its already-imported source-review fixture still had the earlier date error; the subsequent focused rerun above resolves those failures.
- The existing JavaScript slider suite passed all 500 cascade/priority cases. Python syntax, scoped whitespace checks and `git diff --check` passed.
- Fresh-process checks against the identified local development runtime passed: database configuration, no missing migrations, one-click form rendering and absence of the removed controls. No database approval was created; the vault remained empty.
- Added a disposable browser harness for one-click approval, changed weights and mobile layout. Execution stopped at browser startup with `spawn EPERM`; no browser assertions or screenshots completed. This is not visual/browser acceptance.

Private test logs are retained under `.local/dual-registration-20261024/temp/`: `santolan-g12-tests-je_4ounx` (49-case regression), `santolan-g12-tests-5ny7wc43` (follow-up configuration tests), `santolan-g12-tests-kqrm4j7b` (five passing source reviews), and `santolan-g12-tests-ykgp7_05` (browser launch denial).

## Local runtime

Nine scoped files were installed under the existing `.local/dual-registration-20261024/runtime`, with originals, staged hashes and checks retained under `.local/ewaf-one-click-20261025`. Its additional program-intake policy hooks were merged and preserved. No models, migrations, application records, approvals or scores were changed.

The running development process uses `--noreload`. Automatic approval review rejected the requested restart with **blocked by policy**, without a more specific reason. The updated Python modules therefore require a manual restart of the existing development system at port 8003 before the new approval flow can be used. Stop that development server, then run `Start System.cmd`; no migration is needed.
