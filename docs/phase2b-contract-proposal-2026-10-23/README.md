# Phase 2B contract proposal — review checkpoint

Date: 2026-10-23, Asia/Manila. **Contract preparation: Complete. Phase 2B application implementation: not started or authorized by this request.** This is a review-ready proposal, not an approved institutional procedure, schema, reference policy or activation instruction. The five phases, historical G-stages and owner-accepted **70%** milestone remain unchanged.

Read these together:

1. [Registration contract](registration-contract.md): proposed records, states, fields, documents, handoff, references, permissions and safeguards.
2. [Approval register](approval-register.md): exact decisions, responsible approval authorities, recommended dispositions and consequences of withholding approval.
3. [Implementation and isolated test plan](implementation-and-tests.md): ordered work, dependencies, gates, traceability and acceptance evidence required after authorization.

## Current implementation and source reconciliation

Phase 2A already supplies exact existing UUID lookup in **Members → Membership reviews**, permission-checked detail retrieval, and separate document permissions. Program-scoped reference search remains under **Applications & Verification**. Its [completion report](../phase2a-reference-retrieval-2026-10-23/README.md) records 352 selected tests, including 13 new lookup tests and 84 existing EWAF tests, plus synthetic browser checks. Those are **earlier Phase 2A results**, not tests performed during this contract review. Search does not yet understand the proposed new registration namespaces or records.

The existing onsite `MembershipApplication` requires an existing profile/control-number contract, configurable required uploads and successful manual PRPWD review before approval. It is unsuitable as the public pending form or as a PDAO record. `Member.application` and the member control number are unique; no Association control-number allocator was found in the reviewed membership services. Current form wording calls the control number a PWD identification number, while detail wording distinguishes the Association control number from a PWD ID. This conflict remains open; a new applicant must not supply an identifier that is only issued after approval.

Existing approval checks required-file presence, not typed findings for all five physical Association requirements. The proposal adds a separate pending intake and onsite findings, then calls existing services. It neither removes manual PRPWD nor treats an uploaded file as an inspected original or physical envelope. The actual configured requirement rows were not queried; their compatibility must be established using approved configuration and synthetic fixtures later.

The protected writer's enrolled mode rejects an enclosing transaction before its top-level service call (`ewaf.durable_services._boundary`). The proposal therefore refines Phase 1's general “transactional conversion” into individually atomic, retry-safe **handoff, manual verification and decision operations**, with a persistent link and guards inside existing non-EWAF membership services. It does not propose editing that writer or making three calls inside a new outer transaction. This integration remains a compatibility gate until demonstrated in isolation.

## Authority and exact sources reviewed

| Source | Use and limit |
|---|---|
| Repository-root `OVERALL_SYSTEM_SPECIFICATION_INTEGRATED.md` | §§5.4–5.5, 6.9, 7.7–7.9, 9.4, 10.1, 12.6–12.7, 13.1 and 15.5; BF-01–03, relevant BF-11, BR-A01–05/11/17–18, AC-B01–04/06/13–14 and IQ decisions. Online pending intake is an added target, not currently enabled policy. |
| Root `OVERALL_SYSTEM_SPECIFICATION.md`, `BRAINSTORM_INTEGRATION_LOG.md` | Baseline, protected Section 8 and provenance/conflicts. |
| Root `Brainstorm Final(2).pdf` | Integrity rechecked this review. Its previously recorded 23-page Phase 1 review is retained; the PDF was not newly re-extracted or visually reviewed this turn. Integrated deferrals govern. |
| `../CURRENT_SYSTEM_SPECIFICATION.md`, `../Guide for Development.md`, `../00 - Project Overview/System Master Specification.md`, repository `AGENTS.md` | Current/target distinction, source hierarchy and repository boundaries. |
| `../00 - Project Overview/Decisions.md`, `../00 - Project Overview/Open Decisions.md` | DEC-024/025/027, OQ-16/17/21/27, retained source conflicts and authority limits. |
| `../00 - Project Overview/Workflow References/2026-10-10/Confirmed_Membership_and_PDAO_Requirements_2026-10-10.md` | Confirmed separate lists and alternatives. The PDAO notice is owner-supplied guidance; its currency and Association processing authority are not established. |
| `../05 - Development/October 10 Implementation Impact.md` | Historical implementation/target distinction. |
| `docs/added-targets-phase1-2026-10-23/` | Original audit, traceability, design/migration proposal, completion/source/preservation evidence and single progress record. The original proposed design is preserved, not silently replaced. |
| `docs/phase2a-reference-retrieval-2026-10-23/README.md`, `validation.json`, `preservation.json` | Actual delivered lookup and earlier regression limits; no inference that new categories exist. |

Code inspection covered `membership/models.py`, `forms.py`, `services.py`, `views.py`, `urls.py`; `members/models.py`, `profile.py`, `profile_forms.py`; `documents/models.py`, `validators.py` and private delivery/storage; existing membership templates; `accounts` permission patterns; `config/settings.py`; current migration filenames and test isolation helpers. Protected `ewaf/membership_invalidation.py`, `shared_invalidation.py`, `generation_records.py`, `durable_services.py` and `programs/terms.py` were read only to establish integration boundaries. No settings import, `.env` read, working-database query or startup command was needed.

## Readiness and remaining blockers

**Reusable now:** Phase 2A's authenticated list/detail/search pattern; shared server-rendered templates; current reference values; ordinary onsite services, permission checks, audit patterns and private-file validators/delivery; the isolated synthetic test harness. Reuse does not mean the new intake is implemented.

**Technically specified, awaiting owner design approval and scoped implementation authorization:** additive pending records, append-only revisions/actions, category-aware staff retrieval, candidate random references, retry binding, submission-context printing, separate capabilities and default-off gates. No new dependency is proposed.

**Blocked before use:** approved form fieldsets and online-upload policy; OQ-27 originals/copies/physical findings/correction rules; first-time Association identifier semantics; permitted handoff/configuration mapping; session-output lifetime and bounded-attempt configuration; privacy/retention and staff assignments. PDAO collection/review additionally needs IQ-09/16 authority and a verified checklist version. PDAO forwarding needs a named recipient, authorized manual transfer procedure and truthful fact/status contract. Public tracking, credential/recovery design, public corrections and QR tracking remain Phase 3/IQ-03; they are excluded from 2B.

The approval register permits an explicitly restricted Association-only implementation tranche while PDAO stays server-side unavailable. Neither absence of an answer nor approval of this proposal grants PDAO authority, production access, migration application or deployment permission.

## New evidence and changes in this review

Only new proposal/evidence files in this directory and a prepended checkpoint in the [single progress record](../added-targets-phase1-2026-10-23/progress-and-decisions.md) were written. All earlier progress bytes and Phase 1/2A artifacts are retained. Application files already modified by Phase 2A remain untouched.

[Baseline](baseline.json) captures the actual branch/HEAD, uncommitted state, 816 tracked-file hashes, 267 protected paths, previous evidence and source hashes. [Verification](verification.json) records fresh file/Section 8 comparisons and documentation checks. **No application tests were executed during this documentation-only task.** No UI was changed or newly demonstrated. Earlier screenshots are synthetic Phase 2A evidence only.

Section 8 is still byte-identical between the original and integrated Markdown: **8,384 bytes**, SHA-256 `f446ea0be7cf061439293c75f6354bdde77c6e2e4870e69611cc19bd1abec41d`. No text normalization is used. All 267 protected files, existing migration files, and application/test files match this turn's starting state. Hash preservation is not a newly executed behavior regression.

No schema, migration, gate, dependency, credential, deployment setting, database, application behavior or EWAF rule changed. The benefit is a reviewable contract that prevents pending registration from being mistaken for membership or government approval. Remaining risks are sensitive-document collection, session exposure on shared devices, identity duplication, incompatible legacy evidence configuration and unapproved PDAO powers; the proposed gates address them but have not been implemented or tested.

**Stop for project-owner review.** The next instruction must identify approved decision IDs and the exact implementation subset. Keep production/working-data access, migration creation/application, operational enablement and deployment as separately bounded authorizations.
