# Public event carousel - November 8, 2026

Removed the Activity listings / Scheduled activities heading, introductory sentence and Schedule / Show activities filter shown in the owner's screenshot. The Events image header remains, with its jump link targeting the accessible scheduled-event region.

Scheduled events now use the shared swipe-card controls with two equal-width cards on desktop (992 px and above) and one on smaller screens. Extra cards slide horizontally using touch, mouse drag, arrow buttons or keyboard navigation. A final single card is centered. The row measures all event content to retain one stable height without internal vertical scrolling. Images, title-initial fallbacks, dates, locations and existing event detail popups remain available.

The public view supplies the complete existing published upcoming/ongoing queryset instead of slicing it into ten-item pages. Existing publication/date filtering and explicit past-period URLs remain unchanged. Drafts and archived records remain private; no event records, attendance, participation rules or schema changed. The removed filter's empty-state wording was replaced with editable check-back guidance.

The shared carousel supports an optional CSS column count; other decks retain their content-based widths. Linked event cards disable native browser link/image dragging and suppress clicks following a swipe, so dragging does not accidentally open a popup. Ordinary clicks still open details. Print and no-JavaScript views retain every event.

## Verification

- `node scripts/public_event_carousel_qa.cjs` passed at 1920, 1440, 992, 768, 390 and 320 px. It verified the correct number of visible cards, reachability of every event, equal/stable height, centered final group, no horizontal page overflow, mouse/touch swiping, popup behavior, keyboard navigation, print and no-JavaScript fallback. No browser errors occurred.
- The shared card-sizing regression passed 36 deck/viewport combinations, including Home, About, Resources and Events, plus enlarged text, touch, print and fallback checks. The harness now permits the existing rounded event-image clipping while still checking that content fits fully; screenshots wait for slide animations to finish.
- All three focused disposable-database checks passed across the initial run and focused rerun: public observance publication boundaries and historical event visibility, including the eleventh upcoming event beyond the former page limit. One existing test had a stale Home expectation: Home has already been changed to show only an event happening now. Its assertion was corrected to match that existing behavior, and the focused rerun passed.
- Django system check, JavaScript syntax and `git diff --check` passed. The retained local server was restarted at port 8013. Browser checks were read-only; no live event content was edited.

Evidence: `results.json`, `events-1440.png`, `events-390.png` and the shared regression evidence in `../public-card-sizing-2026-11-08/`.
