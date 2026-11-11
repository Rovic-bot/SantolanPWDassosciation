# About background cards — November 8, 2026

The public About page's right-hand Mission and background panel now presents
the published background sections as individual cards. Only the current card
is visible. Next or a leftward swipe slides it off to the left and reveals the
next card from the right. Previous/rightward swipe reverses this movement.

The seven current sections retain their published text. Controls provide a
card counter, Previous/Next buttons, and Left/Right/Home/End keyboard navigation.
The first/last boundaries stop movement without wrapping. There is no automatic
advancement. Offscreen cards are hidden and inert for keyboard/screen-reader use.

Touch uses horizontal pointer gestures while vertical page scrolling and pinch
zoom remain available. Device and portal reduced-motion preferences skip the
slide animation. Without JavaScript, all source content is readable inline;
printing also exposes every card. The visual editor retains its original
editable field. Saved plain-text overrides are grouped safely using text nodes.

Implementation is limited to `templates/public/about.html` and new About-only
CSS/JavaScript assets. No database records, business rules, admin behavior or
other public page assets were changed.

Validation:

- `node scripts/public_about_cards_qa.cjs` passed 35 card/viewport checks at
  1440, 992, 768, 390 and 320 pixels without horizontal overflow.
- Mouse drag and actual Chromium touch input passed both directions; vertical
  gestures still scroll. Confirmed the outgoing next-card animation exits left.
- Buttons, keyboard navigation, first/last boundaries, one visible/accessible
  card, reduced motion, print and no-JavaScript fallbacks passed.
- Compared every published heading, paragraph and list item to the unenhanced
  source. Saved CMS text containing HTML-like input remains escaped text.
- Home does not load the new About assets. No JavaScript errors were observed.
- Django system/database check, JavaScript syntax and scoped whitespace checks
  passed. No migrations or database tests were required for this presentation.

Evidence: `results.json`, `about-1440.png`, `about-390.png`, `about-320.png`
and `second-card-*.png` in this directory. Local development server restarted
at http://127.0.0.1:8013/about/.
