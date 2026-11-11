# Event creation workspace - November 2, 2026

Create Event now uses the program builder's glass surfaces, typography, themes, numbered section navigation, sticky actions, and live summary. The compact workspace has three sections: Event details, Event schedule, and Event image.

The six existing fields remain: Title, Description, Location, Starts at, Ends at, and Image. No category, audience, participation, capacity, or linked-program control was introduced. New events still default to General Events through the existing form. Existing-event editing, annual observances, public pages, and publication rules retain their workflows.

The date-range implementation and picker markup were extracted from the existing program builder for reuse. Event creation has one blue range, with month/year controls, keyboard navigation, start/end endpoint selection, rounded range ends, and automatic date/time updates. The selected dates retain Philippine wall time. Invalid or incomplete ranges block submission. Native datetime inputs remain available when JavaScript is disabled. Program creation and editing retain their two independent ranges in the same shared calendar.

The Image control supports a local preview, filename/size, removing the pending selection, and format/size feedback. The existing protected multipart POST, image validator, private storage, generated accessible image description, audit record, and draft-only creation remain unchanged. Successful saving opens the existing event record for review. No new model, migration, dependency, API, authentication, or publication operation was added.

## Files changed

- `events/views.py`: route creation to its new template while preserving the existing editor.
- `templates/events/builder/page.html`, `static/css/event-builder.css`, `static/js/event-builder.js`: creation workspace and interactions.
- `templates/partials/range_calendar.html`, `templates/partials/range_settings.html`, `static/js/schedule-calendar.js`: shared calendar and date controls extracted from the program builder.
- `templates/programs/builder/calendar.html`, `templates/programs/builder/page.html`, `static/js/program-builder.js`: load and reuse the shared calendar.
- `templates/admin_portal/dashboard_topbar.html`: event-builder-only breadcrumb and return action.
- `scripts/event_builder_browser_qa.py`, `scripts/event_builder_browser_qa.cjs`: disposable browser verification.
- This validation and screenshot evidence.

## Verification

- 24 focused Django tests passed: existing event field/publication checks and program-builder regressions.
- Event browser checks passed at 1600, 1440, 1280, 1024, 768, 390, and 320 pixels in both themes (14 combinations).
- The existing program browser passed its 14 creation and six editing layouts, calendar interactions, and two audited draft saves after calendar extraction.
- Event browser checks verified the exact field set, automatic range changes, endpoint edits, keyboard access, rounded bands, rejected invalid dates/images, image preview/removal, escaped live-preview text, responsive layout, no-JavaScript fallback, and one complete draft save with an image. Django then confirmed saved datetimes, General classification, private status, no capacity/program linkage, image storage/accessibility text, audit creation, and public inaccessibility of the draft/image.
- Writes used separate disposable MySQL and synthetic uploads. Retained creation pages, the event list, and an existing editor rendered under a read-only SQL guard. Retained business records were not changed.
- System/database checks, JavaScript syntax checks, and whitespace checks passed. Production static collection completed: four changed/new assets and 206 unchanged.
- Desktop light/dark and mobile screenshots were visually inspected after browser paint completion.

Initial harness issues were a route-name typo in the image privacy check and a transient Chrome resource error; corrected/rerun checks passed. Unit artifacts: `santolan-g12-tests-1vnwnvgy`; both final browser harnesses: `santolan-g12-tests-1pjl1z_5`; final mobile-render verification: `santolan-g12-tests-52sfvmht`.

## Compact event schedule follow-up

The event calendar now occupies the full scheduling panel width. Its Event schedule, Start date, and End date controls form a compact group beside the Start time and End time fields below the calendar. When the calendar is narrower than 600 pixels, the date controls move directly below the time fields. Desktop date targets are larger. The existing program calendar retains its original layout and behavior.

The event browser checks now assert full-width calendar geometry, placement beside or below the time fields, and a compact date-control height at all 14 theme/viewport combinations. Both event and program browser harnesses passed again, including their existing range interactions and protected draft saves, in disposable MySQL (`santolan-g12-tests-_h085b_f`). An initial disposable MySQL startup crashed before tests; the fresh retry completed successfully. Desktop and mobile calendar screenshots were visually inspected. System/database checks, JavaScript syntax, and `git diff --check` passed; production static collection copied one updated stylesheet with 209 assets unchanged.

[Dark creation page](event-create-dark.png) · [Light creation page](event-create-light.png) · [Desktop calendar](event-calendar-desktop.png) · [Mobile calendar](event-calendar-mobile.png)
