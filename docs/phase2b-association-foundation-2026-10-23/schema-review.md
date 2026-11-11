# Exact additive schema review — Association foundation

2026-10-23. Owner authorization permits narrowly scoped additive non-EWAF migration files after matching the approved contract and existing dependencies, then testing the reviewed migration on verified disposable MySQL. No working database access is permitted.

The proposed five records are implemented in the existing membership app: `RegistrationSubmissionContext`, `RegistrationIntake`, `RegistrationRevision`, `RegistrationAttachment`, `RegistrationAction`. Existing membership/member/document models and all historical migrations retain their fields and constraints. New records hold pending data, revisions, private files, contextual output authorization and audit history; no Member/program/EWAF/assistance record is created by submission.

Dependency: the current `membership.0005_onsite_profile_capture` leaf plus Django's swappable user dependency. File storage reuses existing components; no new documents migration or deferred schema activation is needed. The migration must contain only creation of these five tables and their new-table relationships, indexes and constraints. An offline autodetector verifies the full model/migration difference and refuses unrelated changes before writing it.

Deliberate restriction within the approved Association-only scope: category is constrained to Association; only received/review/needs-information/onsite-readiness/onsite-observation states exist. The nullable future membership-application relation is constrained to NULL. It cannot be populated through direct ORM/SQL to make a pending record appear handed off. Implementing a later bridge requires separately approved rules and a reviewed additive constraint change; no bridge is claimed now.

Reference/request/context ownership and revision/upload-slot uniqueness use ordinary MySQL constraints. Online versus staff channels have matching context actor constraints. Histories use service-guarded append-only models and protected links. No grants are assigned to existing accounts. This is not a retention/deletion policy or authority to collect real data.

Migration validation will distinguish model-synchronized baseline setup from execution of the single new migration. No blanket migration command or historical migration application is allowed in the new test runner. The fixture baseline cannot establish every historical upgrade path; that limitation must remain in the completion report.
