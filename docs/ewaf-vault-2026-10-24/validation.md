# EWAF Configuration Vault - 24 October 2026

## Owner-confirmed scope

The owner requested a Configuration Vault tab, removal of the weights from EWAF program cards, configuration only in the vault, and automatic use of shared configuration by new programs. Follow-up answers explicitly confirmed sharing both weights and scoring rules (ranges, category encodings, assessment periods and tie procedures), and retaining verified system release records for Previous Assistance Received.

The four registered inputs are household monthly income, 4Ps membership, employment status and household-member count. The fifth input is the confirmed, non-voided release count in the approved scope and period. Weights are approved configuration values; applicants do not supply weights or override scoring inputs.

## Implemented behavior

- **EWAF Programs / Configuration Vault** tabs are available in the existing private EWAF workspace. Program cards retain configuration status, applicant counts and capacity. They no longer contain criterion-weight rows when the vault is enabled.
- The vault owns the five-criterion weight editor and shared rules. Source fields, value formats and units match registration fields and the release ledger. Numeric bounds, mappings, direction, dates, evidence types and tie procedures are entered under recorded Association authority; no production values were invented or seeded.
- Draft and locked vault revisions are immutable and audited, with actor, reason, time, predecessor, exact policy, AHP judgments, calculated validation and content digest. Explicit authorization/attestation is required to lock a complete policy. Draft saving does not deactivate an approved version. Current effective dates determine the active approved version.
- New EWAF programs automatically inherit the active approved version. Activating a vault revision also assigns it to previously unconfigured, unpublished drafts without applications. A program retains the version it inherited; later vault versions do not rewrite existing program configurations or calculations.
- Program authorization and applicable external approval remain required. Publication binds the inherited shared policy to the authorized program terms in a new immutable operational configuration revision. Per-program policy/weight edits are rejected in both the operational service and the old HTTP configuration actions while the vault is enabled.
- Programs with historical configurations retain their original configuration, calculation, evidence and selection contracts. The additive nullable vault reference is omitted from historical payloads so issued digests continue to replay unchanged.
- **Verify registered inputs** reads the four member fields and successful-release ledger directly. Staff cannot enter replacement income, household size, employment, 4Ps values or PA counts. Current, owned, verified supporting documents must match the document types approved for each registered criterion. Review dates must fall within the shared assessment period/cutoff, and staff must explicitly attest with an explanation.
- The new registered-input review is immutable and audited. Changed member information, document verification, release records, program policy, current-information declarations or eligibility context requires renewed review. Missing, unencoded or out-of-range information blocks usable scoring rather than receiving an assumed value.
- The new source contract retains the existing membership, identity, applicable disability classification, program-document and Admin eligibility checks. Criterion evidence is accepted through the new registered-input review; program eligibility is taken from the existing accepted Admin checklist. The earlier PR assessment contract remains intact for historical configurations.
- Exact AHP/normalization arithmetic, complete-pool calculation after closing, human selection, tie/slot rules, private evidence, explicit results publication and actual-release controls are retained. Calculation and input acceptance do not automatically select a beneficiary. Release and void paths were exercised against the new contract.

## Schema and local installation

`ewaf.0010_shared_configuration_vault` adds two empty tables (`VaultRevision` and `RegisteredInputReview`) and a nullable protected vault reference on operational configurations. There is no data backfill, reference renumbering or rewriting of earlier policies/results.

`EWAF_VAULT_ENABLED` defaults to false in ordinary source configuration. It is enabled in the identified fictional local development workspace at `http://127.0.0.1:8003/`. Existing runtime-only intake/source hooks remain preserved. Twenty-eight scoped runtime files were installed; unrelated runtime files were checked against the pre-change hashes.

A guarded 60,288,781-byte SQL backup was saved privately before migration. Database name, loopback port 3308, server UUID and data directory were checked before backup/migration. No credentials or private uploads are included in this documentation.

## Validation

- Source regression suites: **62 tests passed** across vault, program application workflow, household criteria and operational EWAF. Log: `.local/dual-registration-20261024/temp/santolan-g12-tests-q4796kwv/django.log`.
- Expanded source vault suite: **15 tests passed**, including HTTP form submission, enforced sources, concurrent revision saves, inherited publication, immutable history, review/audit rollback and successful-release/void counting. Log: `.local/dual-registration-20261024/temp/santolan-g12-tests-tsk7scgy/django.log`.
- Integrated runtime regression suites: **64 tests passed** against a separate disposable MySQL database with migrations. Log: `.local/household-criteria-20261024/temp/santolan-g12-tests-ssbwdhs9/django.log`.
- Runtime vault follow-up: **15 tests passed** after transactional inheritance changes. Log: `.local/household-criteria-20261024/temp/santolan-g12-tests-l00qwvp6/django.log`.
- Final source form/authorization checks after fixing registered units: **2 tests passed**. Log: `.local/dual-registration-20261024/temp/santolan-g12-tests-ldr8ya4u/django.log`.
- Read-only live-runtime rendering verified the empty vault, five-criterion form, tab navigation, compact program cards and removal of per-program editing. It used no live login or business writes. Browser visual QA was not performed; the earlier browser-launch approval rejection was respected.
- Django database checks and migration-state checks passed; no missing migrations were detected. Scoped Python syntax checks and `git diff --check` passed.
- Preservation comparison retained all **81,279 existing rows across 107 tables**. The only allowed metadata additions were one migration record and two content-type records. Sessions and request/login throttle tables were excluded. Existing program/application/member/configuration/score/decision/release/audit data and unrelated runtime files remained unchanged.

The live vault starts empty. The Association must enter and approve its actual shared rules once; numeric examples in tests are synthetic and were not loaded into the development database. This local implementation does not claim production or institutional acceptance.
