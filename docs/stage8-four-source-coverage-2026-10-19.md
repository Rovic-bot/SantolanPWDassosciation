# Stage 8 four-criterion source and consumption coverage

Scope: fictional records in verified disposable MySQL only. Accepted milestone
remains **70%**. The earlier consolidated writer integrations are retained; this
sprint adds no Membership, Member, Document, Program, Event, Assistance, Accounts
or PDAO writer changes.

| Dependency or action | Coverage in the four-criterion path | Evidence / boundary |
|---|---|---|
| Membership / manual verification | Existing current-source and G12 provenance checks plus integrated generation invalidation | Existing intake/verification writers preserved; no member account or inferred PDAO-ID rule |
| Member profile / active status | Full source snapshot, generation binding, before/after observation and protected recapture | Four-criterion changed-and-restored status and separate-connection member race tests |
| Supporting documents / verification | Verified evidence mappings, source bytes/digests, current review, expiry and disputes | Four document-review invalidation, preserved history and separate-connection race tests |
| Program applications | Server-resolved full retained inventory; explicit cutoff; unresolved in-scope records block | New after-cutoff entry stales request; pending applicant retained; 129-record pool rejected, not truncated |
| Eligibility / Program Relevance | Current active eligible case plus membership/qualifications/evidence, immutable PR findings; three distinct fictional role mappings | Functional need, consent and accessible alternative outcomes must match policy; PR has no score trace; disability label alone does not pass |
| Program terms / requirements / approval / publication | Original approval, PDAO and source rules preserved; current evidence/terms provenance and generation/dependency recapture | No new link, approval, publication or waiver capability |
| Linked events | Existing complete linked-event source locks and invalidation remain participating | Event writers, annual observances and attendance code unchanged; Events regressions |
| Assistance decisions / release / void | Existing complete cross-program invalidation and source receipt inventory | Existing cross-program release/void races in EWAF regression; four PA supports only all retained nonvoided successful receipts, never a claimed lookback window |
| Accounts / permissions | Global authority generation and fresh database permission checks | Four authority race; cached-superuser revocation check; transient human choice requires existing decide-assistance permission |
| Reference data / diagnostic writers | Earlier integrated paths and conservative native-audit dependency projection retained | No narrowing of Gate 1 audit dependencies |
| Four configuration bundle | One transaction retains configuration, exact validation, test proposal, three matching native ProgramLogs and one source invalidation | Expected generation map is derived to one server-resolved program; stale scope/context, audit and generation failure roll back |
| Four complete-pool request | Explicit profile, accepted snapshot, full inventory, current policy and expected source/authority/revision | Old five contract cannot reinterpret four policy; legacy capture cannot bypass generation owner |
| Four result graph | Exactly one result per eligible in-scope applicant and four complete traces | Partial/missing result or trace rollback; exact numerical and PR eligibility replay; no fifth score hidden in payload |
| Development promotion | Existing T/H/P/S fence and immutable complete graph, audit, expected-value CAS and final revalidation | Four competing processors; writer during calculation rejects; writer waiting behind promotion invalidates afterwards; failed audit/CAS rolls back |
| Expiry / interrupted work / retries | Existing deadline at protected use; sticky expiry and explicit recovery/replacement | Four expiry during calculation and after CAS, interrupted-attempt recovery, predecessor preservation and failed replacement tests |
| Human decision preview | Current four run and complete eligible result, expected generation token, fresh permissions and nonempty reason | Transient only; no database decision, AssistanceCase change, receipt, business rank or publication |
| Permanent developmental decisions | **SCHEMA-DEPENDENT; NOT IMPLEMENTED** | Exact two-table additive proposal in policy/persistence document; separate migration authorization required |
| Operational policy / real beneficiary processing | **BLOCKED / PROHIBITED** | Unknown approval date, program scope and scoring rules remain unresolved; operational result API still rejects |
| Privileged SQL / external ORM / file replacement / unsupported processes | **OUTSIDE ATOMICITY GUARANTEE** | Re-observation detects many changes but cannot guarantee an unfenced changed-and-restored source; filesystem/MySQL are not jointly atomic |

## Transaction and replay contract

The configuration bundle uses the established Terms → Authority → Program →
SourceState prefix and retains its three native audits and generation transition
in the same transaction. A new explicit revision is a source change even if its
mathematical parameters repeat a predecessor; it is never a silent rewrite.

Request acceptance and protected consumption use the existing ordered complete
source-lock routine: Terms → Authority → Program → SourceState → linked Event →
Applications → Members → remaining ordered source rows. Numerical work occurs
outside the source transaction. Promotion then reacquires the full fence, rejects
changed generation/context/permissions/deadline, persists and replays the complete
graph, records its immutable promotion audit, conditionally updates the development
reference and performs the final protected-use check before returning.

Three new version identifiers make four history explicit: configuration/policy
`g18-four-fictional-policy-1`; snapshot `g18-four-complete-pool-1`; binding
`g18-four-complete-pool-1:four-fictional-1`. Original five-criterion constants,
mathematical engines, historical payloads and digest formats are unchanged. New
four inputs have a separate calculator and policy validator. Only bounded scalar
normalization and the independently validated four AHP reference are reused.

Historical result inspection verifies integrity without claiming present usability.
The current development reference is consumed only after fresh protected checks.
These guarantees apply to the supported integrated writers in the verified test
session; they do not claim general deadlock freedom, unlimited pool size, production
capacity, out-of-band mutation protection or a filesystem transaction.
