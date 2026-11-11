# Application tracking reflects the recorded status

The owner requested that eligible applicants see “You are now eligible” and that tracking reflect the application's current status. This supersedes the older broad “Under review” / “Decision available” projection described in the October 24 tracking validation.

Tracking now maps all 15 existing application states to clear labels, explanations, and relevant next steps. Eligible applications retain that heading through EWAF processing and ranking, with stage-specific explanations. Selection, waitlisting, non-selection, ineligibility, unsuccessful verification, closure, and assistance release have distinct messages. Eligibility does not imply selection; selection does not imply actual release.

The existing refresh action reads the current database state. Reference access, expiry, rate limits, archived-member restrictions, and private/no-store responses remain unchanged. Tracking does not load or reveal notes, documents, scores, numeric ranks, or other applicants. No workflow transitions or stored records were changed.

Validation:

- Django `check --database default`: no issues.
- Read-only rendering of an existing eligible application showed the correct eligible heading and next steps, with no “Under review” heading.
- Compared the message mapping with the model's status choices: no unmapped states.
- Python syntax and `git diff --check` passed.
- Updated regression source for status messages and the projection allowlist; no automated test suites or synthetic data generators were executed.
- No applications were submitted or modified and no emails were sent. Other status transitions were not exercised against live records.
