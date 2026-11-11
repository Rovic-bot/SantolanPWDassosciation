# Ineligible applicants do not block ranking — November 8, 2026

## Owner-confirmed behavior

The owner clarified that an applicant already marked Ineligible is outside the program's EWAF ranking pool and must not block ranking of eligible applicants merely because their member record later changes. This supersedes the unresolved-exclusion limitation in the November 8 eligible-readiness and current-selection-label validation notes.

The reported HM Focus program had ten accepted eligible applicants and two excluded applicants. Finn Testfoxtrot's recorded ineligible decision referenced member version 2 while his current profile was version 3. That version mismatch was the sole generation blocker; Gia Testgolf, selected in the supplied link, had no blocking errors.

## Implementation

- Centralized operational exclusion validation in `ewaf.readiness.ineligible_exclusion_errors` and reused it in document/member-record dataset, registered-input vault, and retained operational inventory paths.
- A recorded ineligible decision with its matching audit remains an exclusion after member/program source versions change. Its current scoring inputs and submission timing do not block the eligible pool.
- A bare Ineligible status without the matching recorded decision remains an integrity error. This does not create an unaudited way to remove applicants from a pool.
- Excluded rows remain in the private snapshot manifest, with their original decision and current source versions retained. They receive no accepted scoring inputs, calculation, rank, or beneficiary selection control.
- Eligible applicants retain all existing membership, eligibility, evidence, scoring, timing, permission, configuration, audit, and concurrency checks. Pending applications retain the existing approved ranking-window behavior.
- No eligibility or selection decision, stored score/rank, old run, policy artifact, public data, or mathematical formula was rewritten. No migration is required.

## Verification

A read-only capture and calculation against the retained local program successfully computed ten eligible applications, excluded both ineligible applications, and reported zero blocking errors. Saved-ranking counts remained unchanged; an SQL guard rejected business mutations. The local Django/database system check passed.

Sixteen distinct focused tests passed across the following checks, using fresh disposable native MySQL through `scripts/g12_test_runner.py` and `scripts.registration_intake_test_runner.RegistrationIntakeTestRunner`:

- `ewaf.test_ineligible_exclusion` (8): document-backed, reviewed-member-record, automatic-member-record, registered-input vault, and retained operational workflows. Actual generation excludes ineligible applicants with changed sources, missing scoring inputs, or late submission timestamps; retains their decisions and snapshots; preserves the eligible-only scores and prior runs; and exposes no selection action for the excluded applicant. Raw status changes without a matching decision still fail. Eligible applicants with changed sources still block generation.
- `ewaf.test_eligible_readiness` (6): previously approved reuse of unchanged Eligible reviews, source-change protection, selection/release behavior, and audit integrity.
- Existing applicant-panel selection POST and open/closed-registration pending-pool tests (2).

The initial 16-test invocation passed 13 checks. Three new tests initially added an extra application after the accepted-input snapshot, which correctly changed its captured program-application list and provenance. The fixtures were corrected to create the recorded exclusion before accepting the eligible inputs, then change only that excluded applicant's sources. All eight exclusion tests passed on rerun (33.468 seconds). Production code did not change between these runs; the other eight checks had already passed.

Logs:

- Initial invocation: `C:\Users\rovic\AppData\Local\Temp\santolan-g12-tests-bir0tgel\django.log`.
- Eight-test rerun: `C:\Users\rovic\AppData\Local\Temp\santolan-g12-tests-asr_q1eg\django.log`.

After restarting only the retained development runtime, browser verification of the owner's exact run-35 URL confirmed an enabled **Generate EWAF Ranking** button. Opening Finn's row showed **Ineligible / Pool excluded**, no Needs review marker, and no selection action. The ten saved ranking rows remained visible. Business POSTs were prohibited during this check; login was the only permitted POST. No new live ranking or decision was saved.

Evidence: [browser results](ewaf-ineligible-exclusion-2026-11-08/browser-results.json), [enabled generation](ewaf-ineligible-exclusion-2026-11-08/generate-enabled.png), [excluded applicant](ewaf-ineligible-exclusion-2026-11-08/excluded-applicant.png).

The Django/database check and `git -c core.safecrlf=false diff --check` passed. Existing unrelated changes were preserved.
