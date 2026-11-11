# Annual observance calendar and Resources FAQ — November 11, 2026

## Authorized changes

The owner requested the event-style calendar when editing annual observance
dates, and an expanding FAQ list in Resources based on the supplied reference.
The previously confirmed yearly recurrence remains in effect.

## Implementation

- Annual observance editing reuses the event/program calendar with month/year
  navigation, keyboard controls, start/end selection, and highlighted ranges.
  It uses dates only; selected month/day values repeat every year.
- Existing fixed dates and whole-month schedules initialize the calendar without
  changing their rules. Descriptive rules remain intact until dates are chosen;
  “Keep current annual rule” clears an unsaved replacement selection.
- Incomplete, reversed, and cross-month ranges are blocked before submission.
  Existing server validation, version checks, audit history, and save services
  are unchanged. Native date fields remain available without JavaScript.
- Resources FAQs use numbered disclosure rows with plus/close icons. Opening
  another answer smoothly closes the previous answer. Animation can reverse
  during repeated clicks and respects OS and saved reduced-motion preferences.
- FAQ content and CMS editing fields are retained. Native disclosures support
  keyboard use and no-JavaScript browsing; printing expands all answers. The
  existing Guides and resources carousel is unaffected.
- Both light and dark palettes use shared public portal colors. Spacing and
  icon contrast are scoped to the FAQ component.

## Validation

- Read-only Django rendering covered all existing annual recurrence types and
  both event/program builders. All existing annual records round-tripped through
  the edit form without changing recurrence rules. SQL writes were blocked.
- Browser previews checked calendar initialization, yearly ranges, one-day
  selection, incomplete/reversed/cross-month rejection, reset, keyboard arrows,
  and mobile sizing. Event/program date-time and time editing still worked.
- FAQ previews checked one-open-at-a-time behavior, keyboard activation, rapid
  toggling, desktop/mobile layouts, light/dark/high-contrast icons, both motion
  preferences, printing, and native disclosures without JavaScript.
- No browser exceptions or form submissions occurred. No operational records,
  publications, private attachments, or emails were changed during verification.
- Django database/system checks, JavaScript syntax checks, and Git whitespace
  checks passed. No migration or automated Django test suite was needed.

Private preview scripts and screenshots are under
`.local/development/observance-calendar-preview/` and the associated inspection
scripts. They are not deployment assets.
