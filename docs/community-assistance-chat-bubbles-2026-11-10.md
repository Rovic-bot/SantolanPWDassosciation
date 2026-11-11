# Community Assistance conversation layout

The owner requested left-aligned member messages, right-aligned admin replies, the member's registered name and photo, and an animated sidebar with its toggle centered on the panel edge.

The admin ticket header now shows the linked member record's full name and portrait. The original concern and subsequent member replies use compact bubbles on the left with the same portrait. Staff replies use green bubbles on the right, without visible staff names or icons. Timestamps remain below each bubble; the subject appears above the conversation. Contact details, delivery choices, and the activity history remain available.

Portraits use the existing member portrait resolver and protected document URLs. The referral view checks member access before resolving the image; existing document and linked registration permissions still apply. An initial is displayed when no permitted photo is available or the image cannot load. No new public photo endpoint or media URL was introduced.

The complete evidence/activity/action sidebar slides right into a 42-pixel rail, giving its width to the conversation. Its toggle sits at the middle of the panel's left edge. Expanding restores the panel with the reverse transition. Collapsed contents are inert and excluded from the accessibility tree. Reply drafts and per-ticket collapsed state are preserved. System and in-app reduced-motion settings disable the transitions. The stacked mobile sidebar also collapses to the right.

## Validation

- Read-only rendering used an existing ticket and member. Browser requests that could modify records were blocked, and existing private images were supplied locally for the preview without triggering access-audit writes.
- Verified the registered name, loaded member portrait, left/right message alignment, and absence of visible staff names/icons in replies.
- Checked the centered edge control, keyboard collapse/expand, restored ticket actions, preserved draft, and intermediate animation frames in both directions.
- Checked light, dark, and high-contrast rendering; no horizontal overflow at 1440, 1024, 390, or 320 pixels. Both system and in-app reduced-motion preferences produced immediate state changes.
- Django system checks, JavaScript syntax, and `git diff --check` passed. No automated test suite, new records, database migration, message submission, or email sending was used.

Private preview artifacts remain under ignored `.local/development/referral-ticket-layout/` and are not included in documentation assets.
