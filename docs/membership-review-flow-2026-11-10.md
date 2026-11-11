# Online Association membership review flow

**Latest owner decision:** See “PRPWD unlocks both actions” below. That decision supersedes the earlier mandatory-email and approval-stage-lock descriptions retained in this change history.

The owner requested this sequence at the top of the review page:

1. **Verify the PWD number:** Open PRPWD and copy the PWD number, check the applicant's matching record, and explicitly confirm the manual check.
2. **Invite for office verification:** Send the invitation to the saved email address; the application remains pending.
3. **Approve membership and send confirmation:** After the invitation has been successfully sent and the applicant visits, confirm the onsite verification and approve using the existing membership/confirmation-email service.

The three cards appear above the application fields and stack in sequence on smaller screens. They use the admin portal's existing theme tokens. The approval button and onsite confirmation checkbox are associated with the existing application editor through native HTML form attributes, so its fields and server validation still apply. Decline and Leave pending remain available below the application. The onsite-only review layout is retained.

New invitations require PRPWD verification permission, an explicit manual-match attestation, a configured registry URL, and a lookup number matching the saved current revision. These checks happen inside the locked invitation transaction before creating an email job. Opening a registry page alone never proves verification. The protected invitation action records the checked number, registry URL, and attestation alongside its existing actor, time, revision, and email ID. On reload, that attestation is reused only for the same revision, number, and registry URL.

Unsaved PWD-number corrections cannot be used to invite someone against a different saved record. Existing invitation retry/idempotency behavior and historical actions are retained. No old verification attestation is fabricated. Final approval still requires a successfully sent invitation, the matching recipient, the in-person visit confirmation, and the existing approval validation. No schema change is needed.

## Validation

- Django database/system checks, template loading, JavaScript syntax, and diff whitespace checks passed.
- Read-only inspection used the existing pending online application; no applicant or account was created.
- Direct read-only validation rejected a missing/mismatched lookup number and missing manual confirmation. Matching saved values were accepted by the validation function without submitting an invitation.
- A private rendered preview of that existing application confirmed the top-of-page sequence, native form associations, disabled invitation until manual confirmation, and approval remaining blocked before successful email delivery.
- Browser inspection showed no JavaScript errors, readable light/dark layouts, and no horizontal overflow at 390px. All POSTs and external requests were blocked during this inspection; PRPWD was not queried and no email or decision was submitted.
- Existing regression test source was updated for the new invitation inputs and extended for rejection/audit behavior. Per the owner's instruction, no automated test suite was executed and no test fixtures were imported into the development database.
- Restarted the local development website against the same database. No business records were changed by this task.

## Compact equal-height refinement

The owner subsequently requested matching desktop card heights using step 3 as the reference. Step 1 now has shorter instructions and a shorter attestation label, with repeated text removed. The desktop grid stretches all three cards to the same row height; mobile cards retain natural heights without clipping. Browser measurements confirmed all three matched step 3's natural height: 362px at a 1600px viewport and 386px at 1440px. A 390px viewport had no horizontal overflow. Verification gates and email behavior are unchanged. System and JavaScript syntax checks passed, and the local server was restarted.

## Explicit approval-stage lock

The owner reported that opening PRPWD appeared to enable both later steps and clarified that this was a button-state issue, not a completed membership approval. Read-only inspection found the current application still pending with no invitation, and the existing server-side approval guard rejected it even when an office-visit confirmation was supplied.

Step 3 now has a native disabled fieldset until a server response confirms successful invitation delivery. JavaScript also reads an explicit server-rendered invitation state, leaves the office confirmation disabled before delivery, and cancels premature approval submissions. It never treats opening PRPWD or clicking Send as successful email delivery. Event handlers use the workspace lifecycle cleanup, and the stylesheet/script cache versions were updated.

Read-only browser inspection of the existing pending application confirmed that opening PRPWD leaves approval and onsite confirmation disabled; confirming the PRPWD match enables only the invitation button. The native fieldset stayed locked even when the approval button's own disabled property was cleared, and the submit guard cancelled a forced approval event. External requests and POSTs were blocked during inspection. No email, membership decision, or database record was created or changed; no automated test suite ran.

## PRPWD unlocks both actions

The owner subsequently requested that steps 2 and 3 both become available after step 1. The invitation is now optional before membership approval. Opening PRPWD for the current number unlocks the onsite confirmation controls. The invitation button still requires the manual PRPWD-match checkbox; the approval button requires the onsite-visit confirmation. Neither action depends on submitting the other. Changing the PWD number resets the lookup and visit confirmation.

The server requires the existing PRPWD review and explicit onsite attestation before approval, but no longer requires a successfully sent invitation. The onsite verification audit is always recorded for online approvals, including when no invitation was sent. Its payload links a successfully sent invitation only when applicable; otherwise the invitation fields are null and `invitation_sent` is false. The final membership confirmation email is still queued by the existing approval service. Historical evidence and onsite-only behavior remain unchanged.

Read-only validation on the existing pending application confirmed the office-attestation validator permits a confirmed visit without an invitation and rejects an unconfirmed visit. Browser inspection confirmed that PRPWD opens the step 3 controls and that both action buttons become available after their respective attestations, without sending an invitation. Unchecking the visit confirmation disables approval again. No POST, email, member creation, or external registry query occurred during inspection. Django checks, Python source parsing, JavaScript syntax, and whitespace checks passed. Regression source was aligned with the new policy; no automated test suite was executed.
