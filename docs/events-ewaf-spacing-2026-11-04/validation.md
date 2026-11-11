# Events Calendar and EWAF spacing — November 4, 2026

The owner's screenshot follow-up requested less unused space above the event list, annual observance cards, and EWAF queue/selected-program panel; removal of the observance introduction and program-row arrows; and a spaced button labeled “Configuration Vault.”

The event actions remain below the filters, aligned above the calendar in the right column. The event list now starts beside those actions. Narrow layouts keep the actions above the list. The observance introduction is removed, its accessible section label is retained, and the quarter cards follow the preceding content with a 1.25rem gap.

The EWAF Vault action has 0.75rem vertical spacing and the requested label. An empty feedback region no longer reserves a blank row above the queue and analysis. The program arrows and their unused grid column are removed; row and keyboard selection still work.

Only templates and page-scoped CSS changed. Existing navigation, filters, permissions and business rules are retained; no models, migrations, calculation changes or new dependencies were introduced.

Validation: both existing browser journeys passed on a fresh disposable MySQL instance: `scripts.events_workspace_browser_qa` and `scripts.ewaf_selection_browser_qa`. They covered 28 responsive/theme combinations, event list scrolling, calendar navigation, observance links, EWAF selection and filters, keyboard use, no-JavaScript fallbacks and two protected synthetic ranking generations. No JavaScript errors were reported. Desktop dark/light and narrow-screen screenshots were inspected. Django database/system checks and `git diff --check` passed.

Assets were collected and the identity-checked local web process was refreshed independently of its retained database. HTTP checks confirmed the updated styles on port 8013.

- [Events desktop](events-dark-1600.png)
- [EWAF desktop](ewaf-selection-dark-1600.png)
- [Events browser results](events-workspace-browser-results.json)
- [EWAF browser results](ewaf-selection-browser-results.json)
