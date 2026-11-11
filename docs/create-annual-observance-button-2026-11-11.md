# Create annual observance button — November 11, 2026

## Follow-up: shared Create/Edit authoring

At the owner's request, Create now shares the Edit builder template, section navigation, yearly date-range calendar, image preview, live summary, and responsive styles. Both use the compact form: title, target audience, start/end dates, description, and optional image. New entries require both dates in the same month; one-day ranges and February 29 are supported. Creation saves a private draft for separate review/publication, while editing retains its existing Save changes/publication behavior.

No legal authority, official-source URL, or participation policy is invented for new entries. Both reference fields may be absent; a supplied reference still requires the complete valid pair. The reference catalogue remains strictly validated. Target audience remains required for annual-observance publication; the omitted participation field is optional and the public display retains its organizer-contact fallback. Existing source and participation metadata remain on edited records and in immutable history. Blank official-source links are omitted from review/history displays. These are application-validation changes with no database schema change or migration.

Eight focused disposable-database tests passed: shared fields/layout, HTTP creation and subsequent publication, invalid date/audience rejection, optional image handling, permissions/CSRF/version checks, audit rollback, retained metadata/history, and invalid official sources. External sockets were blocked. Intercepted Chrome checks passed at 1440/390/320 px for layout, date validation, leap-day selection, live summary, image selection/removal, submitted form values, existing edit initialization, and JavaScript-disabled native dates. Screenshots were inspected, JavaScript syntax and diff checks passed, and the migration autodetector found no events model-state change. No actual observance was created or published.

## Initial button change

The owner requested a visible creation button for adding Annual Observances after deployment. The shared Admin Annual Observances section now has a visible heading and a **Create annual observance** link to `events:observance_create`. It appears in the Events Calendar and dedicated Annual Observances page, including an empty calendar.

Visibility requires observance viewing access, creation permission, and initialized observance storage. The existing protected creation view, validation, draft saving, review/publication workflow, and audit history remain unchanged. No migration or deployment was performed.

Verification used current templates and in-memory objects with database cursor access blocked. Permission/storage visibility combinations and named URL resolution passed. Intercepted Chrome checks passed on both pages at 1366, 390, and 320 px: visible 44 px button, no horizontal page overflow, keyboard activation, and navigation to the existing form with Save draft. The mobile screenshot was inspected. No actual observance was created or published; no database records or external services were accessed during these checks.
