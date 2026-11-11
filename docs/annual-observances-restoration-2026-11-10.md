# Fixed annual observances restored

The owner clarified that the annual calendar is fixed reference content and must be retained when clearing operational development data. The earlier reset incorrectly included these entries with operational events.

Restored all 12 published entries, one per month, from the retained local archive to `santolan_pwd_development`. Saved UUIDs, titles, recurrence rules, date fields, sources, descriptions, and participation guidance were preserved. The archived entries had no images attached. Restoration used `events.services.save_observance` with publication enabled and the existing real administrator, with an explicit reason recording the owner's request and assistant execution. It created one fresh immutable revision and audit entry per observance. No old administrator/demo account or historical operational data was imported.

Read-only verification confirmed 12 public calendar entries and 12 Admin row links resolving to the permission-checked edit view. Editing an entry saves and publishes through the existing form, validation, version checks, and audit service. All unrelated table counts were unchanged during restoration. No automated test suite or synthetic fixtures were used.

The source snapshot and restoration report are retained privately alongside the pre-reset backup under `C:\Users\rovic\Documents\Santolan Development Backups\before-fresh-20261110-135526\`.

For future development resets, treat `events_annualobservance` and its reference-content revision/log tables as retained calendar configuration. Keep these distinct from `events_event`, registrations, attendance, application programs, members, beneficiaries, and actual assistance records. Do not silently delete custom edits or restore scheduled events when preserving the annual calendar.
