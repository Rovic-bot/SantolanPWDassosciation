> [!note] Dated plan preserved — October 10 target supersedes conflicting scope
> This plan is historical planning/implementation evidence, including any older “Current requirements” heading below. It is not authority for new work against the October 10 target. Read [[CURRENT_SYSTEM_SPECIFICATION]], [[Workflow Source Register]], [[October 10 Implementation Impact]] and [[Open Decisions]]. Preserve the owner-defined 70% milestone and accepted controls. New target changes include seven public sections/eight Admin groups, program-specific approved photo/alternative evidence, dedicated Results and workbook-derived controlled EWAF. RSVP remains approval-gated; Gemini is PROPOSED. No application code/data changes are authorized by this documentation update.

# Revised 70% implementation plan — 2026-10-06

Authority: [[CURRENT_SYSTEM_SPECIFICATION]], [[Development Roadmap]], [[Workflow Acceptance Tests]] and the owner's explicit instruction to review/implement the system through the **first seven revised roadmap stages**. This authorization supersedes the documentation-only boundary of the preceding task for this implementation task. The user also approved retaining control number/name/birthdate/contact matching, Help Desk-assisted Admin correction/resubmission and immutable old references searchable by Admin. Program photo recency and selection methods remain explicitly configurable/authorized rather than seeded policy.

## Scope and completion rule

Retain the existing Django/MySQL foundation, Admin authentication/permissions, UI and recorded data. Complete public information/CMS, onsite membership/evidence, Member records, programs/event application context, secure login-free Member applications, private required calendar photo and manual queue, canonical references/states, final eligibility and legitimate non-EWAF selection/actual receipt history.

EWAF computation/configuration acceptance remains stage eight. Existing mathematical/history artifacts are preserved; new use of the conflicting legacy computation is blocked at service boundaries. EWAF-required programs cannot select/release until current stage-eight output is available. Non-EWAF programs require an explicitly approved published method and reasoned authorized selection within slots. No fake score/rank is created to reach the milestone. Final program result publication, analytics and exports remain stage nine; retire automatic applicant-list publication and retain general announcements/CMS.

Seven accepted development stages out of ten establish the revised local milestone **70%** only after relevant checks pass. This is neither a production readiness percentage nor a claim of association UAT/WCAG certification. Do not mark complete from this plan.

## Implementation and preservation

- Relevant guide sections: 10–28 (stack, roles, portal, onsite records/documents, programs/events/application/eligibility), 41–42 (human final processing/receipt history), 48–55 (uploads/security/privacy/audit/tests), 61–66 (UI/accessibility/development/acceptance) and 68–74 (decisions/progress/current workflow).
- Affected source: `core` public CMS/routes; membership guidance; documents verification/provenance; Member document links/history; programs models/forms/services/photo/correction UI; event-to-program context and attendance controls; eligibility/selection/receipt services; publication guards; EWAF stage-eight guards; shared navigation/accessibility and focused/integration tests.
- Additive concepts: editable public content and immutable revisions; explicit document verification; program policy/authorization/public code; reference allocation counters; canonical application state and retained legacy state; current photo pointer, immutable photo evidence/reviews; reusable-document provenance and retained document revisions; optional event application-program link.
- Preserve issued references, earlier photos/documents/calculations, event attendance, decisions, releases/voids and audits. Legacy incomplete submissions need current photo/evidence review before new final processing. No backfilled automatic photo/eligibility approval.
- Preserve migration history. Remove/retire only obsolete active routes, unreachable duplicate public-intake/status code or contradictory publication behavior after checking callers/tests. Do not remove stored data to improve a percentage.
- Program requirements are locked once applications exist; changes must not silently replace existing evidence snapshots. Program-specific policies must be explicitly authorized. No invented association contact information, document lists, photo capture interval, tie policy or EWAF coefficients.

## Evidence and checks

Implementation completed and locally validated on 2026-10-07: [revised70-validation.md](revised70-validation.md). The pending checklist below is the original plan; the validation record records the actual outcome.

Baseline: `manage.py check --database default` passed; all **247 existing tests passed in 66.918 seconds** before this task's source changes. They establish the old baseline only.

Verified source backup: `.local/revised70-20261006/source-before.zip` at the vault root (286 files, including existing uncommitted work). A private native-MySQL dump and before fingerprints cover 45 existing tables. Existing program/application/event/announcement records require preservation; no operational personal data is copied into this note.

Before final acceptance: generate/review migrations; test clean schema and legacy transition; verify data preservation; test ordinary Admin permissions, forged public intake, generic matching, private uploads, concurrent references/duplicate/slot attempts, verified-document reuse, photo pending/rejection/resubmission/history, eligibility transitions, non-EWAF selection/receipt/void, blocked stale or EWAF-dependent processing, CMS draft/publication/audit and obsolete publication/status guards. Run relevant regression and browser/accessibility checks against synthetic test records only. Record actual outcomes in a separate dated validation report and update current progress honestly.

Official implementation references: [Django 5.2 migrations](https://docs.djangoproject.com/en/5.2/topics/migrations/) and [browser SpeechSynthesis API](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis). These support implementation mechanics, not association business policy.

## Current state

Implementation and local acceptance completed on 2026-10-07: **70% by the owner-defined first seven revised stages**. See [revised validation](revised70-validation.md). Stages 8–10, actual institutional policies, association UAT and production acceptance remain incomplete.
