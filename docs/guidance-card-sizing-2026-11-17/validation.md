# Equal guidance card sizes — November 17, 2026

The owner requested equal sizes for the six Guidance and support cards on the deployed Home page. The grid now gives every row the same content-based height and stretches each card to fill its cell. Cards use a column layout with flexible details, keeping the existing action links aligned at the bottom. Widths remain equal within the responsive two-column or one-column grid. No fixed height, clipped content or internal scrolling was introduced; opening details or enlarging text increases the shared height as needed.

Changed four presentation files: `templates/public/guidance/section.html`, `templates/public/guidance/card.html`, `static/css/home-guidance.css`, and the stylesheet cache version in `templates/public/home.html`. The stylesheet was rebuilt from the existing Tailwind configuration. Text, destinations, disclosures, display controls, themes and existing hover/focus behavior are retained. No business rules, records, database fields or migrations changed.

## Verification before deployment

- `npm run build:guidance`, compilation of the three changed templates, `scripts/current_development.py check`, and `git -c core.safecrlf=false diff --check` passed.
- 19 read-only Chrome checks passed using the deployed Home HTML with only the four candidate presentation changes substituted. The six cards had matching widths and heights at 1440, 1280, 992, 768, 390 and 320 px, with aligned action links and no clipped content or horizontal page overflow.
- Dark mode, high contrast, Largest text, Tagalog with Largest text, and JavaScript-disabled rendering passed. Keyboard disclosure opening/closing and the Reading help display button remained functional. Expanded details fit while all cards retained equal heights. Existing action destinations were retained.
- No JavaScript errors or write requests occurred. Desktop and mobile screenshots were inspected; fixed viewport controls are excluded from section captures where applicable.
- [Preview measurements](preview/checks.json) and [desktop layout](preview/1440-light.png).

The scoped release is based on deployment branch head `0ed3d9a66f16eac53da8042e50e6dc843d5b8320`. The previously deployed smooth dark-mode transition is retained, and unfinished work in the main local checkout is preserved.

## Hosted activation

Commit `1ee7a262ade6bec8f38337545bdf6284cb92c1ec` was deployed through the existing Render service. Deploy `dep-dbu1dkmk1f9s73a1ndh0` reached **live** on November 17, 2026 at **08:58:01 UTC / 4:58:01 PM Philippine time**.

All 19 checks passed again against the actual hosted Home page, with no substituted HTML or assets. For example, all six cards measured 576 × 250 px at a 1440 px viewport and 309 × 278 px at a 390 px viewport. Larger text, translated content and expanded details increased the shared height without clipping. Dark mode, high contrast, keyboard disclosures, action links and JavaScript-disabled layout passed. No JavaScript errors or write requests occurred.

The served stylesheet matched the release's exact Git bytes, all six updated card templates were present in the returned HTML, and the existing theme-transition asset remained linked. `/healthz/` returned HTTP 200 with `status: ok`. Render returned no application error logs from activation through **08:59:01 UTC**. Hosted desktop and mobile screenshots were visually inspected.

- [Hosted checks](hosted/checks.json) and [release verification](hosted/release.json)
- [Desktop cards](hosted/1440-light.png), [mobile cards](hosted/390-light.png), and [dark-mode cards](hosted/1440-dark.png)
