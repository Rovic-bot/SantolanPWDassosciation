# Observance popup and announcement navigation — November 11, 2026

- Annual observance cards are now single accessible links. The Read more button
  is removed; clicking anywhere on a card or pressing Enter opens its details.
  Dragging still browses the carousel without opening a popup.
- The popup follows the supplied rounded layout: image/gradient header, title,
  category, official-source link, recurring schedule, description, audience,
  participation, legal basis, and calendar icon. Uploaded images are used when
  present; the fallback is decorative. Existing published text is preserved.
- View announcement history was removed from the workspace. The former
  /announcements/manage/notices/ URL redirects to the main Announcements tab.
  Protected publication history remains available within announcement review.

Validation: Django system/database, JavaScript syntax and whitespace checks
passed. Browser checks verified whole-card mouse and keyboard access, close,
mobile layout, swipe without accidental opening, and the old URL redirect.
Desktop/mobile screenshots are in the ignored .local/development directory.
No publication or database records were changed. Local server restarted.

Owner follow-up: removed the Official source button and Legal basis field from
the annual-observance popup. The heading now uses the full width and the footer
has two columns (Target audience and Who may participate), stacking on mobile.
Confirmed both removed labels are absent in the rendered popup and there is no
mobile horizontal overflow. Django and whitespace checks passed; server restarted.

Sizing follow-up: widened the popup from 560px to 760px and shortened the image
header from 300px to 240px, with tighter body/footer spacing. The displayed
observance measures 760px by 527px on desktop without internal scrolling;
the 390px mobile viewport fits without horizontal overflow. Content and opening
animation are preserved.
