# Member overview and update-card highlight

The member overview now falls back to the current approved Association registration profile for sex/gender and civil status when the older coded member columns are blank. Existing coded values retain precedence. It does not read pending update requests or revert to an original application after an approved edit. No stored values or historical records were changed.

The overview displays family members and household members under their own labels. Dependents remain visible when recorded (including zero), or for older profiles that use that field. Family size is not treated as a dependent count.

The public Update member information guidance card uses the portal's warm cream `#e6dfd2` with dark `#1c1a18` text in light and dark modes. High contrast uses white with `#111` text and a stronger border. Scoped Tailwind tokens also cover expanded details, icons, links, hover, and keyboard focus. Other cards retain their existing colors and click-only disclosures.

Validation:

- Django system checks with the active local database passed; template loading and whitespace checks passed.
- Read-only inspection of the existing approved member confirmed saved gender, civil status, and family count reach the overview presentation and rendered template. No personal values were included in verification output.
- Live read-only browser inspection confirmed the cream background and dark heading, description, disclosure toggle, and action-link text in light/dark modes; high-contrast rendering used white/dark text.
- Hover kept details closed, clicking opened them, and Enter closed them. A 390px viewport had no horizontal overflow.
- Rebuilt the local guidance stylesheet, updated its cache version, and restarted the local development server.

No automated test suite, fixture, synthetic record, email, or database mutation was used for this change. The local development database and approved record were preserved.
