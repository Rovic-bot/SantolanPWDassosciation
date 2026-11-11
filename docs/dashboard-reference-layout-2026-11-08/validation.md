# Dashboard reference layout — November 8, 2026

The owner supplied a dashboard reference with four headline cards, a wide Membership growth chart beside a smaller breakdown, and paired charts below. The dashboard now uses this arrangement instead of masonry packing. The lead row uses a 2:1 split on large desktops, a 7:5 split on smaller desktops, and equal columns on tablets; phones stack cards. Other chart cards remain paired, with the existing detailed eligibility and calendar charts spanning the row.

The disability doughnut retains every recorded category and uses a compact legend with counts and member-based percentages. Application completion continues to display five complete programs before scrolling. Existing metric definitions, source values, permissions and all twelve charts are preserved; the reference's demonstration categories and numbers were not copied into application data.

Read-only synthetic browser verification passed at 1920, 1440, 1024, 768, 390 and 320 px. Checks covered lead-row proportions, paired rows, all twelve cards, all seven sample disability categories, unclipped SVG text, no page overflow, 200% text and the data dialog. Existing disability-chart checks passed for dark/light themes, full catalog, overlap, empty/single categories and forced colors. Completion-scroll checks passed for 3, 5 and 8 programs, long labels, keyboard scrolling and mobile sizes. JavaScript syntax and `git diff --check` passed.

Screenshots contain synthetic fixtures. The development server was restarted with versioned assets. The prior packing helper is retired; the layout works with CSS, including without JavaScript. No database or business-rule changes were made.
