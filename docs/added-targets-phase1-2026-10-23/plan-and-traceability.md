# Traceability provenance reconciliation — 2026-10-23

All original sources are now accessible at the repository root and match the expected checksums supplied directly by the owner. The integrated Markdown's 12 BF / 18 BR-A / 14 AC-B / 16 IQ rows and the original 23-page Brainstorm confirm the matrix below: **no substantive mapping or phase change**. Section 8 is byte-identical to the baseline. See [final completion review](completion-review.md) and [source verification](final-source-verification.json).

Phase 1 is Complete as audit/design work. All feature-acceptance statuses and pending policies below remain unchanged; no Phase 2 authorization is inferred. The five phases still overlay the historical G-stages. The following original matrix and its earlier PDF-only source statement are retained unchanged as historical evidence; the source-availability limitation is superseded by this addendum.

---

# Added targets five phase plan and traceability

Date: 2026-10-23. Status: Phase 1 design for review; no application implementation authorized by this document. Accepted milestone remains 70%. These five phases overlay, and do not replace, historical G-stage identifiers or dated validations.

Source: [integrated reading edition](../../Santolan_Overall_Specification_Integrated.pdf), supplied by the owner during this audit, §§3.4, 5.3–5.11, 6.9, 7.7–7.13, 9.4, 10.1, 12.6–12.7, 13.1, 15.4–15.5. Its BF/BR-A/AC-B/IQ identifiers are retained below. The integrated Markdown, separate integration log, and original `Brainstorm Final(2).pdf` are unavailable. Brainstorm page references are inherited citations from the integrated PDF, not independent examination of that original. See [progress and decisions](progress-and-decisions.md).

## Exactly five development phases

| Phase | Agreed target and proposed development scope | Entry dependencies | Required checkpoint |
|---|---|---|---|
| 1 — Baseline audit, traceability, design | Read sources; inspect checkout; hash existing files and Section 8; characterize baseline; propose records, permissions, states, gates and migrations; record every BF, BR-A, AC-B and IQ disposition. Test/evidence tooling and documentation only. | Current authorization. Missing-source limitations remain explicit. | Deliver this report; resolve remaining source verification; owner reviews design. Stop. |
| 2 — Registration and kiosk-inspired retrieval | Separate Association/PDAO pending intake; accessible pre-submission guidance, print/walk-in channels, receipts and controlled completed-form output; Members inbox/search/detail; onsite findings, corrections/history; approved adapter to existing membership decision service; permitted PDAO forwarding facts. No tracking activation. | Explicit Phase 2 authorization; approved Phase 1 non-EWAF schema plan and IQ-09/10/16 contracts, privacy/upload/checklist handling, first-time identifier policy. Independent Association work may proceed if PDAO remains blocked. | Synthetic authorized journeys, direct unauthorized requests, duplicates, concurrency/audit rollback and baseline regression; report blocked pieces. Stop. |
| 3 — Tracking, information updates, review | Three separately projected tracking views only after approved access contract; no-change declaration; staff change/stale/discrepancy/routine-review cases; selected/nonselected evaluation-review requests; existing authorized correction services and explicit recalculation only. | Explicit Phase 3 authorization; IQ-03, IQ-08, IQ-12 and dependent IQ-02/07/10/16 decisions; safe current source-service integration demonstrated. | Approved tracking/review routes only; source dates/history, complete-pool, terminal-case and disclosure protections demonstrated. Stop. |
| 4 — Public services and content integration | Append Resources & Help; CMS source/review metadata; Home/footer/notice links, external verification labeling, approved form guidance; separate member-only referral tickets; event audience/instructions; optional approved RSVP; accessible explanations of actual method. | Explicit Phase 4 authorization; reviewed content; ticket-specific verification/state/reference contract; IQ-11/16 and IQ-13 placement. Event-creation conflict requires a decision if new scheduled events are needed. | Demonstrate public content/private drafts, ticket/RSVP separation, unchanged masks and eight Admin groups, accessible journeys. Stop. |
| 5 — Regression, accessibility, handover | Reconcile all identifiers to delivered evidence/deferral; targeted/full regression; privacy/security/concurrency and accessibility journeys; UAT materials and actual findings only if performed; authorized disposable backup/restore; status/guidance and enablement proposal. | Explicit Phase 5 authorization; exact approved scope/configuration, isolated fixtures, reviewable migration sequence; separate authorization for disposable restore and actual UAT participants. | Pass/Fail/Blocked/Not Tested register, protected-file diff, known limits and production prerequisites. Stop; no automatic deployment or milestone increase. |

No phase implies production access, working-database migration, deployment, commit, merge or push. A later "proceed" applies only to that phase's agreed scope. Phase 5 does not become a vehicle for deferred EWAF, new roles, notifications, government APIs or cash disbursement.

## BF requirement inventory

Categories describe inspected source, not working-database availability. "Reusable" does not mean the complete addition exists. Paths are repository-relative. All added behavior is deferred from Phase 1.

| ID / source | Existing or missing capability; disposition | Affected modules and reuse evidence | Delivery phase / acceptance / gates |
|---|---|---|---|
| BF-01; §§5.4, 7.7, 9.4 | **Existing/reusable + absent + policy-blocked.** Onsite intake/approval exists; public pending registration, completed-form receipt and cross-channel reconciliation absent. Add a pending envelope without creating a Member. | `membership/{models,forms,services,views}.py`, `members/models.py`, `documents/validators.py`; `submit_application`, `record_verification`, `decide_application`. Existing form's control-number and all-required-files assumptions cannot be inherited blindly. | P2; AC-B01/03/04/06/13; IQ-10/16, OQ-27. |
| BF-02; §§5.4, 7.8 | **Absent + policy-blocked.** Separate PDAO guidance exists; individual ID-assistance intake/forwarding does not. Program PDAO approvals are a different lifecycle. | `membership/guidance.py`; future membership intake sidecars. Preserve `programs/approval_services.py`, `binding_services.py`, protected terms. Never reuse `PDAOApprovalRecord` as an individual's ID application. | P2; AC-B01/04/06; IQ-09/10/16. |
| BF-03; §§5.4, 6.9, 7.9 | **Existing/reusable + absent.** Membership UUID/submission key, permission-checked staff detail and attachments exist. Membership list searches name/control number, not reference. New category references, receipt/completed-form output, reference search and optional QR absent. | `membership/models.py`, `views.application_list/application_detail/download_document`; `programs/workflow.allocate_reference` remains program-only. | P2; AC-B01/02/03/13; IQ-10 and submission-context access approval. QR may remain deferred. |
| BF-04; §§5.5, 7.9, 12.6 | **Absent + policy-blocked.** Legacy program status/QR routes return HTTP 410. No current public registration tracking. Do not reactivate legacy tokens. | `programs/views.application_status/application_qr`; new safe projections over existing application or new intake records, distinct from Admin views. | P3; AC-B05/06/13; IQ-03/09/10/12. |
| BF-05; §§5.6, 7.11 | **Absent + policy-blocked.** Existing verification is program-scoped; no ticket-specific member grant or request lifecycle. | `programs/services.py`, `events/services.py` matching helpers are reference patterns only; new ticket service under Applications & Verification. Existing assistance case/release models are unsuitable as ticket records. | P4; AC-B09/13; ticket contract, IQ-10/16. No ticket tracking inferred. |
| BF-06; §§5.7, 7.10 | **Existing/reusable + optional-only + absent + policy-blocked.** Member/document/application corrections and EWAF source invalidation exist. `program_intake` source collection uses optional settings and different matching. No ordinary current-information declaration or approved routine sampling workflow. | `members/services.update_member`, `documents/services.verify_document`, `programs/workflow.correct_application`, `ewaf/evidence_services.py`; `program_intake` remains excluded from ordinary `INSTALLED_APPS`. | P3; AC-B07/08/14; IQ-01/02/07/08/12. No automatic calculations or invented review intervals. |
| BF-07; §§5.3, 5.10–5.11 | **Existing/reusable + absent.** CMS revisions/publication, Home/support pages and notices exist. Dedicated eighth destination and structured resource provenance absent. | `core/{models,content,urls}.py`, `core/context_processors.py`, `templates/public/`, `announcements/`; reuse one maintained content record per subject. | P4; AC-B11/13; IQ-13 resolved target placement, IQ-16 ownership and reviewed source content. |
| BF-08; §§5.9, 7.13 | **Existing/reusable + conflicting + policy-blocked.** Annual observances, existing scheduled event records and restricted attendance exist. Public registration is HTTP 410; new custom event creation is also HTTP 410. RSVP absent. | `events/{views,models,services,observance_models}.py`. Keep observances separate; do not restore event creation without scope decision. | P4; AC-B12/13; IQ-11/16; conflict C-05 in progress register. |
| BF-09; §§5.8, 7.12 | **Existing/reusable + absent + policy-blocked.** Masked result projections, explicit publication, Help Desk and controlled corrections exist. Dedicated evaluation-review requests/private applicant explanations absent. | `announcements/{results,public_results}.py`, `programs/workflow.py`, `assistance/services.py`; read calculation provenance via current permission-checked services. | P3 private review, P4 public explanation; AC-B10/11/14; IQ-03/12. |
| BF-10; §§3.4, 5.8, 15.5 | **Conflicting; explicitly deferred.** Public eligible lists, expanded identifiers and numerical ranks prohibited within this mission. Preserve initials/last-four masks and unset numerical business rank. | Existing `announcements/results.py` allowlist and `ewaf/operational_*` comparison remain protected. | No implementation in P2–P5; P5 proves continued exclusion; AC-B11/14; IQ-04/05. |
| BF-11; §§5.10, 12.7 | **Existing/reusable + incomplete.** Shared semantic templates/display controls exist; new journey accessibility is unimplemented and untested. | `templates/partials/accessibility.html`, `templates/public/`, shared styles and browser harness patterns. No reliance on toolbar or QR alone. | P2/P3/P4 per feature, P5 comprehensive evaluation; AC-B13; IQ-07 approved assisted/evidence routes. |
| BF-12; §§3.4, 7.10, 15.5 | **Conflicting; explicitly deferred.** Household Monthly Income changes SI meaning and is not approved. Existing income fields are not approval. | Preserve `members/models.py` fields and all EWAF versions/inputs/policy. | No implementation in P2–P5; P5 preservation; AC-B14; IQ-06. |

## Supplementary rules and checks

| Rule | Preserved/additive contract | Planned evidence |
|---|---|---|
| BR-A01 | Online/printed/walk-in intake with required onsite process | P2 AC-B01/03/04; common policy snapshot and onsite guard |
| BR-A02 | Pending ≠ Member; PDAO forwarding ≠ government approval | P2 AC-B04/06; no Member or ID issuance from PDAO path |
| BR-A03 | Retained form/reference/receipt and correct Admin category | P2 AC-B01/02; atomic writes and retry rollback |
| BR-A04 | Reference possession never opens private staff forms | P2 AC-B02 and P3 AC-B05; direct GET/POST/download denial |
| BR-A05 | Online printout resolves to same intake | P2 AC-B03; no name-only merge or second Member |
| BR-A06 | Approved tracking fields/access/next actions | P3 AC-B05/06; blocked until IQ-03 approval |
| BR-A07 | Declaration never renews independent verification | P3 AC-B07; unchanged dates, source-version tests |
| BR-A08 | Routine review has approved basis/alternatives/resolution | P3 AC-B08; policy fixture labeled synthetic, no imputation |
| BR-A09 | Screening ≠ approval; uncertain ≠ confirmed failure | P3 AC-B07/08; preserve ordinary eligibility path; IQ-02 |
| BR-A10 | Classification match ≠ PR rubric and yields no extra points | P3/P5 AC-B07/14; preserve complete approved qualifications |
| BR-A11 | Tickets/RSVP/readiness never create PA evidence | P2/P4 AC-B04/09/12; inspect release/PA invariance |
| BR-A12 | Own evaluation review for selected and nonselected | P3 AC-B10; private findings; explicit existing correction/recalculation |
| BR-A13 | Explain actual method; no public ranks/allowlist expansion | P4/P5 AC-B11/14; current policy and masked projection tests |
| BR-A14 | Resources public without membership/data collection | P4 AC-B11/13; anonymous browse and source review |
| BR-A15 | RSVP intention distinct from selection/attendance | P4 AC-B12; direct restricted-attendance denial |
| BR-A16 | CMS uses current authorization/history | P4 AC-B11; draft/private asset denial, publish/audit rollback |
| BR-A17 | Accessible alternatives preserve safeguards | P2–P5 AC-B13; keyboard, plain text, print/QR alternatives |
| BR-A18 | Deferred field/measurement/disclosure/access changes stay gated | All phases; AC-B05/11/14; protected manifest and direct-route checks |

## Acceptance plan and current evidence status

Statuses below refer to acceptance of the **added capability**, not the successful creation of this plan. Each future test must use synthetic data and approved contracts; no fabricated operational policy.

| Check | Phase / concrete test plan | Phase 1 status |
|---|---|---|
| AC-B01 | P2: both categories, validation failure, same-key retry, changed-payload replay, concurrent submission, receipt and inbox consistency, no Member side effect | Not Tested — addition absent; IQ-09/10 blocks dependent design activation |
| AC-B02 | P2: staff reference selection/search; deny anonymous/wrong-permission/revoked/cross-object detail, attachment and completed-form downloads; audit failure prevents delivery | Not Tested — reusable baseline inspected, no new routes |
| AC-B03 | P2: online plus print retrieves same retained record; walk-in creates one; same name/contact never auto-merges; stale correction preserves revisions | Not Tested; cross-channel policy IQ-10 pending |
| AC-B04 | P2: all decision entry points require approved onsite findings and manual PRPWD; one Member under concurrent approval; PDAO paths cannot call membership approval or issue ID | Blocked — first-time identifier/checklist adapter and PDAO authority pending |
| AC-B05 | P3: allowlisted status projection; generic failures; bounded abuse/recovery; cross-record/QR/reference tampering; no private form/evidence/reason/edit access | Blocked — IQ-03; retired routes remain 410 |
| AC-B06 | P2 stored states, P3 projection: received/needs-information/ready/decision/forwarded remain distinct; only genuine appointments displayed | Blocked — state/access/forwarding contracts awaiting approval |
| AC-B07 | P3: no-change leaves verified dates untouched; unsupported changes remain untrusted; approved corrections retain predecessors and invalidate dependent use without calculating | Not Tested for additions; existing stale-source baseline tests passed |
| AC-B08 | P3: approved routine basis, reviewer/observation/effective dates, no arbitrary interval/sample/expiry; unresolved cases block complete pool | Blocked — IQ-08; existing pending-pool baseline passed |
| AC-B09 | P4: ticket-specific verified member grant, revoked member and forged grant blocked; receipt/history; ticket cannot write eligibility/selection/releases/PA | Blocked — ticket access/state/reference contract absent |
| AC-B10 | P3: selected and nonselected own-case requests, representative authority, stale/concurrent request handling, immutable provenance; closed/published remedy denied without authority | Blocked — IQ-03/12; existing correction/recalculation services remain protected |
| AC-B11 | P4: anonymous Resources, private drafts/assets, linked maintained records, sources/review/publication, method fidelity, unchanged masks and no eligible list/ranks | Not Tested for additions; existing masked-publication baseline passed |
| AC-B12 | P4: actual scheduled event, approved audience/fields, duplicate/cancel/capacity handling, separate actual attendance; no PA/release effect | Blocked — IQ-11 and event creation conflict if relevant |
| AC-B13 | P2–P5: keyboard/focus, status/errors, screen-reader sample, contrast, 200% text/zoom/reflow/mobile, controlled read-aloud/select-and-read, accessible upload, print/save, text QR alternative, calendar list; representative UAT | Not Tested — no new UI or UAT session; no WCAG certification |
| AC-B14 | P1 baseline and P5 post-extension: four/five histories, AHP/RI/CR, directions/bounds/missing/stale, complete pool, ties/unset rank, history, decisions/capacity, publication/release/PA; hash/diff protected sources | Baseline subset Pass: 84 existing tests. Final acceptance Not Tested: additions do not exist and full regression not run |

See [baseline and tests](baseline-and-tests.md) for exact commands, limits and existing test names. Future test assertions must strengthen extension boundaries without changing existing assertions to permit altered EWAF behavior.
