# External PDAO approval — October 29, 2026

## Owner-confirmed workflow

The owner confirmed: “allow publication and applications, pdao approval is an
external process that they will do outside the system.” This supersedes the
in-system PDAO reconciliation prerequisite for the active local workflow.
Publication must not invent a government approval record.

The main development settings inherited mandatory PDAO enforcement from the
retained demo settings. That caused Publish to fail with “The program requires
an explicitly reconciled approval covering its current terms,” even though the
draft had its required details and approved EWAF weights.

`config/current_development_settings.py` now explicitly disables that gate.
The normal settings already default to disabled. The program review page hides
the PDAO approval panel and prerequisite when enforcement is disabled. Historical
approval records and the separately configurable enforcement mode remain intact.

Publish still checks permissions, current version, required program information
and approved EWAF configuration. Applications still check the schedule, verified
membership, program qualifications and required evidence. Scoring, human
selection, releases and their audit controls are unchanged.

## Validation

- **45 tests passed** in fresh disposable MySQL with synthetic media:
  `programs.test_one_click_publication`,
  `programs.test_approved_terms.DraftApprovedTermsTests`,
  `programs.test_approved_terms.ApprovedTermsConcurrencyTests`,
  `ewaf.test_intake_policy`, and `ewaf.test_vault`.
- Launcher: `scripts/g12_test_runner.py`, with
  `scripts.registration_intake_test_runner.RegistrationIntakeTestRunner`.
  Artifacts: temporary directory `santolan-g12-tests-s7n274dz`.
- Publication assertions cover both non-EWAF and approved-weights programs
  accepting applications without creating PDAO approval records. The intake
  suite covers actual synthetic submissions, schedule limits, duplicate handling
  and retained scoring/selection restrictions. Permission, CSRF, stale submission,
  audit rollback and concurrent publication checks passed.
- A read-only probe of the reported draft returned HTTP 200, confirmed that the
  PDAO gate was disabled and no EWAF publication problem remained, and verified
  that the Publish button was present without PDAO prerequisites. SQL writes
  were blocked. Local rendered evidence:
  `.local/external-pdao-20261029/program-review.html`.
- Django/database checks, migration-drift checks and `git diff --check` passed.
  No migration was required. The full project suite was not run on this final
  change; no browser screenshot pass is claimed.

The identity-verified development web process on port 8013 was refreshed; MySQL
remained running. The reported program remains a draft for the owner to publish.
No program, application, approval or business audit record was changed by the
read-only checks. Earlier disability-choice changes and unrelated files remain.
