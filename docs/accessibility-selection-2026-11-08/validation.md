# Public display preferences and selected-text reading - 8 November 2026

The public portal now uses one high-contrast theme: white reading surfaces, dark text, clear borders, and white text on dark support panels. It overrides the conflicting legacy themes after page-specific styles. Buttons, focus outlines, dates, status labels, step markers, and assistance icons remain visible. Normal pages retain the charcoal and cream palette.

The Display panel retains text size, high contrast, reduced motion, and Reset preferences. Its controls fit at 320px with the largest text setting. The page-wide Read page aloud and Stop reading buttons have been removed.

Highlighting public page text reveals a floating Read aloud control. Clicking it, activating it with Enter, or pressing Alt + R reads only that selection. Closing it or pressing Escape cancels playback. Changing or clearing the selection also cancels playback. Long selections are read in ordered chunks without truncating words. Form values, editable content, private dialogs, and Admin pages are excluded. Selected text is neither stored nor submitted by the application. Browser speech support is required; unsupported browsers retain the display controls without a dead reading action.

Accessibility and FAQ fallback guidance now explains selection-based reading. Published CMS records were not edited. There are no schema, business-rule, permission, or workflow changes. Existing working-tree changes were preserved.

## Validation

- Read-only Chrome checks passed for exact selection output, no automatic playback, native mouse selection, touch activation, keyboard activation, sequential long passages, completion, cancellation, dismissal, error recovery, and exclusion of form/editable values.
- Floating controls and Display preferences were checked at 1440, 768, 390, and 320px. Preference persistence, Reset, enlarged text, reduced motion, Escape focus restoration, unsupported speech, and print hiding passed.
- Computed text contrast checks passed on Home, About, Programs, Resources, Membership, Events, Announcements, Results, and program details, including all shared carousel card states. Final checks also covered the accessibility information page and program action hover, step markers, and assistance icon.
- Screenshots of normal and high-contrast controls, selected text, Resources, and program details were visually inspected. These checks are targeted UI verification, not a complete WCAG audit; the contrast calculation does not model every image or composited layer.
- Speech tests used a controlled browser speech mock to verify exact utterances and lifecycle events. Audible output and installed system voices were not manually tested.
- `node --check static/js/selection-reader.js`, the configured `scripts/current_development.py check`, and `git diff --check` passed. No browser JavaScript errors were recorded.

Browser requests were restricted to GET/HEAD for the main QA contexts. No reference or application form was submitted, no record or published content was changed, and no message was sent. The identity-verified local web process was refreshed to load template changes after checking for in-progress emails; MySQL remained running.

Evidence: [checks](checks.json), [contrast results](contrast-scan.json), [selected text](selected-text-final.png), [normal Display panel](display-default-final.png), [320px panel with largest text](display-320.png), [program details](program-detail-contrast-final.png), and [FAQ](faq-contrast-final.png). Files ending in `-final.png` supersede earlier diagnostic page screenshots in this folder.
