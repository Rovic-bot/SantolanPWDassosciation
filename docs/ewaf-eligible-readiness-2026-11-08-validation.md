# Eligible applicant ranking readiness - November 8, 2026

## Report and diagnosis

The owner reported that applicants already marked Eligible still showed Needs review in EWAF. Read-only diagnosis of the two reported applicants in the HM Focus program found that their accepted scoring inputs predated a direct Eligible confirmation. The only source differences were the application version, eligibility review audit/digest, and the additional passing administrator-review checklist item. Member information, required qualifications, evidence and scoring inputs had not changed.

The previous comparison accepted identical repeated eligibility reviews only for automatic member-record scoring. Older document-backed and reviewed-member-record configurations therefore demanded another input review after the same eligibility confirmation.

## Correction

- Reuse an existing accepted input review when a complete, matching assistance audit chain proves an Eligible-to-Eligible confirmation with unchanged source facts. The direct-review passing administrator attestation is allowed as an addition to an otherwise identical checklist.
- Require the original/current approved eligibility, active status, matching audit digests, actor, reason, chronological review timestamps and a log for every application-version increment. Changes to member information, requirements, evidence, policy, prior assistance or other source facts remain significant. A reversed eligibility outcome, removed/failed requirement, unexplained version or broken audit chain cannot qualify.
- Apply the same proof to current-ranking comparison for retained dataset inputs, as well as automatic member-record inputs. New explicit selection decisions retain the eligibility-recheck audit witnesses. The post-cutoff release projection also recognizes these unchanged confirmations while preserving its receipt and approval checks.
- Do not rewrite accepted reviews, stored rankings, scores, ranks, decisions or release records. Ranking/selection remain separate operations, with existing permission, validity, capacity, tie and audit controls.
- Label a decision belonging to an older ranking as Previous ranking rather than Review required. The underlying historic decision and current selection controls are unchanged.

## Validation

21 focused tests passed in fresh disposable native MySQL using `scripts/g12_test_runner.py` with `scripts.registration_intake_test_runner.RegistrationIntakeTestRunner`:

- `ewaf.test_eligible_readiness` (6): both document-backed and reviewed-member-record inputs; direct Eligible readiness before first ranking, repeated confirmations without a new input review/ranking, no review badge, explicit selection with audit witnesses, actual release, retained original snapshots, and rejection of changed source facts or a broken audit chain.
- `ewaf.test_ranking_freshness` (8): existing automatic-input freshness, artwork changes, actual input changes, reversed eligibility, unexplained versions, invalid audit chains and selection-audit rollback.
- `ewaf.test_applicant_panel` (7): existing permission checks, explicit selection, input display, stale edits, row filtering and read-only workspace behavior.

Test duration: 86.293 seconds. Log: `C:/Users/rovic/AppData/Local/Temp/santolan-g12-tests-olk3juzw/django.log`.

Read-only inventory and RequestFactory rendering against the retained development database returned HTTP 200. Both reported applicants now have no readiness errors, `needs_review=False`, and Accepted inputs ready for ranking. The HM Focus ready count increased from 8 to 10. Their historic Not selected decisions now explicitly say Previous ranking.

The same program still contains a separate **Ineligible** record with a stale/unverified exclusion review. That existing program-level problem was retained; no eligibility decision or live ranking was created to hide it. The read-only SQL wrapper rejected all INSERT/UPDATE/DELETE/DDL operations during verification.

Django/database check and `git diff --check` passed. The local server on port 8013 was restarted while retaining its database and uploads. No migration, mathematical formula change, policy mutation, live review, beneficiary decision, release or email was performed.
