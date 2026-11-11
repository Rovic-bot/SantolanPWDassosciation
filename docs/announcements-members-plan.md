# Announcements and unified Members navigation — 2026-10-07

The owner explicitly authorized completing Program Announcements, combining onsite membership registration and member records in one Admin sidebar tab, and retaining sidebar scroll position between pages. This extends the first-seven-stage milestone with the announcement portion of stage 9. Guide sections 15–20, 54–55 and 61–66 and [[CURRENT_SYSTEM_SPECIFICATION]] govern implementation. The owner approved masked initials plus the last four reference characters, with Help Desk guidance for ambiguous entries; full references, names and scores remain private.

## Implementation plan

- Reuse Announcement and its existing program link. Add immutable result revisions and an explicit reviewed revision pointer. Keep historical applicant rows private. Add Admin draft/preview, publication authorization, withdrawal and reasoned revision history.
- Generate public result rows only from completed, current eligibility and authorized selection. All applications must reach a final outcome before publication. Pending/correctable cases block publication. EWAF programs require an accepted current EWAF run; stage 8 remains incomplete and their publication stays blocked. No new waitlist decision policy is invented.
- Use a strict public projection: program context, schedule, slots, eligible count, approved method and selected masked names/reference suffixes. Sort by masked identity, not private score or reference order. Duplicate displays retain the same mask and instruct applicants to use the Help Desk; do not reveal more characters to disambiguate. Preview and publication require explicit privacy review, including small-group risk and organization-authored text.
- Verify source freshness at publication and public reads; preserve the authorized historical revision if records change, but withhold stale results pending renewed review/publication. Closing applications never publishes automatically.
- Present one Members sidebar entry with internal Member records, Onsite registration and Membership reviews links according to existing permissions. Preserve server-side RBAC and the in-person/manual approval workflow.
- Persist only navigation scroll offsets in per-tab browser session storage. Restore the menu without moving content focus; support custom and native Admin pages, mobile menu reopening and storage-unavailable browsers.

## Validation and recovery

Run service/HTTP privacy, eligibility, concurrency/version and audit rollback regressions; browser-check result preview/publication, unified member navigation and sidebar position across custom/native pages. Additive migration only; original source/notes are verified in the private task backup. Back up the database before applying the migration. Do not claim stage 8, all of stage 9, UAT or production readiness from this work.

Status: completed and locally validated. See [validation and changed-file inventory](announcements-members-validation.md).
