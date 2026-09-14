# Cookies — DRAFT

> **This is placeholder text**, written to describe what the platform actually
> does. It has not been reviewed by a lawyer.

**Version: 2026-09-draft-1**

This platform sets **one** cookie.

| Name | What it is | How long | Why |
|---|---|---|---|
| `refresh_token` | A random value that proves your browser is the one that signed in | 14 days | Keeps you signed in without storing your password anywhere |

It is `httpOnly`, which means no page script can read it, and `SameSite=Strict`,
which means no other website can cause your browser to send it.

There are no analytics cookies, no advertising cookies, and no third-party
cookies of any kind. Nothing you do here is reported to anyone else.

You can sign out at any time, which deletes the cookie and revokes the value it
held.
