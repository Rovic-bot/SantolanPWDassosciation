# Equal guidance card sizes — November 17, 2026

The owner requested equal sizes for the six Guidance and support cards on the deployed Home page. The grid now gives every row the same content-based height and stretches each card to fill its cell. Cards use a column layout with flexible details, keeping the existing action links aligned at the bottom. Widths remain equal within the responsive two-column or one-column grid. No fixed height, clipped content or internal scrolling was introduced; opening details or enlarging text increases the shared height as needed.

Changed four presentation files: `templates/public/guidance/section.html`, `templates/public/guidance/card.html`, `static/css/home-guidance.css`, and the stylesheet cache version in `templates/public/home.html`. The stylesheet was rebuilt from the existing Tailwind configuration. Text, destinations, disclosures, display controls, themes and existing hover/focus behavior are retained. No business rules, records, database fields or migrations changed.

## Verification before deployment

- `npm run build:guidance`, compilation of the three changed templates, `scripts/current_development.py check`, and `git -c core.safecrlf=false diff --check` passed.
- 19 read-only Chrome checks passed using the deployed Home HTML with only the four candidate presentation changes substituted. The six cards had matching widths and heights at 1440, 1280, 992, 768, 390 and 320 px, with aligned action links and no clipped content or horizontal page overflow.
- Dark mode, high contrast, Largest text, Tagalog with Largest text, and JavaScript-disabled rendering passed. Keyboard disclosure opening/closing and the Reading help display button remained functional. Expanded details fit while all cards retained equal heights. Existing action destinations were retained.
- No JavaScript errors or write requests occurred. Desktop and mobile screenshots were inspected; fixed viewport controls are excluded from section captures where applicable.
- [Preview measurements](preview/checks.json) and [desktop layout](preview/1440-light.png).

The scoped release is based on deployment branch head `0ed3d9a66f16eac53da8042e50e6dc843d5b8320`. The previously deployed smooth dark-mode transition is retained, and unfinished work in the main local checkout is preserved. Hosted activation will be recorded after verification.
