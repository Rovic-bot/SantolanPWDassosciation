# Usable local registration demo — 2026-10-24

The owner explicitly selected **Local capstone demo with fictional data**. The requested online form -> reference/office instructions -> authorized Admin retrieval flow is now running at `http://127.0.0.1:8001/`. This is a separate isolated demonstration, not real Association collection or institutional acceptance. Phases remain Partial and the accepted milestone remains 70%.

## Use the demo

1. Open `http://127.0.0.1:8001/membership/registration/apply/` and enter fictional applicant information. The form is enabled and uses the current shared onsite layout.
2. Submit. The receipt displays an AMR reference and instructions to go to the Association office / Help Desk for verification, immediately before the retained submitted form. Save the reference.
3. Open `http://127.0.0.1:8001/accounts/login/`. The synthetic staff username/password are in the ignored local file `.local/registration-demo-20261024/Demo login.txt`; no real account was changed.
4. Open Onsite Member Registration, enter the full AMR reference in **Load online application**, and view the submitted information. The same record is also visible in the pending registration inbox. A reference alone does not grant private access.

The normal site on port 8000 is separate. Use port **8001** for this enabled demo. Each demo page carries a fictional-data banner. Public submission has no applicant account requirement. Do not enter real identities or documents. The existing synthetic policy parameters are used only for this demonstration; the receipt session is time-limited and Finish revokes access. Registration-to-Member approval and PDAO/Phase 3 operations are not activated.

## Isolation and startup

The hidden demo launcher reuses the existing fresh G12 MySQL launcher with `.env` disabled, isolated grants, a newly created temporary datadir and separate private media. A verified **schema-only** backup and its recorded migration-history metadata were restored; no real application records, accounts or private uploads were copied. Only the exact fingerprinted membership 0006, members 0006 and core 0002 were then applied in this disposable database. No historical migration was executed, no migration was faked, and the unchanged `runlocal` startup guard passed before serving. The existing annual-observance deferral remains.

Process-only policy overrides, separate session/CSRF cookie names and a loopback-only server prevent the demo from configuring the ordinary site. A least-privilege synthetic staff account has the permissions needed for the onsite entry screen, pending form retrieval and separate private attachment access, not membership approval or PDAO authority. Runtime tools, credentials and logs remain ignored under `.local/registration-demo-20261024/`; identity evidence without credentials is in `isolation.json`.

The demo remains running in the background. Browser refreshes retain its data. A future fresh launch creates a new isolated dataset; this is not a durable operational records service. Stop/restart must target the recorded demo process only, not the ordinary site/database. No working-database connection or modification occurred in this task.

## Actual changes and validation

Application change: `templates/membership/registration/receipt.html` moves the existing required onsite instructions directly below the reference/time, ahead of the long submitted-form section. No service, model, migration, ordinary setting or security gate was rewritten. The active demonstration uses already implemented registration and reference retrieval.

Browser validation (`browser.log`, `ui/checks.json`) passed the live isolated journey: submit fictional form -> reference receipt and office instructions -> staff login/inbox -> Onsite Member Registration lookup -> prefilled same record. It also passed 16 responsive checks, middle-name/suffix behavior, keyboard submission/lookup, public/Admin layout comparison, anonymous lookup denial and Finish revocation. Expected denied receipt after Finish returned 403. No full regression rerun is claimed.

Fresh read-only verification of the identified **demo database only**, after the browser journey: one RegistrationIntake, one RegistrationRevision, zero legacy MembershipApplications and zero Members. All 267 protected files and Section 8 unchanged. Normal `.env`, settings and startup guard unchanged. Evidence: `verification.json`. Historical reports/counts remain intact; the demo screenshots are in a new directory.

No production deployment, working-database migration, real-data testing, institutional approval, new EWAF behavior, commit, push or merge. Operational collection still requires its separate decisions; the owner's selected fictional demonstration is now usable.
