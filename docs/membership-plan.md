# Membership documentation and historical milestone plan

## Current requirements — 2026-10-06

Authority: [Current System Specification](../../CURRENT_SYSTEM_SPECIFICATION.md), [[Business Rules]], [[Database Plan]] and [[Workflow Acceptance Tests]]. Documentation only; no application implementation/test pass is claimed.

In-person membership at the Barangay Santolan PWD Association Help Desk, Admin-only encoding/verification, public approved requirements/guide and official internal member records. No public membership intake or member account. Preserve manual reference-link review where required, documents and audit history.

For all states/reference formats, modules, permissions, photo outcomes and EWAF governance use the primary specification; do not infer policy from the old plan. [[Open Decisions]] lists genuine ambiguities.

> [!warning] OUTDATED / HISTORICAL — earlier scope and evidence only
> Everything below retains the original dated text, checkbox states, source paths and test results. Former "current", "next", "complete" and "approved" labels refer to that revision only. They do not establish the 2026-10-06 workflow or authorize application/source/database actions now. [[CURRENT_SYSTEM_SPECIFICATION]] supersedes contradictory rules.

## Historical Milestone Plan

**SUPERSEDED — 2026-09-28 (affected workflow portions only).** The original plan below is retained to explain previous implementation and validation. Its old workflow instructions and migration commands are historical, not instructions for this documentation-only task. Unrelated controls remain in force.

Authorized on 2026-09-20: user requested “proceed with the 20% to 30% development”. Membership precedes announcement publishing under the ten-milestone roadmap. Applicable development guide sections: 16–18, 20, 48–53, 61–66, 69.

Scope: public registration; configurable membership document requirements; private uploads; permission-controlled application review; manual PRPWD hyperlink verification; approval/rejection; atomic conversion to Member; application audit history. No member login, registry API, or EWAF processing.

Affected modules: membership models/forms/services/views/admin/templates/tests, documents configuration/storage/validation, minimal members record, URL/settings/dashboard integration, migrations and documentation. Existing users and authentication remain in place.

Implementation conventions: pending/approved/rejected express the guide's required decisions. Further states/reopening need a later explicit workflow. Employment and disability descriptions are free text until categories are finalized; no encoding is inferred. Control numbers are trimmed and uppercased for storage and uniqueness; future four-field matching is not implemented. Required document names remain unseeded. Registration is closed initially; administrators configure the verified official PRPWD hyperlink, document requirements (or deliberately none), and then open registration. This is configuration, not a missing implementation.

Each submitted application stores an immutable requirement snapshot. Approval uses that snapshot, recorded verification, a locked pending row, and a unique member control number. Version checks prevent stale reviews from overwriting another reviewer. Upload paths are random and private; extension/MIME/signature and byte limits apply. Signature checks do not claim malware detection. Submission retries reuse a signed 24-hour key; a shared configurable network limit protects submission attempts.

Acceptance: application creates only Pending; only authorized staff review; document access requires a separate permission; verification actor/time/result/notes saved; approval requires verification and required uploads; approval produces exactly one member and audit event; rejection produces no member; stale/duplicate/concurrent decisions cannot corrupt state; all migrations and regression/security tests pass on disposable native MySQL; public/admin browser workflows pass on desktop and mobile; documentation reflects evidence.
