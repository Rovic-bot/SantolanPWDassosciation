# Stage 8 consolidated source coverage

2026-10-19. Disposable development scope only. Accepted milestone: **70%**.
Read with [validation and acceptance conditions](stage8-consolidated-validation-2026-10-19.md).
The versioned contract is `g18-stage8-integrated-disposable-1` in
`ewaf/generation_protocol.py`. This is a supported-application-writer contract,
not a database trigger or protection against privileged SQL.

## Scope and native audit matrix

| Writer family | Status within registered disposable session | Trusted affected scope and mandatory evidence |
|---|---|---|
| User/Group Admin, permission M2M, deletion, password/status | COVERED, preserved Gate 2C | One global AuthorityGeneration transition plus AuthorityInvalidation and native LogEntry/SecurityEvent; no per-program authority fan-out. Ordinary authentication maintenance remains excluded. |
| Membership onsite submission, manual verification, approval/rejection | COVERED, new adapter | Pending intake has no retained program applications. One native MembershipEvent and zero-program SourceMutationBatch; no invented program or SourceInvalidation. Approval creates a new Member. Finalized intake reopening remains prohibited. Duplicate submission creates no transition. |
| Member profile/status | COVERED, new adapter | Every retained application program for the Member, including closed/incomplete applications. Native MemberEvent and exactly one SourceInvalidation per program. Original no-change rejection and version checks retained. |
| Membership document verification/revocation | COVERED, new adapter | Same complete Member scope; immutable DocumentVerification and matching MemberEvent, exact file digest and reviewer/version. Missing or expired evidence fails closed. |
| Program definition, requirements, publication, approval/control/terms binding | COVERED, preserved Gate 2D-1 | Program-native ProgramLog and source artifacts; existing PDAO and protected terms rules unchanged. |
| Public verified-member application submission / Admin closure | COVERED, preserved Gate 2D-2A | Server-derived program scope, system submission audit without fabricated Admin identity, ProgramLog and applicable AssistanceLog. Every new retained application invalidates, including after evaluation cutoff. |
| Application photo review / correction and evidence revisions | COVERED, preserved Gate 2D-2B | Program scope; exact ProgramLog, immutable revision/review and case audit evidence. Existing cleanup and retained-file protections preserved. |
| Linked event save / publication | COVERED, preserved Gate 2D-2C | Trusted union of old/new links, all programs ordered before Event, exact EventLog. Unlinked events do not invent program invalidations. Registration/attendance and annual observances unchanged. |
| Eligibility review / assistance decision | COVERED, new adapter | Target program; AssistanceLog exact before/after case, actor and application version. Decision prelocks all program applications and Members. Existing human decision and retired EWAF selection restrictions remain. |
| Assistance release / void | COVERED, new adapter | Every retained program for the receipt's Member, not just issuing program. Native AssistanceLog, receipt history and case/application transitions checked. Second-program CAS failure rolls back the entire receipt and all invalidations. |
| DocumentType, MembershipDocumentRequirement, DisabilityType, MembershipSettings Admin forms | COVERED, new outer Admin transaction | Conservatively every Program. Exact native Django LogEntry; no-change forms keep accepted native log behavior without source invalidation. Existing protected reference restrictions remain. Tokens captured server-side under the fence; these existing forms have no optimistic source-token field. |
| Reference bulk actions / guarded reference model/queryset bypass | PROHIBITED in registered session | Admin bulk POST rejected. Existing protected DocumentType/DisabilityType and reference queryset methods require the private owned Admin writer context before acquiring Terms. No new delete workflow. |
| EWAF evidence policy, assessment, configuration/validation/review/authority evidence/scoring policy | COVERED, preserved Gate 2D-1 | Program scope, immutable source artifact and native ProgramLog, exact scope/audit validation. No policy activation. |
| EWAF readiness / applicant diagnostic graph | COVERED, new adapter | Program scope; readiness artifact and ProgramLog; diagnostic run/item/five traces and all seven native audits. Existing Gate 1 conservative audit dependency retained. |
| Program private photo/document and membership/member private document access audits | COVERED, new adapters | Program or complete retained Member program scope; exact native ProgramLog/MemberEvent/MembershipEvent. Pending-intake access has zero program scope. These audits remain source dependencies; viewing evidence can conservatively stale a development result. |
| Evaluation date, evidence expiry, future program/event timestamp boundary | COVERED at protected use | Finite deadline, no later than next local evaluation midnight; earlier source boundaries shorten it. Protected current reads recheck time and source graph; observed current-result expiry creates sticky audited invalidation. |
| Public/ordinary application requests outside registration | Accepted behavior preserved | Adapters bypass generation integration without querying generation tables; no activation flag or new permissions. Development pages are absent/404 and no current pointer is consumed. |
| Direct SQL, raw unguarded ORM, management imports/permission catalog changes, alternate processes | UNRESOLVED / outside contract | Not fenced by application decorators. Setup occurs before audited epoch registration. Such writes invalidate the assurance of an active session; do not resume protected use as if integrated. Snapshot recapture detects many changes but cannot prove changed-and-restored external writes. |
| External file replacement/tampering, remote/custom storage | UNRESOLVED / outside atomic contract | Current bytes/digests are checked; MySQL cannot lock external storage. Newly saved failed-transaction files use existing cleanup, not a distributed transaction. Referenced evidence is retained. |
| Four-criterion operational policy / selection / publication | PROHIBITED / BLOCKED_POLICY | Explicit policy gaps remain; fixed fictional demonstration only. No new operational selection or publication endpoint. |

## Verified transaction and lock structure

The participating entry point owns the transaction before the original writer:

`Terms singleton -> global AuthorityGeneration -> ALL affected Programs (PK) ->
ALL ProgramSourceStates (program PK) -> linked Events when needed ->
Applications (PK) -> distinct Members (PK) -> ordered remaining source rows ->
business/native audit -> SourceMutationBatch/SourceInvalidation -> generation CAS -> commit`.

Scope is resolved under Terms using server records before any Program lock.
Expected-token dictionaries must exactly match that scope. Source adapters
recheck scope, actor identity and authority at exit. Lower-level existing helpers
may revisit already locked rows; they do not discover an additional lower-order
program after locking a Member. New rows follow locked parent/reference rows.

Membership pending-intake branch omits program/application/member levels and
locks Settings before Intake. Member/document branches lock all relevant
applications before Member. Assistance decision locks all program Members in PK
order before invoking its existing joined helper. Receipt/void resolves all
member programs first. Reference Admin owns the entire form transaction before
validation, save, native audit and final invalidation. Diagnostic assessment
rows are prelocked by PK rather than criterion traversal order.

The promotion capture path uses separate, ordered `select_for_update` queries,
not a joined application/photo lock. It includes all retained applications and
rejects an inventory larger than the existing supported limit (128), rather than
truncating it. Existing Gate 2D-2B photo split and Gate 2D-2C Event prefix remain.
SQL-order assertions and separate-connection MySQL tests verify selected paths;
the global Terms fence serializes participating writers. This does not claim
deadlock freedom against arbitrary transactions, external writers or future code.

## Atomicity and failure boundaries

Native audits are compared to pre-operation immutable history and the entire
new audit set. Missing, duplicate, wrong-program/member, forged actor/content or
unexpected history changes fail before commit. Business mutation, mandatory
native audit, batch, one invalidation per affected program and CAS updates share
one owned transaction. A late audit/CAS/final validation failure rolls everything
back, including an earlier program's update in a multi-program batch.

Authority changes use the global generation; a pointer may remain physically
present but is unusable when its recorded authority differs. Source changes
clear the pointer while preserving the old run/bindings. Revoke/restore and
changed/restore retain distinct monotonic generations. Expected revisions also
prevent two accepted requests from both promoting the same state.

Filesystem cleanup and HTTP streaming are explicitly separate. A failed outer
membership transaction removes only newly journaled files; old evidence stays.
Private access adapters close opened response handles on late failure. No claim
is made that a successful database audit proves delivery or that an interrupted
process cannot leave an orphan file requiring later maintenance.

## Remaining integration limitations

- Existing ordinary source-edit forms do not submit the new internal generation
  tokens. In a registered development session those service paths fail closed
  unless called through the test/internal contract with exact tokens; outside
  registration their accepted behavior is unchanged. The new private calculation
  form supplies its own expected token. This is not a production rollout.
- Reference Admin and access-audit writers capture current tokens server-side
  under the shared fence. They do not add optimistic concurrency UX to old forms.
- EligibilityStatus remains the existing fixed/protected reference; no new
  mutable catalog service is introduced. Arbitrary catalog writes are not covered.
- Whole-history audit comparisons and coarse Terms serialization favor bounded
  correctness over production throughput. No throughput/load claim is made.
- Deadlock/lock-timeout errors fail closed; no hidden partial retry is added.
  Retry the whole operation with fresh versions/tokens. Interrupted calculation
  attempts require explicit authorized recovery, not automatic predecessor reuse.
- Approved policy, operational four-criterion persistence and accessible
  functional-need alternatives require further owner decisions. No migration,
  production use or permission grant follows from this development contract.
