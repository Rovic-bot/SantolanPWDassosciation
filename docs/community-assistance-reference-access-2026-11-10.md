# Conversation access using only its reference

The owner explicitly requested that returning to a Community Assistance Desk conversation require only the conversation reference, without the registered name or PWD/control number. This replaces the earlier three-field access rule for this specific service.

The form, access service, receipt instructions and future email instructions now use only the complete private `ASR-<UUID>` reference. It is a bearer access key; the form explains that anyone with it can open an active conversation. Sequential inbox aliases remain invalid access credentials. Initial submission still uses the existing member-verification flow.

Reference, IP and session throttling, signed session-bound expiring access, current member eligibility checks, protected message visibility, CSRF, and closure enforcement remain in place. Closed references cannot be reused. Existing records and email history are unchanged; no schema migration is needed.

Verification used read-only inspections against existing local tickets and guarded rendered browser previews. Reference-only access succeeded; malformed/short references, invalid sessions/signatures, expiry, and existing closed references were rejected. The rendered continuation form has exactly one visible input. Light/dark/high-contrast, mobile and standalone views passed browser inspection without JavaScript errors or horizontal overflow. Django system checks and `git diff --check` passed. No automated test suite, operational record, or email send was used. The development server was restarted.
