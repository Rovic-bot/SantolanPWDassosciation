# Online registration in the populated development workspace — 2026-10-24

The owner's requested local integration is running at **http://127.0.0.1:8000/**. This is the populated fictional development workspace with online Association registration, reference retrieval and the existing membership approval writer. It replaces the small registration-only dataset previously served at that address. It is not real-data activation or institutional acceptance. The accepted milestone remains **70%**; the broader phase statuses remain **Partial**.

## Where to use it

- Public Portal → **Membership → Start online membership registration**: `/membership/register/` → `/membership/registration/apply/`.
- Submit fictional applicant information to receive an AMR reference, same-session form/receipt access and instructions to visit the office/Help Desk. Submission does not create an official Member.
- Full Admin login: `/accounts/login/`, using the existing **lab_admin** account. Its password was retained, not reset. The original ignored `.local/main-testing/login.json` and the new ignored runtime access file retain its local credentials; no credentials are included here.
- **Members → Onsite registration → Load online application** retrieves the submitted fields by AMR reference. **Members → Membership reviews → Pending Association registrations** monitors submissions and opens their onsite review and authorized membership-decision workflow.
- Use **Start System.cmd** for later sessions. It calls `scripts/run-current-development.ps1`, now targeting `.local/full-system-registration-20261024/start.py`. It resumes saved fictional records, checks the instance identity, runs the unchanged migration guard and refuses an unexpected occupied port. It does not migrate, reset, seed or fall back to `.env`.

## Data and environment preservation

The previous full workspace was identified from its actual private manifest, server UUID and datadir: `santolan_lab_20261021_162439_1cae` on the separate loopback MySQL service at port 3308. It contained 1,800 Members, 1,840 legacy membership applications, 47 programs, 4,776 program applications, 807 assistance releases and 20 operational calculation runs. The frozen runtime also contained existing fictional program-intake/EWAF integration hooks; those were preserved byte-for-byte.

A consistent SQL backup and private-media copy were verified before any extension. All original rows were restored exactly into **santolan_lab_registration_20261024**, with its own database-scoped account and private-media directory on that existing fictional MySQL instance. The 13,788 original media files match their hashes. The original full database, original runtime and original private media remain unchanged. The small registration demo database is retained too; only its verified port-8000 web process was stopped. The temporary port-8003 validation server was stopped after the switch.

The browser journey then added one explicitly fictional pending registration, linked legacy application and approved Member. Current totals are **1,801 Members**, 1,841 legacy membership applications, 47 programs, 4,776 program applications, 807 assistance releases and 20 operational runs. All original business/calculation rows remain present and unchanged. Expected changes to pre-existing rows were restricted to `auth_user.last_login` and the existing login attempt-window timestamps/counters. The initial preservation check flagged the latter; a separate column-level review confirmed these authentication-only changes. Both evidence records were retained.

No connection to the normal `santolan_pwd` working database on port 3307 was made for this task. Its credentials, records and schema were not changed. No production deployment, commit, merge or push occurred.

## Code integration and exact changed files

The current checkout remains `feature/events` at `776cac5d1119410717c6a31c044ea85f4d619941`; pre-existing uncommitted work remains intact. The main repository application implementation already contained the registration feature, so it was reused rather than recreated.

The root launcher change is **scripts/run-current-development.ps1**: select the full populated runtime instead of the small demo. `Start System.cmd` continues invoking that launcher without another change in this task. This report, its evidence and `docs/added-targets-phase1-2026-10-23/progress-and-decisions.md` record the new result.

The retained runtime copy is `.local/full-system-registration-20261024/runtime/`. Its existing-file changes are listed in `preservation-reviewed.json`:

| Runtime paths | Purpose |
|---|---|
| `membership/models.py`, `services.py`, `views.py`, `urls.py`; existing `registration_*.py` modules copied from the root | Reuse the implemented pending records, references, private receipt, atomic retries, onsite findings, reference retrieval and native membership handoff. |
| `documents/services.py`, `documents/views.py`, `members/views.py`, `main_testing/review_views.py` | Enforce linked-registration document permissions on the original full workspace's alternate document routes as well as the ordinary routes. Preserve its existing review behavior. |
| `templates/membership/encode.html`, `guidelines.html`, `list.html`, `templates/membership/registration/*`, `static/css/registration.css`, `static/js/registration.js` | Reuse the public/onsite form layout, reference lookup, inbox, receipt and review UI. |
| `main_testing/templates/main_testing/explore.html` | Point resume instructions to Start System, avoiding the older rebuild/restore command that would select a different runtime. |
| New local `config/full_registration_settings.py`, `main_testing/registration_boundary.py` | Explicit fictional-only policy and visible environment marker; separate session/CSRF cookie names. Ordinary settings stay unchanged. |
| Existing registration tests and exact-migration runner helpers copied into the runtime | Execute tests against the combined code, including the previously installed integration hooks. No existing EWAF assertion was edited. |

`clone-verification.json` contains the exact copied-file list. `before.json` preserves the original runtime hashes; `preservation-reviewed.json` lists changes against them. Ignored local preparation, startup, browser and verification scripts/manifests are retained beside the runtime. Do not run the older `main_testing.py rebuild/restore/start` installer over this runtime: it manages a different frozen snapshot and could discard this integration. Future updates must preserve both the root protected baseline and this workspace's pre-existing integration hooks.

## Migrations

Only these already-reviewed additive files were copied and applied, in order, to the new fictional clone:

1. `membership.0006_association_pending_intake` — SHA-256 `fc897f9ee2f2f1b2433cccc7bf7f6bd531c199363f0cfa5fe2bdcfb9583b224d`.
2. `membership.0007_registration_membership_handoff` — SHA-256 `8d400ddcc416c0081518dd45a5cbc2097e7b36103d391260174347c0e4c2ddb8`.

The entire two-item forward plan was checked before application. No historical/EWAF migration was executed or rewritten, no migration was faked, and no startup deferral was added. All previously applied migration history was retained. Django's checks and `makemigrations --check --dry-run` passed with no model drift; the unchanged startup guard had no pending migrations. No `members/0006` or `core/0002` migration was introduced into this original 70% runtime as part of registration integration.

The fresh regression environment also exercised exact 0007 reverse/forward behavior and refusal to reverse a linked registration before DDL. The live fictional clone now has a link: **do not reverse 0007 by deleting that history**. To disable the demonstration, stop its web process or review its local feature contract while retaining data and schema. No working-database migration is authorized by this local setup.

## Actual validation

| Check | Result |
|---|---|
| Original → clone table comparison before migrations | Every original row and column matched; SQL backup retained privately. |
| Media/source comparison | 13,788 private files matched; original runtime unchanged. |
| Targeted combined-runtime regression | **315 tests run in 193.044s: 314 passed, one assertion failure, no errors.** See `regression-executed.log`. |
| Remaining assertion | `test_guidance_reflects_gate_with_resources_appended_to_public_navigation` expects 8 Public destinations; the original 70% runtime retains 7. The later Resources feature has not been copied into this registration-only integration. This result is visible; no assertion was weakened and the whole run is not reported as passing. |
| Registration, Finish, prefill, handoff, reference retrieval, writer and program-intake coverage | Passed within that run, except the navigation assertion above. Includes unauthorized/private-file access, retry/concurrency, audit rollback, revoked sessions and native writer compatibility. |
| EWAF/formula/configuration/scoring/evidence/decisions/operational/release/publication tests | Passed within that same run; historical results were not reused as new passes. |
| Full browser journey at temporary port 8003 | Passed actual public submission → AMR receipt → full Admin reference-prefill → onsite observations → native review/manual verification → approval → Member; anonymous denial and Finish revocation passed. One initial browser fixture failed before submission because a numeric disability option belonged to the small demo; corrected the harness to select an existing fictional option. |
| Final port-8000 browser check | All eight Admin groups and one entry page per group returned 200; populated counts, public form, saved AMR retrieval and approved Member were present. Anonymous inbox denied; mobile form overflow and keyboard focus checks passed; no JavaScript errors. See `ui/port8000-smoke.json`. |
| Startup | Port 8000 launched normally after staging; retained the demonstrated approval. Start System's launcher recognized that same running full instance. |
| Initial sandbox attempt | Fresh-test MySQL config creation and initial Chrome launch were blocked by sandbox permissions; these were rerun with tool approval. These failed launch attempts are not test passes. |

The executed regression command was:

```powershell
.\.venv\Scripts\python.exe -B .local/full-system-registration-20261024/test_runtime.py test membership.test_registration_intake membership.test_registration_finish membership.test_registration_prefill membership.test_registration_handoff membership.test_registration_handoff_migration membership.test_reference_retrieval ewaf.test_membership_writers ewaf.tests ewaf.test_configuration ewaf.test_weighted_scoring ewaf.test_scoring_inputs ewaf.test_evidence ewaf.test_decisions ewaf.test_operational assistance.tests announcements.test_results program_intake.tests --testrunner=scripts.registration_handoff_test_runner.RegistrationHandoffTestRunner --noinput --verbosity=1
```

It used the existing fresh G12 harness with `.env` disabled, restricted grants, a fresh random-port MySQL/datadir and separate temporary private media. The verified test instance was port 60727, UUID `e98ec158-cf25-11f1-abd5-581122e63603`, under `santolan-g12-tests-7k1zujqm`; it was shut down by the harness. Historical migrations were not executed in that model-synchronized test baseline. This was targeted regression, not the entire repository test suite. Screen-reader/device matrix, comprehensive contrast/reflow testing and participant UAT were not performed; no WCAG certification is claimed.

## EWAF and operating boundaries

All **267 root protected files** match the Phase 1 hashes. The corresponding files in the original populated runtime and its extended copy also match each other, preserving that workspace's pre-existing hooks. Original and integrated Section 8 are byte-identical: **8,384 bytes**, SHA-256 `f446ea0be7cf061439293c75f6354bdde77c6e2e4870e69611cc19bd1abec41d`. Existing calculation, program-application and assistance rows are unchanged. File preservation and behavioral test results are separate evidence.

Registration remains separate from official membership until the existing writer, required onsite findings, accepted basis, manual verification and authorized decision complete. Public references do not authorize private retrieval. Existing accounts/passwords/grants are preserved; the full superuser already has the registration permissions created by the additive schema. There is no new member account, notification, public tracking/recovery or PDAO processing activation.

The enabled local registration contract reuses the previously reviewed **fictional** fixture, with its requirements fingerprint recalculated against the cloned, unchanged requirement configuration. It grants no Association authority. Actual applicant collection still needs approved membership qualifications, identity/representative procedures, document handling, legitimate identifiers, assessment responsibility, decision authority, staff assignments, privacy/retention and target-specific security/activation approval. The operational-closure report continues governing these unresolved decisions.

Practical outcome: the full populated development system and registration flow are usable together at one address. Remaining risks include local-only development settings, human duplicate/identity review, operational approval dependencies and the explicitly recorded Public-navigation test mismatch. No performance, fairness, production readiness or increased milestone claim is made.
