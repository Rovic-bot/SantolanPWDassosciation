# Admin input examples

November 10, 2026. The owner requested example text across admin input fields, using `/membership/registration/apply/` as the reference, and explicitly confirmed the scope as “Across admin forms.”

The reference page was inspected directly and its existing `OnlineRegistrationForm` examples reviewed. It uses placeholder examples such as `e.g. Dela Cruz`, `e.g. Juan`, and `e.g. 123 Mabini Street` alongside persistent field labels and help text.

## Changes

- Added `static/js/admin-input-examples.js` through both the custom admin workspace layout and authenticated native Django admin layout.
- Common examples cover identity, addresses, contact details, identifiers and household inputs. Program, event and announcement forms have specific examples and writing guidance. Review, correction, approval and assistance fields have short prompts describing the information needed.
- Existing useful placeholders remain; generic identity prompts are replaced with the reference form's concrete examples. Existing values, labels, help text, required fields and validation attributes are unchanged. The script never assigns input values or approved policy settings.
- Date controls, choices, uploads, passwords, secrets, hidden inputs, disabled and read-only fields are excluded. Numeric policy fields receive descriptive guidance instead of invented thresholds or scoring defaults.
- Page-scoped observation handles newly added requirements, popup forms and replaced form fragments. Workspace navigation cleans up the observer with the existing `WorkspacePage` lifecycle.
- Public layouts do not load the new script, and the script also checks the admin body class. Existing public registration behavior is retained.
- The existing admin placeholder colors are used in both themes. JavaScript is progressive enhancement; existing form labels, instructions and validation remain available without it.

## Validation

- Inspected the live reference form and rendered five actual admin form views/templates for read-only browser previews: program builder, event builder, announcement editor, onsite membership form and native administrator creation form. A SQL wrapper rejected all database writes while rendering; the onsite preview used an unsaved synthetic context rather than issuing a registration context.
- Headless Chrome checked placeholders, compared every field's value/checked/required/disabled/read-only properties before and after enhancement, and confirmed passwords, hidden fields and upload controls were excluded.
- Checked newly added program requirements and a dynamically inserted popup, existing custom placeholders/entered values, and the public-page isolation guard.
- Program and onsite form sections were checked at 1440 and 390 pixels in light and dark themes; no horizontal overflow occurred. Screenshots and the browser result summary are in this folder.
- No browser POSTs, database writes, applicant submissions, program saves or emails occurred during these previews. Browser checks reported no JavaScript errors.
- JavaScript syntax, Django checks and `git diff --check` passed. The retained development app was restarted to load the shared template additions.

No model changes or migrations are required. Private rendered previews and the scratch browser checker remain under `.local/admin-input-examples-20261110/`.
