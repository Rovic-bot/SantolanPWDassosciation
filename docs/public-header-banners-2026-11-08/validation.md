# Public photo headers — November 8, 2026

Implemented the owner's reference for rounded photo headers with a soft fade behind readable headings. About, Announcements, Events, Programs, Membership and Resources now share the photo-banner treatment. The shared Results page inherits it as well. Home retains its existing rounded image hero and editable background.

The banners use existing public community photographs. Each section's existing `hero_picture` field controls its image through Content Management; its editable title and introduction remain connected. Program period filters remain within the banner and keep their in-place navigation. The previous separate About photo panel is replaced by the shared background/fade treatment. Mobile layouts strengthen the overlay and allow titles to wrap without clipping; high-contrast and forced-colors styles preserve readable copy.

No stored content, publication permissions, program records or database schema changed. Public image changes still use the existing authorized content editor publication workflow.

Validation:

- `node scripts/public_header_banners_qa.cjs` passed 28 public layout checks: all seven navigation tabs at 1440, 768, 390 and 320 px. Images loaded, headings stayed within their banners and pages had no horizontal overflow.
- Confirmed program filtering preserves the current document and reloads the banner image successfully.
- Opened each of the six section image controls in the actual admin preview and confirmed titles remained editable. No content was saved or published during browser checks.
- Inspected desktop and mobile screenshots in this directory. Browser output is in `results.json`; no page errors were observed.
- Django configuration check, JavaScript syntax and whitespace checks passed.
- All nine `core.tests.test_portal_editor` tests passed using the isolated disposable MySQL runner, covering public rendering, private drafts, publication, permissions, images, stale saves and revision rollback.

The local development server at port 8013 was restarted with the new templates and stylesheet.
