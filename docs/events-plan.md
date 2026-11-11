> [!note] Dated plan preserved — October 10 target supersedes conflicting scope
> This plan is historical planning/implementation evidence, including any older “Current requirements” heading below. It is not authority for new work against the October 10 target. Read [[CURRENT_SYSTEM_SPECIFICATION]], [[Workflow Source Register]], [[October 10 Implementation Impact]] and [[Open Decisions]]. Preserve the owner-defined 70% milestone and accepted controls. New target changes include seven public sections/eight Admin groups, program-specific approved photo/alternative evidence, dedicated Results and workbook-derived controlled EWAF. RSVP remains approval-gated; Gemini is PROPOSED. No application code/data changes are authorized by this documentation update.

# Programs and events documentation

## Current requirements — 2026-10-06

Authority: [Current System Specification](../../CURRENT_SYSTEM_SPECIFICATION.md), [[Business Rules]], [[Database Plan]] and [[Workflow Acceptance Tests]]. Documentation only; no application implementation/test pass is claimed.

Public users browse program/event information; only Verified Members submit organizational event applications through internal membership verification, requirements/reused evidence, calendar-photo submission/reference, manual photo review, final eligibility and EWAF when applicable. Preserve prior open attendance as historical; public-gathering participation policy is open, not a nonmember application bypass.

For all states/reference formats, modules, permissions, photo outcomes and EWAF governance use the primary specification; do not infer policy from the old plan. [[Open Decisions]] lists genuine ambiguities.

> [!warning] OUTDATED / HISTORICAL — earlier scope and evidence only
> Everything below retains the original dated text, checkbox states, source paths and test results. Former "current", "next", "complete" and "approved" labels refer to that revision only. They do not establish the 2026-10-06 workflow or authorize application/source/database actions now. [[CURRENT_SYSTEM_SPECIFICATION]] supersedes contradictory rules.

## Historical Milestone Plan

**SUPERSEDED — 2026-09-28 (affected workflow portions only).** The original plan below is retained to explain previous implementation and validation. Its old workflow instructions and migration commands are historical, not instructions for this documentation-only task. Unrelated controls remain in force.

Authorized on September 27, 2026 after the user verified milestone 40%. Authority: the vault's Guide for Development sections 21–23, 49–54, 61–66; Business Rules; Development Roadmap; and the user's explicit answers to the open event questions.

## Confirmed rules

- Members have no accounts. All four submitted values must match an active official member; no additional PRPWD lookup and no EWAF or assistance counting.
- Names ignore capitalization and repeated whitespace. Preserve accents, punctuation, and name order; use Unicode NFC normalization. Control numbers follow the existing trimmed uppercase storage convention and are compared explicitly after the database lookup.
- Phone numbers ignore ordinary formatting and equate Philippine `+63`/`63` with local `0`. No fuzzy matching, letter removal, or guessed digits. Birthdate is exact.
- The user selected Registered, Confirmed, Attended, Absent, and Cancelled. Only authorized admins change an existing registration's status, with a required reason and retained before/after history. Cancellation releases capacity; restoration checks active membership and capacity again.

## Implementation boundaries

Create event drafts with title, description, Philippine-time start/end, location, registration period, optional capacity, and optional re-encoded image/description. Explicit publish/withdraw/cancel/archive actions have separate permissions. Cancellation retains a public notice; drafts and archives are private. No physical deletion endpoint. Editing public content requires publishing permission.

Registration opens inclusively and closes exclusively, no later than the event start. Capacity is unlimited only when explicitly left blank. One retained registration per event/member; repeated submissions return the existing registration, while cancelled records need admin restoration. Event locks serialize registration, capacity edits and attendance changes. Stale forms are rejected. Attendance is recorded only after the event starts; corrections require reasons. Archiving preserves participation history.

Generic failed-verification messages, CSRF, HMAC database rate counters, permission-separated roster/history access, session-scoped receipts, and publication-aware image delivery protect private records. The receipt contains a random reference, not member data; no public lookup by reference. No email/SMS notification service or new member portal is introduced. Admins use existing official channels when event arrangements change.

Use existing UI components and styles. Connect public list/detail/homepage, admin navigation/dashboard, and member participation history. Add one migration with Event, EventRegistration, EventLog, and VerificationWindow; no existing table schema changes. Reuse the image processor with optional per-module limits, preserving announcement defaults. No new dependency or `.env` edits.

## Acceptance gates

1. Create/edit/publish/withdraw/cancel/archive and image access work with correct permissions and audit rollback.
2. All four matching checks, active membership, time boundaries, duplicate prevention, capacity, cancellation/restoration and attendance rules are tested.
3. Concurrent submissions cannot duplicate registrations or overbook the last slot on native MySQL.
4. Public data excludes member information; unauthorized roster/history/image access is blocked.
5. Existing membership, member, announcement and authentication tests remain passing; Chrome validates end-to-end behavior, responsive layout, enlarged text, focus and reduced motion.
6. Back up the normal database before the additive migration and compare existing records afterward. Update progress only after verification.

Source backup: ignored `.local/milestone50/before-source.zip`. Branch: `feature/events`; existing uncommitted work is preserved. Programs, eligibility, EWAF, analytics, report exports, production deployment and association UAT remain outside this milestone.
