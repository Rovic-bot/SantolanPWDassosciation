# Smooth dark-mode transitions — November 17, 2026

The owner requested a smooth animation when enabling or disabling dark mode on the deployed system. Public pages, the custom Admin workspace and native Django Administration now share a stationary 360 ms fade between palettes, including gradient backgrounds. Browsers without the View Transition API use a 320 ms color transition. The existing theme keys and separate public/Admin preferences are retained.

Initial saved-theme restoration remains immediate. Both the device's reduced-motion setting and the Display panel's Reduce motion option bypass the animation. A superseding toggle, hidden tab or workspace replacement settles and cleans up the temporary transition. Existing page-navigation animations resume after the theme change. No models, database fields, migrations, records, business rules or permissions changed.

## Validation before deployment

- JavaScript syntax checks passed for all three affected scripts. `scripts/current_development.py check` reported no issues. `git -c core.safecrlf=false diff --check` passed.
- Current release templates rendered for custom and native Admin previews with database access explicitly blocked.
- 43 read-only Chrome/Playwright checks passed. Home and Membership were checked at 1440 and 390 px, custom Admin previews at both widths, and native Administration at 1440 px. Checks covered the actual fade duration, keyboard activation/focus, both directions, saved preference restoration, reset, reduced motion, rapid toggles, changing motion during an animation, high contrast, the older-browser fallback, unavailable storage, and input preservation. No horizontal overflow, JavaScript errors, unhandled promises or write requests occurred.
- Public previews used the deployed HTML with only the theme asset wiring substituted; candidate assets came from an isolated checkout of the deployment branch. Admin previews used fictional content rendered through that checkout's real base templates. This was not an authenticated production Admin test.
- Screenshots were inspected. [Browser results](preview/checks.json), [mobile public display](preview/home-390-dark.png), [desktop Admin preview](preview/theme_admin-1440-dark.png).

## Release scope

The isolated release is based on `3ad739ef57162b206bd1c044d37ffa306a3b0488` of `Rovic-bot/SantolanPWDassosciation`, branch `deployment/free-render-supabase`. That head differs from running commit `a7fd90017c67176ee76292743c25f82682fe1665` only by the prior address-dropdown validation note. Deployment-specific template content and all unfinished local work are preserved. Seven source files change: the new shared CSS/JavaScript, the existing public/Admin theme handlers, and the three base templates with updated asset versions.

## Hosted activation

Commit `d63370ba6919df37e9c388cce6d4800e6167d630` was deployed through the existing Render service. Deploy `dep-dbu16ton74is73f4j860` reached **live** on November 17, 2026 at **08:43:49 UTC / 4:43:49 PM Philippine time**.

29 browser checks passed against the actual [hosted system](https://santolan-pwd-system.onrender.com/), with no substituted page HTML or assets. They cover Home and Membership at 1440 and 390 px, both toggle directions, keyboard focus, persistence, reset, reduced motion, rapid toggles, high contrast, the fallback and unavailable storage. A captured intermediate animation frame confirmed actual blending, and the public page's navigation-animation name was restored after completion. The fallback duration was sampled synchronously during the change event to avoid reading after its short cleanup timer had already finished.

All four served changed assets, including the Admin theme handler, matched the release's exact Git bytes at their content-hashed URLs. `/healthz/` returned HTTP 200 with `status: ok`. There were no JavaScript errors, unhandled promises or write requests. Render's application error-log query returned no entries from activation through **08:46:34 UTC**. Hosted screenshots were visually inspected. Authenticated production Admin actions were not exercised; its templates and interactions were verified through the database-blocked previews above.

- [Hosted browser results](hosted/checks.json)
- [Deployment and asset verification](hosted/release.json)
- [Before the fade](hosted/fade-before.png), [intermediate frame](hosted/fade-midpoint.png), [after the fade](hosted/fade-after.png)
- [Hosted mobile display](hosted/home-390-dark.png)
