# Membership page form placement — 2026-10-24

Status: public form visibility completed; operational online submission remains gated. Accepted milestone remains 70%.

The owner clarified that online and onsite are separate application channels and that the applicant portion of the Admin onsite form belongs on the public Membership page. The previous implementation already supported the full pending applicant form, but a closed registration policy left only instructions visible. This change displays its 24 shared applicant fields as an explicitly disabled preview directly on Membership while closed. It does not accept or retain information. When open under the existing reviewed policy, Membership continues to link to the protected, active submission flow. Onsite encoding remains unchanged. Both channels require onsite verification and authorized approval.

Changed application files:

- `membership/views.py`: builds an unbound, disabled applicant-only preview when public registration is unavailable. No input binding, context creation or pending table access.
- `templates/membership/guidelines.html`: separates online and onsite routes, renders the shared blank fields, explains closure, and tells existing online applicants to bring their reference instead of being encoded twice.
- `membership/test_registration_entry.py`: tests the closed preview, forbidden staff fields, ignored query input, no session creation, rejected submission, and existing enabled route.

Validation performed now:

```powershell
.\.venv\Scripts\python.exe -B scripts/g12_test_runner.py test membership.test_registration_entry core.tests.test_public_portal membership.test_registration_prefill --testrunner scripts.remaining_phases_test_runner.RemainingPhasesTestRunner --noinput --verbosity 2
```

16 tests passed in 2.690 seconds in fresh isolated MySQL with synthetic data and separate private media; see `tests-isolated.log`. The initial sandbox launch was denied temporary-file access before tests; `tests.log` retains that failure. The approved escalated run succeeded. No historical counts are claimed as new results.

Read-only browser check of the refreshed local public page: HTTP 200, disabled fields, no submitting form, no page errors, and no horizontal overflow at 320/390/768/1440 pixels. See `browser.json` and [page capture](public-membership.png). The initial sandbox browser launch was denied; the approved retry passed. Visual inspection confirmed both channels and the blank shared fields. Screen-reader and contrast testing were not performed in this change.

All 267 protected files unchanged; Section 8 byte comparison equal (`preservation.json`). `git diff --check` passed with existing line-ending warnings. No EWAF behavioral suite was rerun for this display-only change; prior evidence remains separate.

The already authorized local web server was refreshed using `runlocal` with the unchanged startup guard. No migrations, operational configuration, staff grants, credentials, working records, membership writers or Admin navigation changed. No commit, push or deployment.

Remaining operational blockers are the previously recorded privacy/retention and document-handling authority, actual staff assignments and approved security configuration (session lifetime, request budgets and upload limits). This request confirms form placement and two application channels; it does not supply those values. The preview is not represented as a completed or enabled registration service. No public tracking, PDAO operation or membership handoff was enabled.
