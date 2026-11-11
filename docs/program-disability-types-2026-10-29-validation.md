# Program disability choices — October 29, 2026

The owner requested that Create program → Applicable Disability Types match the
ten labels and order in the supplied Association registration screenshot.
`ProgramDisabilityChoiceField` now displays those labels in that order on the
shared create/edit form. Optional multiple selection remains available.

The display labels retain the existing controlled classification IDs. No member
classification, saved program restriction, eligibility logic, EWAF rule or
historical reference was changed. No schema migration is needed.

## Local catalog

The retained development database at port 8013 contained only Visual Disability
from the ten-category catalog. Added the other nine existing controlled catalog
names using the model writer, with a Django Admin addition audit for each. The
previous rows were backed up and verified unchanged. Local evidence is under
`.local/program-disability-labels-20261029/` (`catalog-before.json` and
`catalog-update.json`). Normal migrated installations already receive these
categories from `members.0005_controlled_disability_catalog`.

Only the identity-verified development web process was restarted; its MySQL
process remained running. No existing program or member was edited.

## Verification

- **47 tests passed**: `programs.test_ui_cleanup.CatalogUITests` and
  `programs.tests`, using `scripts/g12_test_runner.py` with
  `scripts.registration_intake_test_runner.RegistrationIntakeTestRunner`.
  The run used fresh disposable MySQL, `test_g12_disposable`, and synthetic media.
  Test artifacts: temporary directory `santolan-g12-tests-w1eyx224`.
- Read-only rendering of the actual Create program view returned HTTP 200 with
  all ten labels in the requested order. Each choice round-tripped to its
  original database ID. SQL mutations were blocked during this check.
- Headless Chrome checked the rendered page: ten checkboxes, simultaneous
  selections, and no horizontal overflow at 390px. No program was submitted.
  The [field screenshot](program-disability-types-2026-10-29.png) was visually
  inspected; its checked values are browser-only examples.
- Django database checks and migration-drift checks passed with the retained
  development settings. The initial default-settings check could not connect
  to its inactive database; validation then used the active development settings.
- `git diff --check` passed. The full project suite was not run.
