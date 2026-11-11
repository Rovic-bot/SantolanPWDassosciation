# Automatic referral review and ticket closure — 2026-10-25

The owner requested that ticket actions move to In review automatically, with Close ticket used when the work is done. This supersedes the earlier manual In review, Needs information and Referred buttons.

## Current behavior

Opening a Received ticket from its subject or View ticket button starts review immediately for staff with review permission. A direct link also starts review automatically in the browser. The page then shows In review and a single status button, Close ticket. Closing takes one click, without a reason, confirmation checkbox or additional verification form.

Reply in Gmail and Record Gmail reply remain available to authorized staff. Recording a reply retains the current status and creates an activity entry; it does not send an email or assert delivery. Existing request data, references, evidence and history are retained. Previously handled tickets keep their status when reopened, and closed tickets remain closed.

Opening from the inbox uses a native CSRF-protected POST, so it works without JavaScript. Direct links use a small script to submit the same protected action; a no-script fallback provides Open ticket for review. GET requests themselves remain read-only, and staff without review permission can view the request without changing it.

All actions retain fresh permission checks, strict input validation and transactional history. Simultaneous opens create one review event. Duplicate closes and replies remain idempotent for the same actor/version; competing edits are rejected. No new model or migration is required. No membership, benefit, ranking, selection or release logic changed.

## Verification

**40 focused tests passed** in 2.576 seconds with disposable native MySQL and synthetic email:

```powershell
.venv/Scripts/python.exe -B .local/dual-registration-20261024/run_tests.py test assistance.test_referrals assistance.test_referral_quick_actions --testrunner scripts.referral_test_runner.ReferralTestRunner --noinput --verbosity 1
```

Coverage includes automatic review, read-only access, CSRF, closed tickets, existing status preservation, stale edits, audit rollback, duplicate and simultaneous opens/replies, competing close/reply actions, private evidence and inbox filters. No application tickets were modified and no real email was sent during verification.

JavaScript syntax and Git whitespace checks passed. Fictional inbox/detail templates rendered with database access prohibited. The detail page exposes only Close ticket and Record Gmail reply as submitted actions; the previous review form and manual status choices are absent.

Browser launch remains unavailable in this environment (`spawn EPERM`); no screenshot comparison or responsive-browser pass is claimed. Local evidence and source/runtime baselines are retained under ignored `.local/referral-auto-review-20261025/`.

## Local runtime

Ten source, test, template, style and script files were synchronized to the identified development runtime after every existing runtime hash matched its recorded baseline. Backups and verified resulting hashes are retained in the ignored evidence directory. The synchronized runtime passed Django's database configuration check with no issues.

The restart script verified the development website on port 8003, but Windows denied stopping its Python process. Run `Restart System.cmd` locally and refresh the inbox to load the updated Python and cached templates. No database migration, GitHub push or hosted deployment was performed for this change.
