# Public portal motion and event palette - November 11, 2026

The public portal now transitions between sidebar destinations with a short
content fade and slide. Native document transitions retain ordinary navigation,
history and links; browsers without that feature use an arrival animation.
The sidebar and accessibility control remain separate from the moving content.

Announcement, event and annual-observance dialogs animate when opened. Their
fetched contents have a short entrance, and loading starts in the appropriate
popup shape. Home's Guidance and support cards animate their existing native
disclosures, including keyboard activation and reversal during rapid clicks.

The All, Announcements and Program Results filters transition only the results
region. Existing results remain visible while the GET request is pending.
Search, pagination, focus restoration, history and request cancellation remain
supported. Selecting the current filter cancels a different pending filter.

The event popup uses Home's warm neutral surface, canvas, text and border tokens
in both light and dark themes. High contrast and forced colors remain supported.
The system reduced-motion preference and the saved Display setting disable the
new motion; the saved preference is applied before first paint.

Validation completed against the running local site with browser requests
restricted to GET:

- Sidebar document transitions and the actual content animation.
- Event, announcement and annual-observance opening and closing.
- Guidance keyboard opening/closing and rapid reversal.
- All three announcement categories, browser Back, rapid category changes,
  cancellation by returning to the current category, failed requests and retry.
- Filter fallback without the View Transition API.
- Desktop and mobile event layout, shared light/dark palette, high contrast,
  forced colors, and both reduced-motion settings.
- No browser JavaScript errors; Django system/database, JavaScript syntax and
  whitespace checks passed.

Preview scripts and screenshots are in the ignored .local/development directory.
No database records, publication states or business rules were changed.
