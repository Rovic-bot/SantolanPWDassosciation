# New concern details field

The owner requested a Concern field on the public New concern form. It follows Type of assistance needed and is required, with a four-row textarea and the existing 6,000-character concern limit. Blank or whitespace-only concerns are rejected.

Submission passes the entered concern to the existing ticket creation service instead of copying Subject into the concern. Subject remains the title; the concern appears as the opening message in the public conversation and the admin ticket. The existing full-page redirect, membership verification, private reference, retry protections and acknowledgment delivery remain in place. No schema change or migration is needed.

Validation: read-only checks confirmed six required fields, missing/blank/overlength rejection, and the submitted concern reaching the ticket service (write operations were mocked for this mapping check). Browser previews confirmed field order, required textarea, desktop and 390/320-pixel rendering, and the retained full-page conversation flow. Submissions were intercepted; no tickets, messages or emails were created. Django/database checks and `git diff --check` passed. No Django test suite was run.
