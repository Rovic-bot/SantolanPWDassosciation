# Event categories and participation — 24 October 2026

## Owner-approved scope

The owner requested General Events (open to everyone, subject to the organizer's published participation rules), Specific Events (focused on a disability group or observance), and separate Target Audience and Who May Participate fields. The owner also explicitly confirmed inclusion of scheduled Association activities, such as meetings and community gatherings.

Authorized staff can create scheduled General or Specific Events using the existing event editor, dates, venue, publication permissions, and audit history. The annual observance calendar remains available under Specific Events. Its existing disability/health classification is retained as **Observance subject**, separate from the public event categories.

## Behavior

- Public Events has All, General, and Specific category views. Scheduled activities have Upcoming/Ongoing and Past filters with pagination. Cancelled events retain explicit notices. Annual observances retain their January–December calendar and official source links.
- Target Audience describes the focus. Who May Participate records the organizer's actual participation instructions. A Specific event may explicitly welcome everyone; its focus never automatically limits participants to one disability classification.
- Both fields appear independently in admin forms, review previews, public cards, and public details. Annual observances now have a dedicated public detail route with an explicit field allowlist. Observance references remain private starting material and are never automatically published.
- Scheduled event category and both audience fields are required before publication. Annual observances require both audience fields before publication. Incomplete drafts can be saved; attempting to publish shows a validation message and leaves the draft/history unchanged.
- The event editor's existing permission and optimistic version checks remain. General/Specific activities are reachable from the existing Events workspace; no extra sidebar group or permission grants were added. Staff with scheduled-event permissions can reach that workspace without receiving observance permissions.
- This request changes public descriptions and staff event authoring. It does not enable public RSVP, create member accounts, change verified-member program applications, or alter attendance rules. Protected linked-program audience descriptions cannot be silently changed. Existing canonical term schemas/digests, scoring, selection, and actual assistance controls are preserved.

## Historical data and migration

Migration `events.0007_event_participation_details` adds an optional category and the two text fields to scheduled Event records, plus the two fields to AnnualObservance and its immutable revision snapshots. New fields on existing records start empty. Existing scheduled activities are not newly listed until their category and audience details are explicitly supplied and reviewed. Existing published observances remain visible as observances, with clear messages where audience or participation information has not been published. No organizer rules, participants, schedules, or target groups were guessed.

Before applying the single allowed migration, the identified fictional database was backed up (60,278,779 bytes). Fingerprints confirmed all **81,327 original rows and existing column values across 110 tables** were preserved. All prior attendance, application, CMS, announcement, observance, and audit data remained intact. Existing observance revision columns were not rewritten.

Exactly 26 scoped runtime files were updated and checked by hash, including the publication-validation correction. Private backups and detailed fingerprints remain under `.local/event-participation-20261024/`. Unrelated runtime files and unfinished source changes were preserved. No content was created or published in the running workspace during validation.

## Checks

- **105 source tests passed** for scheduled Events, observance access/workflow/concurrency, category and participation behavior, public navigation, and workspace navigation.
- **68 runtime tests passed** for observance workflow/concurrency, participation behavior, and the runtime-only verified program intake integration.
- An additional **8 source participation tests passed** after adding an HTTP regression for missing publication fields and correcting how the publication form displays those errors. The same **8 tests passed in the final runtime**; evidence is recorded in `runtime-publication-validation-tests.log`.
- Disposable MySQL databases were used for all tests. The source migration check found no missing migrations. The running workspace applied only the new Events migration and passed database/configuration and migration checks.
- Live HTTP checks passed for all category views, annual detail pages, separate fields, scheduled/observance admin forms, Upcoming/Past controls, and existing Home, About, Announcements, and Programs pages. No new event publication or public RSVP was performed.
- Python syntax, runtime hashes, and `git diff --check` passed. Browser visual inspection was not performed.

Evidence is saved alongside this note: source/runtime test logs, `migration-check.log`, `http-checks.json`, and `preservation-summary.json`.

Running page: `http://127.0.0.1:8003/events/`.
