# Claimed PDAO ID to Association membership

## Behavior

The owner requested an optional Association membership application after a PDAO applicant has actually received their PWD ID. The separate membership application must reuse recorded identity information and collect its remaining requirements.

In the private PDAO application page:

1. Authorized staff open an application already forwarded to PDAO.
2. After actual collection, staff enter the issued PWD ID and confirm that the applicant or representative received it.
3. **Start Association Membership** opens the existing onsite membership form with recorded details filled in.
4. Staff complete missing fields and confirm the applicant wants membership and agrees to reuse the details.
5. Saving creates one pending Association intake. The normal membership review, PRPWD procedure and final decision remain required.

The ready-for-collection email does not establish collection. Existing forwarded records are not automatically marked claimed. The optional membership button requires both PDAO record access and Association intake encoding permissions. Reopening a completed transfer opens its existing membership application.

## Information carried over

Name (including an optional suffix), date of birth, the actual issued PWD ID, equivalent address/contact fields, sex/gender, compatible civil/employment values and PhilHealth number are copied from the retained PDAO record. Only exact education equivalents are copied; PDAO College does not establish graduation.

The shared membership form now requires **type of disability** and an explicit **4Ps Yes/No** answer for both public and staff submissions. There is no default 4Ps answer. Household income/size and other missing membership information still require completion.

Disability mappings:

| PDAO | Association |
| --- | --- |
| Deaf / Hard of Hearing | Hearing |
| Intellectual Disability | Intellectual |
| Learning Disability | Learning and Behavioral |
| Mental Disability | Mental Disability |
| Physical Disability | Physical / Orthopedic |
| Psychosocial Disability | Psychosocial |
| Speech / Language Impairment | Speech |
| Visual Disability | Visual Disability |
| Cancer (RA 11215) | Cancer (R.A. 11215) |
| Rare Disease (RA 10747) | Rare Disease (R.A. 10747) |

One recorded mapped disability is filled in automatically. For multiple recorded types, the existing single-type membership form requires a choice from those mapped types. The PDAO submission retains every original classification. No unrecorded classification is inferred.

## Integrity and privacy

- New migration: membership.0016_pdao_claim_membership.
- PDAOIDClaim records actual collection and a one-time link to a pending RegistrationIntake. It does not directly create a Member.
- A protected unique link, row locking, session-bound submission contexts and idempotent retries prevent duplicate applications from the same PDAO record.
- Recorded fields are supplied again by the server when saving; edited browser values cannot replace them. Later authorized membership corrections remain versioned through the existing review workflow.
- Both collection and membership transfer append processing audit events. PDAO original data and review revisions remain intact.
- Audit or permission failure rolls back the complete transfer and cleans up newly uploaded private files.
- The new production table uses RLS with the existing django_server_only policy for santolan_app. Neither anon nor authenticated has table SELECT access.
- Claiming an ID invalidates a queued readiness notice through the existing version guard. New readiness notices cannot be requested for a claimed ID.

## Validation

- Thirteen feature tests passed across the acceptance and PostgreSQL policy runs: all ten disability mappings, required fields, explicit consent, actual-claim gate, server-owned prefill, suffix preservation, permissions, CSRF/session binding, audit rollback/file cleanup, immutable claim identity, complete-link constraint, repeat submission and simultaneous submission.
- Existing PDAO notice, Association alignment and PDF registration suites were exercised. The initial combined run passed 44 of 45 tests.
- The remaining assertion expects the retired data-dashboard-theme-toggle control. The identical failure was reproduced in an unchanged f4f66c7 checkout; it is unrelated to this feature.
- A real Chrome/Playwright flow passed at desktop and mobile widths: claim ID, open membership form, inspect carried fields, answer 4Ps, complete household information/consent, review and save. The review dialog displays disabled carried fields correctly. Screenshots were visually checked after suppressing capture-time animations.
- Fresh disposable PostgreSQL databases and fictional applicants were used. No production applicants were submitted, claimed, approved or emailed for testing.
- Production checks found no missing model migrations. The deployment retains its previously documented HSTS subdomain/preload warnings.

## Database rollout

A fresh custom-format PostgreSQL backup and a private object archive containing 31 objects were verified before migration. Backup files and credentials remain in the ignored local operator directory.

The reviewed plan contained only membership.0016_pdao_claim_membership. It was applied through the existing trusted Django migration environment with verified TLS. Post-migration inspection confirmed the migration entry, an empty claim table, the migration role as owner, RLS, runtime-role access and no anon/authenticated SELECT access. Supabase's security advisor returned no notices.

The existing Render service uses manual deployment from deployment/free-render-supabase. Preserve the additive table if rolling application code back; do not erase claimed-ID or linked-application history.
