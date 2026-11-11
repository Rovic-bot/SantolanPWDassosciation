# Public header image gradients — 9 November 2026

Fixed the photo headers shared by About, Announcements, Events, Programs, Membership, Resources and Results. The image now covers the complete banner, removing the abrupt vertical edge at 25% width. A continuous gradient matches the existing warm cream palette in light mode and charcoal surface in dark mode. The previous flat dark overlay is removed, allowing the right side of the photograph to remain visible.

The same gradient uses a theme-specific surface color. Tablet and phone overlays remain stronger behind the wider text area. Header dimensions, content, uploaded photographs, editor controls and program filters are retained. High-contrast and forced-colors treatments take precedence. CSS asset versions were updated and the verified local web process was refreshed; no database, publication or workflow changes were needed.

Read-only Chrome validation passed 64 header layouts: the seven navigation tabs plus Results, in light and dark modes, at 1440, 768, 390 and 320 pixels. Images loaded, headings remained inside their banners, and no horizontal page overflow or JavaScript errors occurred. Separate high-contrast checks preserved the opaque light backing and dark text; forced-colors checks hid decorative photos. Home's existing header was included in the regression check. Django database checks and `git diff --check` passed.

Desktop light/dark and mobile screenshots were visually inspected. Evidence:

- [Browser results](results.json)
- [Events in dark mode](events-dark-1440.png)
- [Events in light mode](events-light-1440.png)
- [Programs on mobile](programs-dark-390.png)

Only `static/css/public-section-banners.css`, the header theme rule in `static/css/public-dark.css`, and the two stylesheet versions in `templates/public/base.html` were changed for this request. Existing unfinished changes are preserved.
