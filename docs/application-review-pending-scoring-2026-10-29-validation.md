# Application review with pending scoring rules — October 29, 2026

The reported application-review page raised an unhandled `ValidationError` from
`latest_configuration()` in `programs/applicant_information.py`. The program's
approved weights permit intake, but its scoring rules are still pending. The
page requested a locked scoring configuration outside its existing validation
handler, so it crashed before showing the member's saved information.

The configuration lookup now runs inside the same validation handler as the
reviewed-input lookup. When no usable scoring configuration is available, the
page retains registered values and shows **Current information needs review**.
It does not mark those values verified or unlock calculations. Valid reviewed
inputs still use the existing approved-configuration and current-evidence checks.
Only `ValidationError` is handled; unexpected database/programming errors are
not suppressed.

## Verification

- A read-only invocation of the exact reported route with the existing
  authorized administrator returned HTTP 200, rendered saved information and
  eligibility-review controls, and showed the pending-review message. All SQL
  mutations were blocked during that check.
- Added a regression in `ewaf.test_intake_policy` that submits a synthetic
  application under approved weights with dataset features enabled, opens its
  review page, and verifies the pending display, unchanged configuration and
  continued scoring restrictions.
- Ran `ewaf.test_intake_policy` and `ewaf.test_current_weights` using
  `scripts/g12_test_runner.py` and
  `scripts.registration_intake_test_runner.RegistrationIntakeTestRunner`.
  **15 of 16 tests passed**, including the new regression and existing reviewed
  applicant-information/privacy tests. Browser checks in that suite also passed.
  The separate delivery/publication test
  `test_publish_after_confirmed_delivery_preserves_pool_and_release` failed
  because its release date preceded its approval. Its failure originates in
  `assistance.services.record_release`, outside the changed display code; no
  delivery rule or unrelated test was changed. The full project suite was not run.
- Disposable MySQL/synthetic-media artifacts:
  temporary directory `santolan-g12-tests-3t0778_b`.
- Django/database checks, migration-drift checks and `git diff --check` passed.
  No schema migration was needed.

The identity-verified development web process was refreshed on port 8013; MySQL
remained running. No working application, member, evidence, eligibility, score,
selection or audit record was changed.
