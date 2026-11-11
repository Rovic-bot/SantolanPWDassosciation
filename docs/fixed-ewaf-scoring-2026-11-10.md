# Fixed EWAF scoring survives a fresh database

## Owner decision and source

The owner explicitly requested the previous scoring rules as permanent application configuration, independent of database resets. Editable approved weights remain separate. This supersedes the requirement to create/approve a shared dataset-policy row for new composite programs.

Read the retained **local** archive `santolan_ewaf_twelve_demo` on 127.0.0.1:3309, without modifying it. The latest approved shared calculation policy was revision 22. Recovered its executable rule choices, not its fictional operational records, old administrators, test procedure descriptions, or test validity dates. The previously confirmed November 10 five-category employment scores supersede the archive's older employment mapping.

Canonical rules now live in [fixed_scoring_rules_v1.json](../ewaf/fixed_scoring_rules_v1.json) and [fixed_scoring.py](../ewaf/fixed_scoring.py). They are loaded from source, with no policy-table lookup, migration seed, fixture, or startup database insertion. Preserve this version for historical replay; later authorized changes need a new version.

## Retained calculation rules

- Four criteria: SES, employment, previous assistance, household members.
- Normalize income and assistance inversely; employment and household members increasingly, using the eligible applicant pool's minimum and maximum.
- SES = normalized income need × (0.90 + 0.10 × household 4Ps indicator). Explicit Yes = 1, No = 0; missing values are not No. Do not normalize SES a second time.
- Employment: Employed 1; Self-Employed 2; Student 3; Retired 4; Unemployed 5.
- Previous assistance: actual confirmed, non-voided Association releases across programs within 12 calendar months, inclusive clamped dates and the retained recording cutoff. No application, selection, or attendance counts as a release.
- Equal-value columns receive normalized credit 1 before the SES adjustment. All four weights remain active.
- Current approved member records supply inputs. Invalid/missing inputs remain blockers. During registration, only eligible applicants enter the ranking.
- Exact weighted sum × 100; exact competition ranks and existing display rounding. Boundary ties hold selection; no automatic tie-break or beneficiary selection. No need classifications are introduced.
- The registration closing time remains the program cutoff; the existing versioned rolling observation supports ranking while registration is open.

The rule definition has no operational expiry. The retained run schema requires an end datetime, so year 9999 is the compatibility sentinel, replacing the old demo-only December 2026 expiry. The code-version effective date records this owner decision, not a fabricated external approval.

## Persistence and integration

Weights and ranking records remain in MySQL. A program receives an immutable **audit snapshot** of the fixed code definition and its approved weight reference during publication. This snapshot is for replay and integrity, not an editable source of scoring rules. No `SharedDatasetPolicy` record is required. Thus resetting MySQL cannot delete the authoritative scoring definition; a newly published program gets its snapshot from code after real weights are approved.

The existing generation, source validation, exact math, weight-version capture, freshness, selection, publication, and release services recognize these snapshots. Previously bound historical methods retain their own contracts. Shared weight changes still require fresh calculations before further decisions; old runs are not rewritten. Authorized program schedule corrections retain the same fixed definition and weights in a new audited snapshot.

## Local application and validation

Backup before configuration changes:
`C:\Users\rovic\Documents\Santolan Development Backups\before-fixed-scoring-20261110-164748\santolan_pwd_development.sql`

The backup completed with 140 table definitions, 487,495 bytes, and a SHA-256 manifest. No restore was performed.

Applied fixed scoring to the existing Rice Distribution program using its existing approved weights and real administrator, with an explicit owner-request/development-assistant reason. Added one operational configuration snapshot and one program audit entry. No member, program, application, selection, release, email or ranking was created. Shared dataset-policy count remains **0**.

- Django database/system checks: passed; migration dry-run: no model changes.
- Read-only SQL guard rejected mutation statements during readiness and rendering. Initial MySQL read-only transaction mode rejected the application's `SELECT FOR UPDATE`; repeated inspection with a mutation-blocking wrapper permitting read locks instead. No validation writes occurred.
- Existing two eligible applicants passed readiness and exact calculation in memory; saved ranking count stayed **0**.
- Read-only workspace and Vault renders returned HTTP 200. Browser preview confirmed one enabled Generate EWAF Ranking button and no scoring-configuration-pending warning.
- Python syntax and `git diff --check` passed.
- Added regression source for database-independent definitions, copy isolation and tamper rejection; no automated test suite, synthetic fixture or data generator was executed.
- Actual ranking submission, future program publication, schedule edits, selection and release were not exercised through writes. Those remain manual testing steps; their existing services and guards are retained.

Private rendering/backup inspection artifacts remain under `.local/development/`; they are not public assets or repository fixtures.
