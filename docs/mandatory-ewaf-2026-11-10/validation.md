# Mandatory EWAF, finite capacity and required disability selection

Date: November 10, 2026.

## Owner decision

The owner explicitly reversed the earlier non-EWAF/unlimited decision: all existing and future programs must use EWAF; remove the toggle; require positive beneficiary slots; require applicable disability types and provide Select all. This supersedes today's earlier non-EWAF automatic-selection and blank-disability-default requirements. The recorded milestone percentage and EWAF calculation policies are unchanged.

## Behavior

- Program setup has no EWAF toggle. Model defaults and the program save service use EWAF, including when an HTTP submission forges an opt-out. Model validation rejects a false EWAF setting.
- Saving a new or edited program requires a positive integer beneficiary slot count. There is no unlimited-capacity mode. Description, purpose and benefit remain optional.
- The disability checklist requires at least one applicable type. Select all disability types selects all enabled catalog choices; individual choices can still be cleared. Both client and server validate the requirement.
- Eligibility records Eligible with a pending selection decision. It does not calculate ranking or automatically select a member. Existing approved EWAF configuration, ranking, explicit human selection and finite capacity controls apply.
- Earlier immutable source records, reviews, actual receipts, issued references, published result revisions and calculations remain intact. A protected adoption audit identifies pre-existing selections/receipts and earlier all-type scopes; these witnesses preserve history without enabling new non-EWAF selections. Later edits continue to invalidate publication sources normally.
- An earlier approved empty disability relation keeps its original signed source and displays the included catalog as a locked selection. New blank selections fail. Earlier private drafts can explicitly save the displayed choices.
- Program capacity, public result copy, operational selection capacity and assistance/report summaries use the retained finite count. Historical selections still reserve places and appear as prior approvals.
- Administration changes shows “Program EWAF setting changed” with a simple explanation and the existing change filter.

## Retained local data

Applied the exact reviewed `programs.0010_mandatory_ewaf` data forward after stopping the retained web service and taking a verified full MySQL backup. This development database is model-synchronized and has no migration ledger; no blanket/historical migrations or fabricated migration records were applied. The migration's field alterations affect Django validation metadata, not physical MySQL columns.

- All 19 programs now use EWAF; five previously false settings were converted, retaining their existing counts. Seven adoption audits also preserve earlier empty/all-type scopes.
- All records across 133 tables were fingerprinted. Only five program flags/version counters and the seven new program audit rows changed. Original program fields other than those two columns and every previous audit were compared exactly.
- Publication currentness and every actual-receipt verification result were compared before and after. All 27 receipts from the converted programs still pass their original audit verification. No configuration, score, rank, application, decision, receipt, result revision, upload or certificate job was rewritten or created.
- One existing private draft, `programttt`, has no count. It is shown as Not set and requires a positive count before saving or publishing. No capacity was invented.
- Recovery backup and detailed private proof: `.local/mandatory-ewaf-20261110/backup-20261110-031035/`. Backup SHA-256: `1d9ef747439fd53c97ab475441a0f83aa19cee35a461bb6d73bd97e2d66ef80f`.
- Previously non-EWAF programs still need the normal approved EWAF configuration before future processing. Conversion did not fabricate approval, recalculate rankings or issue certificates.

## Verification

All tests used a fresh isolated native MySQL instance via `scripts/g12_test_runner.py` and `RegistrationIntakeTestRunner`; application data was never a test database.

- Ten mandatory-EWAF tests passed: forged opt-out, positive/required slots, required/explicit all-type selection, eligible versus selected separation, publication gate, preserved receipt/result/capacity/report/audit history, historical all-type scope, rollback on audit failure, historical migration model registry, and retained receipt-only/strict roster publication sources.
- Eighteen existing certificate delivery/concurrency tests and four recorded-EWAF result tests passed. No real email was sent.
- Two existing EWAF tests passed for exact calculations, separate human decisions, ties, finite slot capacity and concurrent selections.
- One browser test passed in light/dark themes at 1440 and 390 pixels: no toggle/unlimited label; blank and zero slot rejection; required disability group; Select all selects ten types; individual deselection; persisted EWAF draft; no horizontal overflow or JavaScript errors. Screenshots and `results.json` are beside this document.
- Final focused run: 13/13 passed in `santolan-g12-tests-zouixgp1`. Earlier regression run `santolan-g12-tests-pi83xczd` passed all 30 backend tests; its browser minimum-value issue was fixed and verified in the final run. There are 35 distinct passing checks across these runs.
- Django database checks, migration drift detection, JavaScript syntax and `git diff --check` passed. The retained local application was restarted.

The earlier non-EWAF acceptance scripts and historical validation documents describe the superseded behavior; they are not acceptance criteria for this decision. This was a focused workflow validation, not a claim that every historical milestone suite passes unchanged.
