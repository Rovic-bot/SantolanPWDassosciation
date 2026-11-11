# Confirmed and Corrected System Answers — H01–H12

**Project:** Santolan PWD Association Management System  
**Review date:** November 10, 2026  
**Basis:** Current local source code, active development email configuration, project documentation, and the project owner's explicit decisions in this conversation.

“Confirmed” means supported by the inspected implementation or explicitly stated by the project owner. It does **not** mean that the Association officers or the entire project group have independently signed off. Where an answer describes an intended policy that differs from the code, that distinction is stated below. Older October target documents are not treated as proof of current implementation.

This is a documentation review. No application behavior, operational records, or configuration was changed. No emails were sent and no automated tests or sample-data generators were run.

## H01 — Membership Verification

**Assessment: Tama ang existing answer, with clarification.**

**Corrected answer:**

The membership form and applicable Association requirements are reviewed onsite using a checklist. An authorized admin manually checks the applicant's PRPWD record and records the verification result in the system before approving membership. The system retains the verification result, reviewing admin, date/time, and related review or audit records. PRPWD checking is manual; the system does not automatically verify applicants through a PRPWD API.

The confirmed Association checklist consists of:

1. Association membership application form.
2. One 2×2 ID picture.
3. Birth certificate **or** marriage certificate.
4. Voter's Certificate.
5. One physical long envelope.

The envelope is an onsite item, not a mandatory digital upload. The separate PDAO checklist must not be substituted for this Association checklist. Recording PRPWD verification is also distinct from checking document completeness and recording the final membership decision.

**Evidence:** [Membership services](../membership/services.py), [registration handoff/checklist](../membership/registration_handoff.py), [membership decisions](../membership/registration_decisions.py), and the owner-confirmed October 10 membership/PDAO requirements note in the project documentation.

## H02 — Registration and Member/Control Number

**Assessment: Tama ang three entry options; outdated ang statement na hindi pa required ang email at PWD number.**

**Corrected answer:**

There are three ways to start Association registration:

- **Online:** The applicant completes the online Association form, including the required email address and PWD number. Submission is preliminary; it does not automatically make the applicant an approved member. Staff review the submission and send the office-verification invitation. The applicant waits for that invitation, visits the Association office, and brings the required documents. Approval requires the recorded onsite verification and successful manual PRPWD confirmation.
- **Onsite:** The applicant brings the requirements to the Association office. Staff can interview the applicant, receive a completed paper form, and encode the information. The current onsite Association form also requires email and PWD number. A complete and successfully verified application can be approved; arrival at the office alone is not approval.
- **Downloaded form:** The applicant downloads and completes the paper form, then submits it onsite for staff encoding and the same review process. Downloading or completing the form is not a separate approval route.

For new registrations using the current Association form, the PWD number is recorded as the member/control number. Existing members' issued identifiers are retained. A registration receipt/reference is a different identifier and must not be presented as the member/control number.

If PRPWD is unavailable, staff must not record a successful verification that did not occur. The application remains pending until the required checks can be completed. Any pending notice or office invitation follows the corresponding admin action; a PRPWD outage does not itself automatically send an email or approve membership.

**Correction:** Remove “One of our solutions is to require email and PWD number for the next update.” They are already required in the current Association online and onsite forms. This statement does not apply automatically to every separate PDAO form or historical record.

**Evidence:** [Registration forms](../membership/registration_forms.py), [office-verification gate](../membership/office_verification.py), [registration decisions and member-number mapping](../membership/registration_decisions.py).

## H03 — Program Application

**Assessment: Tama—requirements depend on the program. Clarify the common application information.**

**Corrected answer:**

Applicants must be approved members eligible to apply through the system. The current membership check asks for their PWD/control number and full name. The application then collects the applicant's name, email address, a declaration about whether their information has changed, and confirmation that the submitted information is accurate. If changes are reported, the applicant must explain them for staff review.

Additional uploads and questions depend on the requirements published by the admin for that program. A current calendar photo is **not universally mandatory** in the current confirmed-information application flow. It can be required through an applicable program requirement. Entering a PWD number does not automatically mean every program requires another uploaded copy of the PWD ID.

Staff review the submitted information and applicable evidence before recording eligibility. Eligibility, ranking, beneficiary selection, and actual assistance release are separate steps.

**Evidence:** [Membership check and dynamic requirements](../programs/forms.py), [confirmed application form](../programs/confirmation_forms.py), [eligibility review form](../assistance/forms.py).

## H04 — Events, Attendance, and RSVP

**Assessment: The owner's stated policy is clear, but “there is no attendance feature” is not an accurate description of the current code.**

**Corrected answer:**

The project owner's stated approach is that community events are open to members and visitors, with no RSVP and no required event-attendance workflow. Beneficiary selection for assistance programs is a separate process and should not be described as a restriction on who may attend an open community event.

However, the existing application still contains event-attendance models and admin routes. These can record an attendee by name with an optional linked member record, so attendance in the current code is **not limited to selected program applicants**. Therefore, the correct documentation is: “No RSVP or attendance requirement under the stated event policy; attendance functionality remains in the implementation.” Do not claim that attendance has already been removed.

**Implementation gap:** Aligning or removing the retained attendance UI is separate implementation work; this answer does not perform that change or delete attendance history.

**Evidence:** [EventAttendance model](../events/models.py), [attendance routes](../events/urls.py).

## H05 — EWAF Criteria and Weights

**Assessment: Confirmed by the owner; the four criteria and configurable weights are correct.**

**Corrected answer:**

The confirmed four criteria are:

| Criterion | Meaning |
| --- | --- |
| Socioeconomic Status (SES) | Accepted household income, with the verified 4Ps adjustment when the approved configuration uses that method. |
| Employment Status (ES) | The applicant's employment category. |
| Previous Assistance (PA) | Recorded assistance actually received, interpreted under the approved assessment policy. Selection alone is not proof of receipt. |
| Household Members (HM) | The accepted number of household members. |

Authorized Association personnel may configure the weights using the system's configuration and authorization process. The percentages must belong to an approved configuration; **25% each is not a permanent policy**. Changing weights must preserve earlier configuration versions and calculation history.

The owner also confirmed these employment scores for new calculations:

| Employment status | Score |
| --- | ---: |
| Employed | 1 |
| Self-Employed | 2 |
| Student | 3 |
| Retired | 4 |
| Unemployed | 5 |

These are category scores, not percentages or the final EWAF score. Historical calculations retain their original scoring version. The current owner-approved program setup uses EWAF for all programs and requires beneficiary slots; the earlier unlimited/non-EWAF proposal was withdrawn.

**Evidence:** [Dataset criteria and SES methods](../ewaf/dataset_methods.py), [versioned employment scoring](../ewaf/employment_scoring.py), [EWAF configuration services](../ewaf/operational_services.py), [mandatory program setup](../programs/forms.py).

## H06 — EWAF Configuration Approval

**Assessment: Correct as the intended account-permission arrangement, with a technical qualification.**

**Corrected answer:**

The designated main administrator is intended to manage EWAF configuration. Other staff accounts receive only the permissions assigned to their role and should not receive EWAF configuration or authorization permissions unless the Association explicitly grants them.

The system checks configuration and authorization permissions and uses an authorized, locked configuration for operational calculations. It does **not** enforce a voting process in which every designated officer must agree before a configuration can be activated.

“Only one account may change EWAF” is an account-management policy, not a built-in one-account limit. Additional superusers or staff granted the relevant permissions can also have that authority. To implement the stated arrangement, those permissions must be restricted to the intended account.

**Evidence:** [Workspace permissions](../core/permissions.py), [operational configuration permissions and locking](../ewaf/operational_services.py).

## H07 — Beneficiary Selection, Reasons, and Ties

**Assessment: The transparency policy is correct; the current forms do not all require an individually typed explanation.**

**Corrected answer:**

EWAF ranking supports the decision; authorized personnel make the beneficiary-selection decision within the approved slots. Decisions must be traceable and have a recorded reason. Before publishing results, the admin must enter a reason explaining why the selected group was chosen for the program. That reason is included in the public results, so it should explain the selection basis without revealing private medical or household details.

There are two different kinds of reasons in the implementation:

- The detailed decision form requires a reason. Some quick selection actions instead save a standard audit explanation; they do not require a unique explanation typed for each applicant.
- The publication form requires a shared explanation for the selected group. This does not replace or prove an individually written reason for every selected or non-selected applicant.

When scores tie, the approved configuration determines the handling. A hold policy blocks the affected decision for further review; a documented human tie procedure requires an explanation of how that procedure was applied. No universal first-come, random, or manually adjusted score rule is confirmed here.

**Remaining policy detail:** If the Association requires a specific, individually typed reason for every selection and non-selection, the quick actions must be aligned with that requirement. The exact tie procedure must be specified in the approved configuration.

**Evidence:** [Decision and quick-action forms](../ewaf/operational_forms.py), [tie enforcement](../ewaf/operational_services.py), [required public selection reason](../announcements/selection_reason.py), [recorded-results publication](../announcements/recorded_results.py).

## H08 — Certificate and Onsite Claiming

**Assessment: Screenshot/printed certificate and representative attendance are owner-stated policy; clarify the email trigger and release verification.**

**Corrected answer:**

After the admin publishes program results, certificate emails are queued for the selected applicants. Selecting an applicant alone is not the same as publishing results or sending the certificate. The certificate is proof of selection and does not establish that assistance has already been released.

Under the owner's stated approach, the member or an allowed dependent/representative may bring the certificate as a screenshot or printed copy. Staff must check the relevant selection record and follow the Association's claimant-verification procedure before recording an actual release.

The system records assistance-release details and the admin's confirmation that assistance was actually received. The inspected release form does not have a dedicated structured representative-identity or authorization checklist.

**Still to be specified by the Association:** Which representatives are permitted, what identity or authorization evidence they must show, and how staff must record that verification. Do not state that possession of a certificate alone authorizes anyone to claim assistance.

**Evidence:** [Certificate queue on publication](../announcements/recorded_results.py), [certificate delivery](../announcements/certificate_delivery.py), [release form](../assistance/forms.py).

## H09 — Email Notifications and Delivery Problems

**Assessment: The listed notification purposes are supported, but “gumagana” must not imply guaranteed delivery to every inbox.**

**Corrected answer:**

The system supports the following relevant notifications:

| Notification | Trigger |
| --- | --- |
| Pending membership or missing-information notice | Admin sends a pending notice with a reason. |
| Office-verification invitation | Admin sends the invitation for the pending online Association application. |
| Membership approval | The applicable membership approval workflow queues the approval email. |
| Member-information update verification | The update workflow sends the email verification code or the staff-requested office verification message. |
| Program eligibility decision and remarks | The eligibility decision is saved through the corresponding review workflow. |
| Selection certificate | Admin publishes results containing the selected applicant. |

The active local configuration uses **Gmail for certificate delivery, with Resend disabled**. The inspected membership, program-decision, and member-update email services use the saved Association email connection. The existence of optional Resend code does not mean Resend is currently being used.

If a message is not received, staff should inspect the recorded delivery status, verify the recipient address and sender connection, and use the available retry action where applicable. The member can also check Spam/Junk. An uncertain delivery must be checked against the sender's Sent folder before retrying to avoid duplicate messages. A provider-accepted message is not proof that the recipient read it or that it reached the main inbox.

Previously sent certificates are not automatically resent on every publication. If certificate information is incorrect, the underlying record and published selection must be reviewed. A formal replacement/correction process that preserves the issued certificate history still needs to be defined; do not promise that editing a member record automatically replaces an already-issued certificate.

**Verification limit:** This review checked implementation and provider settings; it did not send a live email or verify a recipient inbox. An automatic receipt email immediately after every registration submission is not confirmed by the workflows listed above.

**Evidence:** [Pending notices](../membership/pending_email.py), [approval mail](../membership/approval_email.py), [office invitation](../membership/office_verification.py), [program decision mail](../programs/decision_email.py), [member update mail](../members/update_mail.py), [certificate retry rules](../announcements/certificate_delivery.py).

## H10 — Reranking and Publishing Results

**Assessment: Partly correct. Recalculation is versioned and subject to checks, not unrestricted rewriting after publication.**

**Corrected answer:**

If accepted applicant information or the approved EWAF configuration changes, a new ranking should be generated before relying on the ranking as an assessment of those changed inputs. A previous calculation remains historical evidence; it should not be presented as though it used the new inputs or weights.

The system can create another calculation when the required authorization, configuration, applicant-data, and timing checks permit it. Earlier calculations, decisions, and published revisions must be retained. Scores and ranks must not be manually overwritten.

The current announcements workflow publishes the **recorded selections**. That publication path explicitly does not require a fresh complete ranking or rerun all eligibility checks. Clicking Publish Results does not recalculate scores, change selections, or record assistance delivery. It does require the publication explanation and checks that the displayed records have not changed during the action.

Therefore, generating another ranking does not automatically replace the public results, revise all beneficiary decisions, or resend certificates. Any changed decision and publication must go through their own authorized actions and preserve history.

**Correction:** Replace “puwedeng mag-rank nang mag-rank basta hanggang maayos” with “puwedeng gumawa ng bagong validated ranking when permitted, with preserved versions and a separate review of decisions and publication.” Do not claim that publication currently enforces fresh ranking in every path.

**Evidence:** [Operational generation and decisions](../ewaf/operational_services.py), [recorded-results publication](../announcements/recorded_results.py), [certificate delivery](../announcements/certificate_delivery.py).

## H11 — Admin Roles and Permissions

**Assessment: Correct in principle; a proposed person's assignment is not yet a confirmed role assignment.**

**Corrected answer:**

The super administrator has the full administrative permission set. Other staff accounts can access only the administrative functions granted through their assigned permissions. Access to membership approval, program management, EWAF configuration/authorization, beneficiary decisions, results publication, and reports must follow those assignments.

Ma'am Faye may be the proposed super administrator, but this review does not confirm her appointment or inspect an account to identify her. The Association must identify the actual account holders and approve their access. A role title alone does not establish that all necessary permissions have been assigned.

For the arrangement described in H06, other staff should receive their operational permissions without EWAF configuration/authorization access. Creating another superuser would also grant that broader authority and must be considered when administering accounts.

**Remaining confirmation:** The named officers and final permission matrix. Do not present example officer-to-function assignments as already approved.

**Evidence:** [Workspace permission checks](../core/permissions.py), [account forms](../accounts/forms.py), [EWAF permission checks](../ewaf/operational_services.py).

## H12 — Dashboard, Reports, and Empty Data

**Assessment: Correct general purpose, but the confirmed report inventory is narrower than the draft suggests.**

**Corrected answer:**

The dashboard should summarize relevant membership and program operations. The inspected Reports module provides these report categories, using shared data projections for the report screen and CSV/PDF exports:

| Report | Main contents |
| --- | --- |
| Members | Member/control number, name, joined date, and member status. |
| Applications | Program application information, eligibility, beneficiary selection, release approval, and whether assistance was actually received. |
| Programs | Program information, assistance type, dates, slots, and status. |
| Assistance | Recorded assistance received, release date/reference, and received or voided status. |

An event count or chart on the dashboard does not establish that a dedicated Events export exists. A separate event report, its fields, or any additional report scope still needs Association confirmation.

Dashboard and export counts should agree **when they represent the same measure, filters, permissions, date basis, and data snapshot**. For example, applications submitted during a period and assistance released during that period are different measures and need not have equal counts. Changes made between loading the dashboard and exporting can also change the totals.

For an empty result, display **“No data”** or **“No records match these filters.”** A genuine count of zero may still be shown as **0**. If a percentage has no valid denominator, show **“No data”** or **“N/A”**, rather than a misleading **0%**. Existing report tables already have empty-result messages; this review does not certify every dashboard/chart calculation or every empty-chart state.

**Remaining confirmation:** The Association's final required report set, intended date/filter definitions, and any additional event or custom reports. The four categories above are the supported implementation inventory, not a claim of institutional sign-off.

**Evidence:** [Report routes](../reports/urls.py), [report filters](../reports/forms.py), [shared report/export data](../reports/services.py), [report empty states](../templates/reports/detail_table.html), [member report empty state](../templates/reports/member_table.html).

## Items that must not be presented as already settled

- **H04:** The owner specified open events without required attendance/RSVP, but attendance code still exists.
- **H06/H11:** The actual designated account holders and permission assignments need Association confirmation; no one-account-only restriction or unanimous approval workflow is enforced.
- **H07:** The exact approved tie procedure and any requirement for individually typed reasons in every quick action need explicit policy/configuration alignment.
- **H08:** Representative identity and authorization requirements remain unspecified.
- **H09:** The certificate correction/replacement procedure remains unspecified; live inbox delivery was not tested.
- **H10:** Publishing recorded selections does not currently guarantee that the ranking has been refreshed.
- **H12:** The final institution-approved report set and all dashboard/export reconciliation claims require scoped confirmation and verification.

The answers above can be used for the project discussion with these qualifications retained. This document does not authorize changes to business rules or claim that unresolved policy details have already been implemented.
