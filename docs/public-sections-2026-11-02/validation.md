# Public section layouts · November 2, 2026

The seven navigation destinations share the homepage palette and navigation. The new section templates and stylesheet cover About, Announcements, Events, Programs, Results, Membership & PWD ID, and Resources & Help. The change does not alter views, data queries, publication rules, permissions, or submission workflows.

Local browser checks on the retained development site (port 8013):

- Each destination returned 200, exposed one main heading and one current navigation link, and fit the viewport at 320, 390, 768, 1024 and 1440 CSS pixels. The mobile menu opened and closed with Escape.
- Announcement search, category filters, program search and clearing filters, and the past-event filter returned the requested view. Search text in the program catalog cleared its leading icon.
- A direct link to PDAO requirements opened the correct service. Keyboard service switching and the Association checklist worked. With JavaScript disabled, both service guides and the public navigation remained available.
- The About disclosure, Resources FAQ and display preferences responded. All seven tabs fit a 320px viewport with the largest text and high contrast enabled. These checks did not include a screen-reader audit.
- Django system checks and Git whitespace checks passed.

[About at 1440px](about-desktop.png) · [Membership at 390px](membership-mobile.png)
