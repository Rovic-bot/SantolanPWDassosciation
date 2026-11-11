> [!note] Dated plan preserved — October 10 target supersedes conflicting scope
> This plan is historical planning/implementation evidence, including any older “Current requirements” heading below. It is not authority for new work against the October 10 target. Read [[CURRENT_SYSTEM_SPECIFICATION]], [[Workflow Source Register]], [[October 10 Implementation Impact]] and [[Open Decisions]]. Preserve the owner-defined 70% milestone and accepted controls. New target changes include seven public sections/eight Admin groups, program-specific approved photo/alternative evidence, dedicated Results and workbook-derived controlled EWAF. RSVP remains approval-gated; Gemini is PROPOSED. No application code/data changes are authorized by this documentation update.

# Program Application documentation

## Current requirements — 2026-10-06

Authority: [Current System Specification](../../CURRENT_SYSTEM_SPECIFICATION.md), [[Business Rules]], [[Database Plan]] and [[Workflow Acceptance Tests]]. Documentation only; no application implementation/test pass is claimed.

Available program → minimal internal Membership Verification → requirements and verified-data reuse → proof plus calendar photo → complete submission/reference/Pending Photo Verification → manual Admin photo review → final eligibility → applicable controlled EWAF → generated ranking → authorized slot-constrained selection/final processing → masked Program Announcement. No universal disability rejection, fixed income/matrix, required status/QR or automatic applicant publication.

For all states/reference formats, modules, permissions, photo outcomes and EWAF governance use the primary specification; do not infer policy from the old plan. [[Open Decisions]] lists genuine ambiguities.

> [!warning] OUTDATED / HISTORICAL — earlier scope and evidence only
> Everything below retains the original dated text, checkbox states, source paths and test results. Former "current", "next", "complete" and "approved" labels refer to that revision only. They do not establish the 2026-10-06 workflow or authorize application/source/database actions now. [[CURRENT_SYSTEM_SPECIFICATION]] supersedes contradictory rules.

## Historical Milestone Plan

**SUPERSEDED — 2026-09-28 (affected workflow portions only).** The original plan below is retained to explain previous implementation and validation. Its old workflow instructions and migration commands are historical, not instructions for this documentation-only task. Unrelated controls remain in force.

Authorized September 28, 2026 after completion of Events. Authority: the vault Development Roadmap milestone 6 and Guide for Development sections 24–27, 49–54, 61–66. Existing uncommitted work is preserved; source backup: ignored `.local/milestone60/before-source.zip`.

## Confirmed business rules

The user confirmed that beneficiary slots do not cap applications; selection follows later review. Reuse event four-field active-member verification and its conservative normalization. Initial application states are Submitted, Under Review, and Cancelled, changed only by authorized administrators with reasons and retained history. Eligibility, approval, assistance release and EWAF are later milestones.

## Implementation

- Program drafts, publication, withdrawal, cancellation with public notice, and archive. Name, description, free-text assistance type, application period, optional program dates, slots, internal budget, amount, benefit and public instructions. No seeded institutional categories or requirements.
- Per-program active/required document uploads, written questions and acknowledgement checkboxes. Configure labels, instructions and order. Deactivate obsolete items; preserve submission snapshots, answers and private files.
- Session-bound membership verification followed by requirements. Grants expire in 15 minutes and are invalidated by program/configuration or member changes. Submission rechecks under locks. One retained application per program/member; repeats return the existing receipt. No public profile, roster or lookup by reference.
- Separate permissions for program editing, publication, requirement configuration, application viewing/status changes, document downloads and detailed audit history. No generic Django admin bypass or physical deletion workflow.
- Database locks serialize program changes, requirements and submissions; database uniqueness enforces duplicates. File validation reuses the membership limits (5 MB each, 20 MB aggregate, 20 files). Program document download is authenticated, audited, no-store and attachment-only.
- Public current/past program lists/details, administrator navigation/dashboard, private roster/search/filter/pagination, and member program history use existing styles.

## Verification gates

Tests cover lifecycle, matching, session isolation/expiry, active status, duplicate and concurrent submission, snapshots, upload validation/cleanup, rollback, permissions, privacy, stale forms, and preserved existing workflows. Browser checks exercise the full workflow and responsive/enlarged-text pages. Back up native MySQL before additive migrations and compare existing business tables afterward. Update completion only after validation.

Technical choices: dates use Philippine time; optional program dates may be announced later; registration closes after it opens and no later than a supplied program end. Budget is private internal planning data. At most 50 active requirements/questions per program (including up to 20 documents) bounds form size. These limits and behavior are documented, not seeded association policies. No deployment or remote publication is included.
