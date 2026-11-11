# Representative receipt notification — November 11, 2026

The owner requested removal of the representative authorization/guardianship basis field and the separate representative identity/authority checkboxes. They also requested an email to the beneficiary after Confirm and record receipt records collection by an authorized representative.

## Implemented behavior

- The representative form retains name, relationship and the beneficiary's absence reason. Beneficiary-record identity verification and confirmation of actual handover remain required. New claimant snapshots use schema version 2 and do not invent the removed attestations. Earlier saved evidence remains readable.
- `record_actual_receipt` queues a representative notification inside the receipt transaction after the existing release writer completes its audit checks. Delivery starts only after that outer transaction commits. Personally collected assistance does not trigger this representative-specific notification.
- `assistance/receipt_email.py` retains append-only queued/sending/sent/failed/uncertain/skipped events in the existing private AssistanceLog history, scoped to the release. No database migration is needed. Emails identify the program, assistance, representative and receipt date; absence reasons, verification remarks and identity evidence are excluded.
- Delivery uses the existing Association email connection and shared SMTP delivery helper. Missing/invalid recipient information and transport failures do not erase an already committed receipt. SMTP acceptance is distinguished from an uncertain outcome and from the in-memory test backend; inbox delivery is not guaranteed by an SMTP acceptance result.
- Receipt rows display delivery status and an authorized POST/CSRF-protected Retry email action when applicable. Retrying does not create another receipt or send automatically after an uncertain outcome. The UI cautions that retrying an unconfirmed attempt can produce a duplicate email. Voided receipts cannot be retried.
- Existing eligibility, publication, human selection, release authorization, immutable receipt history and EWAF assistance-history invalidation continue through their existing services.

## Validation

The focused command passed **19 tests**:

```powershell
.venv\Scripts\python.exe -B scripts/g12_test_runner.py test assistance.test_claimant_receipt.ClaimantReceiptTests assistance.test_receipt_email.RepresentativeReceiptEmailTests --testrunner=scripts.email_test_runner.EmailTestRunner --noinput --verbosity 1
```

The launcher used disposable native MySQL fixtures; the email test runner blocked non-loopback networking and used Django's in-memory email backend. Coverage included existing receipt validation/selection safeguards, the simplified fields, post-commit delivery, one queued notification, content privacy, failure retention, retry permissions and CSRF, unknown delivery outcomes, missing recipient handling, audit rollback and void suppression. No application records were changed and no real emails were sent. Test artifacts were retained in temporary directory `santolan-g12-tests-l5ygpc4j`.

Python syntax and `git diff --check` passed. Real Gmail authentication and beneficiary inbox delivery were not exercised by this validation; the Association must have a connected sender before live delivery can succeed.

## Follow-up: previously loaded form

The owner's follow-up screenshot showed the removed controls alongside the new email explanation. Its capture preceded the verified local web-process restart. The local development launcher disables automatic Python reload, so an already loaded form is not evidence of the restarted process's current form definition.

A fresh `ReceiptForm` import was checked with database access blocked: representative name, relationship and absence reason are the only representative fields, and the form validates without the removed controls. Two focused disposable-database tests also passed: the existing rendered-form/permissions/CSRF regression and the new `test_confirm_receipt_http_flow_sends_after_commit_without_removed_fields`. The latter exercises the actual receipt POST endpoint, its redirect, post-commit notification, displayed test-delivery status and duplicate-submission protection. Artifacts: temporary directory `santolan-g12-tests-pds38a93`. External networking remained blocked and no real emails or application-data changes occurred.

No further production-code change was needed for this follow-up. A receipt popup loaded before the restart must be closed and reopened after refreshing the page to display the current form.
