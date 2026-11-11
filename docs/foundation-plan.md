# Foundation milestone (0–10%)

> [!warning] OUTDATED / HISTORICAL milestone plan — marked 2026-10-06
> This entire plan describes the original foundation scope and unresolved choices at that time; it is not a current instruction to restart the project or replace the user model. Current authority is [CURRENT_SYSTEM_SPECIFICATION](../../CURRENT_SYSTEM_SPECIFICATION.md). Preserve useful stack/testing/private-storage conventions, use Admin-only access and the current workflow/acceptance notes, and make no application/source/database changes in this documentation task.

Authority: the vault's Guide for Development, sections 10–12, 48–53, 60–66, and the authorized ten-milestone roadmap.

## Scope and acceptance

- Django configuration uses environment secrets and MySQL, with separate disposable test storage.
- Domain apps remain shells; no member accounts, workflow statuses, or EWAF values are introduced.
- A responsive Bootstrap public homepage establishes the community/blog design. Unavailable sections have honest empty states.
- A shared admin layout and dashboard require active staff access. Django admin enforces model permissions.
- Built-in auth, admin, content types, and session migrations run successfully.
- Tests cover anonymous/nonstaff/inactive access, CSRF, logout, password hashing, host validation, private media, static assets, and real MySQL.
- Local server and assets respond successfully; desktop/mobile layouts are inspected.
- Setup/run instructions and milestone evidence are recorded before marking completion.

## Implementation boundaries

Affected code: config, core views/URLs/tests, templates, static CSS/Bootstrap, scripts, and documentation. No custom database fields or domain migrations are needed.

Full RBAC/public portal workflows follow in milestone 20%; membership and publishing modules follow their authorized sequence. Resolve the custom User choice before domain relationships. XAMPP is left intact; a project-local native MySQL instance is used if XAMPP's database is incompatible.
