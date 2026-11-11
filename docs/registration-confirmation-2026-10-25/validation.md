# Registration confirmation and onsite prefill — 2026-10-25

The owner requested a reference-number confirmation with barangay verification instructions after public online registration, replacing the final “Form access closed” message. They also requested that Admin load the submitted information into onsite registration using that reference.

## Result

Both the immediate receipt and the final Done screen show “Registration submitted,” the issued AMR reference, an instruction to save it, and directions to visit the Barangay Santolan PWD Association Help Desk with the required documents. The instructions explain that Admin uses the reference to load the submitted information and that verification and approval remain pending. Receipt print controls appear before the full submitted-data summary; the previously implemented Word-template print layout is preserved.

Done still revokes private-form access. The service returns only the issued reference after validating ownership and committing the existing revocation/audit transaction. The session retains that reference for repeated Done requests, with no applicant fields or documents. Posted references/context IDs cannot select a record. Starting a new submission clears the previous confirmation. An unsubmitted or unrelated session receives neutral guidance without a success claim or reference.

The existing authenticated Onsite Member Registration → Already applied online? → Load online application flow already populated the retained pending form. Its destination now explicitly says “Onsite Member Registration” and “Online application loaded,” and tells Admin to verify the filled details. The existing correction, onsite findings and approval steps remain separate. Retrieval creates no duplicate registration or Member and does not mark declarations verified.

## Verification

- **91 focused tests passed** in a new disposable MySQL instance using the existing isolated launcher and `RegistrationHandoffTestRunner`: registration Finish, intake, PDF field contract, prefill and reference retrieval. Django system checks passed.
- Added checks cover the issued reference and instructions before/after Done, repeated confirmation without private data, unrelated-browser denial, clearing previous confirmation, audit rollback, and no false success for an unsubmitted form.
- An integrated test submits the current Association form, finishes public form access, enters the displayed reference through Admin lookup, checks every submitted field in the populated form, verifies the audited same-record load, and confirms no duplicate application or Member.
- Six synthetic applicant/staff print samples still render with digital assessment fields excluded. Updated browser harnesses pass JavaScript syntax checks. Browser execution and visual rendering were not rerun because browser launching is unavailable in this environment.
- Whitespace checks passed. No model, migration, permission assignment, reference format, scoring or membership-decision rule changed.

## Local runtime

Seven scoped runtime files were updated only after matching their pre-change contents against repository backups. Backups, source hashes and the runtime manifest are under ignored `.local/registration-confirmation-20261025/`.

The restart script identified the existing development instance on port 8003, but Windows denied stopping its process. Run `Restart System.cmd` to load the updated Python and templates. No application-data mutation, migration, commit, push or deployment was performed.
