# Changes made under the remaining-phase authorization

Compare against `baseline.json`, captured at this turn's start, rather than HEAD alone: the checkout already contained extensive uncommitted Phase 1/2A/2B work. Branch remains `feature/events`; HEAD remains `776cac5d1119410717c6a31c044ea85f4d619941`. No commit, merge, push or deployment occurred.

## Application and template changes

| File | Change in this continuation |
| --- | --- |
| `membership/registration_views.py` | Existing staff inbox state/channel filters; exact reference lookup takes precedence. Finish code unchanged. |
| `templates/membership/registration/inbox.html` | Accessible filter controls/status and retained pagination parameters. |
| `members/models.py` | Registers the two additive private review models. |
| `members/review_models.py` (new) | Private review case and append-only action records; guarded writes, protected relationships and constraints. |
| `members/review_services.py` (new) | Disabled-by-default policy, current permissions, idempotent staff concern intake, stale-write checks, retained findings and internal staff-only status projections. No accepted-evidence or EWAF writer. |
| `members/review_views.py` (new) | Authenticated, CSRF-protected, noncached concern/list/detail workflows and generic unavailable responses. |
| `members/urls.py` | Private Member review routes only. |
| `members/views.py` | Supplies availability for gated Member detail links. |
| `templates/members/detail.html` | Gated private information/evaluation concern links. |
| `templates/members/reviews/list.html` (new) | Concern intake, declaration and private review history list. |
| `templates/members/reviews/detail.html` (new) | Versioned findings form and retained history; unaccepted-source wording. |
| `core/models.py` | Resource CMS keys and four optional publication metadata fields. |
| `core/content.py` | Existing CMS lifecycle extended with reviewed source/provider/date, archive, published metadata snapshots and fresh permission checks. Public fallback wording uses maintained guides and the actual no-business-rank method. |
| `core/resources.py` (new) | Public topic index/details read published CMS snapshots only. |
| `core/urls.py` | Resources index/detail routes. |
| `core/context_processors.py` | Appends Resources & Help after the original seven public destinations. |
| `templates/public/base.html` | Resources current-page indication and footer link. |
| `templates/public/home.html` | Resources shortcut and links to maintained instructions/results/help. |
| `templates/public/resources/index.html` (new) | Seven public topics, canonical guides and separately published external verification link. |
| `templates/public/resources/detail.html` (new) | Published text/source/provider/review date, without personal-data collection. |

## Additive migrations

| File | Scope |
| --- | --- |
| `members/migrations/0006_private_information_review.py` (new) | Two new review tables and three checks; depends on members 0005, programs 0005 and swappable user. |
| `core/migrations/0002_resource_publication_metadata.py` (new) | Four optional metadata fields and expanded CMS key choices; depends on core 0001. |

Existing `membership/migrations/0006_association_pending_intake.py` was tested, not edited. All 58 pre-existing migration files are unchanged. Exact hashes, rehearsal scope and conditional recovery are in [migration readiness](phase5/migration-and-activation-readiness.md).

## Tests and tooling

| File | Purpose |
| --- | --- |
| `membership/test_registration_completion.py` (new) | Inbox compatibility and exact retained membership migration/startup lifecycle. |
| `membership/test_registration_intake.py` | Updates the non-EWAF navigation expectation for the authorized eighth destination. Existing security/business assertions retained. |
| `members/test_information_review.py` (new) | Permissions, gates, declarations, concerns, history, stale updates, rollback, retries/concurrency and unchanged source/decision data. |
| `core/tests/test_resources.py` (new) | CMS source validation, publication/withdrawal/archive, privacy, permission revocation, audit rollback and canonical links. |
| `core/tests/test_public_portal.py` | Keeps original public order and expects the added eighth destination. |
| `scripts/remaining_phases_test_runner.py` (new) | Fresh disposable MySQL/private-media checks and whole-plan fingerprint validation for only the three reviewed additive migrations. |
| `scripts/remaining_full_test_runner.py` (new) | Broad ordinary-app discovery with an explicit inventory of historical migration exclusions. Does not edit their assertions. |
| `scripts/remaining_schema_tests.py` (new) | Additive reverse/forward compatibility and rejection of mixed migration plans before any operation. |
| `scripts/remaining_recovery_tests.py` (new) | Native disposable MySQL dump/restore plus one synthetic private-file backup/restore. |
| `scripts/remaining_phases_browser_qa.py` (new) | Isolated synthetic live-server fixtures and browser runner. |
| `scripts/remaining_phases_browser_qa.cjs` (new) | Registration/review/Resources browser journeys, responsive/keyboard/reflow and sampled accessibility checks. |
| `scripts/remaining_phases_evidence.py` (new) | Read-only protected/source/history comparison and actual test-log evidence capture. |

## Documentation and evidence

`docs/remaining-phases-2026-10-23/` contains this continuation's baseline, separate Phase 2B/3/4/5 checkpoints, designs, retained successful/failed logs, test inventories, migration/recovery instructions, full BF/BR-A/AC-B/IQ traceability, staff guidance/UAT forms and synthetic UI evidence. The existing `docs/added-targets-phase1-2026-10-23/progress-and-decisions.md` has new checkpoint entries prepended; its original 46,880 bytes remain intact. Prior audit reports, source originals and validation evidence remain unchanged.

The initially dirty `membership/models.py`, `membership/urls.py`, `membership/views.py`, `templates/membership/guidelines.html` and `templates/membership/list.html` were not changed in this continuation. Existing Finish services, registration schema, startup guard, settings, styles/sidebar, credentials, issued identifiers and protected EWAF files were not rewritten. There are no new dependencies, staff grants or operational configuration changes.
