# Association intake activation prerequisites and operating limits

2026-10-23. This is a review checklist, **not an activation instruction**. Ordinary settings contain no `ASSOCIATION_REGISTRATION_POLICY`; no environment, deployment configuration or working database was changed. All new intake routes/actions remain server-side unavailable until their applicable reviewed contract is supplied. Tests use explicitly fictional parameters in `membership/test_registration_intake.py`; never copy them into ordinary settings as policy.

## Required contract configuration

The owner approved the technical direction, not the missing institutional facts or numeric security values. A future separately reviewed configuration must supply the complete mapping below; there are no fallback durations, upload limits or attempt budgets in the extension. Existing global upload ceilings still apply and cannot be enlarged through this mapping.

| Keys / controls | Required review |
|---|---|
| `version`, `form_version`, `field_contract_reference` | Approved Association minimum fields, form purpose/version and acknowledgement handling, including staff encoding. Pending-intake output must not be represented as an approved membership/government-ID form. |
| `authority_reference`, `staff_assignments_reference` | Association collection/process authority and actual assignments to the specific existing staff capabilities. A technical superuser is not a source of institutional policy. |
| `privacy_version`, `privacy_notice`, `retention_reference` | Approved notice/purpose/processing basis, record and scan retention/disposal/hold/backup requirements and responsible staff. Acknowledgement is not a substitute for the processing basis. |
| `upload_policy_reference`, `upload_slots` | Approved optional pre-upload slots chosen only from `photo_2x2`, `civil_document`, `voter_certificate`; an empty list supports no pre-uploads. The envelope is physical only. Birth OR Marriage stays one civil slot; no additional Association voter alternative. |
| `file_max_bytes`, `total_max_bytes`, `body_max_bytes`, `file_count_limit` | Explicit positive reviewed bounds; per-file/aggregate/count cannot exceed existing application ceilings. Existing defaults were not newly approved. File signature checking is not malware scanning. |
| `context_seconds`, `attempt_window_seconds`, `address_attempt_limit`, `session_attempt_limit`, `reference_attempt_limit` | Explicit reviewed session lifetime, bounded request/attempt window and reference-collision retry policy. No numeric operational values are supplied by this delivery. |
| `security_review_reference`, `onsite_instructions` | Reviewed private storage/delivery, shared-device/timeout behavior, failed-upload cleanup and approved accessible onsite instructions. No contact, appointment or deadline was invented. |
| `public_enabled`, `staff_enabled` | Independent explicit booleans; neither enables the other. Missing/false gate or incomplete common contract denies the new action. Existing legacy workflows remain separately governed. |
| `correction_enabled`, `correction_procedure_reference` | Separate approved assisted/onsite correction procedure. A staff/view grant alone cannot enable corrections. Public post-submission correction is absent. |
| `onsite_enabled`, `onsite_procedure_reference`, `onsite_methods` | Separate approved identity/paper-matching and physical observation procedure/methods. Required for readiness, presented-online-printout and onsite observation actions. Sighted does not mean authentic, current, registry-verified or approved. |

The mapping is supplied through Django settings only after separate review; there is no self-approving policy editor or enable button. Strings naming documents are not evidence that those documents were institutionally approved. Reviewers must verify their actual authority, content and scope outside the feature. Changes to the retained contract digest invalidate old submission contexts; plan guidance for applicants before changing a live contract. No public recovery route is provided.

## Staff capabilities and placement

New operations require active authenticated staff, `accounts.access_dashboard`, existing `membership.view_membershipapplication`, and `membership.view_registrationintake`. Specific operations additionally require:

- `membership.encode_registrationintake`: pending printed/walk-in encoding.
- `membership.review_registrationintake`: processing review and information requests.
- `membership.correct_registrationintake`: append a retained correction under its separate procedure gate.
- `membership.onsite_registrationintake`: gated readiness/printout matching/onsite observations.
- `membership.view_registration_documents`: private attachment retrieval, separately from form viewing.

The migration defines capabilities but assigns **none**. Existing staff accounts, roles and grants remain untouched. Approved assignments must reflect who may perform the actual institutional function; superuser mechanics are not an external delegation of authority. Account active/permission checks are refreshed at service entry and again before audit writes/delivery, after record locks or file work. Final concurrent-revocation testing checks rollback when authority is removed during review.

Use **Members → Membership Reviews → Pending Association registrations** when the staff contract and permissions are ready. The new exact search uses AMR references and existing Phase 2A's presentation pattern. Older UUID membership references stay in the existing review search; program references remain under Applications & Verification. No group, role, public navigation destination or ordinary program-matching contract changes.

## Permitted foundation workflow

1. Applicant reads the confirmed five-item checklist, approved privacy notice and mandatory onsite instructions. The minimum form records name, birthdate, residence, optional contact and acknowledgement; allowed pre-uploads are optional.
2. A validated submission commits one pending intake, original revision, immutable AMR reference, request fingerprint, private attachments and action history. Identical authorized retries return it; changed retries conflict. It creates no existing `MembershipApplication`, Member, government ID, program application, assistance release or EWAF calculation.
3. The same browser session may view/print/save only the original submitted form and receipt. A different, expired or finished session cannot retrieve it using the reference. Attachments, later corrections, internal statuses and reasons are not in the public projection. The explicit Finish action revokes output access while preserving the pending record. Downloaded/printed copies remain outside the system's control.
4. Authorized staff retrieve the intake, review its current form and retained original/correction history, and download evidence only with the additional document permission. The separate completed-form print view omits private reviewer notes/history. A correct identifier never bypasses access checks.
5. Printed blank forms and walk-ins use the same pending form through authorized staff encoding. An online printout uses the original reference; gated presentation history does not create another intake. Exact declared-name/birthdate suggestions are review prompts, not reliable identity proof or automatic merges. Different accepted requests may remain separate pending records until authorized human review.
6. State transitions retain reasons and expected versions. Corrections append a new revision and return readiness/observations to review; earlier findings/files remain retained. Only approved-method observations may be recorded under the onsite gate.
7. **Stop before membership handoff.** Association identifier/manual-PRPWD relationships, OQ-27 evidence acceptance and required socioeconomic assessment are not fully authorized contracts. The service refuses handoff and the database requires its future membership link to remain NULL. Existing onsite approval remains the only implemented official membership path; do not manually copy/approve a new intake to evade the blocker. No new socioeconomic fields or trusted evidence are fabricated.

PDAO, QR, public tracking/recovery/corrections, member accounts, notifications, automated transmission, final-case reopening and institutional retention jobs are absent or blocked. No route, capability or configuration option activates PDAO or handoff in this delivery.

## Storage, disposal and disablement

Uploads use the existing private-storage and validation components with random object keys. Failed acceptance rolls back rows and attempts removal of newly written objects. If removal fails, the restricted error log records only the opaque storage key for an authorized operator to retry; no automatic cleanup job or disposal power is added. The failed submission never receives a success receipt. Production unsafe-file handling and storage/retention procedures still need security/privacy review.

New records have protected links and service-controlled append-only history. In particular, staff-linked submission contexts protect their actor relation, so deleting an account referenced by a new assisted intake can be blocked. Account deactivation/revocation uses existing controls; actual disposal/account-removal policy remains D09/D10 review work. No real account or pending-record deletion was performed or authorized here.

Disable public acceptance separately from staff review; disable correction/onsite actions independently. The current shared public gate also controls receipt output: turning it off refuses all subsequent public form/receipt requests. Retain authorized staff read access only where the staff gate remains separately approved. Do not reverse/delete schema after records exist or silently purge files/history. Working migration application and any operational disable/rollback procedure require separate review.

The unchanged startup migration guard may report the new unapplied migration on the working installation. Do not bypass it or apply the migration automatically. Disposable testing of this migration is not working-database or deployment approval.
