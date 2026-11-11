# Association classification mapping — October 29, 2026

## Reported failure and correction

The owner reported that a current member could not apply for a program and
suspected a mismatch between the Contact number and Mobile nos. fields. Both
labels use `contact_number`. The current member name and phone were usable for
identity verification; the program was published and accepting applications.

The failure was the classification link: the Association declaration used
`Physical / Orthopedic`, while the controlled catalog used
`Physical Disability (Orthopedic)`. Registration approval previously looked up
only identical database names, leaving the member without a classification ID.
Program screening correctly treated that missing link as needing clarification.

The ten exact Association labels now share one explicit mapping with program
choices. Registration approval and explicit member disability edits resolve
those labels to existing active catalog IDs. The declared text remains intact;
unknown text is not guessed or normalized into a different classification.

Added `members.services.repair_disability_link` for a narrowly scoped correction
of an active approved member whose exact Association declaration has no existing
classification link. It requires staff permission, the current version, a reason,
an unchanged matching declaration and an active catalog entry. It uses the
existing transaction, source-writer and profile-audit controls. Existing links
cannot be overwritten by this repair.

Applied that correction only to the owner-reported member. An audit event records
the missing link and restored catalog ID. All member columns except version and
update time were compared before/after and preserved, as was the original
membership application. No contact number, name, declaration or application was
changed or invented. No batch reclassification was performed.

The current program verification page now labels the phone field **Mobile number**
and explains that it uses the current member record.

## Validation

- **29 tests passed** across `members.test_disability_mapping`,
  `members.test_registration_edit`, `membership.test_onsite_registration_alignment`
  and `programs.test_ui_cleanup.CatalogUITests`.
- After extending two assertions, **both focused reruns passed**, including
  verification POST → application page using the current mobile number, and an
  explicit member disability edit creating the correct catalog link.
- Coverage includes all ten labels, unknown/inactive categories, original-record
  preservation, permissions, stale versions, required reason, conflicting or
  existing classifications, and rollback when audit recording fails. Wrong names
  and phone numbers retain the generic verification failure.
- Tests used `scripts/g12_test_runner.py` and
  `scripts.registration_intake_test_runner.RegistrationIntakeTestRunner`, with
  fresh disposable MySQL and synthetic media. Temporary artifacts:
  `santolan-g12-tests-2qnrz0b1` and `santolan-g12-tests-tv4p3vqy`.
- The reported member's current-record verification returned `passed`, and the
  resulting in-memory grant validated. No grant was placed in a browser session
  and no program application was submitted.
- Django/database checks, migration-drift checks and `git diff --check` passed.
  No schema migration was needed. The full project suite was not run.
- Refreshed only the identity-verified development web process. An actual HTTP
  GET returned 200 and the updated mobile-number guidance. MySQL stayed running.

Existing program qualifications, secure identity matching, eligibility, EWAF,
selection and release controls remain unchanged.
