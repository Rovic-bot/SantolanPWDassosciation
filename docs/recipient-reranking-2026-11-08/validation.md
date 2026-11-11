# Ranking new applicants alongside completed recipients — November 8, 2026

The owner reported that adding an eligible applicant marked two already fulfilled recipients as needing review and left the new applicant outside the saved ranking. The requested behavior is to rank the growing applicant pool, retain completed recipients in that ranking, and prevent selecting or recording assistance for them again.

## Cause and correction

The automatic-input source includes `dataset_program_applications`, the sorted list of every application in the program. Adding an applicant changed that list. The receipt fulfillment projection compared the recipient's source against its original ranking source and treated the larger roster as a change to the recipient's information. The projection then failed to recognize the audited `ELIGIBLE` to `COMPLETED` transition, producing `APPLICATION_NOT_CANDIDATE` and `APPLICATION_REVIEW_UNRESOLVED`.

`ewaf/revised/fulfillment.py` now accepts append-only roster growth when comparing a completed recipient with its retained source in the current-eligible automatic-input workflow. It carries the current roster into the new calculation; a saved ranking remains stale until regenerated. The original receipt approval can also be matched after successive roster expansions. Every other profile, evidence, history, application-version, configuration and receipt-audit check remains in place. Roster removal is not accepted by this exception.

This does not change scoring formulas or manually assign scores or ranks. New calculations use the existing locked rules and current eligible pool. Completed recipients retain their original selections and receipt evidence. Existing service checks block repeat selection and duplicate receipts, and their selection panel continues to display the recorded-assistance state instead of a selection action. Genuine member-information or audit changes still require review.

No model, migration, dependency or template change was needed. Other unfinished repository work was preserved.

## Validation

**31 distinct focused tests are verified passing**, on fresh disposable native MySQL databases:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test ewaf.test_recipient_reranking ewaf.test_rolling_delivery.RollingDeliveryTests ewaf.test_rolling_pool.RollingPoolTests assistance.test_receipt_button --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

The initial combined run (`santolan-g12-tests-5jtcq9qh`) passed 30 tests. One corruption fixture attempted to void a receipt without clearing its active-application binding and correctly hit the database's `release_active_or_void` constraint. The fixture was corrected to represent a consistent voided row; both new regression tests then passed in `santolan-g12-tests-7xln9dgo`. No implementation changes occurred between those runs.

The new tests cover two completed recipients plus a third eligible applicant, stale previous results, a subsequent fourth applicant, fresh calculations containing the whole pool, successful selection of the newcomer, blocked repeat selection and duplicate receipt recording, unchanged prior calculation and receipt history, and rejection of changed member information, damaged receipt audits, voided receipts and roster removal. Existing focused suites cover rolling registration, selection, delivery permissions, capacity, audit rollback and receipt behavior.

Django/database checks and `git diff --check` passed.

## Retained local program

A read-only preflight confirmed three eligible ranking inputs, two valid receipt audits and no review errors after the correction. A private backup of the affected records was saved under ignored `.local/rolling-ranking-update-20261108/`.

The owner's requested reranking was then generated through `operational_services.generate`, appending run **45**, revision **3**, after run **44**. A transaction-scoped SQL guard allowed only the new operational-run insert and its mandatory program-audit insert. Assertions confirmed that all prior runs, configurations, program/application/member records, selections, receipts and existing audit rows remained unchanged. No applicant was selected and no assistance receipt was recorded by this operation.

After restarting the local development server on port 8013, read-only validation rendered the actual workspace and selection templates: three ranked applicants, no unranked applicants, no review warnings, two received-assistance states without selection/unselection actions, and an enabled selection action for the newcomer. The ranking passed current-source validation.

Sanitized evidence: [regeneration](regeneration.json) and [post-restart verification](verification.json). Private applicant records and the backup remain outside committed documentation.
