# Shared public navigation isolation — 26 October 2026

The owner still observed different navbars on Announcements, Programs, Membership & PWD ID, and Resources & Help, and confirmed the browser address as `http://127.0.0.1:8003/`. Direct GET requests returned the previously corrected source CSS and matching navigation markup. The browser's cached assets and rendered state could not be inspected, so stale browser CSS remains a possible cause rather than a confirmed diagnosis.

The navigation rules now live in `static/css/public-navigation.css`, imported by the public stylesheet. Its selectors use the specificity of `#public-header` to protect the shared dimensions, background, padding, Membership button and arrow from page-specific styles, including earlier cached overrides. A class alternative matches the old shared-header markup still retained by a running development process. The common template now identifies the header explicitly. Desktop menu-toggle hiding is preserved despite the stronger selectors; collapsed-menu sizing and keyboard behavior remain intact.

Versioned URLs force a fresh request for the public stylesheet, imported navigation stylesheet, and the four affected page styles. Receipt styles are versioned too because they previously supplied a separate Membership treatment. The reference remains the owner's Results screenshot: paper background, 96px desktop minimum navbar height, existing logo and link sizing, 1320px maximum container, outlined Membership link and active underline. Mobile uses the same shared 78px minimum across tabs. No business rules, records, migrations, dependencies, startup checks or private workspace styles changed.

Validation performed:

- Two existing Django navigation tests passed with no system-check issues, covering the navigation destinations and all eight public tabs. The existing isolated MySQL launcher used `test_g12_disposable`; artifacts are under `.local/dual-registration-20261024/temp/santolan-g12-tests-b9eey36b/`.
- GET checks passed for all eight tabs on ports 8000 and 8003. Each has one current primary navigation link and identical header markup apart from that marker. Both ports serve the exact new shared CSS bytes and its versioned import. [HTTP checks](http-checks.json)
- The fresh port-8000 process renders `id="public-header"` and the new asset URLs, including all four affected page styles. Port 8003 still renders its cached templates with old URLs; the CSS fallback supports that markup once the stylesheet is refreshed.
- The scoped diff was reviewed and `git diff --check` passed. Actual browser layout, mobile interactions and screenshots were not verified; Chromium previously returned `spawn EPERM`, and no available Computer Use JavaScript session was exposed.

Nine scoped files were installed in the retained local runtime after verifying baseline hashes. Backups and installed hashes are under `.local/public-navbar-isolation-20261026/`. The runtime base template and development banner were preserved.

The existing restart script verified the port-8003 instance and Python process, but Windows denied stopping process 22040 (`Access is denied`). This is an operating-system restriction, not an automatic approval-review rejection. No bypass was attempted. The user must run `Restart System.cmd` to refresh that process's template cache, then reload the browser. The fresh preview at `http://127.0.0.1:8000/` already renders the versioned templates. This report does not claim the owner's browser has visually confirmed the correction.
