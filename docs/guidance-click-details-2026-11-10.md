# Guidance cards: click to expand

The owner requested details only on click. All six home guidance cards now use native details/summary disclosures. Details remain collapsed on hover, focus and touch until activated. Clicking again collapses them; Enter and Space use native keyboard behavior. Existing action links and Display controls remain separate. The shared light/dark/high-contrast palette and independent card heights are retained.

Rebuilt the local Tailwind stylesheet and updated its cache version. Django system checks and diff whitespace checks passed. Read-only browser inspection of the live homepage confirmed hover remains collapsed, click expands, Enter collapses, and the EWAF action opens its linked disclosure. No business data, fixtures or test accounts were created, and no automated test suite ran.

Restarting exposed a Windows virtual-environment launcher PID mismatch in the new local server helper. Startup now stores the PID reported by the identity-verified application after it is healthy, rather than the wrapper process PID. The guarded start/restart completed successfully against the same fresh database.
