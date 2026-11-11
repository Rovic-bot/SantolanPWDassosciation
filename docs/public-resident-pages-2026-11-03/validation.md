# Resident pages · November 3, 2026

The resident template family builds on the public section palette, navigation, typography and focus styling. Published detail views pair content with schedules or next steps. Long membership and PDAO forms present a directory linked to real fieldsets. Verification, application progress, assistance requests, receipts and unavailable states have task-specific panels. Screen-only styling preserves the official print layouts. Existing public landing tabs remain the entry points.

Public and staff routes share a few templates. The navigation context supplies a resident parent for these templates only on named public endpoints. Staff sign-in, review and print pages retain their previous parent. No changes to form validation, access grants, publishing, storage or service flags. Existing redirect, binary and retired endpoints retain their response contracts.

- **Live check:** 11 destinations at 1440px and 320px on port 8013: program detail and verification, announcement, result, event, tracking, Association membership form, PDAO public application availability and print preparation, referral information and verification. Checked directory links/focus, privacy dialogs, page overflow and active styles. Largest text and high contrast checked on tracking. The local online PDAO route correctly returned 503 under its existing configuration.
- **Synthetic browser check:** 15 additional template states at both widths, covering protected submission, application errors, active PDAO and referral forms, progress, shared public error views, publications and session receipts. Checked official Association print versus on-screen confirmation, and PDAO signature content versus screen-only controls in print. No real submission was made for these previews.
- **Automated checks:** 113 existing registration, PDAO, referral, tracking and receipt workflow tests passed on the disposable G12 database. Two route-boundary tests passed separately. Django system checks and Git whitespace checks passed.

[Tracking at desktop size](tracking-desktop.png) · [Synthetic receipt at phone size](receipt-mobile-synthetic.png)
