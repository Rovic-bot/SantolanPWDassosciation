# Deployed performance improvements — November 16, 2026

The owner requested faster loading in the existing deployed system. This change is based on live commit `5f17f608c07eb69a4cf1ec06d56d54c06e04c501` of `deployment/free-render-supabase`, in a separate checkout. The original local development branch and its unfinished changes remain untouched.

## Changes

- Replace the browser Tailwind compiler and external CDN request with locally compiled CSS using the existing pinned Tailwind 3.4.19 dependency. Rebuild with `npm ci` and `npm run build:public` after changing utility classes. The stylesheet preserves the previous configuration and final position in the cascade.
- Use the already available smaller logo, favicon and responsive default hero files. Preserve the original images and the publication editor's custom-artwork override.
- Render smaller WebP previews for published program, event, announcement and annual-observance cards, and published CMS artwork. Card previews fit within 960 pixels; the custom home hero fits within 1600. Detail/download and staff-preview routes retain their original PNG bytes. The renderer serializes decoding and retains at most 32 encoded previews per process, keyed by storage, immutable upload path and size. It never caches an authorization decision. Existing views check publication/token/access before every cache lookup; withdrawn or replaced artwork cannot be retrieved through an old cached authorization. Existing no-store headers remain.
- Compress dynamic responses with Django's standard GZip middleware and its default random padding. Keep private storage, protected downloads, authentication and no-store behavior.
- Fingerprint and precompress static assets with a strict manifest, allowing long browser caching for files whose URLs change with their content. Omitted vendor source maps are not rewritten; missing real CSS assets still fail collection. OCR and address-data directory prefixes remain stable and their files remain available.
- Build the 2,030 static assets in the Docker image using `config.settings_static_build`, which has no database connection or deployment credentials. Startup checks configuration and the manifest, then starts Gunicorn without recompressing assets. Existing worker/thread counts and hosting plans remain unchanged.
- Load the homepage's seven CMS snapshots in one query. Request profiling on a private loopback copy of the live database reduced homepage queries from 73 to 67. Published results still perform their existing freshness checks.

There are no schema changes, migrations, scoring/selection changes, member messages, live record edits or changes to upload originals. No shared HTML cache or public media path was added.

## Verification before deployment

- 24 focused tests pass on an identity-checked, disposable PostgreSQL database with external network disabled. Coverage includes bulk publication/fallback/withdrawal, cached-image access after withdrawal, draft protection, replacement paths, original-file preservation, static fingerprints/compression/cache headers, missing-file failures, private-media denial, production settings and sanitized error logging.
- A broader historical suite was compared with the unchanged deployed commit. Its 92 failing assertions/subtests across 18 methods also fail on the baseline; these include earlier homepage/anchor and editorial-layout expectations. They are recorded as existing failures, not new passes. An older picture-publication test also requires an approved weight configuration under the enabled feature settings; it is not a release gate for this display-only change.
- Desktop and mobile Chrome checks cover seven public routes, no external compiler, no page errors or horizontal overflow, dark mode and high contrast, event-popup open/close, all ten published event/observance thumbnails, and immutable caching for 29 stylesheets. Both registration forms render under the manifest backend, including OCR and address-data directory references.
- The local preview homepage transferred approximately 0.52 MB versus 6.32 MB on the original live page (about 92% less). The ten event/observance card previews total 681,078 bytes. These are payload measurements; local preview timings are not hosted latency claims.
- Django database/system checks, model/migration drift checks and `git diff --check` pass. Production checks retain only the previously documented HSTS subdomain/preload warnings. Every literal static template reference is in the collected manifest.

Private profiling snapshots, test databases, credentials and rendered verification artifacts are outside the source checkout and are not committed. No Docker daemon was available locally; the Render build verifies the final Linux image and startup.

## Hosting limit

Render Free still spins down after 15 minutes without inbound traffic and can take about a minute to wake. Moving asset work into the build removes application startup work, but does not remove the provider's idle wake-up delay. The Free plan is preserved. Reference: <https://render.com/docs/free#spinning-down-on-idle>.

The exact live commit, deployment result and hosted measurements are recorded after deployment verification.
