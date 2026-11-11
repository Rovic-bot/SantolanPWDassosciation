# Incremental certificates and publication before receipt

Validated November 8, 2026, against the owner's explicit request in this session.

## Authorized behavior

- Publishing three selected members queues three certificate emails. After selecting a fourth member and publishing again, only that fourth member receives a new certificate email. Previous successful deliveries are retained.
- Recording actual receipt requires the selected member's exact application reference to appear as Selected in an explicitly published Announcements result revision.
- Selecting another member does not revoke publication for previously published members. The new member waits until the next publication.
- Eligibility, ranking, human selection, publication, and actual receipt remain separate actions. Publication alone does not mark assistance as received. Receipt does not depend on successful email delivery.

## Implementation

`announcements/certificate_delivery.py` retains the existing unique certificate job per application and checks all saved delivery evidence: sent state, acceptance timestamp, and successful attempt history. Publication reuses existing jobs and attachments, skips accepted messages, and can requeue safely failed or previously blocked messages. Uncertain Gmail sends are never retried automatically. Recipient and attachment remain fixed after a send attempt. New selections get their own jobs and message identifiers.

`announcements/release_publication.py` validates the published announcement, its schema-2 selection snapshot, and its native publication audit. Exact full references establish which selected members were published. A newly changed selection pool does not erase earlier publication permission. A draft, withdrawn, future, unrelated, or legacy masked-only snapshot cannot authorize a receipt; those selections must be explicitly published again.

`assistance/services.py` enforces publication in the shared receipt writer, including direct requests, and records the announcement, revision, source digest, publication timestamp, and publication audit identifier in the receipt's approval snapshot. It locks the announcement while recording to serialize concurrent withdrawal. Existing eligibility, selection, capacity, audit rollback, and duplicate-receipt controls remain in place. Historical receipts are not rewritten.

The assistance table disables the receipt button for selected members awaiting publication and explains the next action below the button. The certificate status panel explains the incremental delivery behavior.

No model changes or migrations are required.

## Verification

Tests ran on fresh, disposable native MySQL databases through `scripts/g12_test_runner.py` with `scripts.registration_intake_test_runner.RegistrationIntakeTestRunner`. Certificate transport used the in-memory email backend; no real email was sent.

- `announcements/test_incremental_certificates.py`: three initial emails, fourth-only email after republication, repeated publication and manual retry without duplicates, safe retry preserving the original PDF, uncertain Gmail delivery without automatic retry, and retained success overriding stale queue state.
- `assistance/test_publication_gate.py`: disabled unpublished UI, rejected POST and direct writer, old published selection remaining usable after a new selection, new member waiting for republication, withdrawn/future/mismatched snapshots, publication audit requirement, receipt audit rollback, and concurrent withdrawal waiting for receipt commit.
- Existing certificate, result publication, assistance, receipt-button, operational delivery, and rolling-delivery checks were exercised. Older fixtures now explicitly publish selections before recording receipts. Rolling-delivery fixture time is fixed early in the local day to avoid an evening run crossing midnight.
- The initial 125-test batch had seven fixture/old-expectation failures, which were corrected. A 20-test follow-up passed the new publication, concurrency, rolling-delivery, and browser cases and identified two remaining old assertions. The final 29-test run passed both corrected assertions plus certificate suites. Imported test fixture classes were then aliased to avoid redundant discovery; the test behaviors were unchanged.
- The final standalone publication/receipt browser test passed after the layout adjustment. At 1440px and 390px, the published applicant could record receipt, the newly selected applicant remained disabled, and after republication the new applicant could record receipt. Each saved receipt referenced the appropriate publication revision. The mobile table scrolls horizontally and the explanatory message remains visible below the button. Screenshots were visually inspected.
- `scripts/current_development.py check`: passed. `git -c core.safecrlf=false diff --check`: passed.

Repeat the focused new cases with:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test announcements.test_incremental_certificates assistance.test_publication_gate scripts.publication_receipt_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

## Retained development data

A read-only SQL guard verified the reported program before and after the local app restart. Its three certificate records each had one successful attempt; all three used the same recipient address. Multiple messages in that shared inbox may therefore represent different members' certificates. Duplicate sending was not reproduced from the saved history.

The three accepted certificates are not retryable. The existing two actual receipts remain intact, and the published third member remains able to record receipt. No real selections, rankings, publications, receipts, or emails were created or altered during this change. The local app was restarted on port 8013 with its existing database and uploads.

Evidence: [read-only checks](verification.json), [browser checks](browser-results.json), [desktop](waiting-for-publication-1440.png), [mobile](waiting-for-publication-390.png), [published receipts](published-and-recorded.png). Screenshots contain fictional disposable-test data only.
