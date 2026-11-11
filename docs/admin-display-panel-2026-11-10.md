# Admin Display/accessibility panel

The admin workspace and native admin screens now use the public portal's Display-panel layout: text-size selector, dark mode, high contrast, reduced motion, reset, Tagalog interface-label toggle, and selected-text reading. The dashboard and onsite-registration header theme buttons were removed. Theme persistence and chart theme-change events remain active through the panel.

The panel reuses admin light/dark tokens; high contrast uses white with dark text. Mobile widths and maximum heights keep the panel inside the viewport and scrollable. Admin language preference is stored separately from public language preference. Translation covers the Display controls and common navigation labels, not all admin prose; saved member information, submitted values, and database records are unchanged.

Selected-text reading is available only after an explicit action on visible text. Editable values and hidden content are excluded. Admin reading requires a local device/browser voice; it does not fall back to a remote voice. If the browser has no local voice, it reports that reading is unavailable.

Verification used private, read-only renders of an existing member record and the native admin shell. Browser checks confirmed opening/closing, text size (20px root for Largest), dark mode, high contrast, reduced motion, Tagalog controls, persistence after reload, reset, Escape behavior, and a 390px viewport with the panel fully visible. Both admin shells worked without JavaScript errors. Selected-text controls appeared for a visible heading and closed on Escape; no speech playback was initiated. The public panel and its dark-mode control also remained functional. Screenshot inspection confirmed readable light and dark panel text.

Django checks, JavaScript syntax checks, and whitespace checks passed. No emails, operational changes, synthetic records, fixtures, or automated test suites were used. The local server was restarted after the change.
