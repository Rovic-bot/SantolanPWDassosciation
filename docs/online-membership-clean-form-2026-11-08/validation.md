# Online membership application layout — 2026-11-08

The owner requested a cleaner Association online application matching the supplied two-panel reference. `/membership/registration/apply/` now uses a compact guidance sidebar and one rounded form panel. The seven existing sections use thin dividers, small uppercase labels, light fields and consistent spacing. Fields are arranged in two columns on wider screens and one column on phones.

The change is confined to the Association application template and its new, scoped `public-membership-application.css`. Existing fields, requirements, policy content, privacy acknowledgement, uploads and submission behavior are preserved. No business logic, schema or stored application data changed. The separate PDAO application does not load this stylesheet.

Validation completed against the local development system:

- Django system check: no issues.
- Headless Chrome: 1440, 1024, 768, 390 and 320 px widths; no horizontal overflow or controls extending outside the form. Seven sections remain available at every size.
- Privacy notice: automatic opening, keyboard containment, Escape, focus restoration, reopening and entered-value preservation passed. Acknowledgement remains unchecked until explicitly selected.
- All seven directory links reach their section. Required-field validity and visible keyboard focus are retained.
- 200% root text size and high-contrast mode fit at desktop, 390 and 320 px widths.
- With JavaScript disabled, the form, inline privacy notice and native section directory remain available.
- No JavaScript errors. The browser harness blocked all POST requests; none were attempted. Actual submission was not retested for this presentation-only change.
- `git diff --check` passed (existing line-ending warnings only).

Evidence: `browser-results.json`, `form-1440.png` and `form-390.png`. Screenshots show existing demonstration policy copy, with blank application fields.
