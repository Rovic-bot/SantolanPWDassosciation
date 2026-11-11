# Same-day assistance receipts during registration — November 8, 2026

The owner reported that, after recording the first selected applicant's actual receipt, the second receipt failed with `APPLICATION_NOT_CANDIDATE` and `APPLICATION_REVIEW_UNRESOLVED` for the already completed applicant.

## Diagnosis and correction

Read-only inspection of the reported two-applicant program reproduced the failure. The first receipt had a valid native delivery audit and was recorded after ranking, on the same calendar day. The existing fulfillment projection accepted only receipts dated strictly after the scoring cutoff's calendar date. It therefore failed to recognize the first applicant's legitimate `ELIGIBLE` to `COMPLETED` transition, causing validation of the remaining selected applicant to fail.

The current-eligible ranking workflow now recognizes an applicant's own audited receipt as fulfillment of its retained selection, including a receipt on the ranking day and subsequent rolling cutoffs. The receipt must match the original selected decision, run, configuration and exact original source; ranking, selection and recording timestamps must be ordered; and the delivery date must fall between approval and recording. Existing checks still verify the receipt's native audit, approval digests, actor, non-voided state, exact application-version transition and unchanged member/evidence/history information.

This is a read-only projection for ranking validation. It does not change the completed application, receipt, original inputs, scores, ranking or decision. Other programs' receipts retain their original cutoff/history checks. Changed information, a broken receipt or audit, a void, missing selection, stale versions and duplicate recording remain blocked. Actual assistance continues to be recorded only by the explicit authorized receipt action.

No schema change or live data repair was needed. The already recorded receipt and both live selections were preserved. The second live receipt was not automatically recorded.

## Verification

**15 focused tests are verified passing**, using fresh disposable native MySQL databases:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test ewaf.test_rolling_delivery.RollingDeliveryTests assistance.test_receipt_button ewaf.test_automatic_member_inputs.AutomaticMemberInputsTests.test_after_cutoff_delivery_preserves_record_snapshot_and_recalculation scripts.open_registration_receipt_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

Coverage includes sequential same-day receipt POSTs, unchanged selection and scoring history, advancing rolling cutoffs and final reranking, corruption and version checks, changed member information, voided receipts, other-program history, receipt permissions, duplicate/concurrent clicks, audit rollback and the existing fixed-cutoff delivery workflow. The browser test clicks both receipt buttons using fictional applicants and checks their recorded states, unchanged scores and reload behavior.

The final full run (`santolan-g12-tests-h1bclgie`) passed 14 of the 15 tests, including the browser journey. One reranking assertion incorrectly expected identical cutoff metadata between successive observations. It was corrected to verify unchanged scores/ranks and the fully preserved original calculation while allowing the new cutoff timestamp; that test then passed in `santolan-g12-tests-q73sj33u`. No implementation changes were made between those runs.

The test fixture explicitly synchronizes Django's imported datetime default callables with the patched service clock. The first attempt exposed that fixture mismatch. An additional older twelve-member reranking harness could not initialize because it still calls the retired verification signature with `birthdate`; it was not used as current acceptance. Its source was left unchanged. The new focused tests cover the relevant changed-source, audit and void safeguards directly.

Before/after inspection of the retained program used an SQL guard that rejected mutations. After the correction, the first receipt was recognized and the second applicant's `delivery_selection` validation passed. Receipt and decision records remained byte-for-byte equal in their serialized field values.

The local server on port 8013 was restarted with its database and uploads preserved. Post-restart release validation and Django/database checks passed. JavaScript syntax and `git diff --check` passed. Desktop and mobile browser screenshots were visually inspected; both synthetic receipts remained recorded after reload without JavaScript errors or page overflow.

Evidence:

- [Read-only diagnosis](diagnosis.json)
- [Read-only corrected validation](verification.json)
- [First recorded receipt](first-receipt.png)
- [Both receipts, desktop](both-receipts-1440.png)
- [Both receipts, mobile](both-receipts-390.png)
- [Browser results](results.json)
