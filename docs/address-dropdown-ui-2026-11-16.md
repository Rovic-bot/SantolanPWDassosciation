# Address dropdown UI — November 16, 2026

The owner requested a deployed UI fix for address suggestions across Association and PDAO registration, online and onsite. The release starts from `e90cbf6` on `deployment/free-render-supabase`; the running application baseline is `8b605f9`. Work is isolated from the original development checkout and preserves the earlier performance improvements.

## Behavior

- Replace browser-native datalists with a shared searchable combobox for city/municipality, barangay, region and province where present. Existing labelled inputs and submitted field values remain intact.
- Use opaque menus matching the public and staff light/dark/high-contrast palettes, readable wrapped place names, and 44-pixel selection targets. Menus align to their inputs, open above or below according to available space, and follow scrolling and viewport changes. The top layer avoids clipped form cards and sticky panels, with a fixed-position fallback for browsers without the Popover API.
- Filter locally as the user types, including multiword/diacritic-insensitive searches and province-qualified repeated city names. Long lists show up to 50 matches with a prompt to refine the search. Keyboard arrows navigate, Enter accepts the highlighted option, Escape dismisses, and Tab keeps typed text. Pointer/touch selection leaves focus in the input.
- Retain existing city-to-region/province autofill, barangay loading and relationship validation. Loading, empty results and failed downloads have explicit messages; manual input and server validation remain available. Workspace navigation removes the popup elements and listeners.

The pinned geographic catalogue, address rules, house/street and ZIP inputs, personal-data requirements, OCR, consent, submission/review workflows and historical records are unchanged. There are no model changes, migrations, application submissions or email sends. No applicant address is sent to a third-party lookup service.

## Verification

- **17 database-free Django tests passed**, covering the existing four intake contracts, geographic validity, age/conditional rules, retained historical contracts, and rendering all four actual templates.
- **36 dropdown browser scenarios passed**: four forms × three widths (1440, 390 and 320 pixels) × light/dark/high contrast. They exercise every address menu, viewport bounds, keyboard/touch selection, duplicate-city disambiguation, autofill, barangay clearing/loading, scrolling long lists, Escape/Tab, empty matches, a short mobile viewport and workspace cleanup. No JavaScript errors or application POSTs occurred.
- **Six existing browser regression scenarios passed**, covering all four forms, address relationships, mobile/date/conditional fields, unavailable catalogue downloads and no-JavaScript fallback.
- JavaScript syntax, manifest static collection and `git diff --check` pass. The deploy rebuilds fingerprinted assets so browsers receive the new CSS and JavaScript.

Synthetic screenshots: [public desktop](address-dropdown-ui-2026-11-16/public-desktop.png), [public mobile dark](address-dropdown-ui-2026-11-16/public-mobile-dark.png), [onsite PDAO](address-dropdown-ui-2026-11-16/onsite-pdao.png). These contain empty/fictional forms, not applicant records.

Reproduce with `scripts/registration_validation_checks.py` and `OCR_ARTIFACT_DIR` set to a private fixture folder, then `scripts/address_dropdown_browser.cjs` and `scripts/registration_validation_browser.cjs` with `INTAKE_FIXTURES` pointing to that folder and `INTAKE_ARTIFACT_DIR` set to a private output folder. `INTAKE_URL` targets hosted public forms; optional private `INTAKE_STORAGE_STATE` enables the two staff routes. The browser harness blocks all non-GET/HEAD requests.

Keyboard semantics follow the [WAI-ARIA combobox pattern](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/). Browser checks use Chrome; they do not claim certification across all assistive technologies or physical phones.

## Deployment

The final live commit and hosted verification are recorded after Render activation. No hosting-plan or environment change is needed.
