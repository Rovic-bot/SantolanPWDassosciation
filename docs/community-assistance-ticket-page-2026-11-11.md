# Community Assistance ticket pages - November 11, 2026

The owner requested that View ticket open a full page. This supersedes the
inbox popup presentation described in the earlier ticket-layout documentation.

## Viewport layout and phone details menu (subsequent owner request)

The ticket now fills the available screen without vertical document scrolling.
The Back to inbox link and generic workspace top bar are removed from this page.
The admin sidebar remains; on smaller screens its compact Menu control opens
navigation above the chat. Returning to other workspace pages restores their
normal page layout and scrolling.

Messages scroll inside the conversation, with the compact composer anchored
below them. The desktop evidence/activity panel still collapses to the right.
At phone/tablet widths, it is closed initially and opens from a three-dot button
in the ticket header as a right-side drawer, instead of stacking below the chat.
The drawer has its own scroll area, close button, Escape handling, focus return,
and keyboard focus containment. Reduced-motion settings disable its transition.
System email history is now inside this details panel. The Display control keeps
its normal corner position, with space reserved to avoid covering ticket actions.
Viewport resizing also accommodates the smaller space available with a phone
keyboard. No sending, closure, review, permission, or polling rules were changed.

Read-only previews used the existing ticket under a SQL write guard and blocked
all browser POSTs. Checks covered 1440x950, 1440x700, 1024x768, 390x844, 320x740,
and 390x480 layouts; no vertical document or horizontal overflow occurred. The
conversation scrolls independently, and drafts/channel choices survive panel
toggles and responsive changes. Checks also covered sidebar navigation back to
the inbox and re-entry, light/dark appearance, reduced motion, and polling.
No emails, messages, ticket changes, or attachment-access audits were generated.

## Original full-page implementation

- Both View ticket and the request subject navigate to the existing protected
  ticket detail URL. The inbox no longer includes the record dialog or loads
  its assets.
- The detail page fills the available admin workspace, retains its sidebar
  navigation, and provides Back to inbox. The popup-style close-view icon is
  removed; Close ticket still performs the existing conversation-ending action.
- The conversation, compact reply composer, member portrait/name, evidence,
  activity history and animated collapsible right panel remain available.
  Desktop messages scroll within the conversation; smaller screens retain the
  responsive layout and bounded conversation area.
- Live polling and the saved Email/Online conversation selection retain their
  existing behavior. Permissions, automatic review, closure, audits, private
  attachments, reply submission and server-side redirects are unchanged.

Validation used the existing ticket and inbox rendered through their Django
views under a SQL write guard. Browser previews confirmed navigation from both
entry links, the ticket URL, no open dialog, Back to inbox and browser Back,
active admin navigation, sidebar collapse/expand with draft retention, saved
channel on reopening, and background update requests. Desktop, 1024px, 390px
and 320px layouts had no horizontal overflow or JavaScript errors.

All browser POST requests were blocked; no message, email, status change or
attachment-access audit was generated. Django system/database and whitespace
checks passed. No migration was needed. Private preview artifacts remain in
the ignored .local/development directory.
