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

Hosted activation and verification will be recorded after the release is live.
