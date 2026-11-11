# Application completion scrolling — November 8, 2026

Application completion now shows the first five complete program rows, including wrapped labels, and scrolls vertically to the remaining programs. Lists of five or fewer retain their natural height. The existing scroll cue, keyboard-focusable chart viewport and View data control remain available. Program order, counts and completion percentages are unchanged.

Read-only synthetic browser checks passed for 3, 5 and 8 programs at 1920, 1440, 768, 390 and 320 px. Exactly the first five bars were fully visible for longer lists; the final program remained reachable. Keyboard scrolling, a long fifth label and 200% text were checked. No JavaScript errors or page overflow occurred. The dashboard packing helper was enabled during checks.

JavaScript syntax and `git diff --check` passed. The desktop screenshot was inspected. Evidence: `results.json`, `completion-1440.png`, `completion-390.png`. Versioned assets were updated and the development server restarted. No application records or schema changed.
