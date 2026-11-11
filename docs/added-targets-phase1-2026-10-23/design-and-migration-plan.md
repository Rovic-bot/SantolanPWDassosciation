# Proposed additive records and operating contracts

Status: design for review only, 2026-10-23. **No model, migration, application setting, gate, route, or service change has been generated or applied by this plan.** Proposed names below are design labels, not claims that tables exist. Sources: integrated §§5.4–5.11, 6.9, 7.7–7.13, 9.4, 10.1, 12.6–12.7 and [IQ decisions](progress-and-decisions.md).

## Reuse and protected boundary

Keep Django/MySQL, server templates/Bootstrap, existing Admin visual styles, ordinary member matching, permission functions, upload limits, private storage and audited service transactions. Reuse `membership.services.decide_application` for official Association Member creation; keep its writer/invalidation wrapper, locking, reason/version checks and manual PRPWD requirement. Reuse `members.services.update_member`, `documents.services.verify_document`, `programs.workflow.correct_application`, applicable evidence services and their freshness/invalidation behavior for accepted corrections. Do not directly write criterion assessments, source generations, eligibility, configuration, runs, scores, decisions or releases from an extension.

No protected EWAF contract changes are in this plan. If an existing service cannot accept the approved source update safely, defer that integration and retain a pending review record. Do not add a calculation call to submission, intake, correction acceptance or request processing. Existing explicit complete-pool generation/recalculation remains the only relevant route, with its original authorization. A later genuine source change may change later results through that existing route; it cannot rewrite an earlier correct snapshot.

## Minimal proposed records

| Phase / owning domain | Proposed record and minimal fields | Relationships and invariants |
|---|---|---|
| P2 `membership` | **RegistrationIntake**: opaque internal key; category Association/PDAO; channel online/printed/walk-in; approved external reference; received time; processing state/version; current submission revision; submission-request identity/fingerprint; approved policy/form version | Separate pending record, no Member on submit. Nullable one-to-one link to existing `MembershipApplication` only after authorized Association onsite conversion. PDAO category must have no such link. Separate reference namespaces; all reference values immutable. |
| P2 `membership` | **RegistrationRevision**: intake FK, revision/predecessor, typed submitted-field snapshot with schema/form version, author/source channel, captured time, correction reason | Retain original submission and each correction; revisions are append-only through services. Original values are private. Accept only an approved field allowlist; no unrestricted JSON import. New form does not require a post-approval control/government number. |
| P2 `membership`/private documents | **RegistrationAttachment**: revision FK, requirement key/group, private file handle, content type/size/digest, uploaded time, predecessor if replacement | Separate ownership because existing `MembershipApplicationDocument` requires a membership application. Reuse storage/validators/permission patterns, not a public media URL. Physical items are checklist observations, not attachment placeholders. Document reuse into approved onsite record must preserve provenance/access and file lifetime. |
| P2 `membership` | **RegistrationAction**: intake/version, actor or submission context, action, timestamp, reason, protected revision references, typed onsite checklist findings | Receipt/form retrieval, corrections, onsite identity/document findings, conversion and decisions audit atomically. Minimum typed onsite findings include form, 2×2 photo, civil-document alternative chosen, Voter's Certificate and physical envelope, separately from manual PRPWD. Exact originals/copy rules await OQ-27. |
| P2 `membership` | **PDAOForwardingFact**: PDAO-intake FK, approved recipient/authority/process version, actual forwarding time, authorized actor, necessary private proof, predecessor/reason | Record facts only after authorized manual action. No transmission integration or official ID state. Can be folded into typed append-only RegistrationAction if approved design supplies equivalent constraints/provenance; avoid a redundant table. |
| P3 `programs` | **InformationDeclaration**: application FK, exact fields/source versions presented, no-change/changed/uncertain declaration, submitted time and retained predecessor | Does not update independent verification dates, trusted profile, EWAF evidence, score or eligibility. Store with retained application only after successful ordinary submission; retries cannot duplicate declarations. |
| P3 `programs` | **InformationReviewCase** and immutable case actions: specific application/member target, trigger (reported change/stale/discrepancy/approved routine basis), policy/basis, observation/effective dates, reviewer/finding/reason, source-version pointers and resulting authorized-service operation | One typed target contract, no arbitrary generic record mutation. Field minimization and evidence review govern acceptance. Findings are not trusted criterion records until an authorized existing service accepts them. Routine selection/expiry rules remain unset. |
| P3 `programs` | **EvaluationReviewRequest** and immutable actions: application FK, requester authority-verification finding, selected/nonselected context, concern, retained evaluation/run identity and digest when relevant, reviewer/outcome/reason, version/predecessor | Read-only provenance reference, not a new run/score or copy of all applicants. No required FK to deferred EWAF tables merely to open the review screen. Typed provenance is verified via existing ready/authorized services before protected actions. Terminal remedies remain gated. |
| P4 `assistance` or scoped ticket module within existing app | **ReferralTicket**, private attachments and immutable actions: verified member FK, reference, approved minimal concern/request fields, receipt time, workflow version/state and follow-up facts | Separate from `AssistanceCase` and `AssistanceRelease`. No required program, no fake program to obtain a grant, no calculation/selection/release/PA writes. Ticket states and duplicate semantics need approval. |
| P4 `core` | **Resource content metadata** associated with current `PublicContent`/`ContentRevision`: approved resource key/topic, provider/source URL, responsible office, source version/reviewed time/actor, instructions and publication snapshot | Prefer extending current fixed CMS keys with a finite Resources set and metadata sidecar; no generic site builder. Revisions/publication capture metadata together with title/body. Dynamic listings may need a later approved resource-item child table; not automatic scope. |
| P4 `events` | **Event audience policy** and **EventRSVP** with immutable actions: actual Event FK, target audience and permitted participants, approved policy/version, minimum participant fields or verified-member FK, request identity, intention/cancelled state and timestamps | No observance FK as a substitute for event; no attendance, reservation, selected-beneficiary or release side effects. Exact identity/duplicates/capacity/cancellation rules await IQ-11. |

Avoid new records for concepts already retained appropriately: membership decisions/official Members, program references/counters, criterion evidence, calculations/decisions, actual releases and masked result revisions stay in their existing domains. A tracking projection needs no public-copy table. Existing appointment content must not be invented; add an appointment field/record only if assignment is approved, with actual time/actor/history.

Relevant initial-assessment information may be retained privately in the approved intake revision/action schema with its observation date, reviewer and basis. It remains distinct from membership approval and trusted program evidence; no permanent applicant score is calculated. Later accepted updates use existing authorized services and their unchanged source/freshness contracts.

## State contracts proposed for review

Keep the existing `MembershipApplication.status` domain (`pending/approved/rejected`) unchanged. The new intake processing state is separate:

| Intake | Proposed transition | Required conditions / prohibited shortcut |
|---|---|---|
| Both categories | Successful submission → Received → Under Association review | Form/evidence validation, policy version, bounded request, atomic reference/revision/audit. Submission cannot set a decision. |
| Both | Under review → Needs information → Under review | Authorized reason and retained correction revision; changed payload never overwrites original. Recheck stale version. |
| Both | Under review → Ready for onsite verification → Onsite findings recorded | Readiness is an instruction, not verified identity or approval. Record actual onsite findings, not upload success. |
| Association only | Onsite findings recorded → existing pending membership intake → approved/rejected decision | Approved identifier mapping, actual checklist and applicable manual PRPWD, existing authorized membership decision service; linked record uniqueness and transaction. Final rejection/correction/remedy semantics require approved policy. |
| PDAO only | Onsite findings recorded → Ready for authorized forwarding → Forwarded (Association fact) | IQ-09 authority, checklist, recipient, transfer process and actual proof. Never “PDAO approved,” ID issued or Association Member created. |

These labels are proposed state codes for owner review; they are not inferred institutional policy. Corrections before decision return to applicable review; final cases cannot be reopened through a generic status dropdown. Preserve cancellation/withdrawal and terminal remedies as unavailable until authorized. Existing membership decision remains the source of truth after linking; no contradictory duplicate decision field.

Information/evaluation review may use Received → Under review → Needs information → Finding recorded. Finding recorded may reference a supported correction, no change, or unavailable remedy; it cannot itself select a beneficiary. Keep request resolution separate from a terminal application transition. Referral/RSVP state details remain contingent on their specific contracts.

## References, retry and duplicate design

1. Preserve every issued `SPWDA-YYYY-PRGdddddd-NNNNNNNNNN` and existing membership UUID. Do not rename program counter semantics or use one universal namespace for Members/government IDs/requests.
2. Propose separate logical namespaces for Association registration, PDAO assistance intake and referral tickets, with unique DB constraints and immutable stored values. Exact printable format/random allocation and entropy require IQ-10 approval. Prefer non-identifying references; this is a proposal, not a new operational default. Existing internal UUIDs are not secret credentials.
3. Within one transaction, reserve category/request key, compare a canonical validated payload fingerprint and retained form/policy version, create record/revision/reference/audit and then issue receipt. Same valid key and same payload returns the existing accepted result; same key with different payload fails without revealing another record. Handle uniqueness races by re-reading only within the authorized request context. Do not return another person's receipt solely because a key was guessed.
4. Failed validation allocates no accepted reference or successful receipt. Upload failure rolls back record/audit and safely cleans only newly written temporary files. Audit failure prevents a successful state change. Idempotency persists through connection retry without adding duplicate Members.
5. Online plus printed reference: staff retrieve the original, perform approved identity review and record the printed presentation against it. Name/contact matches are review candidates only; never auto-merge people. Staff-recorded duplicate disposition links retained records with evidence/reason; no deletion or reference reassignment. A new walk-in record remains distinct unless approved identity matching establishes the prior intake.
6. First-time applicant fields cannot assume an existing Association control number or government ID. Existing Member control-number allocation and mapping must be settled before conversion. No random/dummy government ID or application reference is inserted into a control-number field to satisfy validation.
7. Optional QR may encode an approved category/reference navigation payload only; it must not carry private values or a reusable private credential. A printable/copyable text reference is always available. Tracking payload/URL and access contract remain IQ-03/10 decisions; optional QR can be omitted in P2.

## Three access surfaces and completed forms

- **Public content**: anonymous, published-only, no personal-data collection to read guides/resources/blank forms. Reviewed external links do not assert authenticity or transmit personal data automatically.
- **Submission-context output**: propose the existing anonymous Django session plus a server-bound successful-submission context for the exact intake/revision, with explicit lifetime/replay/recovery rules approved under IQ-10. Receipt can show its own full reference; private completed form is available only within that authorized interaction or via staff recovery. This is not a tracking credential, account, PIN or OTP. Reject reference-only later downloads. Print/save from the response is an alternative to adding a PDF library. Use existing ReportLab only if a reviewed PDF layout is necessary.
- **Admin private records**: authenticated active staff, dashboard access and category/object/action permissions on every list/detail/search/download/service call. Recheck current authority at mutation/download; neither knowing a UUID nor a prior page view grants access. Retrieval logs avoid sensitive form values and tokens. Private responses use no-store, sandbox/nosniff where appropriate, and never unrestricted `/media/`.

Tracking is a separate, minimal serializer/projection for each process, derived from actual records, and never a filtered Admin template. Allowlist, extra identity checks if needed, throttling, recovery and accessible alternatives must be approved before any route is active. Proposed safe default while undefined: route/action unavailable at server; Help Desk guidance contains no applicant lookup. Do not invent new numeric attempt windows, verification periods or expiry values; record technical settings for approval and exercise boundaries in synthetic fixtures.

## Permissions and Admin placement

| Existing group | Proposed additions / capabilities | Separation |
|---|---|---|
| Dashboard | Permission-filtered links to pending registration, ticket, update and evaluation-review queues | No fabricated counters or public analytics |
| Members | View/search Association intake; view/search PDAO intake; view attachments; encode/correct; record onsite findings; existing membership decision capability; separate record-forwarding capability | Intake visibility does not imply document access, membership decision or PDAO authority |
| Programs & Events | Publish reviewed assessment/correction instructions; event audience policy; RSVP view/manage after approval | Preserve terms/external approval, capacity and restricted attendance |
| Applications & Verification | Ticket view/review; declaration/update review; routine review; evaluation request intake/review; tracking-safe next-action authoring if approved | Review permission does not authorize evidence acceptance, calculation, selection or release |
| EWAF & Selection | Existing authorized provenance links only | No additional calculation/decision power or mutable score field |
| Announcements & CMS | Resource drafting, source review, publishing, forms/help/footer/notice links | Current publication permissions and version/audit rules; private evidence never a CMS asset |
| Reports & Exports | Approved registration receipt/form output; applicable existing exports | Detail access does not automatically permit bulk export; no inferred new reports/finance |
| Administration | Assign reviewed capabilities to existing accounts/groups; review audit/access configuration | No new login roles; no editable audit/history console |

Proposed capabilities are action-level permissions, not seeded users/groups. Exact codenames and assignments require schema/ownership review. Required audits commit with business changes. Actor/time/reason, expected version/predecessor and object context are mandatory; a stale version, revoked permission, changed policy or failed audit aborts the action.

## Additive migration order proposed, not generated

Only new non-EWAF migration files in the later approved phase. Never alter existing migrations or the startup hash guard. The leaf names below were inspected in source/test logs, not queried from the working database.

| Step | Phase / dependency | Proposed operation and validation |
|---|---|---|
| M2-A | P2, existing `membership.0005_onsite_profile_capture`, `documents.0004_onsite_profile_capture`, swappable user | Create pending intake/revision/attachment/action tables and constraints/indexes. Avoid copying old records or auto-linking Members. Optional PDAO fact fields/table only within approved scope. |
| M2-B | P2, M2-A and existing membership service | Add constraints for one linked membership intake per Association registration, category-safe links, unique references/request identity and immutable revision chain. Resolve circular current-revision relation through ordered creation/AddField **in the new migration only**. No EWAF-table dependencies. Service guard enforces approved onsite findings for linked intakes at every decision entry point. |
| M3-A | P3, approved M2 and existing `programs.0005_approved_terms` / Member schema | Create declarations and staff review/request/action records with typed targets and indexes. Non-authoritative evaluation-provenance pointer resolved through current services; do not require deferred EWAF schema merely for request retention. |
| M3-B | P3, IQ-03/10 approved | Only the access/recovery/audit persistence that the approved contract actually requires. Do not pre-create PIN/OTP/token tables while policy is open. Tracking projection itself needs no public mirror table. |
| M4-A | P4, `core.0001_revised_seventy_workflow` | Extend supported CMS keys and add source/review metadata with revision/publication consistency. Existing published content/revisions untouched; new content starts draft. No seeded contacts/legal claims/URLs treated as validated. |
| M4-B | P4, ticket contract, existing Member/user | Separate ticket/grant-if-approved/attachment/action tables, unique request/reference and policy-bound state constraints. No fake Program and no new FK writes to assistance release/EWAF state. |
| M4-C | P4, IQ-11 and actual Event, existing `events.0006_annual_observances` | Add audience-policy/RSVP records only if approved. Do not auto-create events, backfill historic attendance as RSVP, or count RSVP as PA. If working schema lacks dependencies, report prerequisite; do not change startup deferral or apply them implicitly. |
| M5 | P5 | No default new schema. Validate the approved additive sequence on a fresh disposable copy and review an explicit working/production plan separately. |

Before generating any file: approve exact fields, constraints, indexes, data minimization/retention and dependencies for that phase; inspect actual current leaves again; document reversibility and migration SQL/plan. Empty additive tables require no speculative data migration. Existing migrations are immutable. No blanket `migrate` to repair a new screen. Later operational application requires a reviewed exact plan, separate instruction and backup/private-file recovery preparation.

## Proposed feature gates and disabling

Names are illustrative, not settings introduced by this phase:

| Gate | Depends on | Disabled behavior |
|---|---|---|
| Association pending intake | M2 schema, reviewed form/checklist, IQ-10/16, private upload/retry checks | New public submit/output endpoints unavailable; existing guidance and onsite route retained |
| PDAO pending intake / forwarding (separate gates) | IQ-09, M2 schema, reviewed checklist/transfer permissions | No public intake or forwarding action; public guidance only where reviewed |
| Submission-context completed form | IQ-10 access contract and private rendering/access tests | No later full-form endpoint; only permitted receipt output |
| Tracking by process | IQ-03 and related IQ-09/10, allowlist/recovery tests | Server rejects direct requests; never reuse retired program tracker |
| Information/routine/evaluation review | Approved source-service adapter; IQ-08/12; terminal remedy separate gate | Requests/findings may be retained if independently approved; blocked correction/reopen actions fail closed |
| Resources | Reviewed CMS schema/content and permissions | No public draft; preserve existing seven entries until new destination is implemented and enabled |
| Referral tickets / RSVP | Each distinct access/state/reference/audience contract | No direct public intake and no implied ticket tracking |

Every service and view must check its effective gate, approved contract revision, available schema and current permission; missing dependency must fail closed. A flag alone is insufficient. Gate configuration for synthetic tests is explicit and cannot become production defaults. Ordinary `program_intake`, alternative verification routes and deferred EWAF schemas remain unchanged.

Prefer **disable** over destructive rollback: stop new public intake/actions, retain references/submissions/private files/audits, give truthful generic guidance, and keep approved staff handling available only where safe. Already issued references remain resolvable by authorized staff. Do not reverse migrations that would drop new submissions or erase history. Restoring an older code version may not safely handle newer records; review a forward fix or coordinated database/private-media restore in an authorized disposable environment first. Do not automatically delete retained uploads, publish pending drafts or retry PDAO transfer on enablement.

## Validation and dependency review

No new application dependency is proposed. Existing ReportLab/validators/templates/services should cover ordinary forms/receipts. QR remains optional; review a concrete library/security/accessible fallback need before adding anything. PDF audit used already bundled `pypdf`, `pypdfium2` and `openpyxl`; application requirements and environment were not changed.

Each later schema/service slice needs tests for direct unauthorized access, category/object confusion, gate disabled/missing table, bad/stale policy, unsafe/oversized upload, same-key/different-payload/concurrent retry, concurrent review/approval, permission revocation, audit/storage rollback, immutable reference/revisions, no Member/PA/score side effects and cross-channel retention. Browser checks must exercise complete authorized synthetic flows, print/text/QR alternatives, semantic labels/errors/focus and mobile reflow. AC mapping is in [traceability](plan-and-traceability.md). Do not claim a hidden action or scaffold as a complete feature.
