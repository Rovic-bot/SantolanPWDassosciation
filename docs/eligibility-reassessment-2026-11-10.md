# Eligibility reassessment after a member record changes

The owner requested that an applicant marked Needs review can receive another Eligible or Ineligible decision and then participate in a regenerated EWAF ranking.

Read-only inspection of the active local development database found a completed recipient whose member version had changed since the eligibility assessment. The EWAF workspace correctly reported stale eligibility, but the application review form treated Completed as closed. Both the combined review service and the eligibility service also prohibited assessment changes after a successful release.

## Behavior

- The current member-record/rolling EWAF workflow now allows authorized administrators to reassess a completed recipient. The original successful receipt, assistance audit, selection, and ranking must validate first.
- The eligibility form offers Eligible, Needs Information, and Ineligible, with the existing permission, source-token, version, required-evidence, membership, program-qualification, and reason checks. Needs-review EWAF rows link directly to the eligibility section.
- A new review records the current member/program versions and a completed-reassessment witness in the normal append-only eligibility audit. The application stays Completed, preserving the fact that assistance was delivered. A new eligibility assessment does not authorize another selection or receipt.
- Ranking uses the newly reviewed current inputs, with the eligibility outcome projected separately from the actual completion status. Eligible enters the pool; Ineligible is excluded; Needs Information remains unresolved under the existing pool rules. A subsequent member edit invalidates that review again.
- The program's own recorded fulfillment remains excluded from its previous-assistance input, matching the existing post-delivery ranking behavior. Other assistance uses the current ledger and the existing configured scope/window. Scoring formulas and weights are unchanged.
- Earlier rankings and publication snapshots are not rewritten. New ranking generation remains an explicit admin action. Receipt voiding, duplicate-release prevention, and selection-after-release restrictions remain in place. Rejected/closed applications outside this completed-recipient workflow retain their existing reopening restrictions.

The optional calendar-photo review used by the combined Eligible action also retains Completed during this reassessment, records a fresh photo review, and preserves the existing permission/audit checks. No photo or document is fabricated or replaced.

## Verification

No automated test suites, fixtures, seeds, or synthetic operational records were run or created. Verification used the existing local development records with a SQL wrapper rejecting all database writes.

- Django/database system checks passed.
- The affected applicant's actual review view rendered HTTP 200 with all three enabled decision actions, the existing receipt explanation, and a return link to EWAF.
- Each review outcome passed the real service's validation up to the first persistence call; that call was intercepted before writing. Stale forms were rejected, and Needs Information/Ineligible still required reasons.
- An in-memory preview of the proposed eligibility review passed ranking-readiness validation and recalculated the existing three-applicant pool without saving a run. The preview also checked Ineligible exclusion, unresolved Needs Information, exclusion of the program's own receipt, and renewed invalidation after a later member-version change. This is a preflight, not a saved administrative decision or an end-to-end database write test.
- Headless browser inspection of the actual server-rendered review HTML at desktop and mobile widths found enabled decision controls, no horizontal overflow, and no JavaScript errors. Only GET/static requests were allowed.
- `git diff --check` passed. The local development server was restarted.

No actual eligibility decision, ranking, receipt, or email was created during verification. No model, migration, database configuration, or operational record was changed. Private preflight scripts and screenshots remain under ignored `.local/development/`.
