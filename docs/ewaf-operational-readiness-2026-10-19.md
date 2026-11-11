# EWAF operational-readiness acceptance checklist

**Decision: not operationally ready; accepted milestone remains 70%.** The implemented and tested fictional development workflow is available for review. This checklist distinguishes technical evidence from the Association decisions and deployment authorization still needed for an operational 80% milestone.

| Acceptance item | Current status and evidence |
|---|---|
| Existing local Admin demonstration first | Executed before edits: both existing Stage 8 browser tests passed; initial screenshots retained separately |
| Verified SI/ES/PA/ND application inputs | Existing versioned four-profile integration retained; `test_four_workflow`, `test_four_review` and browser exercise real Django application/evidence records with fictional data |
| Mandatory PR eligibility | Verified PR findings retained outside the four numerical traces; missing/disputed or mismatched PR blocks the entire eligible pool |
| Reproducible AHP/Min-Max/WSM | Four-weight replay, reference consistency, exact Decimal score, accepted raw/encoded values, normalized values, weights and contributions retained; no manual score/rank edit |
| Configuration/evidence version compatibility | Explicit four-profile configuration/validation/policy, generation-bound requests and four-trace results; no five-criterion constants or historical payload reinterpretation |
| Whole-pool completeness | All retained applications inventoried, explicit cutoff, no silent omissions, unresolved in-scope case blocks; 24 verified applicants independently checked with 96 traces |
| Ordering and ties | Exact full-precision descending comparison in Admin; equal counts include the application itself. Equal row positions confer no priority. Operational ranking/tie policy still blocked |
| Recalculation and calculation history | Explicit full-pool replacement with predecessor preservation, complete-graph verification and protected promotion; failed/stale replacement cannot restore an old current result |
| Saved reasoned human review | New immutable fictional decision/audit records, revision/predecessor, actor/time/reason and exact run/evidence provenance; paged history; idempotent retry and stale-form protection |
| Separation of human review and score | SELECT_DEMO, DEFER_REVIEW and WITHDRAW_DEMO never modify scores, allocate actual slots, change AssistanceCase, create receipts or publish results |
| Source freshness and expiry | Existing supported writer adapters retained; decision records recheck current complete run before and after insertion; expiry/final-check failure rolls back both decision and audit |
| Permissions/privacy | Fresh database authorization, existing decision permission, disposable capability, CSRF and no-store; ordinary app mode has no new operational scoring/decision endpoint |
| Audit and concurrency | Atomic decision/audit insertion, append-only supported ORM guards, exact digests, competing decision writers and source writer serialization tested on separate MySQL connections |
| Historical preservation | Five/four replay, additive migration forward/reverse/reapply, all earlier migration bytes and staged work preserved; source delta and hashes in package |
| Minimalist Admin UI/accessibility | Existing shell/CSS preserved; numerical comparison and saved history use existing components. Browser checks labels, keyboard disclosure, 320/390/768/1440 widths, no page overflow/errors |
| Full regression and browser QA | Exact final counts/durations are in the sprint validation report and retained logs; initial failures also included |
| Complete approved operational configuration | **Blocked:** Association rules/authority/scope/dates remain pending in the consolidated policy sheet |
| Actual beneficiary selection and slot policy | **Blocked:** fictional decisions are not an operational allocation mechanism; tie/exception/nonselection and approval policies must be supplied |
| Operational source-change recalculation | **Blocked:** supported writes invalidate safely; operational reevaluation/reapproval cadence and consumer integration require approved policy. No background processing infrastructure was added |
| Application DB migration / deployment / activation | **Not performed or authorized.** The owner approved migration creation/disposable testing only. Ordinary local startup continues to defer the exact new migration |
| Capacity for the Association's actual pool | **Not established:** 24 verified records exercised; existing engineering ceiling is 128 retained applications; 129 is rejected before capture. No silent truncation. No production throughput/deadlock-freedom claim |
| Representative officer/PWD UAT and 80% acceptance | **Pending owner/adviser review.** Browser checks do not establish WCAG certification or representative usability acceptance |

## End-to-end demonstration

Use the supplied screenshots or rerun the existing isolated harness from the repository root. Every command below starts a new empty loopback MySQL instance, disables `.env`, restricts grants to disposable databases, uses fictional temporary media and destroys the Django test database. It never connects to the regular application database.

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test scripts.stage8_readiness_browser_qa scripts.stage8_four_browser_qa scripts.stage8_browser_qa scripts.revised70_browser_qa --testrunner scripts.durable_test_runner.DurableTestRunner --noinput
```

The new demonstration:

1. Opens the actual Django Admin shell on a disposable live-server port. Shows five retained fictional applications: four fully reviewed, one late pending application outside the explicitly recorded test cutoff.
2. Shows SI/ES/PA/ND configuration and mandatory functional-need/consent/accessible-alternative PR evidence.
3. Calculates two complete versions. Displays four scores in descending order with an exact two-applicant tie and no assigned business rank.
4. Opens the four input/normalization/weight/contribution traces and the retained predecessor run.
5. Records a reasoned fictional selection, then a reasoned defer-for-review revision for the same application. Both audits and original calculations remain intact; actual assistance stays absent.
6. Checks private response caching, labels, keyboard disclosure, responsive widths, lack of score/rank input fields and JavaScript errors.

Screenshots in the package: `initial-browser/stage8-desktop.png`, `initial-browser/four-history.png`, and `browser-final/readiness-{inventory,comparison,calculation,history,decision,mobile}.png`. Historical run pages explicitly identify the accepted cutoff and any retained application outside it.

## Acceptance boundary

Review the implementation and evidence together with [the consolidated policy sheet](ewaf-operational-policy-decisions-2026-10-19.md). Record actual Association decisions once, then implement any resulting policy changes and conduct the remaining operational acceptance. The safe development work does not itself advance the milestone, authorize application migrations, or turn fictional human records into beneficiary approvals.

Supported-path atomicity excludes privileged direct SQL/unsupported ORM callers, external processes and changed-and-restored file tampering. MySQL and files are not one transaction. Those limits are retained from the reviewed source protocol and are not represented as newly solved.
