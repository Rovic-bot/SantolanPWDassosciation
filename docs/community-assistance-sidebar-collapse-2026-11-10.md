# Entire ticket sidebar collapse

The owner clarified that the entire evidence/activity/action sidebar must collapse toward the right, rather than only the Supporting evidence contents.

The subsequent [conversation layout update](community-assistance-chat-bubbles-2026-11-10.md) replaces the original toggle placement and 56-pixel rail described below with a centered edge control, animated transitions, and a 42-pixel rail.

The sidebar now has a Hide panel button. On desktop, it reduces the whole sidebar to a 56-pixel rail on the right and gives the freed width to the conversation. The remaining left-pointing arrow restores evidence, activity history, and Close ticket. On small screens the stacked panel folds into a compact control aligned right. Supporting evidence is again a normal section.

The toggle uses `aria-expanded`, a controlled panel ID, descriptive labels, and keyboard activation. Hidden contents leave the focus order. Reply drafts are preserved. The current ticket's collapsed state survives dialog content reloads within the same workspace page. Without JavaScript, the panel remains available.

Read-only browser inspection verified conversation width expansion, full-panel hiding, keyboard restoration, preserved drafts, restored Close ticket, and no overflow at 1440, 1024, 390, and 320 pixels. Existing light/dark/high-contrast layouts remained usable. Django checks, JavaScript syntax, and `git diff --check` passed. No test suite, database writes, message submission, or email sending was performed. The development server was restarted.
