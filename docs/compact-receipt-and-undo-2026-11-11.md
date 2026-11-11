# Compact receipt form and undo — November 11, 2026

Owner-authorized changes:

- Removed verification remarks from new receipt entry and the receipt-details presentation. Historical snapshot values remain stored. New claimant snapshots use schema version 3; removed fields are not synthesized.
- Both required confirmations now appear in the same receipt card with claimant information. Representative name, relationship and absence reason remain required for representative collection. The existing post-commit beneficiary email flow remains in place.
- In the assistance popup, the toolbar supplies the form title, eliminating the duplicate heading. Compact spacing and three desktop columns reduce form height without shrinking input targets below 44 pixels. Small screens and larger text can still scroll rather than clipping content.
- Receipt details open in a reusable native modal, including when the receipt list is already inside another modal. Escape/Close returns focus and content to the trigger. Without JavaScript, the original expandable details and normal POST form remain usable. Existing admin popup motion applies.
- A single **Undo receipt** button posts to the permission-checked `assistance:undo_receipt` endpoint. The endpoint reuses `void_release`, including current-version checks, transaction/row locks, retained actor/time/reason, audit rollback and EWAF assistance-history invalidation. The fixed reason identifies the action as an accidental/incorrect receipt correction. It does not delete the historical release.
- Undo excludes the release from successful-assistance counts, refreshes the receipt list and retains a Voided history entry. Existing review/approval requirements for replacement receipts remain in force. Missing confirmation, stale versions, cross-application targets, unauthorized requests and repeated submissions do not undo additional records. Previously sent email is not recalled by a void.

## Validation

The focused isolated MySQL run passed **23 tests**:

```powershell
.venv\Scripts\python.exe -B scripts/g12_test_runner.py test assistance.test_claimant_receipt.ClaimantReceiptTests assistance.test_receipt_email.RepresentativeReceiptEmailTests assistance.test_receipt_undo.ReceiptUndoTests --testrunner=scripts.email_test_runner.EmailTestRunner --noinput --verbosity 1
```

The test runner blocked external networking and used disposable databases and synthetic records. Receipt/email regressions and new undo tests covered retained history, exclusion from assistance counts, duplicate protection, permissions, POST-only access, CSRF, confirmation, current versions, target scope and audit rollback. No real receipt was recorded or voided, and no real email was sent. Test artifacts: temporary directory `santolan-g12-tests-yrxv7z45`.

Actual templates were rendered with synthetic data and database cursors blocked. Headless Chrome checks used intercepted fixture requests and local static files. They verified one receipt card with both checkboxes, absent verification remarks, no internal form scrolling at 1366×768, representative/personal collection switching, nested receipt popup opening, Escape/focus restoration, one undo POST with list refresh, recoverable server-error presentation and no horizontal page overflow at 390 and 320 pixels. The browser undo fixture supplies the final response body; actual HTTP redirect behavior is covered by Django tests. Final desktop screenshots were visually inspected. Fixture/screenshot directory: `santolan-compact-receipt-wjq77np4` in the system temporary folder.

JavaScript syntax and `git diff --check` passed. No schema migration was introduced. These checks do not establish inbox delivery or universal no-scroll behavior at every viewport/text size.
