# Admin motion validation — November 11, 2026

Owner-authorized presentation change: animate admin sidebar destinations, page refreshes, popups, Overview charts, circular gauges and the EWAF contribution panel from zero to their saved displayed values.

## Implementation

- `static/css/admin-motion.css` provides a 340 ms content entrance, 260 ms popup entrance and 200 ms native-dialog exit/backdrop transition where supported. Both the workspace shell and native Django admin shell include it. Normal routing, popup focus and dismissal behavior stay in their existing controllers.
- `static/js/admin-motion.js` uses the existing `WorkspacePage` lifecycle, IntersectionObserver, bounded animation frames and the browser Web Animations API. Visible charts animate once per page visit; offscreen charts start when first visible. Layout/theme redraws retain their final values rather than repeatedly restarting the effect. Cleanup cancels page-owned work on navigation.
- Overview SVG rings, pie/donut sectors, bars, columns, area/line charts and scatter points receive appropriate reveal/growth motion. Heatmap cells fade in. Numeric headline metrics and prominent chart percentages count up. No new chart library is introduced.
- EWAF circular gauges and contribution bars animate on entrance. The existing in-place applicant-switch controller now starts contribution values and widths at zero and settles at the new server-provided values in 700 ms. Initial shared animations take 850 ms. Original SVG attributes, source JSON, saved scores, table values and precision remain authoritative.
- Operating-system reduced motion and the application's reduced-motion preference bypass these effects; changing preference mid-animation immediately restores exact final values. Preparing to print also finishes numeric/chart animations. No permanent page transform is retained after entry.

## Validation

Actual Django dashboard, EWAF and native admin templates were rendered with synthetic data and database cursors explicitly blocked. Browser requests were intercepted and fulfilled from those temporary fixtures and repository/dependency static assets; no external requests, real records, business submissions or emails were involved.

Chrome/Playwright checks passed for:

- 13 SVG kinds: member-donut, rings, proportional, progress, horizontal, stacked, pie, donut, column, histogram, area, line and scatter; heatmap rendering also remained available.
- Actual animation calls for the applicable SVG shapes; unchanged final data attributes, completed temporary clips and exact final percentages/counts.
- Three sidebar navigation cycles, Back navigation, refresh and a single motion controller per loaded page.
- Native-dialog entrance, Escape dismissal and focus return on the dashboard; native admin page/popup animation inclusion.
- EWAF intermediate arc/contribution values and exact final totals, followed by an in-place applicant change and its new final values.
- OS reduced motion, application reduced motion and preference changes during active animation.
- Resizing without replaying settled charts; layouts at 1440, 390 and 320 pixels without page overflow. Desktop EWAF and mobile Overview screenshots were visually inspected.
- No browser JavaScript errors or external requests in these checks. JavaScript syntax, Python source syntax, template rendering and `git diff --check` passed.

Synthetic screenshots and browser fixtures were retained in the temporary directory `santolan-admin-motion-nvc0hti5`. These checks establish local functional behavior in Chrome; they are not a cross-browser performance benchmark or a WCAG conformance evaluation.
