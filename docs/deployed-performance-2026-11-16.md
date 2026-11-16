# Deployed performance improvements — November 16, 2026

The owner requested faster loading in the existing deployed system. This change is based on live commit `5f17f608c07eb69a4cf1ec06d56d54c06e04c501` of `deployment/free-render-supabase`, in a separate checkout. The original local development branch and its unfinished changes remain untouched.

## Changes

- Replace the browser Tailwind compiler and external CDN request with locally compiled CSS using the existing pinned Tailwind 3.4.19 dependency. Rebuild with `npm ci` and `npm run build:public` after changing utility classes. The stylesheet preserves the previous configuration and final position in the cascade.
- Use the already available smaller logo, favicon and responsive default hero files. Preserve the original images and the publication editor's custom-artwork override.
- Render smaller WebP previews for published program, event, announcement and annual-observance cards, and published CMS artwork. Card previews fit within 960 pixels; the custom home hero fits within 1600. Detail/download and staff-preview routes retain their original PNG bytes. The renderer serializes decoding and retains at most 32 encoded previews per process, keyed by storage, immutable upload path and size. It never caches an authorization decision. Existing views check publication/token/access before every cache lookup; withdrawn or replaced artwork cannot be retrieved through an old cached authorization. The storage adapter verifies bucket privacy even on a preview cache hit, and existing no-store headers remain.
- Compress dynamic responses with Django's standard GZip middleware and its default random padding. Keep private storage, protected downloads, authentication and no-store behavior.
- Fingerprint and precompress static assets with a strict manifest, allowing long browser caching for files whose URLs change with their content. Omitted vendor source maps are not rewritten; missing real CSS assets still fail collection. OCR and address-data directory prefixes remain stable and their files remain available.
- Build the 2,030 static assets in the Docker image using `config.settings_static_build`, which has no database connection or deployment credentials. Startup checks configuration and the manifest, then starts Gunicorn without recompressing assets. Existing worker/thread counts and hosting plans remain unchanged.
- Load the homepage's seven CMS snapshots in one query. Request profiling on a private loopback copy of the live database reduced homepage queries from 73 to 67. Published results still perform their existing freshness checks.

There are no schema changes, migrations, scoring/selection changes, member messages, live record edits or changes to upload originals. No shared HTML cache or public media path was added.

## Verification before deployment

- 25 focused tests pass on an identity-checked, disposable PostgreSQL database with external network disabled. Coverage includes bulk publication/fallback/withdrawal, cached-image access after withdrawal, bucket-privacy verification on cache hits, draft protection, replacement paths, original-file preservation, static fingerprints/compression/cache headers, missing-file failures, private-media denial, production settings and sanitized error logging.
- A broader historical suite was compared with the unchanged deployed commit. Its 92 failing assertions/subtests across 18 methods also fail on the baseline; these include earlier homepage/anchor and editorial-layout expectations. They are recorded as existing failures, not new passes. An older picture-publication test also requires an approved weight configuration under the enabled feature settings; it is not a release gate for this display-only change.
- Desktop and mobile Chrome checks cover seven public routes, no external compiler, no page errors or horizontal overflow, dark mode and high contrast, event-popup open/close, all ten published event/observance thumbnails, and immutable caching for 29 stylesheets. Both registration forms render under the manifest backend, including OCR and address-data directory references.
- The local preview homepage transferred approximately 0.52 MB versus 6.32 MB on the original live page (about 92% less). The ten event/observance card previews total 681,078 bytes. These are payload measurements; local preview timings are not hosted latency claims.
- Django database/system checks, model/migration drift checks and `git diff --check` pass. Production checks retain only the previously documented HSTS subdomain/preload warnings. Every literal static template reference is in the collected manifest.

Private profiling snapshots, test databases, credentials and rendered verification artifacts are outside the source checkout and are not committed. No Docker daemon was available locally; the Render build verifies the final Linux image and startup.

## Hosting limit

Render Free still spins down after 15 minutes without inbound traffic and can take about a minute to wake. Moving asset work into the build removes application startup work, but does not remove the provider's idle wake-up delay. The Free plan is preserved. Reference: <https://render.com/docs/free#spinning-down-on-idle>.

## Live deployment and measurements

Render deployment `dep-dbtgqem7bikc73ckb2gg` reached `live` on November 16, 2026 at 14:04:46 UTC (22:04:46 Manila), running commit `8b605f95e514ff4c5dd09cf40ccd4e0703ca4f24`. The existing service, Free plan, region, environment, worker settings and manual deployment setting were preserved. The Linux image built and started successfully.

Hosted Chrome measurements use the same seven-route sequence before and after, with a fresh browser context for each desktop/mobile width, without network throttling. Shared assets can be cached after the first route. Decimal MB are used below.

| Desktop route | Before transfer | After transfer | Reduction |
| --- | ---: | ---: | ---: |
| Homepage | 6,320,812 bytes | 517,905 bytes | 91.8% |
| Programs | 3,856,235 bytes | 648,381 bytes | 83.2% |
| Events | 14,513,140 bytes | 968,908 bytes | 93.3% |

On the warm server, the final homepage load-event measurement was 1.68 seconds on desktop and 1.80 seconds on mobile, compared with 2.80 and 2.16 seconds in the original sample. These are individual measurements, not a latency guarantee. The first homepage measurement after the earlier deployment took 11.1 seconds while preview bytes were being generated and other verification requests were running. Preview creation still has a first-request cost after worker restarts, and the hosting wake-up limit above still applies.

Final live checks covered fourteen public page/viewport combinations, dark mode and high-contrast controls, event dialogs, all ten event/observance images and 29 immutable stylesheets on each viewport. No page errors or horizontal overflow were detected. Offscreen lazy images were fetched explicitly by the UI checks. A separate 179-check hosted run covered public pages, registration forms, restricted staff pages, anonymous access denial, no-store responses and fingerprinted static assets. Its temporary verification session was removed in a `finally` block. No application error logs were returned for the post-deploy verification window.

The original working checkout still has its 1,586 pre-existing status entries. Implementation was committed only in the isolated deployment checkout. The temporary local preview server and disposable PostgreSQL cluster were stopped after testing; private evidence remains outside the committed source. This final evidence update is documentation-only and does not require another application deployment.
