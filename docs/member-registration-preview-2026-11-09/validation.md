# Approved member registration preview - 2026-11-09

Implemented the owner's request for `/members/25/registration/print/`, applying the same behavior to all approved members.

- The print action on a member record opens a popup on the same page. The direct print URL opens that popup automatically, with a plain background and no site navigation.
- The popup contains only the retained registration document, a **Print / Save PDF** button and a close button. Printing becomes available after the private document loads and targets that document alone. A failed or unauthorized document response keeps printing disabled.
- Close and Escape dismiss the popup, including when focus is inside the document, and restore focus to its opening control. Reopening fetches the document again. The direct page provides an Open preview action after closing and a document link usable without JavaScript.
- The form fits narrow screens while preserving its A4 dimensions for printing. The original form, recorded values, member number and approval details remain unchanged.

The popup reuses the membership review's dialog markup and behavior. A separate document template at `?preview=1` contains no navigation or buttons. Both variants keep the existing staff, member, original-application and linked-intake permission checks, policy gate, access auditing and `no-store` headers. Framing is permitted only by the same origin. No migration, membership decision or applicant email is needed for this change.

## Validation

The following **23 tests passed** in a fresh disposable native MySQL instance with synthetic applicants:

```powershell
.venv\Scripts\python.exe scripts/g12_test_runner.py test members.test_registration_print membership.test_pending_email scripts.member_print_preview_browser_qa scripts.membership_pending_browser_qa --testrunner=scripts.registration_intake_test_runner.RegistrationIntakeTestRunner --noinput --verbosity 1
```

Existing tests now exercise the protected popup and embedded-document variants. Checks cover original-data preservation after profile edits, legacy registration projection, HTML escaping, every required permission, policy closure, audit failure and rejected mutation requests. The shared pending-review popup browser flow also passed.

Chrome checks at 1440, 390 and 320 pixels confirmed document-only printing, automatic opening from the direct URL, loading readiness, image loading, no horizontal overflow, close/reopen, Escape from the frame, focus restoration, disabled printing after an access error and no record-writing requests or JavaScript errors. A synthetic print export produced one A4 page (594.96 by 841.92 points). Poppler rendering and visual inspection confirmed the complete form and signature; extracted PDF text excluded navigation and popup controls. Physical printer output was not tested.

Django database checks, Python compilation, JavaScript syntax and Git whitespace checks passed. The retained development site was restarted on port 8013 without changing its database or uploads. The private URL remains login-protected.

Evidence: [direct popup](direct-popup.png), [desktop member popup](member-popup-1440.png), [mobile member popup](member-popup-390.png), [printed form](printed-form.png), [browser results](browser-results.json). All saved screenshots contain fictional test data. The synthetic PDF and disposable test logs remain in the temporary test-artifact directory; they are not production records.
