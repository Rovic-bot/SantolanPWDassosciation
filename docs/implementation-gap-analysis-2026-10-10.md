# Implementation Gap Analysis — October 10, 2026

**Scope:** read-only Django implementation review against the October 10 TARGET; documentation output only. **Implementation baseline:** owner-defined 70% milestone (DEC-024), plus the validated DEC-025 announcement/Members navigation extension. Neither credit nor completion percentages change.

## Confirmed membership amendment — documentation only

Subsequent owner-confirmed input: [[Confirmed_Membership_and_PDAO_Requirements_2026-10-10]]; [[Decisions#DEC-027 — Confirmed Association membership and separate PDAO requirements]]. G04's future membership work must use the five Association items: Membership Application Form; one (1) **2×2 ID picture**; **Birth Certificate OR Marriage Certificate**; **Voter's Certificate**; one (1) physical **long envelope**. Support the civil-alternative group/physical completeness and separate applicable manual PRPWD/PDAO review; no combined PDAO checklist/automatic ID prerequisite.

The PDAO six-item **1×1**/whole-body calendar/medical/civil/residency list, and renewal-only original old/expired ID, are separate guidance if displayed. FR-25/26 and UC-12/AT-34 add requirement/acceptance coverage to the original register below; both requirements are PARTIALLY IMPLEMENTED through reusable existing components, with exact checklist/alternative/physical-item behavior still pending later development. Those list choices are confirmed; OQ-27 holds originals/copies, validity/corrections/substitutions, prerequisite and external currency questions. OQ-16's former membership-list uncertainty is resolved only to this extent. Existing reviewed code and implementation evidence below are unchanged; no functionality or percentage is added. The prior BR-12 unconditional-photo wording issue identified below has now been clarified in documentation to existing approved program applicability; its old observation is retained as dated evidence. Other EWAF/program-policy issues remain open.

## Executive Summary

The existing system provides a substantial reusable foundation: Admin authentication and functional permissions, onsite membership intake/manual PRPWD review, official member management, private documents and verified-document reuse, program configuration, secure member verification, atomic applications/references, manual calendar-photo review, reasoned eligibility, non-EWAF human selection, actual assistance receipts/voids, CMS and authorized masked non-EWAF result revisions.

The October 10 target requires changes around those components. Principal gaps are seven public sections and eight Admin groups; program-specific identity evidence and accessible alternatives; external authorization and locked EWAF configuration before opening; accepted criterion evidence; the complete governed EWAF pipeline and automatic recalculation; dedicated Results; dashboard analytics and reports/exports. Optional RSVP and Gemini remain approval-dependent. Existing EWAF mutation services deliberately fail closed; historical models, calculator code and ranking displays are not an operating stage-eight implementation.

**Evidence boundary:** source, forms, routes, templates, permissions, test assertions and migration definitions were inspected in the dirty working tree, including untracked components. HEAD at review was `96ff027`; HEAD alone does not represent this implementation. No Django tests, imports, server, database queries, migrations or live browser checks were executed. Recorded validation is dated evidence, not a fresh pass or production/UAT certification. Configuration values, current database migration application and actual institutional content were not independently verified.

### Authority and evidence

TARGET sources:

- [CURRENT_SYSTEM_SPECIFICATION](../../CURRENT_SYSTEM_SPECIFICATION.md), the consolidated master; [System Master Specification](<../../00 - Project Overview/System Master Specification.md>) is its index.
- [Admin Portal source extraction](<../../00 - Project Overview/Workflow References/2026-10-10/Admin Portal Source Extraction.md>) and [Public Portal source extraction](<../../00 - Project Overview/Workflow References/2026-10-10/Public Portal Source Extraction.md>), backed by the owner-confirmed originals directly in Project Overview.
- [EWAF Computation Specification](<../../00 - Project Overview/EWAF_Computation_Specification_2026-10-10.md>), [formula/cache evidence](<../../00 - Project Overview/Workflow References/2026-10-10/Workbook Formula and Cache Evidence.md>) and [EWAF Specification](<../../04 - EWAF/EWAF Specification.md>).
- [Functional Requirements and Use Cases](<../../01 - Requirements/Functional Requirements and Use Cases.md>), [Business Rules](<../../01 - Requirements/Business Rules.md>), [Open Decisions](<../../00 - Project Overview/Open Decisions.md>), [Security and Accessibility Requirements](<../../01 - Requirements/Security and Accessibility Requirements.md>), [Database Plan](<../../03 - Database/Database Plan.md>) and [acceptance tests](<../../06 - Testing/Workflow Acceptance Tests.md>).
- [Development Roadmap](<../../05 - Development/Development Roadmap.md>), [System Development Progress](<../../05 - Development/System Development Progress.md>) and [implementation impact](<../../05 - Development/October 10 Implementation Impact.md>) separate target backlog from completed work.

Source priority remains Admin V2 → Public document → workbook mathematics → non-superseded specifications → history. Examples, proposals and legacy code do not approve policy. The actual workbook is `Computation - final.xlsx`; the owner resolved the requested filename/location discrepancy. No original document/workbook was changed.

Recorded CURRENT acceptance: [revised70-validation](revised70-validation.md) reports 253 tests, disposable-MySQL concurrency and Chrome checks at five widths; [announcements-members-validation](announcements-members-validation.md) reports 272 tests and the scoped publication/navigation extension. [Policy authorization review](policy-authorization-review.md) records legacy-program authorization recovery. These counts describe earlier runs and must not be added together as new coverage.

### Classification and priority

- **IMPLEMENTED:** the scoped requirement has a working code path and relevant test assertions/recorded acceptance. This does not establish production readiness.
- **PARTIALLY IMPLEMENTED:** compatible functionality exists, but the full target needs additions.
- **NOT IMPLEMENTED:** no enabled implementation of the target functionality was found. A shell, enum or historical display is insufficient.
- **REQUIRES REFACTORING:** existing behavior encodes an incompatible workflow assumption.
- **PENDING CLIENT APPROVAL:** expected behavior or numerical policy is unresolved; do not infer a default.

P0 = integrity/policy dependency before affected live operation; P1 = core target workflow; P2 = reporting/content/readiness extension. Priorities order future work and do not authorize implementation. A mixed requirement is classified by its unfinished target behavior; already working subfunctions retain credit below.

## Module-by-Module Gap Analysis

### Admin 1 — Dashboard

**G02 — Actual overview cards, analytics charts and action center — NOT IMPLEMENTED.**

- **Current/components:** [core/views.py](../core/views.py) `dashboard()` renders [dashboard.html](../templates/admin_portal/dashboard.html) with permission-aware navigation/actions, but supplies no counts, chart datasets or computed action center. `analytics/` contains app registration only.
- **Missing/conflict:** registered/active/inactive/pending membership, available programs, events, submitted applications, evidence reviews, eligible applications and unpublished results are not calculated. Membership/application/eligibility/assistance/participation trends and configuration/deadline alerts are absent.
- **Recommendation:** add authorized aggregate/query services and accessible tables behind charts. Reuse existing queues and distinguish submission, selection, attendance and actual release. Derive program availability from the authoritative gate rather than a card-specific rule.
- **Dependencies/priority:** G06/G10/G12/G16 for the corresponding metrics; G23 metric definitions; P2. Existing record counts can precede EWAF completion without fabricating EWAF values.
- **Required tests:** independently seeded count/filter/date fixtures; voids/cancellations; permission boundaries; pending versus final outcomes; zero/missing data; chart text alternatives and bounded query/load behavior (AT-21/24/25).

### Admin 2 — Members

**Reusable implemented behavior:** onsite Admin encoding/manual PRPWD/approval, official member creation only after approval, optional email, directory search by name/control number, active/inactive/archive handling, protected profile/document/history access and corrections with reasons/versions. Evidence: [membership/services.py](../membership/services.py) `submit_application()`, `record_verification()`, `decide_application()`; [members/views.py](../members/views.py) `member_list()`/`member_detail()`; [members/services.py](../members/services.py) `update_member()`/`change_status()`. Tests include `MembershipTests.test_ordinary_staff_complete_onsite_review_with_legacy_public_intake_closed`, `test_approval_copies_profile_once_and_preserves_application`, and `MemberManagementTests.test_changes_roll_back_when_audit_fails`.

**G03 — 2.1 directory filters and complete review visibility — PARTIALLY IMPLEMENTED.**

- **Current/components:** `member_list()` supports text/status filtering and pagination; pending intake is in `membership.views.application_list()`. Profile, documents and confirmed assistance are separately permission-gated.
- **Missing/conflict:** directory disability-classification filter and the consolidated pending-membership view/submodule mapping are absent. Apparent/non-apparent classification is not represented.
- **Recommendation:** reuse both lists under Members; add approved classification filtering and clear links to pending review without turning an unapproved intake into an official Member. Implement apparent/non-apparent only if appropriate and approved.
- **Dependencies/priority:** approved reference data/OQ-16/26; G01; P2.
- **Required tests:** approved/unknown/inactive classification filters, pending versus official separation, pagination and direct permissions. Retain [members/tests.py](../members/tests.py) `test_search_filters_and_pagination` and `test_history_requires_separate_permission`.

**G04 — 2.2 necessary intake fields/draft and 2.3 return-for-information review — REQUIRES REFACTORING.**

- **Current/components:** [members/models.py](../members/models.py) `PersonalRecord` requires exact `monthly_income`, employment description and dependents; [membership/forms.py](../membership/forms.py) `ApplicationForm` requires disability classification. [membership/models.py](../membership/models.py) permits Pending/Approved/Rejected. Pending submission requires the complete form; approval checks required uploads exist and successful PRPWD, while document verification in [documents/views.py](../documents/views.py) resolves an already-created Member.
- **Missing/conflict:** no incomplete intake draft, guardian/authorized representative, structured PWD-ID status, necessary-only income range/evidence status, dependents evidence status, or distinct reasoned return/correction workflow for pending membership. Presence of a file is not the requested per-document assessment.
- **Recommendation:** extend internal intake/review and add accepted evidence/provenance while preserving official-member creation and manual PRPWD. Keep existing exact-income/history values; do not automatically convert them into verified ranges or fabricate guardian records.
- **Dependencies/priority:** OQ-16/23/26 for field necessity, document/declaration definitions and representative procedure; additive schema design; P1.
- **Required tests:** partial draft cannot become Member; returned intake correction preserves evidence/history; approval requires applicable completed review; duplicate/concurrent approvals; optional email/representative cases; no public intake. Retain [membership/tests.py](../membership/tests.py) approval, rollback, token and private-download regressions (AT-01/02).

**G05 — 2.4 supported corrections and dependent reevaluation — PARTIALLY IMPLEMENTED.**

- **Current/components:** `update_member()` stores old/new profile values, reason and version in `MemberEvent`; document reviews record digest/expiry/member version. [documents/services.py](../documents/services.py) `reusable_documents()` and `program_document_current()` reject stale reused evidence. Downstream eligibility/selection becomes stale after relevant member changes.
- **Missing/conflict:** no correction proposal/supporting-evidence/independent-review workflow; no automatic affected-pool recalculation. All profile version changes can invalidate evidence conservatively; refinement needs an explicit dependency design.
- **Recommendation:** preserve existing corrections and stale guards; add approved high-impact review/evidence where practicable and connect accepted source changes to G17. Do not weaken stale checks before replacements exist.
- **Dependencies/priority:** G12/G17; OQ-09/23/26; P1. Independent review remains qualified, not a newly invented role.
- **Required tests:** before/after/provenance, rejected proposal changes nothing, approved correction retains old intake/run, affected dependency invalidation, audit failure rollback. Retain `MemberManagementTests.test_profile_update_keeps_original_application_and_records_before_after` (AT-16/22).

**2.5 Membership Content — IMPLEMENTED for plain-text approved guidance and configurable document lists.** Reuse [core/content.py](../core/content.py) and document-type/requirement administration; G21 covers target wording and remaining approved content. Institutional values still require approval.

### Admin 3 — Programs & Events

**Reusable implemented behavior:** audited drafts/publication/cancellation/archive, schedules, windows, slots, private budget, benefit/type, configurable document/text/acknowledgement requirements, optional explicit disability qualification, selection-method/photo instructions and authorization actor/time. [programs/services.py](../programs/services.py) guards versions, locks submitted requirements and serializes submission; [events/services.py](../events/services.py) preserves event/attendance history. These do not yet implement every V2 field or policy gate.

**G06 — 3.2–3.4 proposal/external approval and complete configuration before opening — PARTIALLY IMPLEMENTED.**

- **Current/components:** [programs/models.py](../programs/models.py) `Program.registration_available` checks publication/window, `policy_authorized_at`, photo instructions and selection method. `change_publication()` records internal authorization; `save_program()` freezes selected rules after applications exist.
- **Missing/conflict:** no external authority/status/reference/evidence/date or proposal/allocation-reference model; no Program→approved locked EWAF configuration link. An EWAF program can currently pass the application-opening gate without a usable configuration, although final selection/publication correctly remain blocked.
- **Recommendation:** record required offline approval and approved configuration/version; gate publish/open/verify/submit as applicable. Separate internal policy authorization from external approval. Keep non-EWAF operation and the legacy `authorize_policy` recovery path.
- **Dependencies/priority:** OQ-09/26 duties/applicability; G11/G14; P0 before opening affected EWAF/external-approval programs.
- **Required tests:** incomplete/unauthorized/draft configuration cannot open; expiry/version/race checks at submission; offline approval records cannot be forged; non-EWAF remains usable; policy audit rollback. Reuse [test_policy_authorization.py](../programs/test_policy_authorization.py) and `RevisedWorkflowTests.test_no_universal_disability_gate_and_program_policies_locked` (AT-28/31).

**G07 — 3.1 program lifecycle views and 3.2 complete public setup — PARTIALLY IMPLEMENTED.**

- **Current/components:** Program status is Draft/Published/Cancelled/Archived; [programs/views.py](../programs/views.py) `public_list()` separates current/past by closing time; [ProgramForm](../programs/forms.py) supports much of setup. Home's `current_programs` filters public records with future close dates, including upcoming/cancelled records; it does not select only currently available programs.
- **Missing/conflict:** Awaiting External Approval/Upcoming/Available/Closed/Completed management views and Available/Upcoming/Past public grouping are incomplete. Objectives/allocation references and structured accepted alternatives are absent. Future/cancelled entries must not be represented as available.
- **Recommendation:** derive time-based categories from dates and policy gates; add durable approval/completion states only where necessary. Reuse UUIDs, published records and date validation; add approved missing setup metadata. Do not equate application closure with delivered assistance or rewrite old status history.
- **Dependencies/priority:** G06/G11; OQ-26; P1.
- **Required tests:** exact opening/closing boundaries, upcoming view without Apply, cancelled/unapproved/configuration-blocked visibility, completion distinct from selection/release, Home availability and preserved snapshots. Reuse [programs/tests.py](../programs/tests.py) `test_registration_time_boundaries`, `test_slots_do_not_limit_applications_and_duplicates_are_idempotent` (AT-04/31).

**G08 — 3.5 event calendar/annual activities and participation configuration — PARTIALLY IMPLEMENTED.**

- **Current/components:** [events/models.py](../events/models.py), [events/forms.py](../events/forms.py) and [events/views.py](../events/views.py) implement schedules, venue, capacity planning, images/alt text and upcoming/past lists. New `save_attendance()` requires a selected active member from the linked Program and current verified photo; retained historical attendance can be corrected.
- **Missing/conflict:** no month calendar, approved annual-awareness management, structured audience/accessibility settings or independent RSVP records. The member-only new-attendance restriction is CURRENT behavior, not approval of every target event's audience. Capacity currently represents venue planning, not a newly approved RSVP/admission policy.
- **Recommendation:** reuse list/detail/schedule and protected attendance services; add accessible month/list views and approved information. Branch intake by approved event policy only after G09; retain historical nonmember records and associations.
- **Dependencies/priority:** G09/G11; OQ-05/26 actual event dates and audience; P2 for calendar, P1 after approval for participation.
- **Required tests:** calendar time zones/month edges, list equivalence, accessibility, linking restrictions, duplicate retries/corrections, public/member-only policies once approved. Inspect assertions, not names: [test_open_attendance.py](../events/test_open_attendance.py) `test_nonmember_intake_has_atomic_audit_and_no_capacity_or_identity_gate` now asserts nonmember creation is rejected; its title is historical.

**G09 — optional event-specific RSVP — PENDING CLIENT APPROVAL.**

- **Current/components:** `Event.registration_available` always returns False; `events.views.register()`/`registered()` return 410 and `register_member()` raises. Legacy `EventRegistration` remains for history. There is no enabled new RSVP flow.
- **Missing/conflict:** audience, enabling authority, minimal fields, duplicates, cancellation/capacity/admission and retention are unresolved. Re-enabling old registration would silently adopt superseded rules.
- **Recommendation:** keep intake disabled; after approval implement a separate intention record and separate confirmed-participant/actual-attendance metrics. Reuse secure verification only for approved member-only RSVP. Never count RSVP/attendance as PA.
- **Dependencies/priority:** OQ-05/16; approved policy is P0, feature is P2 optional.
- **Required tests:** unapproved/disabled no intake; approved audience validation; permitted minimal fields; duplicate/cancellation/capacity semantics; no automatic selection/admission/attendance/PA (AT-29). Existing [events/tests.py](../events/tests.py) retirement and historical-capacity assertions are preservation tests, not target RSVP acceptance.

### Admin 4 — Applications & Verification

**Reusable implemented behavior:** `verify_member()` matches control/name/birthdate/contact against an active official record using conservative normalization; views throttle verification and store program/member/version-scoped bounded grants in the server-controlled session. `submit_application()` rebuilds requirements under locks, rechecks membership/policy and creates one application/reference atomically. Verified internal documents are reused with digest/expiry/version provenance. Manual photo and eligibility remain distinct. Tests: [programs/tests.py](../programs/tests.py) generic mismatch, grant scope/expiry, changed membership, duplicate/concurrent submission and audit/upload rollback; [test_revised_workflow.py](../programs/test_revised_workflow.py) submission versus verification and retained evidence.

**G10 — 4.1 consolidated All Applications and 4.7 evidence/EWAF readiness — PARTIALLY IMPLEMENTED.**

- **Current/components:** `programs.views.applications()` offers per-program reference/member/status search; [assistance/views.py](../assistance/views.py) `queue()` offers cross-program member/program text and eligibility/decision filters; [photo_views.py](../programs/photo_views.py) has a private photo queue. The cross-program queue does not search public references or provide a program selector/full lifecycle filter/readiness.
- **Missing/conflict:** V2 consolidated application inventory, flagged contradictions, per-criterion completeness and usable EWAF-ready pool are absent. `EWAF_READY`/`RANKED` enum values do not establish enabled transitions.
- **Recommendation:** consolidate queries and links under Applications & Verification; reuse object/history permissions and add readiness derived from current approved evidence, eligibility and configuration. Do not change application records merely to display a queue.
- **Dependencies/priority:** G01/G11/G12/G14/G16; P1.
- **Required tests:** combined program/reference/member/state filters, cross-program ownership, separate history permissions and stale/incomplete evidence never ready (AT-03/09/31).

**G11 — 4.3 conditional calendar photo/approved accessible alternative — REQUIRES REFACTORING.**

- **Current/components:** [programs/forms.py](../programs/forms.py) `ApplicationForm.calendar_photo` is universally required. [workflow.py](../programs/workflow.py) `store_photo()`, `require_verified_photo()` and `correct_application()` assume a current photo; eligibility, selection, release, result collection and new event attendance call the photo gate. Photo states/reviewer/reasons/versions/private delivery and corrections already work.
- **Missing/conflict:** no approved required/not-required applicability, alternate identity evidence or durable alternative review route. Simply making the form optional would leave downstream gates broken or encourage fake verification. Help text and receipt/CMS defaults also assume a mandatory photo.
- **Recommendation:** add versioned program evidence policy and approved state mapping, then replace unconditional downstream prerequisites with one applicable-evidence guard. Preserve the photo route and all old photos/reviews/references; record not-required applicability separately. No AI/facial recognition.
- **Dependencies/priority:** OQ-02/24 approved alternatives, recency, assistance and state design; G06; P0 dependency/P1 implementation.
- **Required tests:** required-photo, approved alternative and no-additional-evidence routes; missing policy blocks; failed/pending applicable evidence blocks all downstream consumers; retained resubmissions; permissions/storage/audit failure/concurrency. Retain photo-negative tests and extend them by policy (AT-06/08/28).

**G12 — 4.4 supporting evidence and 4.5 criterion evidence assessment — NOT IMPLEMENTED as a complete accepted-input workflow.**

- **Current/components:** [documents/models.py](../documents/models.py) `DocumentVerification` stores a boolean review, reason, reviewer, expiry, digest and member version. Eligibility checklists record pass/fail/review. Member socioeconomic/employment/dependent fields are raw profile values; [ewaf/models.py](../ewaf/models.py) `ApplicationInput` has relevance/socioeconomic fields without criterion evidence states. Mutating EWAF inputs is disabled.
- **Missing/conflict:** no per-criterion Declared/Needs Review/Verified/Rejected assessment, accepted value/type, source/evidence version, dispute resolution or assessment-completeness gate. Raw presence/declared income cannot establish accepted scoring input.
- **Recommendation:** reuse protected document reviews and checklist provenance, adding criterion assessment snapshots with approved evidence/rubrics. PA comes from official successful releases, not an editable counter. Keep incomplete/disputed scoring unusable without inventing imputation or automatic ineligibility.
- **Dependencies/priority:** OQ-06/07/08/18/19/23; G04/G14; P0 before live scoring, P1 implementation.
- **Required tests:** declared cannot score; approved assessment sources/encodings; missing/disputed/expired/revoked input; correction preserves history; PA excludes voids, attendance and undelivered selections; no favorable/zero/midpoint default (AT-05/13/31).

**G13 — 4.6 eligibility and branched lifecycle across new routes — PARTIALLY IMPLEMENTED.**

- **Current/components:** [assistance/services.py](../assistance/services.py) `review_eligibility()`/`require_current_review()` check current photo, member/program versions, required evidence and checklist. Confirmed failure is needed for Ineligible; correctable review uses Needs Information. Decision does not equal eligibility. Arbitrary canonical status edits are restricted.
- **Missing/conflict:** full alternative/no-photo lifecycle and transitions through accepted criterion input/EWAF are absent. In preliminary public qualification checking, both missing classification (`needs_information`) and definite mismatch (`ineligible`) render [ineligible.html](../templates/programs/ineligible.html) with the same heading; neither creates a submitted application, but clearer corrective guidance is needed.
- **Recommendation:** retain current evidence/eligibility gates, extend applicable routing and expose distinct recoverable versus definitive outcomes. Decide approved terminal-reopening/waitlist paths before adding them; do not turn Needs Information into eligibility or selection.
- **Dependencies/priority:** G11/G12/G16; OQ-03/13/24; P1.
- **Required tests:** every allowed/disallowed branch, no direct jumps, stale grant/review/configuration/evidence, respectful corrective messages, eligible pool only after all applicable gates. Retain [assistance/tests.py](../assistance/tests.py) `test_required_original_items_must_exist_and_pass`, `test_review_form_rejects_member_or_program_changed_since_opening` (AT-05/09/17).

### Admin 5 — EWAF & Selection

**G14 — 5.1 configuration, 5.2 draft AHP and 5.3 authorization/lock — NOT IMPLEMENTED as a governed live workflow.**

- **Current/components:** [ewaf/models.py](../ewaf/models.py) `Configuration` stores immutable-on-instance-save JSON matrix/encodings/bounds/thresholds and creator/time. [forms.py](../ewaf/forms.py) includes legacy JSON forms. [services.py](../ewaf/services.py) `save_configuration()` always raises after checking permission; [views.py](../ewaf/views.py) renders the unavailable notice.
- **Missing/conflict:** no program association, criterion-definition/evidence metadata, configuration family/version/effective date/reason, draft/authorization/lock states, approver/approval date, stored complete AHP preview or active-version pointer. Fixed five criteria and form order cannot represent substantive authorized alternatives. `save()` immutability alone does not protect bulk updates or all future service/API paths.
- **Recommendation:** extend/reuse historical configuration storage with explicit versioned governance and approved criterion order/count/method. Keep historical rows unchanged. Validate complete definitions and numerical rules before authorization, lock before opening, and enforce invariants beyond editable UI.
- **Dependencies/priority:** OQ-06–12/18/19/23/25; G06/G12; P0 dependency/P1 implementation.
- **Required tests:** draft edits/audits; incomplete/inconsistent cannot activate; permission-separated authorize/lock; same locked version across program; no privileged score/rule edits or old-row deletion; new authorized revision preserves original (AT-11/12/14/30/31).

**G15 — 5.2/5.5/5.6/5.7 workbook math, approved directions and scale — REQUIRES REFACTORING.**

- **Current/components:** [ewaf/calculation.py](../ewaf/calculation.py) `ahp()`, `validate_configuration()`, `calculate()` implement column-normalized row-average weights, consistency and per-input Min–Max/weighted sum in Decimal. [ewaf/tests.py](../ewaf/tests.py) asserts an all-ones matrix, invalid inputs and inverse income/PA behavior.
- **Missing/conflict:** `CRITERIA`/n/RI are fixed; monthly-income SI and PA inverse direction is enforced despite OQ-18/19. Return values omit normalized AHP matrix/column totals and explicit weighted contributions; score is quantized to 20 decimal places on 0–1 scale, while target EWS is explicitly 0–100. No independently checked actual workbook fixture exists in this test file. Threshold and precision rules are not approved by passing synthetic tests.
- **Recommendation:** retain sound algebra as an isolated reusable kernel; make criterion/order/RI/direction/precision policy explicit and approved, expose/persist intermediates and versioned contributions, and separate 0–1 WSM from 0–100 EWS. Never import broken or pasted workbook cells as operational values.
- **Dependencies/priority:** OQ-10/11/12/18/19/25; G14; P0 numerical-policy dependency/P1 implementation.
- **Required tests:** actual matrix independently derived, row/column reorder invariance, finite/reciprocal/inconsistent matrices, approved dimensions/RI, both directions as mathematical fixtures, invalid inputs, weight sum/contributions/scale and approved band boundaries (AT-12/13/30). Synthetic fixtures are not production configuration.

**G16 — 5.4 accepted input snapshots and 5.8 usable program ranking — NOT IMPLEMENTED.**

- **Current/components:** `RankingRun`/`Snapshot` retain run/application/configuration, raw/encoded/normalized values, weights, consistency, score/classification/rank/context. `ranking()` displays historical runs. `save_input()`, `generate_ranking()` and `current_ranking()` fail closed in [services.py](../ewaf/services.py); `require_ranked()` cannot authorize selection.
- **Missing/conflict:** no enabled eligible-pool calculation, complete source cutoff/bounds/assessment snapshots, contribution history, run completion/failure/currentness, guarded promotion or current program ranking. Display ordering of historical snapshots is not an approved tie-break.
- **Recommendation:** reuse historical links with new immutable complete-run semantics; calculate the entire current eligible pool using one locked version, atomically promote only a successful complete run and show evidence flags/breakdowns. Keep stale/failed/partial results unusable.
- **Dependencies/priority:** G11–15; OQ-08/11/12/13; P1.
- **Required tests:** independent multi-applicant pool, only current eligible/assessment-complete inputs, rank by stored precision, true ties versus rounded display, no partial promotion, stale evidence/configuration/eligibility, competing runs, history retained (AT-13/14/15).

**G17 — 5.10 authorized revisions and automatic full-pool recalculation — NOT IMPLEMENTED.**

- **Current/components:** profile/document/photo corrections preserve history and invalidate processing; legacy configurations are immutable and runs retained. There is no enabled recalculation service or source-correction trigger.
- **Missing/conflict:** no configuration revision authorization, dependency detection, idempotent full affected-pool recomputation, failure/retry history or freshness linkage to selection/publication. Existing program service blocks evaluation-rule changes after applications; that is a preservation guard, not controlled same-program revision.
- **Recommendation:** add version-preserving authorized revision orchestration and accepted-source-change triggers. Recalculate every affected eligible application and any dependent normalization/ranking; selection/publication must reject stale outputs until a complete current result exists. Preserve old rules, runs, decisions and publications.
- **Dependencies/priority:** G05/G12/G14–16; OQ-08/09/11/12 including release/void impact on PA; P1.
- **Required tests:** full pool versus favored subset, concurrent correction/run, retry idempotency, old outputs unchanged, rollback/failure and stale selection/publication gates (AT-15/16/22).

**G18 — 5.9 human selection with current EWAF, waitlists/exceptions — PARTIALLY IMPLEMENTED.**

- **Current/components:** `decide_assistance()` records separate explicit reasoned selection after closing, current eligible review and slot locking; non-EWAF selection works. `record_release()`/`void_release()` preserve actual delivery distinctly. EWAF branches invoke the disabled `require_ranked()`.
- **Missing/conflict:** current EWAF run linkage/selection review is unavailable. `WAITLISTED` is only an enum; no approved enabled waitlist or exception workflow. No automatic high-score selection is implemented, which should be preserved.
- **Recommendation:** integrate G16 current-run validation with existing decision and slot services. Preserve computed score/rank and decisions separately; enable ties/waitlists/exceptions only under approved program policy. Add approved PA scope to existing successful-release query, without counting approvals/attendance.
- **Dependencies/priority:** G13/G16/G17; OQ-04/08/13/15; P1, optional policies approval-gated.
- **Required tests:** highest rank alone selects nobody; current run prerequisite; concurrent last slot; rank/score unchanged by decision; Not Selected differs from Ineligible; stale/revoked review; actual receipt/void and PA cutoff. Reuse [assistance/tests.py](../assistance/tests.py) `test_last_slot_can_only_be_approved_once`, `test_simultaneous_release_creates_one_record_and_log`, `test_events_pending_cancelled_and_rejected_never_count` (AT-17/18).

### Admin 6 — Announcements & CMS

**Reusable implemented behavior:** general drafts/publication/withdrawal/history, versioned plain-text CMS, generated safe non-EWAF result drafts, privacy-confirmed publication, immutable revisions, collision handling and read-time source freshness. [announcements/results.py](../announcements/results.py) `collect_results()`, `prepare_results()`, `publish_results()`, `results_current()` and [models.py](../announcements/models.py) `AnnouncementQuerySet.published()` enforce source guards. No automatic deadline applicant publication remains; [program_publication.py](../announcements/program_publication.py) fails closed.

**G19 — 6.2 official Results destination and notice links — NOT IMPLEMENTED.**

- **Current/components:** safe result payloads appear under `announcements.views.public_detail()` and [public_detail.html](../templates/announcements/public_detail.html). [core/urls.py](../core/urls.py)/[config/urls.py](../config/urls.py) provide no dedicated Results destination; [context_processors.py](../core/context_processors.py) exposes six sections.
- **Missing/conflict:** official Results list/detail/archive and Announcement notice→Results navigation are absent. Publication payload includes eligible count/slots/selected rows/method; additional submitted/selected aggregates and disclosure examples need review.
- **Recommendation:** reuse the same authorized revision and freshness gate for Results and notices. Archive past authorized public results by approved program/date semantics; do not expose withdrawn/private revisions as an archive. Keep current DEC-025 masking, process explanation and private Help Desk guidance; new aggregate/disclosure policy remains G27/OQ-22.
- **Dependencies/priority:** G01/G20/G27; current non-EWAF projection can be reused before EWAF; P1.
- **Required tests:** published-only list/detail/archive; no stale/withdrawn/legacy applicant rows/images; notice points to same revision; collisions/context review; no complete references, scores, tokens or evidence; current-page indication (AT-19/27/32).

**G20 — result publication across conditional identity/EWAF workflows — PARTIALLY IMPLEMENTED.**

- **Current/components:** `collect_results()` requires finalized current decisions for all applicable applications, manually verified photo and current eligibility; refuses EWAF programs. Immutable `ProgramResultRevision` retains previous content/source digest. [announcements/test_results.py](../announcements/test_results.py) asserts stale/expired evidence withholds public reads, forged rows cannot override output and audit failure rolls back publication.
- **Missing/conflict:** new applicable-identity gates and successful current EWAF/selection provenance are not supported. Eligibility explanation hard-codes photo review. Publication must eventually validate new accepted evidence/run changes, while actual receipt remains distinct from authorized Selected output.
- **Recommendation:** extend existing projection/fingerprint instead of replacing it. Add only approved allowlisted context; preserve explicit prepare/preview/privacy confirmation/publish and source freshness. Any performance optimization must retain correctness after source changes.
- **Dependencies/priority:** G11/G16–18; OQ-22/25 public disclosure; P1.
- **Required tests:** conditional evidence, stale/failed/incomplete EWAF, original rank remains private, source correction withdraws visibility, receipt leaves valid selection visible and void requires reassessment, concurrent preparation/publication (AT-19/22/32).

**G21 — 6.1 notices and 6.3 current CMS/help wording — PARTIALLY IMPLEMENTED.**

- **Current/components:** [core/content.py](../core/content.py) `published_content()`/`save_content()` support Home/About/Membership/Contact/FAQ/Privacy/Accessibility/EWAF/application guidance with authorized revisions; program/event descriptions and announcements are editable. Plain-text output is escaped. No Gemini dependency exists for FAQ/help.
- **Missing/conflict:** fallback FAQ/application/accessibility text, receipt and event/public templates retain universal-photo or Announcements-only guidance. Annual calendar/content organization is incomplete. Free-text general announcement publishing cannot automatically establish that a human has not pasted sensitive information; generated result fields are protected separately.
- **Recommendation:** align approved fallback content/notice links with Results and applicable evidence, preserve CMS history and human privacy review, and reuse plain-text About content for mission/vision/services/approved leadership. Add structured content only where useful and approved, without creating fake institutional details.
- **Dependencies/priority:** G08/G11/G19; OQ-16/26 actual content; P1 wording/P2 content extension.
- **Required tests:** draft versus published/withdrawn content, escaped output, no generated-score/reference editing, conditional guidance, result notices, non-AI FAQ/help usable (AT-20/27). Reuse [test_content.py](../core/tests/test_content.py) `test_draft_publish_edit_and_withdraw_have_retained_versions`, `test_permissions_stale_content_and_audit_rollback`.

**G22 — 6.4 Gemini assistant — PENDING CLIENT APPROVAL.**

- **Current/components:** static/versioned FAQ and human Help Desk fallback exist; no enabled Gemini client, service, routes or assistant UI was found in inspected apps/templates.
- **Missing/conflict:** proposed scope/API/privacy/cost/grounding/input-retention/safety rules are unapproved.
- **Recommendation:** retain independent FAQ/help; only after OQ-20 approval design published-CMS-only assistance with backend credentials, uncertainty and accessible human fallback. No private retrieval, identity verification or eligibility/scoring/selection decisions.
- **Dependencies/priority:** OQ-20/16; P2 optional after approval.
- **Required tests:** conditional AT-33 grounding, stale/draft exclusion, injection/privacy/cost controls, no private data, keyboard/screen-reader fallback. These are planned tests, not evidence of an assistant.

### Admin 7 — Reports & Exports

**G23 — traceable reports, analytics and PDF/Excel/CSV exports — NOT IMPLEMENTED.**

- **Current/components:** `reports/` and `analytics/` contain app declarations only; root routing has no report/analytics routes. Existing member/application/eligibility/assistance/event lists and successful-release query are reusable record sources, not implemented report generation.
- **Missing/conflict:** membership/demographics, applications, eligibility, participation, confirmed assistance, EWAF/selection, RSVP/attendance, monthly/year-end reporting; export authorization, generation audit, calculation export and chart alternatives. Treasurer-related reports remain “where supported”; no new finance actor/payment system follows.
- **Recommendation:** define separate metric denominators and approved fields; implement permission-checked query/report services and safe PDF/XLSX/CSV outputs. Reuse existing records; expose only approved aggregates publicly, with privacy review.
- **Dependencies/priority:** G02/G09/G12/G16/G18/G20; OQ-08/16/22/26; P2. Implement independent membership/release reports first, dependent EWAF/RSVP reports later.
- **Required tests:** independent totals/time/filter fixtures, successful non-voided releases only, submitted≠eligible≠selected≠delivered, object/export permissions, required-audit rollback, spreadsheet-formula injection protection, pagination/download privacy, accessible tables (AT-21/22).

### Admin 8 — Administration

**Reusable implemented behavior:** 8.1 Admin user/group/functional permission administration is technically superuser-restricted; 8.2 staff-only authentication, password validation/change, session revocation, CSRF, safe redirects, throttling and credential-free sign-in events work. Reuse [accounts/admin.py](../accounts/admin.py) `SuperuserManagement`, [backends.py](../accounts/backends.py) `StaffBackend`/`reserve_windows()`, [decorators.py](../accounts/decorators.py) and [audit/admin.py](../audit/admin.py) `ReadOnlyAuditAdmin`. [accounts/tests/test_accounts.py](../accounts/tests/test_accounts.py) verifies privilege-escalation prevention, revoked access, session/security controls and read-only audits. Current self-password change and privileged UserAdmin reset are reusable; do not invent email recovery or a new business actor.

**G24 — 8.3 complete audit presentation and 8.4 approved reference data — PARTIALLY IMPLEMENTED.**

- **Current/components:** SecurityEvent, Django LogEntry and domain histories exist; member/document/photo/application/eligibility/decision/publication/CMS actions are traced. Disability/document types and membership document requirements are administered. Assistance types remain free text; membership state semantics are fixed, not arbitrary label-configurable workflow.
- **Missing/conflict:** combined cross-domain audit filtering and new EWAF/recalculation/export events are absent. No approved program category/assistance-type catalogue was found. Reference administration must not let status relabeling bypass fixed state meanings.
- **Recommendation:** reuse domain logs with a permission-checked audit view and protected references; add new operation audits with their services. Introduce approved catalogues only with legacy-value mapping, keeping old text/history. Preserve fixed workflow invariants and least privilege.
- **Dependencies/priority:** G14–17/G23; OQ-16/26 access/data definitions; P1 audit integration/P2 catalogues.
- **Required tests:** cross-domain log permissions/filtering, no normal Admin edit/delete, before/after/reasons, credentials/private-token exclusion, catalogue deactivation/mapping and audit failure rollback (AT-03/22).

**G25 — 8.5 institutional privacy and 8.6 backup/recovery — PARTIALLY IMPLEMENTED.**

- **Current/components:** protected no-store documents/photos, public allowlists, generic verification, CSRF/escaping/throttling and environment-based security settings exist. Recorded SQL backups/preservation fingerprints in validation notes are evidence of prior backups. No integrated backup-status/recovery workflow or completed restore acceptance was found in reviewed modules/scripts.
- **Missing/conflict:** actual access matrix, retention/disposal/privacy notices, operational private-media/quarantine/orphan handling, backup monitoring and demonstrated database+media recovery/RPO/RTO are unresolved/incomplete. Configuration flags do not establish deployed HTTPS/proxy/storage security or full privacy compliance.
- **Recommendation:** approve institutional policies and protect database/media backups; demonstrate restoration in disposable infrastructure and record status/recovery duties. Add least-privilege operational controls against privileged database tampering; preserve protected audit/evidence retention obligations.
- **Dependencies/priority:** OQ-16/22; production readiness P0, application extensions P2.
- **Required tests:** unauthorized direct downloads/object swaps/cache/referrer leakage, oversized/mismatched files, deployment media exposure, backup+media restore/reference/history verification and approved retention exceptions (AT-23).

**G26 — 8.7 and global accessibility acceptance — PARTIALLY IMPLEMENTED.**

- **Current/components:** shared semantic templates, skip links, form labels, focus/status behavior, display size/contrast/reduced-motion and optional public TTS in [accessibility.js](../static/js/accessibility.js); responsive browser evidence at five widths. TTS excludes Admin records. Shared Admin/sidebar state controls exist.
- **Missing/conflict:** full screen-reader/keyboard/WCAG evaluation, adequate expiry warning/recovery, approved evidence alternatives, accessible future calendars/charts/reports and representative association/PWD UAT are not established by reflow checks.
- **Recommendation:** reuse shared controls, fix evidenced unmet criteria in each affected flow and test assistive technology with users. Do not claim universal disability support or certification. Preserve non-JS navigation and storage-failure behavior.
- **Dependencies/priority:** G01/G08/G11/G19/G23 and OQ-02/16; P1 throughout, P0 release acceptance.
- **Required tests:** AT-24–26 keyboard focus/current links/errors, screen-reader tables/status announcements, zoom/reflow/contrast/motion, public TTS start/stop, expiry recovery, accessible alternatives and representative UAT.

**G28 — required audit rollback for account security mutations — PARTIALLY IMPLEMENTED.**

- **Current/components:** [accounts/views.py](../accounts/views.py) `StaffPasswordChangeView.form_valid()` calls the parent password-change operation, then writes SecurityEvent through [audit/signals.py](../audit/signals.py) `record_event()`. No enclosing transaction is visible in that view. Existing account tests verify password/session effects and event presence; domain tests explicitly cover rollback elsewhere.
- **Missing/conflict:** code does not demonstrate atomic password change plus required audit. An audit-write failure after the parent operation could leave a changed password without its mandatory event. Sign-in/sign-out event failure behavior likewise has no demonstrated failure-path acceptance here. This is a source-derived concern, not an observed failed runtime test.
- **Recommendation:** in a separately authorized task, define and verify atomic/fail-safe account mutation and audit handling, including session consequences; preserve existing authentication behavior.
- **Dependencies/priority:** FR-18/BR-29 account-security audit contract; P1 verification/fix before release.
- **Required tests:** inject SecurityEvent failure during password change and assert agreed password/session/audit outcome; verify login/logout failure handling without credential leakage. Retain existing session-rotation/revocation tests (AT-03/22).

### Shared navigation and reference receipts

**G01 — seven Public sections/eight Admin groups — REQUIRES REFACTORING.**

- **Current/components:** [core/context_processors.py](../core/context_processors.py) defines six public links; [public/base.html](../templates/public/base.html) renders them. [workspace_header.html](../templates/partials/workspace_header.html) has many function links grouped as Workspace/Management/Activity, not the eight V2 modules. Unified Members links and sidebar scroll persistence already work.
- **Missing/conflict:** Results is missing; Admin functions/submodules need regrouping in the exact specified order. Eight groups do not imply eight new Django apps or duplicate tables.
- **Recommendation:** reuse route names, permission checks, shared UI/state and current-page indication. Map every source submodule to a permitted existing view or an honest unavailable state; no fake working controls.
- **Dependencies/priority:** G19 for the Results destination; preserve G03/G10/G14/G23 unavailable boundaries; P1.
- **Required tests:** exact ordered seven/eight groups for appropriately authorized users, filtered groups for restricted Admin, direct access unchanged, current indicators, keyboard/mobile/scroll/storage-failure regressions. Update [test_public_portal.py](../core/tests/test_public_portal.py) `test_primary_navigation_has_exactly_six_requested_destinations` with the implementation; retain `ProgramResultTests.test_unified_members_navigation_respects_permissions` in [test_results.py](../announcements/test_results.py) (AT-27).

**G27 — submission receipt and future reference/disclosure policy — PARTIALLY IMPLEMENTED.**

- **Current/components:** `workflow.allocate_reference()` plus counters/uniqueness/transactions issue immutable sequential references; [submitted.html](../templates/programs/submitted.html) displays a session-scoped receipt, save/print guidance, pending-photo explanation and Announcements/Help Desk. Status/QR routes return 410; full reference possession does not grant private access. Existing reference preservation/search/idempotency tests are implemented safeguards.
- **Missing/conflict:** receipt lacks Results guidance and conditional-evidence wording/copy affordance. Future random references and new masks/aggregates are unresolved; existing generation is owner-approved CURRENT behavior, not permission to renumber old receipts.
- **Recommendation:** improve accessible receipt wording/link/copy support with G19/G11 while preserving identifiers. Leave generation and broader disclosure unchanged until OQ-21/22. Private clarification is Help Desk guidance, not a public lookup or a new account/ticket requirement.
- **Dependencies/priority:** G11/G19; OQ-21/22 for policy changes; P1 receipt, future reference policy approval-gated.
- **Required tests:** retained reference under retries/corrections/concurrency, receipt/session privacy and accessible save/copy/print guidance, Results link and no promise of selection, no tracker/member inbox (AT-07/10/32).

### Public Portal — all seven sections

| Section / requirement | TARGET status | CURRENT evidence and remaining gap |
|---|---|---|
| Home: published welcome, news, available programs/upcoming events and help | PARTIALLY IMPLEMENTED | `core.views.home()`/`public/home.html` and CMS work. Available-program query, Results navigation and revised guidance need G01/G07/G21. |
| About: editable authorized background, mission/vision, services/contact/leadership | IMPLEMENTED for plain-text published content capability | `core.views.public_page()`/`core.content.save_content()` render authorized escaped content. Actual approved institutional content remains OQ-16; rich/structured authoring is not presumed necessary. |
| Announcements: published news/notices linking official Results | PARTIALLY IMPLEMENTED | `AnnouncementQuerySet.published()`/public views and draft/publish services work; result notices currently contain results themselves. G19/G20/G21. |
| Events: list/month calendar, upcoming/past/details/audience/accessibility | PARTIALLY IMPLEMENTED | Public event list/detail/schedules work; calendar and approved audience/accessibility configuration need G08. Optional RSVP is PENDING CLIENT APPROVAL, G09. |
| Programs: Available/Upcoming/Past and secure verified-member applications | PARTIALLY IMPLEMENTED | Existing current/past list, details, verification, requirements/reuse and submission work. G06/G07/G11/G12/G27 complete the target. |
| Results: separate authorized masked list/detail/archive/explanations/private clarification | NOT IMPLEMENTED as a dedicated section | Reusable current non-EWAF result projection exists under Announcements; G19/G20/G27. New disclosure/aggregates remain PENDING CLIENT APPROVAL. |
| Membership: onsite-only public requirements/steps/help, no public form/accounts | IMPLEMENTED for existing guidance workflow | `membership.views.register()` renders `guidelines.html` with no intake form; tests reject forged public POSTs. Representative/accessibility guidance and approved real content need G04/G11/G21/OQ-16. |

Cross-cutting FAQ/help is implemented through published CMS/Home support sections; footer currently exposes Contact/Privacy/Accessibility/Admin access, while FAQ has a Home anchor/redirect rather than its own footer link. Add explicit FAQ/help reachability under G21. Global controls are implemented; full accessibility acceptance is G26. Gemini remains G22. No member account, online membership form, reference-only status tracker, QR tracker, inbox or unauthorized messaging is required.

### Requirement classification register

This register covers every numbered functional/non-functional requirement. Detailed V2 subfunctions and gaps are above; working subfunctions retain credit even when the full requirement is incomplete.

| Requirement | Classification | Evidence/gap mapping |
|---|---|---|
| FR-01 Public information | PARTIALLY IMPLEMENTED | Existing public pages; G01/G07/G19/G21 |
| FR-02 Internal onsite membership | IMPLEMENTED for the stated Admin-only/manual workflow | Membership services/tests; G04 adds V2 draft/evidence fields |
| FR-03 Admin access/RBAC | IMPLEMENTED for current actions | Accounts, shared permission guards and direct-access tests; new actions need their own permissions |
| FR-04 Programs/events | PARTIALLY IMPLEMENTED | Existing management; G06–09 |
| FR-05 Secure membership verification | IMPLEMENTED for the approved four-field/grant workflow | `verify_member`, throttled views, matching/scope/version tests; operational timing/load acceptance remains G25/G26 |
| FR-06 Reuse/requirements | PARTIALLY IMPLEMENTED | Verified-document reuse works; G11/G12/G13 extend evidence/routing |
| FR-07 Submission/reference | PARTIALLY IMPLEMENTED | Atomic/idempotent photo route works; G11/G27 |
| FR-08 Applicable identity evidence | REQUIRES REFACTORING | Universal photo gates; G11 |
| FR-09 Final eligibility | PARTIALLY IMPLEMENTED | Current manual-photo/checklist path works; G11/G13 |
| FR-10 Branched lifecycle | PARTIALLY IMPLEMENTED | Existing canonical guards/history; G11/G13/G16/G18 |
| FR-11 EWAF configuration | NOT IMPLEMENTED as an enabled governed workflow | G06/G14 |
| FR-12 Automatic complete EWAF/ranking | NOT IMPLEMENTED | Disabled services; G15/G16 |
| FR-13 Controlled automatic recalculation | NOT IMPLEMENTED | G05/G17 |
| FR-14 Human final selection | PARTIALLY IMPLEMENTED | Non-EWAF decisions/slots work; G18 |
| FR-15 Authorized program result notices | PARTIALLY IMPLEMENTED | Non-EWAF publication works; G19/G20 |
| FR-16 CMS | PARTIALLY IMPLEMENTED | Authorized plain-text pages/general announcements work; G08/G21 |
| FR-17 Reports/analytics | NOT IMPLEMENTED | App shells; G02/G23 |
| FR-18 Audit Trail | PARTIALLY IMPLEMENTED | Current domain/security logs; G24/G28/new calculation/export actions |
| FR-19 Optional RSVP | PENDING CLIENT APPROVAL | G09/OQ-05 |
| FR-20 Eight Admin modules | REQUIRES REFACTORING | G01 |
| FR-21 Program authorization/evidence policy | PARTIALLY IMPLEMENTED | Current internal policy authorization; G06/G11/G14 |
| FR-22 Accepted criterion evidence | NOT IMPLEMENTED | G12/OQ-23 |
| FR-23 Workbook mathematics/classification | REQUIRES REFACTORING | Historical kernel partly reusable; G15; directions/thresholds PENDING CLIENT APPROVAL |
| FR-24 Dedicated Results/clarification | NOT IMPLEMENTED as a complete section | G19/G20/G27 |
| FR-P01 Gemini | PENDING CLIENT APPROVAL | G22/OQ-20 |
| NFR-01 Accessibility | PARTIALLY IMPLEMENTED | Shared controls/browser evidence; G26 |
| NFR-02 Privacy/security | PARTIALLY IMPLEMENTED | Current RBAC/uploads/projections; G06/G20/G23/G25/G28 and production acceptance |
| NFR-03 Integrity/reproducibility | PARTIALLY IMPLEMENTED | References/slots/history working; G14–17 governed calculations missing |
| NFR-04 Reliability/recovery | PARTIALLY IMPLEMENTED | Mutation/file cleanup and prior backups; G17/G25 restore/failure acceptance |
| NFR-05 Usability | PARTIALLY IMPLEMENTED | Existing messages/forms; G01/G11/G13/G26/G27 |
| NFR-06 Performance | PARTIALLY IMPLEMENTED | Bounded/rate-limited inputs and responsive evidence; G02/G23/G25 approved load targets/read-time result cost |
| NFR-07 Maintainability | PARTIALLY IMPLEMENTED | Existing services/migrations/shared UI; new governed dependencies/traceable acceptance still needed |

All 36 Business Rules are classified below. Categories apply to the entire stated rule, including unfinished target branches; “pending” identifies a policy whose outcome must not be inferred from code.

| BR | Classification | Coverage |
|---|---|---|
| 1–3 | IMPLEMENTED | Onsite/Admin-only membership/auth; membership/accounts tests |
| 4 | PENDING CLIENT APPROVAL for optional event participation; existing public browsing/member-only programs IMPLEMENTED | G08/G09 |
| 5 | IMPLEMENTED for current approved matching/grants | Program matching/throttle/privacy assertions |
| 6–7 | PARTIALLY IMPLEMENTED | Reuse/qualification checks present; G12/G13 |
| 8–9 | REQUIRES REFACTORING | G11 conditional evidence/submission states |
| 10 | IMPLEMENTED for current application/reference/correction/slot invariants | Programs/workflow/assistance concurrency tests |
| 11–12 | PARTIALLY IMPLEMENTED | G11/G13/G16 lifecycle/applicable eligibility |
| 13–18 | NOT IMPLEMENTED as the governed live EWAF workflow | G14–17; old algebra/history is reusable, not enabled analytics |
| 19–20 | PARTIALLY IMPLEMENTED | Non-EWAF human selection works; G18; exceptions PENDING CLIENT APPROVAL |
| 21 | PARTIALLY IMPLEMENTED | Successful non-voided release count works; OQ-08 scope/window and G17 PA dependencies missing |
| 22 | PARTIALLY IMPLEMENTED | Authorized publication exists; G19 dedicated destination missing |
| 23 | IMPLEMENTED for the current generated DEC-025 projection | Result masking/privacy tests; new disclosure stays OQ-22 |
| 24 | PARTIALLY IMPLEMENTED | No private tracker/accounts; receipt needs Results/conditional guidance, G27 |
| 25–26 | PARTIALLY IMPLEMENTED | CMS/explanations present; G15/G21 remaining target content/governed output |
| 27–29 | PARTIALLY IMPLEMENTED | Current accessibility/security/audits; G24–26/G28 |
| 30 | IMPLEMENTED for current excluded-scope boundaries | No forbidden new actors/AI selection/payment/tracker introduced; EWAF/history disabled appropriately |
| 31 | REQUIRES REFACTORING | G01 navigation |
| 32 | PARTIALLY IMPLEMENTED | Internal authorization present; G06 external/configuration gates |
| 33 | NOT IMPLEMENTED as criterion evidence assessment | G12 |
| 34 | REQUIRES REFACTORING | G15/G16; directions/bands PENDING CLIENT APPROVAL |
| 35 | NOT IMPLEMENTED as a dedicated Results destination | G19/G20 |
| 36 | PENDING CLIENT APPROVAL for Gemini; non-AI help IMPLEMENTED | G21/G22 |

Use-case coverage: UC-01/02 onsite guidance/intake are IMPLEMENTED at the recorded baseline, with V2 extensions G04/G21; UC-03/04 applications/evidence are PARTIALLY IMPLEMENTED (G11/G13/G27); UC-05 controlled configuration/calculation/recalculation is NOT IMPLEMENTED (G14–17); UC-06 human selection/publication is PARTIALLY IMPLEMENTED (G18–20); UC-07 following public results is PARTIALLY IMPLEMENTED (G19/G27); UC-08 CMS/report/audit access is PARTIALLY IMPLEMENTED (G21/G23/G24); UC-09 accessible verification configuration REQUIRES REFACTORING (G06/G11/G12, with actual evidence policy PENDING CLIENT APPROVAL); UC-10 optional RSVP is PENDING CLIENT APPROVAL (G09); UC-11 dedicated Results/clarification is NOT IMPLEMENTED as a complete section (G19/G27). UC-P01 published FAQ/help is IMPLEMENTED, while its Gemini variant is PENDING CLIENT APPROVAL (G21/G22). These map to the same tests/gates, without double-counting completion.

## Reusable Existing Components

| Component | Reuse evidence and boundary |
|---|---|
| Django/MySQL foundation and ORM/migrations | Preserve existing project/configuration/schema conventions. Eight navigation modules do not require eight new apps. Database runtime state was not queried. |
| Staff auth, User/Group permissions, protected Admin | `accounts` backend/decorators/admin and `core.permissions.require_workspace_permissions`; account tests directly exercise privilege escalation/revocation/CSRF. Retain technical superuser restrictions. |
| Onsite/manual membership and directory/history | Membership/member services and private views; tests verify one official Member after approval and original intake retained. Extend fields/review without replacing it. |
| Private documents and verified reuse | `DocumentVerification`, digest/expiry/member-version guards, scoped audited downloads; `test_verified_internal_document_reused_then_revocation_blocks_selection`. Extend criterion assessments rather than treating declarations as verified. |
| Program requirements/availability/version locks | Configurable document/text/acknowledgement and optional relevant disability qualification; snapshots and concurrency checks. Extend governance/conditional evidence. |
| Secure member grant/application/reference allocation | Exact approved matching, hashed throttle keys, scoped expiry, row locks, counters and member/program uniqueness. Preserve legacy receipts and idempotency. |
| Manual photo review/corrections | Private scrubbed images, reviewer/reason/history, old photo/document revisions retained. Keep intact inside the required-photo branch. |
| Eligibility and human non-EWAF decisions | Checklist/current versions, corrective outcomes, close-period gate and slot locks. Integrate EWAF without rewriting actual-assistance history. |
| Actual release/void and PA source | `AssistanceRelease.objects.successful()` and `previous_assistance_count()` exclude voided receipts; current count spans retained successful releases, not an approved new window. |
| Publication/CMS revisions | Generated projection, explicit privacy preview/authorization, current-source digest, selected-only masks/collisions, immutable result history and safe CMS. Reuse for dedicated Results. |
| Event details/attendance history | Dates/venue/images, linked member applications, reasoned corrections and retained historical nonmember records. New RSVP/audience needs policy. |
| Historical EWAF kernel/storage | AHP row-average/consistency, validation and weighted-sum primitives; Configuration/RankingRun/Snapshot history. Reuse after policy-aware refactoring, not by re-enabling old mutation endpoints. |
| Accessibility/shared UI and domain audits | Reuse semantic templates, display controls, public TTS, sidebar state and permission-aware links. Broaden acceptance for new flows. |

## Required Backend Changes

1. Extend program governance/opening with offline authorization, approved evidence applicability and locked configuration references (G06/G11/G14). Recheck the same prerequisites across publication, verification and submission.
2. Add accepted criterion assessment/provenance and applicable-evidence/eligibility/readiness services (G12/G13), preserving working photo/document validation and private delivery.
3. Implement immutable approved EWAF versions, auditable math/intermediates, complete program runs/currentness and automatic affected-pool recalculation (G14–17). Keep business policy in approved configuration, not templates or ad hoc applicant edits.
4. Connect current EWAF output to existing human decisions/release/result services and their stale guards (G18/G20). No automatic selection or payment.
5. Add dedicated public Results queries/views from authorized revisions and update safe receipt/help guidance (G19/G21/G27). Reuse current projection and withdraw/source checks.
6. Add authorized dashboard/report/export queries, metric definitions and operation audits (G02/G23/G24), plus verified account-security audit failure behavior (G28).
7. Add event RSVP only after approval, separately from program applications and attendance; Gemini remains a later proposed scope (G09/G22).

## Required Frontend Changes

- Seven ordered public sections and eight Admin groups with permission-aware V2 submodules; preserve unified Members/sidebar behavior and stable support bookmarks (G01).
- Available/Upcoming/Past programs, accessible calendar/list events, approved audience/accessibility content, external approval/configuration status and clear unavailable controls (G07/G08).
- Necessary internal membership intake/draft/return-review fields and evidence status; conditional required identity/evidence prompts and correctable-versus-definitive feedback (G04/G11/G13).
- Criterion review, AHP preview/authorization/history, inputs/normalized values/contributions, current-run ranking and separate human decisions (G12/G14–18). Do not offer manual score/rank inputs.
- Official Results list/detail/archive and notice links; accessible private-safe receipt save/copy/print guidance (G19/G20/G27).
- Approved CMS/FAQ/help wording, accessible actual-record dashboard/reports/tables/export controls (G02/G21/G23/G26). No member login, inbox, tracker or unapproved chatbot/RSVP form.

## Required Database Changes

**Design recommendations only; no schema or migration was created or applied.** Prefer additive, history-preserving extensions. Existing models and migration definitions were inspected; their live application state was not queried.

| Existing schema/migration evidence | Proposed extension / preserved boundary |
|---|---|
| `membership` intake/settings; `members.PersonalRecord`, Member/MemberEvent | Necessary optional profile/representative/ID information, draft/return review and assessment provenance. Keep mandatory-source history; map old exact-income data explicitly without claiming verification. |
| `documents.0003_revised_seventy_workflow` / DocumentVerification | Accepted evidence states/value/type/source version for criterion assessments; retain current digest/expiry/private-document ownership. |
| `programs.0003_revised_seventy_workflow` / Program/ApplicationPhoto/PhotoVerification/counters/document revisions | Versioned external approval, applicability/accepted alternative policy and approved evidence review mapping; retain all current photos/reviews/states/references. |
| `ewaf.0001_initial` / Configuration/ApplicationInput/RankingRun/Snapshot | Governed configuration family/version/program/status/approval/lock/effective metadata; criterion definitions and AHP intermediates; accepted-input/contribution snapshots; complete-run failure/currentness/algorithm/precision/pool provenance. Preserve historical 0–1 scores with their original scale; never reinterpret them as 0–100. |
| `assistance.0003_revised_seventy_workflow` / AssistanceCase/Release/Log | Add current run/result/version decision provenance where needed; preserve successful-release uniqueness, void history and independent selection/delivery. |
| `announcements.0003_authorized_program_results` and `0004_preserve_result_source_content` | Reuse ProgramResultRevision and previous content for Results; add approved context/source references if necessary. Dedicated routes alone do not require new tables. Never expose old private revisions as public archives. |
| `events.0005_revised_seventy_workflow` / Event→Program, EventAttendance, legacy EventRegistration | Approved audience/configuration and separate RSVP, only after decision. Preserve legacy association/status/history; no automatic conversion into new valid applications/attendance. |
| `core.0001_revised_seventy_workflow` / PublicContent/ContentRevision; domain audits | Reuse CMS/history; add approved catalogue/audit/report records only where required. No model/table is implied merely by a UI module. |

`programs.0003` retains prior codes in `legacy_status` and does not synthesize photo approval; do not run or rewrite that data migration. Future work needs reviewed migration plans, backups and disposable-data tests. Proposed configuration/state/entity names are not approved executable schema. Configuration/Snapshot immutability must include authorized service/API/bulk-operation boundaries, with operational protection for privileged database access.

## EWAF Implementation Gaps

### Seventeen required stages

| Stage | Classification | Actual code and missing target behavior |
|---|---|---|
| 1 AHP pairwise matrix | PARTIALLY IMPLEMENTED | `ahp()` validates a fixed five-by-five reciprocal positive matrix. Approved variable definitions/order/dimensions and draft versioning absent (G14/G15). |
| 2 Column totals | PARTIALLY IMPLEMENTED | Calculated internally, not returned/stored as auditable intermediates. |
| 3 AHP matrix normalization | PARTIALLY IMPLEMENTED | `matrix[i][j]/totals[j]` used internally for weights; normalized matrix not returned/persisted. This is not applicant Min–Max. |
| 4 Row averages/priority weights | PARTIALLY IMPLEMENTED | Algebra implemented; governed approved derivation, sum/precision metadata and workbook-specific regression missing. |
| 5 Weighted sum vector | PARTIALLY IMPLEMENTED | `A×w` returned in consistency JSON; complete approved configuration workflow missing. |
| 6 Consistency vector | PARTIALLY IMPLEMENTED | `WSV_i/w_i` returned; auditable configuration validation/preview missing. |
| 7 Maximum eigenvalue estimate | PARTIALLY IMPLEMENTED | Mean CV returned; policy/order/version context missing. |
| 8 Consistency Index | PARTIALLY IMPLEMENTED | `(lambda-5)/4` correct for n=5, not generalized approved dimensions. |
| 9 Consistency Ratio | PARTIALLY IMPLEMENTED | CI/1.12 and strict CR<0.10; variable RI/small-count handling and approved draft failure workflow absent. |
| 10 Applicant input validation | PARTIALLY IMPLEMENTED | Finite numbers, approved-category lookup/bounds rejection in `calculate()`; no accepted-evidence/current-eligible pool pipeline. |
| 11 Applicant Min–Max | REQUIRES REFACTORING | Generic formulas exist; enforced older SI/PA inverse direction conflicts with unresolved target. Bound scope/edge policies pending. |
| 12 Weighted Sum Model | PARTIALLY IMPLEMENTED | Sum of normalized value×weight implemented; explicit stored contribution breakdown and governed run integration missing. |
| 13 Equity Weighted Score | PARTIALLY IMPLEMENTED | Legacy return/storage is 0–1; target 100×WSM with approved precision/scale/version missing. |
| 14 Need classification | PENDING CLIENT APPROVAL | Legacy threshold engine exists but new bands/endpoints/precision unapproved; no enabled target run. |
| 15 Program-specific ranking | NOT IMPLEMENTED as live target | Historical snapshots/display only; mutation/current-ranking services disabled (G16). |
| 16 Human selection | PARTIALLY IMPLEMENTED | Reasoned non-EWAF selection/slots work; current EWAF integration and optional approved tie/waitlist rules missing (G18). |
| 17 Recalculation/versioned audit | NOT IMPLEMENTED | Retained history/stale guards do not automatically recompute the affected pool (G17). |

### Workbook-specific mathematical acceptance

The authoritative extraction records both formulas and stored values; an XLSX reader does not recalculate. Original `Sheet1!C3:G7` order is **PA, SI, ES, ND, PR**, while the historical code uses **SI, ES, PA, ND, PR**. Reorder both axes and weights by criterion identity; neither position is an approved universal API default.

- Column totals are `SUM` of each matrix column (`C9:G9`). `C12:G16` divide each comparison by its column total using `IMDIV`, ordinary real division for these finite real inputs. Row averages of that normalized matrix derive weights.
- Workbook `C29:C33` instead reference empty `Q10:U14` and cache `#DIV/0!`. Intended row-average arithmetic is documented, not a repaired source file. Later normalized matrix, weights, WSV/CV and scoring inputs include disconnected literals; importing cached/pasted values would not provide reproducible updates.
- Working matrix derived weights in workbook order are approximately `[0.1680255420615515, 0.4036844693219095, 0.2482410868847711, 0.06352025110971905, 0.1165286506220489]`. `A×w`, elementwise division by `w`, mean CV, `(lambda-5)/(5-1)` and division by RI(5)=1.12 yield lambda≈5.079861732363076, CI≈0.019965433090769036, CR≈0.017826279545329494. CR<0.10 is the reference consistency check, not approval of the socioeconomic direction.
- Applicant `C81` is exactly `=IMDIV(E102 -  E101,E103 - E101)` (ascending PA); `C82` is `=IMDIV(E93-E92,E94-E92)` (ascending income SI). These conflict with historical inverse assertions and require OQ-18/19 approval. ES/ND/PR use separate ascending applicant Min–Max examples; definitions/encodings/evidence still require approval.
- Sample normalized inputs in workbook order are `[1/3, 0.2, 2/3, 0.4, 2/3]`; weighted products at `H80:H84` and `SUM` at `H86` give WSM≈0.4053333333333333. Admin V2 explicitly supplies **EWS=100×WSM≈40.53333333333333**. This is an example fixture, not approved live direction/bounds or a beneficiary decision.
- Printed High/Moderate/Low/Minimal bands have no automated classification formula; boundaries using `79.99` etc. do not define all full-precision values. No threshold/default rounding is chosen here. Historical rounded ES=0.2483 must not replace the new row-average-derived value without an approved methodology.

`ewaf.tests.CalculationTests.test_more_income_and_previous_releases_reduce_need` asserts older inverse policy. Keep its historical traceability, but future active policy tests must derive expected directions from approved versions. The all-ones AHP test remains useful and does not validate the actual workbook matrix. More mathematical fixtures can be tested independently before activation; operational scoring stays blocked until required policies and governance are accepted.

## Privacy and Security Gaps

Current implemented safeguards are worth retaining: staff/permission checks in both views/services; private object-scoped audited downloads; no-store/referrer protection; bounded uploads, signature checks and image re-encoding; generic identity failures and hashed throttle counters; escaped plain-text CMS; generated public field allowlists; explicit privacy confirmation; source-freshness filtering and non-editable audit screens.

Remaining work is concentrated in G06/G11/G12/G14–17/G20/G23–28: policy-complete opening, applicable evidence, accepted inputs, immutable live calculation/run history, current-result selection/publication, private exports, complete audit failure behavior, approved access/retention and deployed storage/recovery acceptance. Document signature checks are explicitly not malware scanning (`documents.validators.validate_document`); quarantine/orphan handling is an operational decision, not an already working safeguard.

Read-time `AnnouncementQuerySet.published()` revalidates result candidates and evidence digests; this protects freshness but may become expensive. Measure approved workloads before optimizing, and keep visibility gates equivalent. Masks are potentially identifiable; human small-group/context review remains necessary. General free-text CMS/posts need privacy review independently of protected generated result fields. No unsupported legal/compliance, production security, timing-equivalence or anonymity claim is made.

## Unresolved Client Decisions

| Decision | Required approval / dependent work |
|---|---|
| OQ-02/24 | Program photo applicability, recency/legibility, accessible evidence/assisted alternatives, reviewers and durable conditional state mapping; G04/G11/G13/G20. |
| OQ-03 | Exceptional reopening of rejected/verification-failed/ineligible/closed applications; approved Help Desk correction and immutable receipts remain settled. |
| OQ-04/09/26 | Actual program selection methods, approval duties/effective revisions, required offline external authority/evidence and allocation details; G06/G14/G18. |
| OQ-05 | Optional RSVP/audience, minimal public data, duplicates/cancellation/capacity/admission/attendance policy; G08/G09/G23. |
| OQ-06/07/23 | Socioeconomic definition/period/household basis, employment categories, dependents definitions, relevance rubric, accepted evidence/declaration/dispute handling; G04/G12/G15. |
| OQ-08 | PA scope/window/cutoff and release/void impact; actual successful non-voided delivery remains the source, never attendance/undelivered selection; G12/G17/G18. |
| OQ-10/11/12 | Approved judgments/criterion dimensions/RI/failed-consistency workflow, fixed versus pool bounds, missing/equal/out-of-range handling and calculation storage/display precision; G14–17. The row-average method/reference CR check is established; remaining activation choices are not. |
| OQ-18 | Income/SI normalization direction: ascending workbook versus older enforced inverse; G15. |
| OQ-19 | PA normalization direction: ascending workbook versus older enforced inverse; G15. |
| OQ-13/15 | Tie/non-selection/waitlist timing and authorized exceptions, if needed; no invented internal-ID/submission-time winner or score override; G16/G18. |
| OQ-20 | Gemini scope/privacy/grounding/cost/safety/accessibility approval; G22. |
| OQ-21/22 | Future random-reference format/transition, reference fragments, new aggregate/result disclosure, retention and private clarification. Preserve issued sequences and current DEC-025 masks; G19/G20/G27. |
| OQ-25 | Classification thresholds, exact gap-free endpoints, precision and internal/public use; G15/G20. |
| OQ-16/26 | Official content/contact/hours, document lists/access assignments, privacy/retention, hosting/private media/recovery/performance/UAT, verified annual dates, optional apparent classification/independent review/treasurer scope; G03–05/G08/G21/G23–26. |

Settled matters are not reopened: onsite membership, Admin-only login/no member accounts, approved four-field matching (OQ-01), Help Desk-assisted pending corrections, legacy-reference preservation (OQ-17) and DEC-025 current masking (OQ-14).

**Documentation precision issue:** Business Rule 12 still says final eligibility follows successful “Photo Verification,” while the master/BR-8/9 and updated acceptance tests explicitly permit applicable approved alternatives/no additional photo. Use the master and preserve this wording discrepancy in review; clarify it in a later documentation task instead of silently treating it as universal-photo approval. Likewise, the computation note's diagram places configuration steps beside an eligible pool, while its governance prose/master require lock before opening; the diagram is not authorization to delay locking. No documentation other than this report was edited.

## Recommended Implementation Order

Preserve stages 1–7 and DEC-025. These phases overlay the existing remaining roadmap; they do not restart the project, award 80% or alter recorded percentages.

1. **Policy/design gates and preservation:** resolve only decisions necessary for each phase; inspect current dirty work, approved schema/state mapping and disposable regression environment. Address G06 opening/configuration design and G28 audit failure verification early. Keep affected live actions disabled while required policy is unresolved.
2. **Navigation and current safe Results:** implement G19/G01/G27 and policy-independent G21 wording using existing non-EWAF projection/permissions. Establish seven public/eight Admin groups and preserve Members/sidebar/support bookmarks. No changed mask/reference generator/new aggregates/RSVP/Gemini are implied.
3. **Program governance and accessible application evidence:** after approval, G06/G11/G13, with G04/G05 membership draft/review/correction extensions and G10 consolidated queues. Preserve required-photo behavior and histories; apply one approved identity prerequisite everywhere.
4. **Criterion assessments and governed EWAF configuration:** G12/G14 plus independent G15 workbook arithmetic fixtures. Complete directions/evidence/bounds/precision/threshold decisions before live activation; lock before opening.
5. **Complete EWAF runs, automatic revisions and human decisions:** G16/G17/G18; integrate current-source/run publication G20 and release/void-dependent PA. Preserve immutable previous results and complete-pool promotion/slot locks.
6. **Operational analytics, reporting and approved events:** G02/G23/G24 and G08 accessible calendar. G09 only after event policy approval; its absence does not require blocking independent membership/release reports. G22 remains a separate proposed scope.
7. **Release readiness:** G25/G26, integrated security/privacy/concurrency/accessibility/performance and disposable database+media restore, then representative UAT. Deployment is a separate authorized task.

### Recommended next Codex implementation task

**Add the dedicated Public Results section and seven-section navigation using the existing authorized non-EWAF ProgramResultRevision projection.** Update official notice/receipt links and scoped tests while preserving DEC-025 masks, current-source/withdrawal behavior, issued references, private history and the disabled EWAF/tracker boundaries. Do not add new aggregates or resolve OQ-21/22. Start with a scoped diff/preservation check; eight-module Admin regrouping can follow as its own manageable UI task. This recommendation is not an instruction to start implementation now.

## Testing Requirements

No tests were run for this analysis. Future implementation must retain existing meaningful tests and update only assertions superseded by the approved target, with traceability. Test names alone can mislead: some event titles retain old wording even though assertions now reject nonmember creation. Inspect setup and assertions. Existing `ewaf.tests` configuration-service test also has an old “audits new version” title but currently asserts the stage-eight fail-closed exception.

| Acceptance family | Existing evidence to preserve | New required coverage |
|---|---|---|
| AT-01–04 membership/auth/verification | `membership/tests.py`, `accounts/tests/test_accounts.py`, `programs/tests.py`; dated baseline acceptance | V2 drafts/return/evidence, new action permissions and operational matching/throttle acceptance |
| AT-05–10 reuse/submission/identity/eligibility/receipt | `programs/test_revised_workflow.py`, `assistance/tests.py`, scoped private downloads | Conditional evidence routes, approved state mapping, consolidated readiness, Results receipt wording |
| AT-11–16 configuration/math/recalculation | `ewaf/tests.py` pure kernel/error tests and fail-closed assertions | Actual workbook fixture/intermediates, locked approved versions, accepted inputs, immutable complete runs and full-pool correction/revision tests |
| AT-17–18 selection/delivery | Assistance eligibility/decision/release/void and concurrency assertions | Current EWAF linkage, ties/waitlists/exceptions only after approval, PA cutoff and affected-run invalidation |
| AT-19–23 results/CMS/exports/audits/recovery | `announcements/test_results.py`, `core/tests/test_content.py`, auth/domain rollback/privacy tests | Dedicated Results/currentness, EWAF/alternative evidence, exports/formula injection, account audit failure and demonstrated restore |
| AT-24–27 accessibility/navigation | Revised70 and announcement browser harnesses at 320/390/768/1024/1440; shared controls | Seven/eight navigation, screen readers/keyboard/expiry/UAT, calendar/chart alternatives |
| AT-28–32 new evidence/policy/math/Results | Existing photo/reference/non-EWAF publication controls are baseline only | Approved applicability/external lock/evidence; independent workbook math and policy-specific bands; same authorized Results projection |
| AT-29 RSVP / AT-33 Gemini | Current retired event intake/static FAQ preserved | Conditional tests only after approval; no feature/pass claims before then |

For authorized development, use a separately configured disposable MySQL database/media, never application data. Run focused affected modules first, then relevant integration/concurrency/browser checks; future schema changes need migration drift/system checks and preservation/restore evidence. Do not rerun historical harness expectations as October 10 acceptance without examining them. Record exact command, revision, environment, failures and limits; no unmeasured performance target or fabricated test pass.

## Risks to Existing Functionality

- Dirty tracked and untracked source includes working modules/migrations/templates. Do not reset, clean, overwrite, stage unrelated changes or infer implementation solely from HEAD.
- Conditional identity touches submission, corrections, eligibility, selection, release, event attendance and result freshness. A form-only change risks bypass or dead ends; keep old photo paths until a complete approved branch exists.
- Re-enabling legacy EWAF would impose unapproved inverse directions/fixed criteria and omit governance/recalculation. Keep fail-closed behavior until replacement acceptance.
- Changing score scale/order/precision without explicit historical metadata can corrupt interpretation and ranking. Preserve original scores/runs and use new versioned semantics.
- Relaxing submitted-program locks before controlled versioning could apply different rules to applicants. Retain locks until reviewed revision/recalculation replaces the restriction.
- Results archives, notices, caches and exports can disclose withdrawn/stale/private data if they bypass the shared source/projection gate. Never publish old applicant rows or complete references/ranks.
- PA is based on actual successful delivery; releases/voids can change later pools. Ignoring those dependencies or counting selection/attendance would distort equity calculations.
- New Admin grouping can hide or broaden access; preserve permission checks, unified Members routes, scroll/focus and native Admin security.
- Membership field changes must preserve original exact declarations and evidence, without automatically treating old values as verified.
- Historical attendance and issued receipts are protected records, not data to convert/renumber to fit new workflow.

## Analysis Validation and Stop Boundary

The report cross-references all eight Admin modules, seven public sections, FR-01–24/FR-P01, NFR-01–07, BR-1–36, use cases, seventeen EWAF stages and AT-01–33. Each numbered gap includes module, required functionality/status, actual components, missing/conflicting behavior, recommended change, dependencies, priority and tests. Pending policy is explicit; no scope is silently approved.

Deliverable validation found **87 local file links with no missing targets**, all required report sections and **28 unique gap entries**. All **327 pre-existing repository files** matched their pre-report SHA-256 hashes; Git status gained only this report and lost no existing change entries. This is documentation/preservation validation, not application acceptance. No actual implementation/database state was changed or freshly certified. Remaining policy, runtime, institutional content and UAT uncertainties are intentionally recorded above.

**CODE MODIFIED: NONE. DATABASE MODIFIED: NONE. MIGRATIONS MODIFIED: NONE.** Only this report is added to repository documentation. Analysis ends here; implementation awaits further instructions.
