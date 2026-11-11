# Referral inbox UI and direct actions — 2026-10-25

The owner supplied inbox/detail screenshots and explicitly requested removal of Review & follow-up, with one-click reply recording and status updates and no additional verification form.

## Delivered workflow

The later owner instruction supersedes the manual status buttons described below: opening a Received ticket now starts review automatically, and Close ticket is the only status action. See [Automatic review validation](automatic-review.md) for the current workflow and its 40-test result. This document retains the earlier UI implementation evidence.

The inbox now shows Total requests, Received and Closed cards; a search across reference, subject and member name; status and assistance-type filters; a compact request table; View ticket actions; and pagination. Totals describe the authorized inbox as a whole, while table results reflect the selected filters. Email settings remain permission-controlled.

The detail page shows the reference/status/date, request overview, contact details and concern, private supporting evidence, and an activity timeline. Image evidence uses the existing permission-checked route for its preview; PDF evidence has a preview link. View full size opens the protected inline view; Download retains the original attachment disposition. No unrestricted media URL is exposed.

Review & follow-up, required notes, pasted reply text, channel selection and the Gmail confirmation checkbox are removed from this screen. The Ticket actions panel offers direct In review, Needs information, Referred and Close ticket buttons, excluding the current status. A permitted action saves immediately. Staff can mark a request Referred directly without a preliminary review step. Closed tickets remain final.

Reply in Gmail retains the existing account-independent compose link. After sending there, authorized staff can click Record Gmail reply once. That records the administrator's action without asking for another confirmation or pasted message, keeps the current processing status, and sends no system email. Opening Gmail itself makes no update and is not represented as successful delivery. Public member verification before creating a referral request is unchanged.

Automatic activity entries retain actor, timestamp, old/new status and version. Existing notes, recorded messages, original request details, immutable references and email-attempt history remain available. Earlier system-email history is collapsed; its separate retry controls are retained because a retry can send another message. The older audited review service remains compatible with existing integrations, but its form is absent from the new interface.

## Integrity and access controls

Direct actions require fresh staff permissions, CSRF protection on HTTP requests and the displayed ticket version. Reply recording additionally requires the existing send permission. The service locks the ticket and writes the status/version and history in one transaction. An exact retry from the same actor is idempotent; a competing or changed stale action fails. Unknown actions, duplicate values, unexpected fields and closed-ticket changes are rejected. Failed history writes roll back the change.

Inline evidence retains authentication, separate document permission, access logging, private/no-store caching, nosniff and sandbox response headers. Only the existing supported PDF/JPG/PNG content types may be shown inline; the default route still downloads the attachment.

No model or migration changed. No membership, program application, benefit approval, ranking, selection or assistance-release operation was added to ticket actions. No application records were changed or real email sent during implementation.

## Verification

**37 focused tests passed** in 3.622 seconds, using disposable MySQL with `.env` disabled and synthetic local email:

```powershell
.venv/Scripts/python.exe -B .local/dual-registration-20261024/run_tests.py test assistance.test_referrals assistance.test_referral_quick_actions --testrunner scripts.referral_test_runner.ReferralTestRunner --noinput --verbosity 1
```

The 25 existing referral regressions remain covered. Two old UI assertions now expect View ticket in the inbox and the concern/Gmail link on the detail page. Twelve new tests cover direct actions, reply recording without extra fields, no duplicate mail, exact retries, stale edits, closed tickets, fresh permissions, strict inputs, audit rollback, CSRF, removal of the old form, search/filter totals, private inline evidence, simultaneous duplicate replies and competing status updates.

The identified development runtime passed Django database checks and `makemigrations --check --dry-run` with no changes detected. Python syntax and Git whitespace checks passed. Fictional inbox/detail HTML was rendered with all database access prohibited, checking unique IDs, six View ticket links, five direct action buttons and absence of the old review form.

Chrome/Playwright launch failed with `spawn EPERM`. No visual screenshot comparison or responsive-browser pass is claimed. Synthetic HTML previews and render evidence are retained under ignored `.local/referral-inbox-ui-20261025/`.

## Runtime and publication

Thirteen reviewed source/test/template/style files were synchronized into `.local/dual-registration-20261024/runtime/` after checking all existing files against recorded baselines. Backups, hashes and the synchronized-file list remain in the ignored validation directory. Other unfinished work was preserved.

The restart script verified the development website on port 8003, but Windows denied stopping its process. Run `Restart System.cmd` locally and refresh the referral inbox to load the new code and templates. No database migration, GitHub push or hosted deployment was performed.
