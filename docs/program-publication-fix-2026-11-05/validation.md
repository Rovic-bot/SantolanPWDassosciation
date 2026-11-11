# Simplified program setup: publication repair — November 5, 2026

## Problem and change

Removing selection-method and identity-evidence text inputs from the builder left new drafts with empty values, while publication still required them. An otherwise complete draft could not be approved and published.

The simplified setup now records descriptions of the existing application controls when those descriptions are missing: manual calendar-photo review, Help Desk assistance, eligibility review, approved EWAF support when applicable, and explicit Admin selection within capacity. These descriptions do not create a scoring policy, tie procedure, evidence exception, recency threshold, or eligibility rule. The public application form still requires the existing calendar photo.

The program detail page displays the effective guidance before publication. Existing affected drafts receive missing guidance only during an explicit, audited publication transaction. GET requests preview it without saving. New simplified drafts record it in their normal creation/update audit and remain private until publication. Retained custom text takes precedence; posted values for the removed fields remain ignored.

The repair never fills previously published, authorized, externally approved, or application-bearing records. Existing terms protection, explicit authorization, positive capacity, external approval where enabled, approved EWAF prerequisites, permissions, CSRF, stale versions, and audit rollback remain enforced. Guidance is persisted before EWAF binds its source snapshot, in the same transaction. No migration or bulk data rewrite was performed.

## Verification

56 targeted Django tests passed on a fresh disposable loopback MySQL database. Coverage includes:

- Simplified builder save, review, explicit publication, public guidance and application availability.
- Existing empty/whitespace drafts, read-only previews, retained custom text and correct audit changes.
- Protected historical/authorized terms, external approvals and programs with existing applications.
- Missing capacity, missing external approval, missing EWAF approval, stale/concurrent requests, permissions and CSRF.
- New and existing EWAF drafts binding guidance before their approved intake configuration; shared-policy publication.
- Publication audit failure rolling back guidance, authorization and publication together.
- Public availability and the four direct legacy-policy authorization service/view tests.

Run command:

```powershell
.venv\Scripts\python.exe -B scripts/g12_test_runner.py test programs.test_one_click_publication programs.test_creation_builder programs.test_detail_workspace programs.test_public_availability programs.test_policy_authorization.PolicyAuthorizationTests.test_published_legacy_program_can_be_authorized_without_visibility_change programs.test_policy_authorization.PolicyAuthorizationTests.test_missing_policy_and_confirmation_do_not_authorize programs.test_policy_authorization.PolicyAuthorizationTests.test_authorization_requires_permission_current_version_and_single_use programs.test_policy_authorization.PolicyAuthorizationTests.test_audit_failure_rolls_back_authorization --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

Artifacts: `santolan-g12-tests-tp1p9twf`. This uses a model-synchronized disposable schema; it is not historical migration validation. Django system/database checks and `git diff --check` passed.

The initial broader 55-test run passed 54 tests and exposed one unrelated outdated expectation: `PolicyAuthorizationTests.test_announcement_warning_provides_the_recovery_path` expects an authorization warning/link that the previously redesigned announcement dialog no longer displays. The announcement template and that test were not changed in this repair. The final focused run excludes that announcement-copy test and includes two additional publication regressions.

The local process was restarted. Brave displayed the affected existing draft as **Ready for final approval**, with the old missing-field error absent and the **Approve and publish** button available. A read-only application check confirmed 7 slots and no EWAF publication prerequisite error. The draft remains unpublished; real business records were not altered during verification. All publication writes used synthetic test records.

Previous versions of edited files are under `.local/program-publication-fix-20261105/before/`. All pre-existing working changes were retained.
