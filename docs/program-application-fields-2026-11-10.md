# Program application: remove change-report questions

## Owner-authorized change

Remove “Has your information changed since your last assessment?” and “Information needing review” from new public program applications. The accuracy confirmation now refers only to the submitted application details.

New applications retain the verified member record as their information basis, without recording a false “no changes” declaration. They proceed to eligibility review with the program's configured requirements. Extra POST values for the removed fields are ignored. Membership verification, required attachments, staff eligibility review, and EWAF evidence controls remain in place.

Historical change declarations and their review requirements remain available. The admin confirmation section identifies the saved member record as the basis for new applications and does not show a blank change declaration or claim that reported changes were reviewed.

## Validation

- Django `check --database default`: no issues.
- Read-only form rendering against an existing local program: neither removed label nor field appears; name, email, accuracy confirmation, and the configured requirement remain.
- Admin confirmation template compiles successfully.
- Python source syntax validation and `git diff --check` pass.
- Updated relevant regression test source for the new form and retained historical declarations. No automated test suite, fixture loader, or data generator was run.
- No program application was submitted and no database records or email jobs were created during validation. End-to-end submission was not exercised.

This change supersedes earlier documentation describing these two questions as part of the current application form.
