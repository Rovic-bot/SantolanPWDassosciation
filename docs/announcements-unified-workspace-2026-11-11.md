# Announcements in the program-results workspace — November 11, 2026

The owner clarified that ordinary announcements must appear in the existing
program-results workspace, with its selectable list and right-side overview.
This supersedes the separate announcement-list landing choice recorded earlier
in annual-observance-editor-announcements-2026-11-11.md.

## Delivered behavior

- The main admin Announcements route and the program-results workspace both show
  regular announcements above the program-result rows in the same list surface.
  The existing applicant-only scope for program rows remains unchanged.
- Announcement rows show title, publication status, category, a short summary,
  and publication/update date. Selection updates the existing right-side panel
  immediately, using a separate notice identifier so it cannot collide with a
  program selection.
- The announcement overview includes its image, content preview, dates, the
  public link when currently visible, and permission-appropriate edit/review
  links. Applicant counts, allocations, and slot usage remain specific to
  program results.
- Search covers announcement title/content/source and program title/code.
  Common status and sorting controls apply to both lists. Assistance-type and
  registration filters restrict notices to matching linked programs.
- Both groups have bounded pagination. Result-publication refreshes preserve
  selection and refresh the combined list. The existing history table remains
  available through View announcement history and as the fallback for staff
  who cannot access the program-results workflow.

No publication, selection, eligibility, audit, model, or migration changes.

## Verification

- Read-only Django inspection confirmed the existing published general notice
  and Rice Distribution program appear on both workspace routes. Search,
  status filters, all existing sort modes, explicit selection, publication
  links, and anonymous-access rejection were checked.
- SQL writes were blocked during inspection; announcement records and history
  counts were unchanged.
- Browser previews checked the combined light/dark layout, desktop/mobile,
  larger text, keyboard selection, right-panel switching, the actual edit
  dialog, review link, live result refresh, search for each record type, and
  reset filters. No browser exceptions or submitted forms.
- Django database/system and Git whitespace checks passed.

Private preview scripts and screenshots are under
.local/development/announcement-workspace-preview*.

## Side-by-side lists and review popup

The owner's follow-up places Announcements and Program results in independent
columns, with the existing selected-item overview retained. Small screens stack
the columns. Both lists keep their search, pagination, and selection behavior.

Review announcement now uses the existing accessible publication dialog. Its
content and controls share a template with the full-page fallback. Publication
POSTs retain the existing permission, CSRF, version and audit checks; successful
responses return the popup, and the workspace refreshes without navigation.
History pagination also stays in the popup.

Browser verification confirmed adjacent desktop columns, responsive mobile
layout, review popup content, unchanged workspace URL, Escape dismissal, and
retained selection. A read-only invalid-POST check confirmed form errors render
inside the popup without writes. System, JavaScript syntax and whitespace checks
passed. No actual publication change was made.

The owner subsequently removed the standalone review-page behavior. Direct
review links and redirects after saving an announcement now lead to the
Announcements workspace with the review popup opened automatically. The open
instruction is removed from browser history so closing or refreshing leaves
the workspace in place. The review endpoint only renders dialog responses.
The history-list permission fallback supports the same dialog. Read-only and
browser checks verified the direct-link redirect, automatic popup, unchanged
workspace URL on close, and retained list; no publication changes were submitted.
