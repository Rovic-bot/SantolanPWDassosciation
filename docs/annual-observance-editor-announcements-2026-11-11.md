# Annual observance editor and announcement visibility — November 11, 2026

The announcement landing choice below was subsequently refined by the owner:
ordinary announcements now appear in the program-results workspace itself.
See announcements-unified-workspace-2026-11-11.md for that current behavior.

## Owner-authorized changes

The owner requested an annual observance editor containing title, target audience,
start/end dates, description, and image, styled like the event builder. The owner
confirmed that the dates repeat every year. Public observances should use the
announcement-card design, and published notices must appear in Admin Announcements.

## Implemented behavior

- Existing observances use the shared event-builder surfaces, section navigation,
  live summary, image preview, and save controls. The image control also supports
  removal. The accessibility control retains its normal position; mobile save
  controls sit above it.
- The editor converts explicitly changed dates to annual month/day values. The
  retained calendar supports one date or a range within one month. A one-day
  observance uses the same start/end date. Years chosen in the picker are not
  persisted as a one-off schedule.
- Unchanged fixed dates and whole-month rules retain their original meaning.
  Descriptive rules such as third week or last Monday stay intact when both
  date inputs are blank. The editor displays the current rule rather than
  inventing exact official dates for these references.
- Legal references, source links, category, and participation details remain on
  the existing record; removed fields cannot be overwritten through forged
  form input. Image validation and private revision files remain unchanged.
  A replacement image uses the observance title as its image description, with
  essential image information included in the main description.
- Saves still go through the permission-checked service, row lock, version
  comparison, model validation, immutable revision, and audit log. The service
  supplies the edit reason so no extra reason field is required. Existing
  draft creation and publication/history controls remain available.
- Public observances reuse announcement card styling: image or initials,
  month badge, title, summary, recurring dates, and Read more. The same carousel
  supports pointer, touch, arrows, keyboard, and detail dialogs.
- Admin Announcements now opens the actual announcement list for every
  authorized announcement viewer. The earlier route sent administrators with
  result permissions to the program-results workspace, which omitted general
  notices. Program results remains available through its existing link. Its
  in-place refresh URL now points to its own workspace.

No schema migration, publication, content update, or operational data write was
needed to install this change. All prior observance and announcement history is
retained.

## Validation

- Django system/database check passed; migration dry run reports no changes.
- JavaScript syntax and Git whitespace checks passed.
- Read-only inspection of the existing development database verified all twelve
  published observances round-trip without content or recurrence changes. Both
  publicly visible announcements appear in the admin list.
- Form validation checked yearly date conversion, equal-day dates, invalid and
  incomplete ranges, preservation of omitted metadata, image preparation,
  replacement/removal conflict, and invalid image rejection.
- The versioned save service was exercised with database writes replaced by
  spies and a SQL write guard: proposed updates and audit snapshots were
  inspected, and stale edits were rejected. Actual saves/publication were not
  performed.
- Browser previews checked desktop/mobile layouts, live summary, date errors,
  image preview/removal, admin notices/results navigation, public carousel
  arrows and keyboard controls, detail dialogs, high contrast, larger text, and
  mobile save-button visibility. No browser exceptions or form submissions.

Private inspection scripts and screenshots are under
.local/development/observance-editor-preview*; they are not deployment assets.
