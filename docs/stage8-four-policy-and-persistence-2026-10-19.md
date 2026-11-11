# Stage 8 four-criterion policy and persistence review

Accepted milestone: **70%**. This document records development compatibility and
remaining authorization requirements, not Association scoring approval. Read with
`Stage8_Independent_Review_2026-10-19.md` and the final sprint validation report.

## Policy readiness requirements

The President-approved amendment removes PR from numerical scoring for specifically
authorized programs. Its approval date remains **unknown**. No May date, effective
date, approving role or program list is inferred. The recalculated SI/ES/PA/ND
configuration remains proposed and inactive. Computation.docx is a reference, not
an operational replacement for the historical workbook.

Before operational readiness, the Association must provide a versioned decision
record containing all of the following. Empty fields mean BLOCKED_POLICY.

| Decision | Required content | Current development treatment |
|---|---|---|
| AHP | Confirm exact four-criterion judgments, method and derived weights; authorized program IDs, approver and documentary authority | Six comparisons independently replay the existing 50-digit Decimal reference; no rounded weights supplied manually |
| SI | Measurement, individual/household basis, observation period, units, evidence and verification | Explicit fictional verified income fixture only; no universal income policy inferred |
| ES | Categories, meaning/order, encoding, observation date and evidence | Explicit fictional text encoding only |
| PA | Actual nonvoided assistance measure, count/value basis, cross-program scope, lookback boundaries and direction | Only all retained successful nonvoided receipts across all programs are supported; any invented lookback label is rejected |
| ND | Dependent definition, household scope, observation period and verification | Explicit fictional reviewed dependent count only |
| Normalization | Direction, fixed/cohort bounds, equal bounds, missing/disputed/expired/out-of-range treatment and precision | Fictional fixed bounds only; missing or invalid evidence blocks; no imputation or silent clamping |
| Classification/ties | Gap-free boundaries, precision/display rules, exact ties, exceptions and review | No need classifications, business ranks or automatic tie-breaks; exact higher/equal comparison counts only |
| PR eligibility | Program qualifications, actual functional need, required verified evidence, rubric outcomes, consent/privacy, accessible assessment alternatives and disputed-case review | Three distinct named fictional rubric findings required; disability classification alone cannot establish functional need |
| Authority | Actual amendment approval date, operational effective date, approving role, program scope, supersession and evidence | None populated or assumed |

Unresolved membership and accessible-evidence decisions in Open Decisions remain
unresolved. This implementation neither changes PDAO enforcement nor introduces
home assessment rules, an online membership account or a waiver of evidence.

## Migration-free compatibility decision

The existing schema supports explicitly versioned four-criterion calculation
history. No schema change is necessary for configuration, request, result, trace,
generation binding or development promotion:

| Existing structure | Four-criterion use | Historical preservation |
|---|---|---|
| ConfigurationRevision / ConfigurationValidation | Profile `g18-four-fictional-policy-1`, exact four criterion order, six comparisons and reference replay | Original five-profile validators and outputs retained |
| ScoringPolicyRevision | Four definitions, `FICTIONAL_DISPOSABLE_TEST_ONLY`, separately named eligibility rules | No historical proposal rewritten or activated |
| EvidencePolicyRevision / CriterionAssessment | Existing reviewed sources, including immutable PR human findings used solely as eligibility provenance | Five-entry evidence schema retained; it is not represented as a four-score result |
| DurableRequest / DurableRun | Explicit request profile and snapshot engine `g18-four-complete-pool-1` | Existing digest envelopes preserved; profile-bearing payload makes interpretation unambiguous |
| DurableResult / DurableTrace | Exactly four numeric traces, SI/ES/PA/ND; retained PR eligibility snapshot outside traces | No global CRITERIA change; original five-trace graph rules apply to historical engines |
| RequestSourceBinding / RunSourceBinding | Explicit `g18-four-complete-pool-1:four-fictional-1`, integrated coverage only | Existing generation protocol, graph digest and immutable predecessor links |
| DevelopmentPromotion | Same protected disposable-only CAS and audit transaction after four graph validation | No operational pointer or new consumer |

Existing CharFields accommodate these versions. The trace database check permits
each of the four criterion identifiers; exact cardinality is a service rule,
not a new database constraint. Existing foreign keys and append-only guards apply.
Conservative Gate 1 audit dependencies are unchanged. Ordinary application mode
cannot access these new configuration/capture services or private pages.

## Persistence portion stopped: permanent developmental human decisions

No existing model correctly represents an immutable, non-operational human choice
against a particular generation-bound four-criterion run. AssistanceCase decisions
would affect real business workflows; generic diagnostics or native source audits
are not substitute decision stores. The implemented preview is transient, explicitly
marked **not saved**, and checks the current run, expected generations, actor,
eligible application and reason under the shared fence. It never changes assistance.

**Separate authorization requested:** create and test an additive migration named
`ewaf/0007_development_human_decisions.py` in fresh disposable MySQL only. No such
migration or model is created in this sprint. Proposed exact schema:

1. `DevelopmentHumanDecision`: BigAutoField ID; protected Program FK;
   protected RunSourceBinding FK; protected ProgramApplication FK; protected actor
   FK; actor_label Char(150); decision Char(24), one of SELECT_DEMO, DEFER_REVIEW,
   WITHDRAW_DEMO; reason Text(max_length=1000); recorded_at aware datetime;
   revision PositiveBigInteger; nullable protected OneToOne predecessor to self;
   source_generation, authority_generation and state_revision PositiveBigInteger;
   run_digest and graph_digest Char(64); protocol Char(60) fixed to
   `g18-four-human-decision-1`; payload JSON (immutable accepted eligibility,
   calculation identity and human reason); digest Char(64); protected OneToOne
   audit FK, added after both tables exist.
2. `DevelopmentHumanDecisionAudit`: BigAutoField ID; protected Program FK;
   protected actor FK; actor_label Char(150); recorded_at aware datetime;
   action Char(24) fixed to RECORD_DEMO_DECISION; decision_digest Char(64);
   protocol Char(60) fixed to `g18-four-human-audit-1`; digest Char(64).

Database constraints: unique(program, application, revision); unique predecessor
(OneToOne); unique audit association; checks for the three decision values,
revision/generations/state_revision within 1..9223372036854775807, and fixed
protocol/action. Indexes: (program, application, recorded_at), (run_binding,
recorded_at); standard protected FK indexes. No automatic permissions or Admin
editable registration. Existing `assistance.decide_assistance` plus development
processing/read permissions are prerequisites, not grants.

Dependencies: ewaf 0006, programs 0005, and the swappable AUTH_USER_MODEL dependency.
Two CreateModel operations followed by the decision-to-audit AddField. No data
backfill, seeds, changes to existing tables, or operational current pointer.
The FK to RunSourceBinding transitively retains the run and its accepted request.

Service-only rules: same program/application/run ownership; current complete four
graph; exact source/authority/state token; current actor permissions; unexpired
evidence at both protected-use checks; latest same-program/application predecessor
and revision+1; exact canonical, domain-versioned payload/audit digests. Lock order
T→H→P→S→Event→Application→Member→ordered leaves, then existing decision rows ordered
by PK. Business decision record and mandatory audit commit together. This output
does not mutate an EWAF input or use ProgramLog, so it must not narrow or bypass
the conservative source-audit projection. A source invalidation makes the decision
historical, not an authorization to release. No allocation quota is invented.

Migration acceptance after separate approval: inspect operations and SQL; fresh
MySQL forward/reverse/reapply; exact indexes/checks/FKs; preserve all older rows
and digests; audit/CAS/final-clock failure rollback; duplicate retry and successor
races; stale/revoked/cross-program decisions; no operational consumers; full
regression and protected-history replay. SQL/external-file tampering remains
outside the cooperating-writer guarantee.

## Conditions for milestone review

Technical evidence, independent source review and owner acceptance are still
required. Permanent decision history requires the separate schema authorization
above. Actual operational policy requires the Association decisions in the first
table and separate activation/deployment authorization. If 80% is intended to mean
a demonstration-only milestone, its narrower acceptance definition requires explicit
owner/adviser approval, as the October 19 independent review states. This sprint
does not silently redefine that acceptance boundary.
