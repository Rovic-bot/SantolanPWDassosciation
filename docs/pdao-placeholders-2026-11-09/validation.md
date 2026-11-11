# Online PDAO application placeholders — November 9, 2026

Added example or entry-guidance placeholders to all 31 visible text/email inputs in `PDAOOnlineForm`: names, PWD number, address, contact details, other occupation, organization, existing IDs, family names and emergency contact. The examples are widget hints, never prefilled or submitted values. Existing labels, required fields, native date controls, selection prompts and checkbox options remain unchanged. Onsite and staff-review forms retain their existing presentation.

Verified form rendering without a database connection: all 31 hints are present, initial text values remain blank, entered values are retained, and field labels/required rules are preserved. The local app was restarted and the public PDAO form returned HTTP 200. Chrome checks at 1440, 390 and 320px verified all hints, associated labels, empty values, typing and no horizontal overflow or JavaScript errors. The initial browser check needed to open and close the existing privacy notice before typing; the completed check passed. All POST requests were blocked; no applications or emails were submitted.

`git diff --check` passed. No migration or business-logic change was needed. Evidence: [browser results](browser-results.json), [desktop](form-1440.png), [mobile](form-390.png), [320px](form-320.png).
