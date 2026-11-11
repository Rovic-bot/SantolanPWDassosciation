> [!note] Dated plan preserved — October 10 target supersedes conflicting scope
> This plan is historical planning/implementation evidence, including any older “Current requirements” heading below. It is not authority for new work against the October 10 target. Read [[CURRENT_SYSTEM_SPECIFICATION]], [[Workflow Source Register]], [[October 10 Implementation Impact]] and [[Open Decisions]]. Preserve the owner-defined 70% milestone and accepted controls. New target changes include seven public sections/eight Admin groups, program-specific approved photo/alternative evidence, dedicated Results and workbook-derived controlled EWAF. RSVP remains approval-gated; Gemini is PROPOSED. No application code/data changes are authorized by this documentation update.

# Member records and announcement documentation

## Current requirements — 2026-10-06

Authority: [Current System Specification](../../CURRENT_SYSTEM_SPECIFICATION.md), [[Business Rules]], [[Database Plan]] and [[Workflow Acceptance Tests]]. Documentation only; no application implementation/test pass is claimed.

Authorized Admin manages private official Member records, reasoned verified-source corrections and dependent recalculation. General announcements/CMS stay editable with audit. Program results publish only after authorized final processing with approved masks/reference fragments; no deadline-generated applicant list.

For all states/reference formats, modules, permissions, photo outcomes and EWAF governance use the primary specification; do not infer policy from the old plan. [[Open Decisions]] lists genuine ambiguities.

> [!warning] OUTDATED / HISTORICAL — earlier scope and evidence only
> Everything below retains the original dated text, checkbox states, source paths and test results. Former "current", "next", "complete" and "approved" labels refer to that revision only. They do not establish the 2026-10-06 workflow or authorize application/source/database actions now. [[CURRENT_SYSTEM_SPECIFICATION]] supersedes contradictory rules.

## Historical Milestone Plan

**SUPERSEDED — 2026-09-28 (affected workflow portions only).** The original plan below is retained to explain previous implementation and validation. Its old workflow instructions and migration commands are historical, not instructions for this documentation-only task. Unrelated controls remain in force.

Authorized by the user's September 27, 2026 instruction to finish the 40% milestone. The existing frontend redesign is preserved on `feature/members-announcements`; its initial state is backed up in ignored local storage.

## Requirements and boundaries

Authority: vault development guide §§15, 19, 49–53, 61–66; Business Rules; Decisions; ten-milestone Development Roadmap; UI Design Guide for presentation.

- Official members continue to originate only from approved, manually verified membership applications. No public member directory, account, or generic member creation/deletion screen.
- Private member search/filter/pagination, profile corrections with a reason, Active/Inactive/Archived status, restoration, permission-controlled documents, and record-change history. Original applications and document snapshots remain unchanged.
- Admin announcement creation/editing, draft review, explicit publication/withdrawal/archive/delete, optional validated image and required image description. Public list/details and the latest three published items on the homepage.
- Preserve administrator authentication and configurable roles. Separate capabilities for profile editing, member status, document access, audit viewing, announcement editing, publishing, and deletion.
- Important writes and audit events commit atomically, with row locks and submitted versions rejecting stale changes. Deleted announcements remain as internal tombstones to preserve their audit history.
- Events, assistance programs, eligibility, EWAF, reports, public deployment, and new institutional configuration are outside this milestone. Future participation histories are identified as unavailable; no fake data or links.

## Implementation

Extend `members/`; implement the existing `announcements/` shell. Add protected workspace routes and publication-aware public image routes; keep raw media inaccessible. Reuse public/admin templates and tokens. Add two migrations, image processing through pinned Pillow, tests, and setup/validation notes.

## Acceptance gates

1. Authorized administrators can find/edit/archive/restore members; unauthorized requests, stale writes, invalid values, duplicate control numbers, and missing audit writes are rejected.
2. Documents remain private and associated with the correct member; detailed histories require their own permissions.
3. Draft, archived, deleted, and future-dated announcements cannot be read publicly, including images. Publishing makes content available on the public list/detail/homepage; withdrawal removes it.
4. Images are bounded, decoded, re-encoded without source metadata, and served with fixed image content type. HTML remains escaped; writes require CSRF and POST.
5. Existing authentication and membership workflows pass regression checks; new screens pass responsive, enlarged-text, focus, and reduced-motion checks.
6. Additive migrations apply on native MySQL after a private backup; existing records are compared before/after. Update the roadmap and progress only from observed results.

Results: [milestone validation](members-announcements-validation.md).
