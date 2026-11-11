# Program application tracking popup - November 8, 2026

The Check application action on Resources now opens an accessible popup. The same behavior is connected to tracking links in the program catalogue, program detail, legacy program list, published Results and application receipt. Ordinary links remain usable without JavaScript.

The popup loads the existing tracking verification and limited progress templates. Reference submission, validation errors, Refresh progress and Finish tracking use the original server routes with their existing CSRF and session protections. Finish clears the grant through the existing POST endpoint and closes the popup. The underlying page URL and scroll position stay unchanged.

The shared concern-popup script handles both flows. Tracking content is removed when the popup closes, pending tracking fetches are aborted, and reopening displays a fresh reference form. This does not change grant expiration or treat closing as Finish. Unfinished concerns still remain in page memory on close/reopen. No private data is persisted to local storage. Fetches are same-origin and no-store; POST requests are not retried automatically. Network failures provide an explicit retry, and server throttling/unavailability responses remain inside the popup.

No tracking views, services, authorization rules, feature flags, database models or migrations changed. The existing reference-only verification and allowlist of displayed progress fields are preserved. Popup launch handlers use event delegation so program filters and pagination do not break the tracking link.

## Validation

- The synthetic browser test `scripts.public_tracking_popup_qa` passed with no browser errors. It covered unknown and valid references, limited progress without member details or private application answers, status refresh, Finish/session clearing, close/reopen clearing, network retry, keyboard focus, Escape, no document navigation, unchanged scroll position, and mobile layouts at 390/320 px.
- Program catalogue entry after asynchronous filtering, program detail and published Results entry points all opened the same popup. The no-JavaScript link successfully opened the existing full-page verification form.
- The browser test confirmed application and member records were unchanged. It used a disposable MySQL database and synthetic records only.
- The existing concern-popup browser regression passed, including membership verification, multipart evidence, validation, receipt, Finish, draft preservation, keyboard and mobile checks.
- All 25 focused checks passed across the initial run and focused rerun. The initial run passed both browser tests and 22 of the 23 existing tracking tests. The remaining test still expected the former direct Home shortcut. Its expectation now follows the current Home navigation through Resources and checks popup-enabled links on Programs, Resources, Results and program detail; its focused rerun passed.
- Django system check, JavaScript syntax and whitespace checks passed. Read-only inspection of the running portal at port 8013 confirmed the popup opens with one shared script and no browser errors. No real reference was submitted.

Evidence: `results.json`, desktop/mobile screenshots with synthetic data, and `live-verification-1440.png` (blank form). The development server was restarted with the updated, versioned assets.
