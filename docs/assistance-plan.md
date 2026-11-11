> [!note] Dated plan preserved — October 10 target supersedes conflicting scope
> This plan is historical planning/implementation evidence, including any older “Current requirements” heading below. It is not authority for new work against the October 10 target. Read [[CURRENT_SYSTEM_SPECIFICATION]], [[Workflow Source Register]], [[October 10 Implementation Impact]] and [[Open Decisions]]. Preserve the owner-defined 70% milestone and accepted controls. New target changes include seven public sections/eight Admin groups, program-specific approved photo/alternative evidence, dedicated Results and workbook-derived controlled EWAF. RSVP remains approval-gated; Gemini is PROPOSED. No application code/data changes are authorized by this documentation update.

# Eligibility and final program processing documentation

## Current requirements — 2026-10-06

Authority: [Current System Specification](../../CURRENT_SYSTEM_SPECIFICATION.md), [[Business Rules]], [[Database Plan]] and [[Workflow Acceptance Tests]]. Documentation only; no application implementation/test pass is claimed.

Final eligibility follows current manual photo verification and mandatory requirements. Only the eligible pool enters applicable versioned/locked EWAF. Admin records legitimate final decisions within slots without changing score/rank; preserve confirmed actual receipt and reasoned void history. No automatic beneficiary approval or cash disbursement; changes in source/configuration trigger audited affected recalculation.

For all states/reference formats, modules, permissions, photo outcomes and EWAF governance use the primary specification; do not infer policy from the old plan. [[Open Decisions]] lists genuine ambiguities.

> [!warning] OUTDATED / HISTORICAL — earlier scope and evidence only
> Everything below retains the original dated text, checkbox states, source paths and test results. Former "current", "next", "complete" and "approved" labels refer to that revision only. They do not establish the 2026-10-06 workflow or authorize application/source/database actions now. [[CURRENT_SYSTEM_SPECIFICATION]] supersedes contradictory rules.

## Historical Milestone Plan

**SUPERSEDED — 2026-09-28 (affected workflow portions only).** The original plan below is retained to explain previous implementation and validation. Its old workflow instructions and migration commands are historical, not instructions for this documentation-only task. Unrelated controls remain in force.

Authorized September 28, 2026. The user confirmed basic authorized-administrator approval with remarks before release, configurable Pending/Eligible/Review Needed/Not Eligible labels, retained checklists/history, and reasoned voiding of incorrect releases. Guide sections 28, 37, 41–42, 50–53 and 63 apply. EWAF and the fuller human-validation/analytics workspace remain later milestones.

Implement an assistance workspace with a private application queue, eligibility review against original submitted requirements, separate human decisions, confirmed releases and void corrections. Approval reserves a beneficiary slot; applications remain uncapped. Only non-voided successful releases count as Previous Assistance. One successful release per application; correction requires voiding, renewed review/approval and a replacement record. Budget is planning information, not an invented automatic financial eligibility rule.

Add EligibilityStatus (editable labels/availability with stable meanings), AssistanceCase (current assessment/decision), AssistanceRelease (immutable release details with void metadata), and AssistanceLog (retained action snapshots). Reuse the application version for stale-write checks and program/application/member row locks. Review captures member/program versions; changes require reassessment before approval/release. Required checklist items and active membership must pass for Eligible. Review changes clear prior approval. Released cases cannot be reviewed/cancelled until the release is voided. No generic admin edit/delete bypass.

Affected files: assistance models/forms/services/views/URLs/migrations/tests; assistance templates; program service guards and application link; member history; shared workspace navigation/dashboard; config URLs; browser harness and documentation. No dependency changes planned. Back up native MySQL before additive migrations, preserving existing records and assignments.

Acceptance: permission-separated review/decision/release/void/configuration; reasons, CSRF and no-store privacy; audited atomic actions and stale-edit rejection; valid release dates/values; slot/duplicate protection under concurrency; successful-only counts excluding events/applications/approvals/voids; private member history; working responsive UI; MySQL regression/browser checks and documented results. Preserve existing working-tree changes and stop at milestone 70%.
