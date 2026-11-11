# Development branch publication — 2026-10-25

The owner requested publication to `https://github.com/Rovic-bot/capstone.git` as the main development repository, then requested a new branch. The revised target is `development`. Authenticated repository metadata confirms private visibility, `main` as the default branch, and permission to push. Repository visibility and the default branch are unchanged.

At preparation time, the connected GitHub tool refused both the original write and the subsequent `development` branch creation because the session's approval policy was `never`. No remote commit or branch update was made. The reviewed snapshot and an owner-run publishing shortcut are retained in ignored `.local/github-publish-20261025/`; successful execution records the published commit there. This note does not claim that the push completed.

The publication preserves both existing branches: remote `main` at `c827575293620c5dbbb032ce7aefbbdc04891527` and application history at `776cac5d1119410717c6a31c044ea85f4d619941` on `feature/events`. The new `development` commit extends the application history with the reviewed snapshot. The shortcut requires `development` to be absent and uses an empty expected-reference lease when pushing, so it cannot replace an existing branch. Neither `main` nor `feature/events` is updated. Local unfinished work remains preserved.

## Included source and private local files

The snapshot includes existing tracked files and reviewed application modules, migrations, templates, tests, browser harnesses, static assets, launchers and Markdown validation notes. It contains the latest reference confirmation, Word-template printing and simplified editable approval/decline workflow. Earlier unfinished application work is preserved as development source, not represented as newly validated production behavior.

The three included blank source forms are `Santolan_PWD_Membership_Form.docx`, `Santolan_PWD_Membership_Form_A4_Fixed.pdf`, and `PWD ID Application Form (2024-2025) (New And Renewal).pdf`. The two extracted print logos are included. The supplied Word file remains byte-for-byte unchanged, with SHA-256 `130e956120b8cead01f31522595ab65721314169dae68a650a24883ecfd73aab`.

No `.env`, `.local` runtime/credentials, virtual environment, database, dump, private upload or member data export is published. New generated screenshots, JSON evidence, command captures, duplicate source-document bundles and unrelated reference-document binaries remain local. Existing tracked validation evidence remains in the application history. Some historical validation notes therefore link to evidence available only in the owner's local workspace.

An explicit file manifest and content snapshot are retained in ignored `.local/github-publish-20261025/`. Files are normalized according to the repository's Git text attributes and their Git blob hashes are checked. Text is scanned for private-key/token signatures and exact local secret values without recording those values. Credential URL examples and password literals found in tests are synthetic rejection fixtures or disposable test users. No operational credential is included.

## Validation and setup

The latest membership changes passed 138 focused tests in disposable MySQL, covering registration, confirmation, PDF downloads, prefill, decisions, permissions, retries, concurrency and protected membership writes. The development runtime passed Django checks and the missing-migration check. The detailed commands and limitations are in [the workflow validation](simple-registration-2026-10-25/validation.md). Browser launching was unavailable; no new visual print-pagination pass is claimed.

Publication preparation also checks Python syntax and Git whitespace. It does not apply database migrations, modify application data, provision hosting or claim a fresh complete-system test run. Direct Git network access is unavailable in this environment, and the connected GitHub API blocked its write pending unavailable approval. The publishing shortcut uses ordinary Git under the owner's local session, builds the commit in a separate ignored checkout, checks the original branch heads and verifies the remote result. The local checkout and its uncommitted edits remain intact.

After successful publication, clone `development`, create a Python environment, install the requirements, configure private environment values and a native MySQL database, and follow the README setup instructions. The owner's Start/Restart shortcuts require the existing ignored development runtime and are not fresh-clone provisioning commands. External vault authority documents remain outside the repository.
