# Public navigation and Home information — 2026-10-07

The owner requested exactly **Home, About, Announcements, Events, Programs, Membership** in the public navigation, with all other public information on Home. This follow-up implements that layout without changing membership, verification, eligibility or selection policy.

## Delivered behavior

- Shared desktop/mobile navigation has the six requested destinations in order, with one current-page indicator. Detail/application routes retain their parent navigation context.
- Home has labeled sections for application/reference guidance, Contact / Help Desk, FAQs, EWAF explanation, privacy and accessibility help. Jump links below the hero and footer help links make them directly reachable. Native section targets accept keyboard focus and clear the sticky header.
- These sections use the existing published CMS snapshots or safe defaults. Admin Content Management explains where each topic appears. Drafts and withdrawn content are not displayed, and content remains escaped.
- Existing support-page URLs return HTTP 302 to their Home anchors, preserving bookmarks and existing application/help links. About and Membership remain separate pages. Application forms remain attached to the selected program/event.
- Fixed observed Home overflow at 320 px with 200% text enlargement: reading grids and actions can shrink, and long text wraps. Public CSS changes do not alter Admin workspace CSS or its scroll-persistence script.
- Footer exposes Help Desk, Privacy and Accessibility links directly to Home. Display controls remain available throughout the public experience.

## Verification

`manage.py test core scripts.public_navigation_browser_qa scripts.announcements_members_browser_qa --noinput`: **32 tests passed in 23.511 seconds** on disposable MySQL, including headless Chrome.

The public browser check visited all six main pages at 320, 390, 768, 1024 and 1440 px, checked exact menu order/current state, mobile Escape/focus behavior, all six Home anchors and unobscured focused targets, the privacy redirect, 200% text with high contrast at 320 px, and support-content visibility with JavaScript disabled. Both browser harnesses reported zero JavaScript errors. The Admin regression verified one Members entry, internal onsite/review navigation, sidebar scroll persistence on desktop/mobile and authorized masked result publication using synthetic data.

CMS tests cover published snapshots while newer drafts exist, withdrawal fallback, escaping, permissions and audit history. Compatibility routes preserve GET/HEAD and reject POST. Django database/system checks passed; migration detection reported no changes; `git diff --check` passed (existing line-ending warnings only). The vault audit checked 54 Markdown notes and 860 local/wiki links with no broken links or unbalanced code fences.

An initial harness assertion needed whitespace normalization for the Membership arrow; a subsequent enlarged-text check exposed actual overflow, which was corrected before the final pass. Private logs are in the vault's `.local/public-ui-20261007/`; browser images are in the application's `.local/qa-public-navigation/`. Desktop Home and mobile privacy screenshots were visually inspected. Existing announcement/Admin regression screenshots were regenerated.

These are scoped UI and workflow regression checks, not a full-system production audit or WCAG certification. Controlled EWAF remains unfinished and its publication gate remains enforced. No new completion percentage is claimed. No application data, real organizational content or results were published by this task; no migration, deployment, commit or push was performed.

## Changed files

- `core/context_processors.py`, `core/views.py`: six public destinations, Home CMS context and compatibility redirects.
- `templates/public/home.html`, `templates/public/base.html`: Home guidance, accessible anchor links and footer.
- `templates/content/list.html`: Admin content-location guidance.
- `static/css/public.css`: responsive support sections and enlarged-text reflow.
- `core/tests/test_public_portal.py`, `core/tests/test_content.py`: navigation, redirects and CMS regression coverage.
- `scripts/public_navigation_browser_qa.py`, `scripts/public_navigation_browser_qa.cjs`: new synthetic browser acceptance harness.
- Vault notes: `CURRENT_SYSTEM_SPECIFICATION.md`, `Guide for Development.md`, `UI_Design_Guide_For_Codex.md`, `01 - Requirements/Functional Requirements and Use Cases.md`, `05 - Development/API and Workflow Contracts.md`, `11 - Defense/Formal User Manual.md`, `DOCUMENTATION_CHANGELOG.md`.
- This validation record.

Fifteen existing source/documentation files were byte-verified in the private `before.zip` before editing. Older manual sections remain explicitly historical. Existing unrelated dirty work was preserved. No additional business-policy clarification was needed for this layout request.
