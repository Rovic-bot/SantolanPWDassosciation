# Program disability screening — 26 October 2026

The owner requested an explicit explanation and blocked continuation when an applicant's disability type does not match the program's target disability types. This change applies to the program's existing configured restrictions after the applicant has verified their identity.

## Behavior

- Confirmed mismatches show **Application cannot proceed**, followed by: “You cannot proceed with this application because the disability types in your verified member record do not match this program's target disability types. Review the program requirements or contact the Association Help Desk if your record needs correction.”
- All retained verification paths use the same screening outcome. The legacy four-field path now checks before issuing a verification grant. The retained intake path preserves the specific qualification error after a complete identity match instead of replacing it with a generic identity error.
- A mismatch creates no application, reference or submission audit. Failed reverification clears a previous grant; direct form access and submission remain blocked.
- One matching active classification suffices. Programs with no configured disability restriction continue accepting verified members. Missing or inactive/unmapped classifications require clarification, rather than being labeled a confirmed mismatch. Failed identity checks remain generic and disclose no qualification result.
- Existing application references, requirements, identity evidence, scoring, selection and release rules are unchanged. No model or migration change is required.

## Validation

- **84 source tests passed**: `programs.test_application_workflow`, `programs.tests`, `programs.test_ui_cleanup`, and `program_intake.test_disability_screening`.
- The development-runtime run exercised those modules plus `program_intake.tests`: **121 of 122 passed initially**. The remaining test still expected the old generic mismatch message. Its assertion was updated to the owner's requested behavior; the focused rerun of that test and the three independent intake screening tests **passed all 4 tests**. No production code changed after the 122-test run.
- All Django tests used fresh isolated MySQL instances and `DB_TEST_NAME=test_g12_disposable`, through the existing G12 launcher and `RegistrationIntakeTestRunner`. Application data was not used as a test database.
- An initial broader source run exposed pre-existing intake EWAF fixtures missing required PR policy fields, plus two new fixtures attempting to deactivate a classification protected by published program terms. The new fixtures were corrected to use separate inactive classifications. Independent non-EWAF intake screening tests now validate this change without modifying the unrelated source EWAF fixtures. The complete source intake suite is not claimed to pass.
- A fresh development process on the supported validation port **8000** passed actual CSRF-protected HTTP checks for the explicit mismatch message, blocked direct application access, generic identity failures, and private cache headers. Existing fictional records were used for verification only. Application and program-audit counts remained unchanged.
- Django database/configuration checks, changed Python syntax checks, and `git diff --check` passed.
- Browser visual verification could not run: Chrome launch returned `EPERM`. No desktop/mobile screenshot acceptance is claimed.

## Local runtime

Scoped changes were applied to the retained `.local/dual-registration-20261024/runtime` copy, preserving its additional intake guards and unrelated EWAF changes. Original copies remain under `.local/disability-target-20261026/before/`.

Windows denied stopping the already-running port-8003 Python process, so the automatic restart did not complete. Run **Restart System.cmd** manually to load the Python changes on the normal development site. HTTP verification used the separate fresh port-8000 validation process.

Evidence: `source-tests.log`, `runtime-test-summary.txt`, `runtime-focused-tests.log`, and `http-checks.json` in this directory. Detailed failed-run logs remain in the private temporary test-artifact directories.
