# Integration Log — Brainstorm Final(2) into Overall System Specification

**Integration date:** October 23, 2026  
**Outputs:** OVERALL_SYSTEM_SPECIFICATION_INTEGRATED.md and its Word/PDF reading editions.  
**Sources:** OVERALL_SYSTEM_SPECIFICATION.md (October 22 recorded baseline) and Brainstorm Final(2).pdf (23 pages).  
**Status:** Documentation integration; no application implementation, policy certification, or milestone change.

## Preservation result

- All original baseline text is retained, in its original order, without deletion or replacement.
- Added material is enclosed in marked `BRAINSTORM_ADDITION` blocks in the Markdown master. Removing the blocks reconstructs the original source exactly.
- Section 8, **EWAF methodology and controls**, is byte-for-byte identical in the original and integrated Markdown files. No addition was inserted inside that section.
- The two original input files were not overwritten.
- No repository, database, migration, credential, deployed service, or institutional approval was changed. Application tests were not rerun.
- The original recorded 70% accepted milestone remains unchanged.

## Features integrated as added targets

| Addition | Integrated sections |
| --- | --- |
| Online pending membership and separate PDAO intake, retaining onsite verification | 1.4, 2.4, 3.4, 4.1, 5.4, 7.7–7.8 |
| Unique registration references, receipts, printable completed forms, secured staff retrieval | 5.4, 6.9, 7.7–7.9, 9.4, 13.1 |
| Program/registration tracking and onsite-readiness instructions | 5.5, 7.9, 12.6, 15.5 |
| Separate member-only assistance/referral ticket | 5.6, 6.9, 7.11, 9.4 |
| Current-information confirmation, updates, routine review, evidence reuse | 5.7, 7.10, 9.4, 10.1 |
| Applicant clarification/evaluation-review workflow and non-sensitive explanations | 5.8, 7.12, 9.4 |
| General/specific event audiences, annual content, and expected-attendance RSVP | 5.9, 7.13, 15.5 |
| Resources & Help, helpline/form/source guidance, footer | 5.3, 5.10–5.11, 6.9 |
| Expanded accessibility for intake, forms, tracking, corrections and results | 12.7, AC-B13 |
| New conceptual records, supplementary business rules, acceptance checks | 9.4, 10.1, 13.1, 15.4 |

## EWAF remains unchanged

This includes the historical five-criterion model and specifically authorized newer four-criterion model; Program Relevance treatment; AHP equations; RI values; strict `0 <= CR < 0.10`; explicit normalization bounds/directions; classification authorization; complete-pool and source-freshness controls; exact ties; no numerical business rank; separate human decisions; protected recalculation and history; and existing implementation/acceptance limitations.

Information intake may collect an update for review, but it cannot redefine a criterion, replace its approved measurement, renew verified evidence through a checkbox, start an automatic calculation, or omit unresolved applicants. New service records are not program selections or actual-assistance ledger entries.

## Explicit target extensions, not hidden baseline rewrites

The original onsite-only intake, retired public tracker, and seven-section navigation remain recorded baseline statements. Added-target sections explicitly extend them with pending online intake, protected status tracking, and Resources & Help. These additions are requested requirements, not assertions that those functions currently work.

The eight existing Admin groups remain. A placement map links new functions to those groups; it does not create new login roles or grant institutional decision powers.

## Retained requests that are not enabled

- **Public numerical ranks:** Deferred because the current EWAF does not assign business ranks and public privacy rules exclude them. No ranks are synthesized from row order or typed by staff.
- **Eligible-list publication and expanded identifiers:** Deferred pending a distinct disclosure decision. Existing masks/last-four reference display remain the baseline.
- **Household Monthly Income:** Still pending approval; no criterion or weight change was made.
- **Different member matching fields:** Brainstorm fields are recorded, but ordinary member verification is not silently replaced.
- **Public tracking access and recovery:** The feature is included as a target, while specific access checks/QR payload/recovery remain open. No PIN, OTP, account, or SMS/email channel is invented.
- **Photo verification, sampling rules, RSVP intake, PDAO authority and transfers, and terminal-case remedies:** Preserve existing safeguards and record missing policy decisions.
- **Chatbot:** No chatbot is added. Historical proposed Gemini text is retained, not activated.

## Editorial treatment

Duplicated Brainstorm instructions are consolidated into one detailed target workflow, with shorter Home/announcement links. Editing reminders are not turned into requirements. Conflicting automatic-rejection wording and broad masking instructions are explicitly recorded; they do not silently override the baseline's correction and disclosure controls.

Only the supplied documents were used as the substantive basis. Embedded links, other vault notes, official calendar claims, and repository references were not independently fetched or verified. Source-to-section mapping is provided in §16.5.

## Document integrity checks

Original baseline SHA-256:

```text
6b9fcf60d8ce8d6b67c2c2bbd13c75472fa44997078d59339efc8b75ff75fa29
```

Reconstructed baseline SHA-256 after removing all added blocks:

```text
6b9fcf60d8ce8d6b67c2c2bbd13c75472fa44997078d59339efc8b75ff75fa29
```

Original and integrated EWAF Section 8 SHA-256 (identical):

```text
f446ea0be7cf061439293c75f6354bdde77c6e2e4870e69611cc19bd1abec41d
```

These hashes verify document preservation only, not mathematical correctness, application security, deployed availability, or operational approval.
