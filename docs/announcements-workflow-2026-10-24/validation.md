# Announcements workflow validation — 24 October 2026

## Authorized scope

Later amendment: the owner's October 25 instruction adds public applicant/selected-member tables with full program references and a unified result workflow. See [checked approval and participation validation](../membership-announcement-workflow-2026-10-25/validation.md). The evidence below describes the earlier implementation and retained historical revisions.

Implemented the owner's Announcements workflow narrative: General, Programs, and Program Results; responsible source/office and publication dates; program filters; canonical program/result destinations; and authorized creation, review, approval, and publication through Announcements & CMS. The repeated narrative was treated as one request.

This implementation preserves the existing result authorization, source freshness, immutable revision history, masking, selection, and actual-release controls. It does not authorize new result disclosures or change eligibility/EWAF rules.

## Implemented behavior

- Public Announcements has the three category views plus an aggregate view. General notices show their responsible office and publication date. New General/Programs drafts require an explicit source; publication validates it again. Historical notices with no recorded source display **Source not recorded** until an administrator supplies it. No historical attribution was invented or backfilled.
- Programs notices link to a published, available/upcoming program. Their public title and overview come from that program's current record; manually copied titles, descriptions, and poster images are not used for this category. The existing `assistance_type` supplies the program-category filter. Disability filters follow the canonical eligibility classifications and include programs without a disability restriction. Filter choices are drawn from currently published notices. Private, withdrawn, cancelled, future-publication, and registration-ended programs are withheld from announcement previews. The canonical Programs page continues to enforce membership, availability, and eligibility checks.
- Program Results notices remain generated and published through the existing protected result services. Public notices now contain an overview and link to Results, with no member rows or references in their template context. Results retains the approved privacy-protected outcomes and selection explanation. Existing assistance-recipient publication remains available and distinct from selection publication.
- Home uses the same public preview projection. All public routes retain the publication gate, escaping, and no-store responses. Announcement images remain permission/publication checked.
- Admin has category filtering, source search, program selection, and an explicit **Prepare program results** action. Saving an edited notice returns it to a private draft; an authorized publisher must review and confirm publication again. Existing optimistic version checks, separate permissions, CSRF protection, and transactional audit rollback remain enforced.

## Schema and preservation

Migration `announcements.0005_announcement_categories` adds `source_office`, an optional protected `linked_program` relation for program previews, and a constraint preventing simultaneous preview and result links. Categories are derived from their relationships; the existing result-specific `program` relation is unchanged.

Before applying it, the identified fictional development database was backed up (60,266,423 bytes). Post-migration fingerprints confirmed that **all 81,321 original rows and column values across 110 tables were preserved**. Only the new migration-history entry was added. No announcement was automatically approved, published, rewritten, or reattributed.

Exactly 17 scoped runtime files were updated after before/staged hash verification. Unrelated runtime modules and the runtime's pre-existing Home differences were preserved. The source workspace's unrelated unfinished changes remain untouched. Backup, file manifests, and detailed fingerprints remain private under `.local/announcements-workflow-20261024/`.

## Validation evidence

- **65 source tests passed**, covering Announcements and public navigation, using fresh disposable MySQL. Includes canonical previews, filters, legacy source handling, permission boundaries, forged categories, stale edits, approval confirmation, source invalidation, privacy, image controls, audit rollback, and existing concurrent result publication.
- **97 runtime tests passed**, covering Announcements and the runtime-only program intake integration, also using fresh disposable MySQL with real migrations. No application data was used as a test database.
- `makemigrations --check --dry-run`: no changes detected in source or runtime. Runtime `check --database default`: no issues. `git diff --check`: passed.
- Live HTTP checks at `http://127.0.0.1:8003/` passed for category pages, available filters, published notice details, result links, Home, Results, and authenticated admin forms. Three existing authorized result notices were visible. The Programs category correctly remains empty until an authorized administrator creates and publishes a linked notice. HTTP checks did not create or publish content.
- Browser visual inspection was not performed; validation used rendered-template assertions and live HTTP checks.

Evidence: `source-tests.log`, `runtime-tests.log`, `source-migration-check.log`, `http-checks.json`, and `preservation-summary.json`.

The updated development server is running on port 8003. The existing **Start System.cmd** launcher opens that same local workspace.
