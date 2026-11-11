# Simple onsite registration decision — 2026-10-25

The owner explicitly requested: enter the applicant's reference → load the submitted fields → edit corrections → approve or decline. They removed the separate Processing review, required reason, onsite findings and manual-verification steps from this reference-based workflow. In the follow-up, the owner chose **Admin enters the assigned member number** rather than automatic number assignment.

## Delivered behavior

The AMR lookup opens the existing Onsite Member Registration page. Staff with decision and correction permission can edit the retained applicant fields directly. The page has an assigned member-number field and two buttons: **Approve membership** and **Decline registration**. The member number is required for approval; the registration reference is not accepted as that number. Declining needs no member number or reason.

One transactional service saves any corrections and the final decision. Approval creates one official Member, using the corrected profile and assigned number. Declining creates none. Exact retries return the same result; changed retries, conflicting final decisions, stale versions and duplicate member numbers fail without partial changes. Previously linked but still-pending registrations can complete through the same simplified screen. Finalized records cannot be edited or reopened through it.

Original/corrected revisions, private attachments, AMR references and existing history remain retained. History records the responsible administrator, time and automatic correction/decision descriptions without asking for a reason. Existing manual verification, if superseded by corrected applicant information, is retained in the new decision's private history rather than represented as a successful verification of the changed information. The simplified workflow does not invent PRPWD results, checklist findings, assessments or scores.

The complete registration profile, household income, household-member count and employment fields are copied to approved Members. Family size is not converted into dependents, household income is not converted into individual income, and a PWD ID is not substituted for the assigned Association member number. Existing public receipt/reference behavior and Word-template printing remain unchanged.

This is a new, explicitly authorized decision path for reference-based pending Association registrations. Historical handoff/manual-verification services and their audit history remain available to existing integrations, but their forms are removed from this screen. The request does not alter unrelated Members, program applications, EWAF mathematics, ranking, publication or release histories.

## Validation

**138 focused tests passed** in fresh isolated MySQL with `.env` disabled and separate synthetic media. The final run covered:

- The new decision workflow, including editable fields, no old review prompts, assigned-number validation, approval/decline outcomes, correction history, private attachment retention, permissions, CSRF, stale edits, unsupported fields, duplicate numbers, exact retries, rollback and concurrent approvals.
- Earlier linked registrations, retaining their original acceptance and verification history while applying the new decision.
- The existing protected membership source boundary, including one native audit and zero affected program scope, unchanged program generations, rejected fabricated scope and rollback after a late audit failure.
- Existing intake, receipt/Finish, PDF registration, prefill, reference lookup, historical handoff and native membership-writer regression tests.

Command:

```powershell
.venv/Scripts/python.exe -B .local/dual-registration-20261024/run_tests.py test membership.test_registration_decisions membership.test_registration_finish membership.test_registration_intake membership.test_pdf_registration membership.test_registration_prefill membership.test_reference_retrieval membership.test_registration_handoff ewaf.test_membership_writers --testrunner scripts.registration_handoff_test_runner.RegistrationHandoffTestRunner --noinput --verbosity 1
```

The first 122-test run found one obsolete UI-label assertion. Its labels were updated to the newly requested buttons/member link; the underlying legacy-verification and approval assertions remain. The final run passed all 138 tests in 23.495 seconds. No browser rendering or screenshot pass is claimed; browser launching remains unavailable in this environment. Older approval-browser harnesses describe the previous multi-step workflow and are not acceptance for this change.

The identified development runtime passes `check --database default` and `makemigrations --check --dry-run` with **no changes detected**. No model or migration file was changed and no migration was applied.

## Runtime and preservation

Five code/template files were synchronized to `.local/dual-registration-20261024/runtime/` only after comparing existing files with pre-change baselines. Backups and the file manifest are retained under ignored `.local/simple-registration-20261025/`. Existing unfinished work was preserved. No member or decision was added to application data; all workflow mutations used disposable test databases.

The restart script verified the development server on port 8003, but Windows denied stopping its process. Run `Restart System.cmd` to load the changes. No commit, push or deployment was performed.
