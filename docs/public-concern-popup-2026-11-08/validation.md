# Community Assistance Desk popup — November 8, 2026

The Resources page's Send a concern action now opens a modal dialog. Existing membership verification, concern entry, optional supporting evidence, validation errors, receipt and session-clearing actions stay inside the popup without navigating or scrolling the underlying page to the top.

The browser loads the existing server-rendered private forms, assigns their original request URL to forms without an explicit action, and submits the same fields and multipart uploads using the existing CSRF/session protections. Server redirects determine the next step. No views, services, authorization policies, email behavior or database schema changed. Direct links remain usable without JavaScript.

The dialog supports Escape, a close button, backdrop dismissal, keyboard focus containment and focus return. Closing and reopening retains the unfinished form only in the current page's memory; it is not written to local storage. Cancel/Finish use the existing POST endpoint to clear verification. Requests are not automatically retried on failure, and repeated submission clicks are blocked while a request is pending.

Server HTML is restricted to the expected local request routes. Scripts and no-JavaScript fallback markup are removed before inserting the form; this prevents the fallback evidence-upload styles from hiding the interactive upload button. The warm card styling is scoped to this dialog.

## Validation

- Five focused checks passed in disposable MySQL: the new `scripts.public_concern_popup_qa` browser test plus existing referral HTTP/CSRF/receipt/finish, grant expiry and membership rechecking, idempotent submission/program separation, and public guidance tests.
- The browser test used a fictional verified member, a synthetic PDF and captured local email. It exercised failed verification, successful verification, acknowledgement validation, optional upload, repeated submit protection, receipt, Finish, retry after a network failure, close/reopen draft preservation, focus return and mobile layouts at 390/320 px. Exactly one ticket and one private attachment were created in the disposable test database.
- No-JavaScript browsing followed the ordinary verification URL successfully. No browser page errors occurred. Native focus and the page URL remained correct throughout the popup flow.
- The older referral HTTP test's active-navigation assertion was made independent of HTML attribute order and its receipt assertion uses the existing displayed reference property.
- Read-only inspection of the live portal confirmed the popup opens. No live concern was submitted. Screenshots containing request text in this folder use synthetic test data only.
- Django check, JavaScript syntax and `git diff --check` passed. The local server was restarted with versioned popup assets.

Evidence: `results.json`, desktop verification/form/receipt screenshots and mobile verification/form screenshots in this directory. The existing publication, membership, private evidence and audit rules are preserved.
