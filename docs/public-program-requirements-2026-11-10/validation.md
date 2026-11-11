# Published requirements on public program details

November 10, 2026. Owner requested that a specific program's public detail page display the requirements entered and published by its administrator in the available UI space.

## Finding and change

The public detail view already supplied the program's active configured requirements, in their saved order. The template did not render that context. The inspected program, `ebc30248-516e-4ad4-a445-4972ec141fdf`, had two active definitions, Calendar Picture and reason, each with instructions.

A **Program requirements** card now appears in the main column immediately below Program overview and before Application steps. It shows:

- The requirement's saved label and instructions, without rewriting the administrator's wording.
- Document upload, written answer or acknowledgement type.
- Required or Optional, according to the saved setting.
- Existing public general program instructions when supplied.

Inactive requirements and definitions belonging to another program are excluded by the existing view. An empty program has an explicit message that no additional requirements have been published. Application steps now direct visitors to review the published requirements.

The card is a readable list with natural height, not an upload or application form. It uses the current cream/charcoal public palette and existing responsive columns, with explicit high-contrast borders and text. The requirements stack naturally on smaller screens and remain visible without JavaScript and in print.

No backend query, publication rule, model, migration, stored record, evidence file or application-readiness rule changed. Private applicant documents and answers are not part of the panel. Existing public program visibility and permission-checked evidence routes remain in place.

## Verification

Seven focused Django tests passed through the fresh disposable MySQL runner and `RegistrationIntakeTestRunner`. These cover admin ordering, active/other-program filtering, required/optional labels, all three kinds, exact instructions, empty/general-only states, escaped text, hidden draft/archived/future programs, private applicant answers/files, read-only markup and preserved application readiness. The earlier detail-page assertion that omitted requirements was updated to the owner's newly authorized behavior. The disposable database was destroyed afterward; application data was not used for these tests.

Read-only Chrome checks against the requested local program passed for 1440, 1024, 390 and 320px in light, dark and high contrast with either theme preference. The checks compared the displayed requirements to the active saved definitions, confirmed placement below overview and above steps, verified no input/upload/link controls in the panel, no clipping or horizontal overflow, and text contrast of at least 4.5:1. Enlarged 200% root text, no-JavaScript rendering and print visibility also passed. No JavaScript errors or write requests occurred.

Desktop light and mobile dark screenshots were visually inspected. Fixed navigation/display controls were hidden only during full-page screenshots. The local app was restarted, Django system checks and `git diff --check` passed. No program was edited, application submitted or email sent.

Evidence: `backend-tests.log`, `results.json` and the theme screenshots in this directory.
