# Revised 70% validation — 2026-10-07

Authority: [[CURRENT_SYSTEM_SPECIFICATION]], [[Development Roadmap]] and [[Decisions#DEC-024 — Revised 70% implementation and conservative operating policies]]. The owner explicitly defined the milestone as the first seven revised stages. This is local implementation acceptance, not production readiness, percentage of all requirements, or association UAT.

## Observed result

**253 automated tests passed in 110.855s**, including disposable-MySQL concurrency regressions and the two-phase headless-Chrome workflow. Browser checks passed at 320, 390, 768, 1024 and 1440 px with zero JavaScript errors. Five migrations applied locally; **382 original rows across 45 tables were preserved**, with old application states retained in `legacy_status`.

Command: `.\.venv\Scripts\python.exe manage.py test accounts announcements assistance core documents events ewaf members membership programs scripts.revised70_browser_qa --noinput`.

`manage.py check --database default`, `makemigrations --check --dry-run` and `git diff --check` passed. The test runner created and destroyed `test_santolan_pwd`; temporary media and synthetic Admin/member records were used. No operational photo/member record was submitted to an external service. No deployment was performed.

## Accepted stages and meaningful coverage

1. Foundation: native MySQL/Django, migration consistency, retained environment/startup conventions and private storage. Existing source and actual database were backed up before edits/migration.
2. Admin RBAC/Public Information Portal: retained authentication/session/permission/CSRF tests; required public information pages, public-only optional TTS, shared accessibility controls and permission-aware navigation. No Member account, inbox or public membership submission.
3. In-person membership/documents: retained onsite intake/manual verification/approval tests, exact Help Desk guidance, explicit document verification, validity/hash/member-version provenance and reuse without repeated upload. Revocation/expiry/missing evidence cannot pass current eligibility/final processing.
4. Member records/general announcements/CMS: retained audited profile/status changes and general announcement publishing; new plain-text CMS drafts/authorized publication/withdrawal, optimistic concurrency, immutable revisions and rollback/XSS/RBAC tests. Historical program applicant announcements are excluded from public detail/list/image queries.
5. Programs/events: approved photo instructions and selection method before applications; optional explicit disability qualification, never a score/universal requirement. Organizational events link to a Program Application; new attendance requires a selected active Verified Member. Historical attendance/registration corrections retain original associations. Event application context cannot change after applications exist.
6. Applications/photo review: generic four-field membership matching, grant expiry/throttling/version checks, mandatory scrubbed JPEG/PNG calendar photo, private review/access history, canonical states/reference counter uniqueness, transaction rollback/idempotency/concurrency, Admin reference search and Help Desk corrections with retained photos/documents/reference. Earlier source tests expecting QR lookup, automatic applicant publication and open nonmember attendance were revised or replaced by explicit retirement/gate assertions, not skipped.
7. Eligibility/official decisions/receipt history: mandatory current manual photo; versioned eligibility/checklists and correctable Needs Information; reasoned explicit non-EWAF decisions after closing, configured slots, stale/source/document safeguards, actual receipt/void and successful-only history. Concurrent final-slot/receipt races and audit failure rollback remain tested. EWAF-dependent decisions fail closed.

## Browser evidence

Public: required information pages; membership guide without form; generic mismatch then successful verification; missing-photo validation; submission and private-safe reference confirmation; skip-link keyboard focus; text-size/contrast/reduced-motion controls; five-width overflow checks.

Admin: login; CMS authorization; photo queue; Needs Resubmission; Help Desk replacement with the same reference; manual Verified outcome; eligibility; explicit non-EWAF selection; actual assistance receipt/history. Screenshots were inspected for application, photo review and dashboard. Synthetic colored-image fixtures test the upload/review path; they do not establish human identity-verification effectiveness.

Artifacts: vault `.local/revised70-20261006/acceptance-final.txt`, `preservation-before.json`, `preservation-after.json`, source/DB backups and iteration logs; application `.local/qa-revised70/` contains browser screenshots. These local artifacts are not committed public records.

## Migration and preservation

Applied `assistance.0003`, `core.0001`, `documents.0003`, `events.0005`, `programs.0003` (all `revised_seventy_workflow`). Added CMS/revisions, document verification, program policy/counters, application state/provenance/current photo, photo evidence/reviews, document revisions/source links and optional Event→Program linkage. Reused existing users, Members, applications, documents, eligibility/decisions/releases and audit structures.

Legacy references/tokens/files/audits remain. Migration records each old application state; unfinished legacy applications become Needs Information, historical final selection/receipt is retained where present, and no legacy photo approval is synthesized. Existing programs need approved policy fields and explicit publication authorization before new applications. A one-time legacy policy completion preserves old qualification/requirement snapshots; later evaluation-rule edits are blocked once applications exist. No actual business method/photo interval was seeded.

Row fingerprints compare every original column value, substituting retained `legacy_status` for the deliberately migrated status column; new permission/content-type/migration rows are additive. The schema transition is intentionally not automatically reversible. Rollback requires a coordinated reviewed source/database/private-media recovery plan using backups and preserving any subsequent work; this task did not demonstrate full backup restoration or an RPO/RTO.

## Remaining 30% and acceptance limits

- Stage 8: configurable relevant criteria, approved weights/AHP rules, locked/versioned authorization, deterministic runs/breakdowns and automatic entire affected-pool recalculation. Legacy math/models/history are retained for audit; mutation entry points are disabled. No claim that current analytics recalculate on source corrections.
- Stage 9: authorized masked final program results/publication, collision-safe identification policy, analytics, reports/exports, remaining audit integration. General CMS/announcements are available; application close does not publish results. No new member communications channel was added.
- Stage 10: actual institutional content/access assignments/photo policies; representative PWD/assistive-technology and association UAT; complete WCAG evaluation, measured performance/recovery, production infrastructure and deployment. Browser reflow checks are not WCAG certification.
- Reopening closed/rejected/ineligible applications, exceptional decisions, actual EWAF/masking/tie/retention rules remain in [[Open Decisions]]. Help Desk-assisted correction and preservation of legacy references are already approved and must not be reopened as unanswered questions.
