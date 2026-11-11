# Association logo — 27 October 2026

Applied the owner-supplied logo to the shared public header/footer, custom and native Admin workspace sidebar, native Admin sign-in branding, browser tab icon, and Association membership print letterhead. The ordinary administrator sign-in page inherits the public branding. The neighboring Barangay logo on the printed form remains its separate identity.

`static/images/association-logo.jpg` is an exact copy of the supplied image, now located at `Assets/Logo.jpg`. Both files have SHA-256 `8e81adfce0b7adbe12487019d12a763fc1d89e0da31fe96698b7ec4b8e900afc`. No image generation or source-image editing was performed. Shared branding uses a reusable template partial and `static/css/branding.css`, with contained 40–48 px images. Brand-link images have empty alternative text because the adjacent visible association name already supplies the accessible name. The print letterhead retains its descriptive image alternative and existing print sizing.

## Verification

- The existing local `EWAF-testing` website was restarted through its retained development launcher to refresh cached templates. Home returned HTTP 200 and referenced the new image in the header, footer and favicon.
- Chrome/Playwright passed 20 layout checks: Home, ordinary administrator sign-in, native Admin sign-in, custom Admin workspace preview and native Admin workspace preview, each at widths 320, 390, 1200 and 1440 px. Images decoded successfully, retained their contained sizing, and remained within the viewport. Branding text was not clipped, pages had no horizontal overflow, and no JavaScript errors occurred.
- The two workspace previews rendered the current Django base templates with a synthetic, unsaved staff identity and database access blocked. They verify shared Admin presentation; they are not an authenticated workflow test or a change to any account.
- Desktop/mobile Home, native Admin workspace, and mobile native sign-in screenshots were visually inspected. The print change reuses the verified static image and existing letterhead sizing; printed-page visual verification was not rerun.
- Browser checks, screenshots, rendered previews and results are under ignored `.local/logo-qa/`. `git diff --check` passed.

This is a local presentation update. It introduces no business logic, migration, database record change, approval, or EWAF calculation change. No full Django regression suite was needed for this branding change, and no commit or GitHub push was performed.
