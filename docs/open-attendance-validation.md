# Open event attendance validation

> [!warning] OUTDATED / HISTORICAL validation evidence — marked 2026-10-06
> This entire report retains the original implementation, schema, commands and observed test counts for its dated revision. It is not acceptance of [CURRENT_SYSTEM_SPECIFICATION](../../CURRENT_SYSTEM_SPECIFICATION.md). Former current/next/complete labels and obsolete workflows apply only to that historical scope. New acceptance is planned in [[Workflow Acceptance Tests]]; no tests/code/database actions were performed for this documentation revision. Preserve useful nonconflicting security/history evidence without reintroducing public membership intake, open nonmember organizational applications, universal disability rejection, QR/status requirements, fixed EWAF defaults or automatic applicant publication.


Date: 2026-09-30 (Asia/Manila). Branch: `feature/events`; working tree based on `96ff02768e08e364f70f4a3e1c26b4a0e99399a7`, with existing unrelated work preserved. GAP-002 is complete for local implementation acceptance. This is not production deployment or association UAT.

Authority: guide §§21–23, 50–53, 61–66 and owner-approved DEC-022: individual administrative attendees, optional existing-member link, no public registration. Onsite membership acceptance is recorded separately in [its validation note](onsite-membership-validation.md).

## Delivered behavior

From **Manage events → Review event → Open event attendance → Record attendee**, staff record an attendee name, Attended/Absent status and reason, with an optional existing-member link. New attendance requires no registration, active membership, public identity matching, QR or EWAF. It does not enforce the optional venue planning capacity. The existing after-event-start attendance rule is retained; unpublished drafts and cancelled events reject attendance mutations. Previously published archived events retain administrative historical correction access.

The private roster supports name/status filters, pagination and a clearly labelled count of Attended records in that roster. Legacy registrations/attendance remain separate and are not included in this count. Records are not automatically converted, merged or deduplicated by name: different people may have the same name. Retrying the same submission key creates one record and one audit event, including concurrent retries. Linked member history shows these new records separately from preserved registrations.

Corrections require a reason and current record version; event/attendance locks serialize writes. Attendee name is a retained attendance snapshot, unaffected by later member-name changes. Member links permit inactive/archived members and can be corrected or removed by staff with member-directory access. Staff without that access can record nonmembers or correct name/status on existing attendance without erasing a preserved member link. Member choices show name, control number and status to authorized directory viewers only.

New permissions: `events.view_eventattendance`, `events.add_eventattendance`, `events.change_eventattendance`, `events.view_eventattendancelog`. Active staff, dashboard access and `events.view_event` are also required. `members.view_member` is required to select/change links or open member records. Existing ordinary-role assignments remain unchanged. Attendance/history have no public endpoint, use no-store responses, and preserve CSRF and escaping.

## Schema and preservation

Applied **`events.0004_open_event_attendance`** after a verified private native-MySQL dump (111,954 bytes; checksum retained in local evidence). The migration adds two tables only:

- `EventAttendance`: UUID submission/reference key, protected Event, attendee name (200 characters), optional protected Member, constrained Attended/Absent status, recorded/updated timestamps and optimistic version.
- `EventAttendanceLog`: protected attendance, nullable actor plus retained label, recorded/corrected action, required notes, before/after JSON, timestamp and optional IP.

Existing event, registration and audit schemas/data are untouched. Before/after and post-test comparisons matched original rows across **43 existing tables**, including all historical auth metadata up to original IDs. Only four new permissions, two content types and one migration row were added. Both new attendance tables remain empty in the normal database; synthetic fixtures stayed in disposable `test_santolan_pwd`. No settings, environment, dependency or real role/configuration changes.

Private evidence: `.local/qa-gap002-20260930/before-database.sql`, `migration-before.json`, `migration-evidence.json`, `post-test-preservation.json`, verified `before-source/` and `before-notes/` copies. This backup was created successfully; a restore drill was not performed (GAP-018).

## Observed validation

- **247 automated tests passed** on native MySQL via `manage.py test --noinput --verbosity 1` in 74.372 seconds, including 15 new attendance cases. Coverage includes privacy/permissions, malformed/forged submissions, timing, capacity independence, inactive/archived member links, retained names, link/unlink corrections, stale/no-op updates, transactional audit rollback, legacy preservation, database constraints/history protection, filters/pagination and concurrent retries/corrections. Earlier domain regressions also passed. The initial focused run passed 74 tests; duplicate inherited/discovered legacy cases were then removed from the new test module before the full run.
- **Two Chrome workflows passed** together in 30.164 seconds via `manage.py test scripts.membership_browser_qa scripts.open_attendance_browser_qa --noinput --verbosity 1`, using ordinary authorized staff. Open attendance: 30 responsive checks (six screens × 320/390/768/1024/1440), six Largest-text checks at 390, no duplicate IDs or page/console/resource errors. Membership rerun: 35 responsive/seven Largest-text checks. Attendance screenshots were inspected for create, corrections and mobile roster; final images retain the shared accessible horizontal table region. Results and screenshots are in `.local/qa-gap002-20260930/browser/`; membership evidence remains in `.local/qa-gap001-20260930/browser/`.
- System/database check, pending-migration check, model/migration consistency, JavaScript syntax and whitespace checks passed. Post-test application-data preservation passed again.

Initial Chrome attempts exposed an exact-label test-selector mismatch and actual 320px roster overflow. The selector was corrected to accommodate required/optional label text. The roster now uses existing Bootstrap filter/table components, wrapping text and a labelled keyboard-focusable scroll region. Reruns passed; no failure is hidden as successful evidence.

## Files and remaining scope

Changed: `events/models.py`, `forms.py`, `services.py`, `views.py`, `urls.py`; `members/views.py`; event review and member history templates. Added: migration 0004, `events/test_open_attendance.py`, attendance roster/detail templates and `scripts/open_attendance_browser_qa.py`/`.cjs`. Current operator/plan/decision/schema/progress documentation is linked separately; historical milestone evidence remains intact.

GAP-001 and GAP-002 are locally complete; 16 other work packages remain open. Association permission assignments, UAT, analytics/combined attendance reports and production recovery remain separate tasks. Historical 70% is retained; expanded-scope completion has no verified percentage. Next prerequisite is the authoritative disability classification list and legacy mapping/missing-data policy (GAP-003), followed by status privacy acceptance (GAP-004); approved SI/ES alignment (GAP-007) is independent of unresolved encodings.
