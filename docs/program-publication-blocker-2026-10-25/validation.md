# Program publication blocker diagnosis — 25 October 2026

The owner reported that publication fails with “Weights and data sources are approved. Scoring is pending approved calculation rules.”

## Confirmed cause

A read-only transaction against the identified fictional development database found four locked Configuration Vault revisions, all with `configuration_scope=weights_and_sources`. None contains numerical scoring definitions. Both EWAF-dependent drafts have program policy authorization and inherited source/weight configurations; program authorization is not their missing step.

The one-click vault approval intentionally preserves existing complete policies, but starts with weights and confirmed sources when none exists. It cannot create the missing numerical policy. `prepare_publication()` correctly rejects these incomplete configurations. Reapproving weights creates another source/weight revision and does not resolve this dependency.

The separate revised dataset engine remains a private demonstration. Its supplied implementation contract expressly excludes official activation and invented institutional policy. Its example assumptions do not authorize operational SI encodings, normalization, periods, evidence acceptance, or tie handling.

## Scoped correction

The program readiness check previously treated any inherited draft configuration as centrally approved and ready for publication, even when it contained only weights and sources. It now reports the same scoring blocker before the publication action. Complete inherited configurations retain their existing publication behavior.

The vault approval response and approved-version panel now distinguish approved weights from unfinished scoring. Messages explain that repeating weight approval will not complete the rules. The panel identifies the missing policy categories. The original one-click approval controls remain intact.

No scoring values, directions, encodings, bounds, periods, thresholds or tie procedures were supplied or authorized. No program was published or changed, and no score or member record was written to the populated development database. Operational publication remains blocked until the required scoring policy is completed and approved.

## Validation

- **39 tests passed**, covering the vault and program application workflow in a disposable native MySQL database. Added assertions verify pre-publication warning, absence of the incorrect ready message, accurate one-click feedback, complete-policy publication, and blocked publication preserving the draft version/configuration/audit counts.
- Command: `.venv/Scripts/python.exe -B .local/dual-registration-20261024/run_tests.py test ewaf.test_vault.VaultTests programs.test_application_workflow --testrunner scripts.referral_test_runner.ReferralTestRunner --noinput --verbosity 1`.
- Test evidence: `.local/dual-registration-20261024/temp/santolan-g12-tests-i85mdj_l/django.log`; 24.584 seconds, no failures.
- Python syntax, scoped whitespace, `git diff --check`, and the identified runtime's `manage.py check --database default` passed. No model or migration changes.
- Six source files were synchronized to the existing runtime, preserving its additional program-intake validation hooks. Backups and hashes: `.local/program-publication-blocker-20261025/`.
- Windows denied stopping the verified development Python process (`Access is denied`). Run `Restart System.cmd` manually to load the corrected messages. Restarting does not supply the missing scoring policy or unblock publication.
- Browser visual verification was not performed.
