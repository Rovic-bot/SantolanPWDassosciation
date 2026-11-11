# Public conversation screen

The owner requested a screen-filling chat page with a fixed composer and scrolling messages. This follows the dedicated conversation pages described in [the conversation-page validation](community-assistance-conversation-pages-2026-11-10.md).

- Only the conversation page uses the viewport-sized layout. Its compact subject bar, private reference and composer remain visible while the message list scrolls. The public sidebar remains beside the chat on desktop; on smaller screens its existing bottom navigation has reserved space below the composer. The global footer is omitted on this screen; the back link, open-another-conversation link and session-clearing action remain available.
- The message field starts at 46 pixels and grows with typed content to 104 pixels. Sending successfully resets its height without navigating or replacing the conversation. Mobile visual-viewport changes keep the composer within the available screen; physical device keyboard behavior has not been manually verified.
- Message bubbles keep their natural height, preventing flex shrinking and clipped text. The Display control uses the same bottom-right placement and appearance as Home, with room beside the composer controls on desktop and beside the session links on phones. Existing light, dark, high-contrast and text-size preferences remain available.
- Private access, reference validation, closure, email delivery and message persistence were not changed. No schema changes or migrations are required.

## Verification

Read-only rendering used an existing conversation under a SQL write guard. Browser previews intercepted all submissions; no concern, message, email or other operational record was created. Desktop 1440×900 and 1360×768, phone 390×844 and 320×568, and landscape 844×390 checks confirmed zero page scrolling, a scrollable message list, stationary heading/composer and a 46-pixel empty editor. DOM-only copies of existing messages exercised overflow without creating records.

The preview confirmed capped editor growth, shrinkage after an intercepted successful send, retained page identity, accessible Display controls, and no overflow with largest text/high contrast at 320 pixels. Dark and mobile screenshots were inspected. JavaScript syntax, Django/database checks and `git diff --check` passed. No automated Django test suite was run. Private preview files remain under ignored `.local/development/conversation-pages-preview/`.
