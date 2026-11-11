# G18-B Gate 1 source dependency inventory

Local `feature/events`, 2026-10-18. Accepted milestone **70%**. This is an
inventory of the existing writers and Gate 1 observations, not authorization
to change those writers, enable scoring, or implement Gate 2.

## Classification and lock notation

- **COVERED**: supported source mutations have an observed value, version, audit
  identity or immutable revision that invalidates a matching development context.
  This does **not** mean all writers share an atomic promotion protocol.
- **PROHIBITED**: an existing supported entry point rejects the mutation or the
  requested operation is outside this gate. This is not protection against DBA SQL.
- **UNRESOLVED**: values can be observed but complete mutation/ABA, locking or policy
  semantics are absent. These paths prevent a current-result/atomicity claim.

T = installation `ProgramTermsLock(1)`; P = Program; A = ProgramApplication;
M = Member; E = EligibilityStatus. Sorted collections use ascending primary key.
Durable capture holds **T -> P -> all A -> distinct M -> all E**. Request/attempt
intent, complete historical graph, and failed outcome use separate transactions.
Locks here describe actual code, not a new universal order imposed on writers.

## Coverage matrix

| Source / supported mutation path | Class | Existing locks and audit | Affected scope / Gate 1 observation | Test evidence |
|---|---|---|---|---|
| Onsite membership intake: `membership.services.submit_application` | COVERED | MembershipSettings lock; new intake/documents and MembershipEvent in transaction; file cleanup on failure | No candidate until Member + program application exist; complete program inventory captures later entry | `membership.tests`, durable pool-entry tests |
| Manual PRPWD verification and approval/rejection: `record_verification`, `decide_application` | COVERED | pending intake lock + displayed version; MembershipEvent; approval creates Member atomically | Every program containing that member; status/verification/decision actors and latest audit match in old source context; new intake version/snapshot digest + event identities | `membership.tests`, `ewaf.test_readiness`, `test_evidence_corrections` |
| Reopen or reverify an already decided intake through those services | PROHIBITED | `locked_pending` rejects final decision; no supported reversal | Existing approved provenance retained; no new reversal flow | `membership.tests`; inspected pending guard |
| Membership registration settings / PRPWD URL admin | UNRESOLVED | Django admin LogEntry; no EWAF shared source revision | Future intake only under current code; retroactive re-verification policy unspecified. Not treated as revocation of an already issued verification | `membership.tests`; no retroactive invalidation acceptance test |
| Member profile, disability, income, employment, dependents: `members.services.update_member` | COVERED | M + expected version; MemberEvent before/after in same transaction | All applications/programs of member; member version/profile hash and member event identities | `members.tests`, `test_evidence_corrections`, durable/pool concurrency |
| Active/inactive/archive/restore: `members.services.change_status` | COVERED | M; version increment + MemberEvent | All programs of member; active flag, version, audit IDs; change then restore cannot recover old token | `test_source_freshness` ABA; durable member-writer concurrency |
| Program submission: `programs.services.submit_application` | COVERED | T -> P -> M, reference counter; ProgramLog + versioned submission provenance | One program, ALL retained applications even post-cutoff; no slots/page subset | `programs.tests`, durable pool entry/cutoff/128-cap tests |
| Application status: `programs.services.change_application` | COVERED | P -> A; expected version, ProgramLog; case invalidation + AssistanceLog as applicable | Program inventory and member's PA contexts if receipts change separately; status/version/eligibility audit observed | durable eligibility-exit concurrency, pool tests |
| Eligibility review: `assistance.services.review_eligibility` | COVERED | P -> A -> (all program M for EWAF) -> M -> E; AssistanceLog + A version | Program pool entry/exit; exact checklist/case hash, current versions and audit match | `test_evidence_concurrency`, `test_durable_services`, assistance tests |
| Eligibility status meanings: `assistance.services.configure_status` | PROHIBITED | Always raises after permission check | No interpretation changes; all E rows locked during capture | assistance tests; inspected fixed-workflow guard |
| Photo review/correction: `programs.workflow.review_photo`, `correct_application`, `store_photo` | COVERED | P -> A -> M; photo review/document revision retained, A version, ProgramLog and case invalidation audit | One program application; current photo/review identity, bytes hash, member version, A version | `programs.test_revised_workflow`, `test_evidence_corrections`, `test_readiness` |
| Application answers, direct uploads and reused-document replacement: `correct_application`, initial submission | COVERED | Same workflow locks; retained ProgramDocumentRevision, ProgramLog; no old evidence overwrite through correction flow | One application; requirements snapshot, answers digest, file hashes + reuse lineage | program revised workflow; evidence/readiness tests; new missing-byte test |
| Membership document verify/reject/expiry: `documents.services.verify_document` | COVERED | M; immutable-by-workflow new DocumentVerification + MemberEvent; no Member.version bump required | All member programs, including reused evidence and criterion mappings; latest review ID + bytes hash + expiry | durable document concurrency, evidence concurrency, expired-document regression |
| Membership requirement add/change, required/active/type/instructions/order: `documents.admin.MembershipDocumentRequirementAdmin` | UNRESOLVED | Django admin LogEntry; no shared M/T/source-generation lock or revision | New supplement hashes ALL requirement rows, conservatively invalidating all programs; added row without upload detected. Silent ORM change-and-restore can evade observation | new metadata/addition/concurrent-writer/ABA-limit tests |
| DocumentType name/description, DisabilityType name/active used by protected program | PROHIBITED | `programs.terms` reference guard, T; guarded save/update/delete/bulk update; upsert replacement rejected | Published/approved/historically published program terms frozen | `programs.test_approved_terms` |
| DocumentType metadata used only by membership evidence; unprotected classification edits | UNRESOLVED | reference T guard checks protected program usage, admin LogEntry; no complete revision contract | membership document type metadata hashed; current disability qualifications observed; unversioned ABA remains possible | new document-type metadata test; approved-terms tests |
| Criterion assessments, correction/dispute/rejection: `ewaf.evidence_services.record_assessment` | COVERED | T -> P -> A -> M; revision checks; immutable artifact + protected ProgramLog | Application + program pool; exact latest five assessments, policy identity, source manifest, state, disputes, expiry, trace identity | evidence correction/concurrency; durable missing/disputed/revoked tests |
| Evidence definitions/readiness: `record_policy`, `record_readiness` | COVERED | T -> P (readiness also A/M); immutable revisions + protected ProgramLog | Policy program; definitions and latest assessment provenance checked. Diagnostic writes may conservatively stale a token via source audit IDs | evidence/pool/durable regressions |
| Five-criterion configuration/validation/review/authority evidence: `ewaf.configuration_services.record_*` | COVERED | T -> P -> selected configuration/validation; immutable artifacts, protected ProgramLog | One program; full configuration context, latest history IDs/digests and exact mathematical replay | configuration concurrency, durable configuration-change test |
| Scoring proposal: `ewaf.scoring_services.record_scoring_policy`; applicant diagnostic | COVERED | T -> P (diagnostic A/M/assessments); immutable revisions and audit | One program; current policy/config/evidence-policy identity checked; governance remains unapproved | scoring/pool/durable tests |
| Four-criterion reference configuration activation; edit historical criteria/digests/results | PROHIBITED | No activation contract; old artifacts append-only; operational entry points fail closed | Reference remains proposed; no alteration of historical five-criterion meaning | four-criterion, AHP, normalization, scoring, durable immutability/replay regressions |
| Program definitions, requirements, publication/authorization: `programs.services.save_program`, `save_requirement`, `change_publication` | COVERED | T -> P; version checks and ProgramLog; protected term edits refused | One program; actual terms digest, policy context, program version, status/readiness findings, source audit IDs | approved terms/policy/public availability tests; configuration/pool tests |
| Major changes to approved/published program terms or linked event terms | PROHIBITED | `guard_program_form`, `guard_requirement_form`, `guard_event`; T | Requires future authorized reapproval workflow; no Gate 1 change | `programs.test_approved_terms` |
| Linked event state/terms: `events.services.save_event`, `change_publication` | COVERED | T -> Event, expected version; EventLog; protected link/terms guard | Linked application program; actual terms hash plus new event version/status/publication digest | events/approved-terms regressions; Gate 1 linked-event test |
| Existing approval record/terms/binding: `record_pdao_approval`, `capture_terms`, `bind_approval` | COVERED | T -> P/control; immutable approval/terms/binding + ProgramLog | One program; actual and bound digests/control version; source audit IDs catch new unbound approval records too | PDAO/approved-terms/config/evidence tests; enforcement code/settings untouched |
| Selection/decision: `assistance.services.decide_assistance` | COVERED | P -> A -> sorted program M if EWAF -> M -> E; AssistanceLog/A version | Case and inventory observed; new EWAF-dependent final decisions still denied by existing gate | assistance regression, durable historical-decision rejection |
| Release/void: `assistance.services.record_release`, `void_release` | COVERED | P -> A -> sorted program M if EWAF -> M -> E; void also release lock; AssistanceLog in transaction | ALL retained releases for same member across ALL programs (no time/type default). Full receipt-state hash detects receipt followed by void even if count returns | durable and evidence cross-program receipt/void concurrency tests; Gate 1 receipt/void ABA test |
| Processor activity/staff/superuser/direct/group permissions: `accounts.admin.AdministratorAdmin`, `RoleAdmin` | UNRESOLVED | superuser-only admin, Django LogEntry; no common EWAF lock or monotonic authority generation | New observations reload processor, hash grants/groups/effective permissions + actor/current-group admin event IDs. Revocation rechecked; admin history can detect restoration. Direct ORM changes/restoration and removed-group ABA not guaranteed | new permission topology/cache/admin-audit/interleaving tests; accounts security tests |
| Historical evidence signer's subsequent role revocation | UNRESOLVED | Historical actor/audit retained; no approved retroactive authority revocation contract | Do not silently invalidate previously authorized signed evidence solely because an actor later changes roles | Policy decision required; no acceptance rule invented |
| Document/assessment expiry, evaluation day/timezone | COVERED | Clock, no writer/row lock; expiry inclusive through recorded local date under existing rule | Recomputed before/after calculation and after graph persistence; date/timezone included; expired required evidence blocks | new expiry/history test; existing assessment/document-expiry tests |
| Clock rollback, expiry immediately after last observation | UNRESOLVED | No shared logical-clock/expiry generation | No indefinite usability claim; consumer must recheck; Gate 2 must define valid-until policy | Explicit limitation; no arbitrary wall-clock atomicity claim |
| Private file byte overwrite/removal outside correction service | UNRESOLVED | Filesystem not transactional with MySQL, no immutable object-version provenance | Missing/changed bytes observed and block; original photo/direct-upload review did not bind bytes. Change/restore between reads can evade checks | new missing-byte test; document storage/evidence corrections regressions |
| Direct SQL, bypassed ORM guards, audit deletion/tampering, external imports | UNRESOLVED | Not a supported source writer contract; no DBA tamper-proof claim | Gate 1 is not CDC. Imports/future writers must join Gate 2 or be prohibited | durable integrity/DB constraint tests cover supported graph only |
| Legacy live EWAF save/input/ranking/current result; automatic public results command | PROHIBITED | `ewaf.services.require_current_ewaf_workflow`, durable operational gate, retired `process_closed_programs` | No live scoring, ranking, selection or publication enabled | historical EWAF and durable default-disabled regressions |

## Complete inventory and historical semantics

The retained pool is every program application, ordered by PK, with an explicit
fictional cutoff; post-cutoff rows still participate in the observation digest.
In-scope unresolved applicants block; incomplete eligible applicants block rather
than disappear; ineligible applicants need an audited current outcome. Existing
`pool_services` remains the read-only readiness inventory for incomplete cases.
It has not been changed into an acceptance or operational scoring service.

Only new development snapshots use `durable-pool-development-2` and the supplemental
`g18-b-source-observation-1` envelope. Canonical hash encoding and all historical
source/configuration/math/artifact formats remain unchanged. Version 1 snapshots
replay unchanged; they require a new request before claiming Gate 1 observations.
Historical inspection reports `sources_match_now: null`, never current usability.

No mutation service in this matrix was edited. COVERED entries are supported-path
observation coverage, not durable invalidation records. Gate 1 cannot establish
complete source-change coverage or atomic promotion while UNRESOLVED entries remain.
