# Guardian / representative receipt recording

The owner requested implementation of the discussed Admin → Assistance Releases claimant flow. “Record actual receipt” now opens a form before saving. It works as an ordinary page and inside the existing assistance-receipts popup.

Staff explicitly select beneficiary or guardian / authorized representative. Representative receipts require name, relationship, the beneficiary's absence reason, an authorization/guardianship basis, and attestations that identity and authority were checked onsite. All receipts require beneficiary identity verification and confirmation of actual handover. Optional remarks can record an approved alternative and its approving officer/reference. This records the staff's checks; it does not establish new Association policy or automatically approve an exception. No document scan or full ID number is collected.

The existing private `AssistanceRelease.approval_snapshot` contains a versioned `claimant` snapshot with beneficiary and claimant names, the evidence basis, attestations, remarks, and server-derived staff identity/time. The ordinary release audit retains the same snapshot atomically. Existing receipts retain their original evidence and show “Not recorded on this earlier receipt.” No schema migration or historical backfill was needed.

The web receipt action requires the new fields and preserves invalid submissions for correction. Current selection, published-selection, active-member, version, single-release and audit-rollback guards remain in the release writer. Program benefit, amount and date still come from the existing service. The legacy detailed release service remains available to existing internal callers without fabricating claimant details.

## Validation

- Django system checks, template compilation, JavaScript syntax and scoped whitespace checks passed.
- Read-only rendering against the existing local database returned HTTP 200 for the claimant page and receipt list; the list exposes the new action. Existing receipt count remained two; no real release was submitted.
- Form checks rejected incomplete representative submissions and accepted complete attestations; beneficiary receipts discard unused representative details.
- The initial 50-test run against a fresh disposable MySQL database encountered 41 errors and four failures in older assistance fixtures, principally because they use the retired non-EWAF eligibility workflow. Those policy guards were retained. The new claimant regression tests use the operational EWAF fixtures instead.
- All nine new EWAF-based claimant tests passed in a fresh disposable MySQL database: snapshot/audit retention, required representative checks, trusted beneficiary/staff identity, invalid-form recovery, atomic rollback, explicit receipt confirmation, GET/HEAD/CSRF safety, stale/duplicate submissions, and selection/publication gating.
- Native browser inspection was blocked by Computer Use because it could not establish the Windows browser URL. No alternative browser automation was attempted; visual layout has not been verified.

The development server at port 8013 was restarted with the new flow. Application records and membership/email actions were not changed by this task.

## Follow-up: selection from an earlier ranking

The owner encountered a blocked confirmation: the saved beneficiary selection referred to an earlier EWAF calculation while a newer calculation was current. The initial receipt page incorrectly called the applicant a selected beneficiary and the release list enabled its action using a previous selection without checking the run. The release writer correctly rejected it.

The release writer and receipt UI now share the same initial run/decision check. The list disables the action and labels a stale decision “Selection needs review.” Opening the claimant form directly displays the reason before entry, disables confirmation, and links to that applicant in the latest ranking. Workflow errors no longer instruct staff to correct unrelated fields. A read-only check of the affected local ranking confirmed that it is current, permits an authorized human selection, and the applicant has no receipt and no selection on that calculation. No beneficiary decision or release was submitted.

Regression coverage includes blocked GET/POST/direct service calls for a stale selection and successful receipt recording after a human selection is reconfirmed on the latest calculation in the disposable test environment.

All 11 claimant regression tests passed on disposable MySQL after this correction. Django checks, scoped whitespace checks and read-only rendering of the affected local form/list passed. The local server was restarted.
