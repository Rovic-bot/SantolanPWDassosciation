# Blank program disability selection includes all types

Historical validation: superseded for new setup by the owner's later [mandatory EWAF and required disability selection decision](../mandatory-ewaf-2026-11-10/validation.md). Earlier approved unrestricted scopes remain retained history; new blank selections are invalid.

Owner request, November 10, 2026: when no disability type is selected in a program's eligibility profile, all disability types are included automatically.

The existing eligibility services already treat an empty disability selection as unrestricted. The program builder now states “All disability types included” when nothing is checked, and its instructions explain the automatic default. The Eligibility profile shows every active current catalog type with its Included check mark. The public program detail uses the same included-type list. An explicitly selected subset still limits disability screening to that subset.

The empty database relation remains the unrestricted representation. Rendering the included list does not populate or modify approved qualifications, program versions, publication history, member classifications, or audit records. Earlier retained classifications and inactive explicitly selected qualifications keep their existing handling. Membership, evidence review, other eligibility criteria, EWAF, and the prior non-EWAF automatic-selection change are preserved.

No migration or application-data update is required. Verification uses a fresh disposable MySQL database and synthetic members; no real applications or messages are created.

Three focused tests passed, including a real browser flow:

- Saving no disability types, checking each current catalog classification against the program, and rendering all included types without changing the stored terms, version, or audit count.
- Selecting one type, displaying only that type, and rejecting a verified-member classification that does not match.
- Browser checks at 1440 px and 390 px in light and dark themes: blank selection, selecting a specific type, clearing it back to all types, and all ten current catalog types shown as Included. The existing non-EWAF automatic selection and publication flow also passed. No JavaScript errors or viewport overflow.

Disposable artifacts: `C:\Users\rovic\AppData\Local\Temp\santolan-g12-tests-ucjdsagn`.

Evidence: [browser results](results.json), [mobile dark profile](eligibility-dark-390.png), [desktop light profile](eligibility-light-1440.png).

- Django configuration/database check: passed.
- Migration drift check: no changes detected.
- JavaScript syntax and `git diff --check`: passed.
