# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Use GitHub's private reporting instead: go to the **Security** tab of this repository and click **Report a vulnerability**. If that is not available, message a maintainer (@VTSLM or @https-hari) directly.

Include:
- what the problem is and where (file, endpoint or page)
- steps to reproduce
- what an attacker could do with it

We aim to acknowledge reports within 3 days and to fix confirmed issues before the next release.

## Supported versions

Only the latest code on `main` receives fixes. Tagged sprint releases (`v0.1.0`, `v0.2.0`, ...) are snapshots and are not patched.

## Leaked credentials

If a key, password or token is committed by mistake:
1. Tell a maintainer straight away.
2. Rotate the credential at the provider (Supabase, Firebase, Razorpay, Google, OpenAI). Removing it from the code is not enough, because git history and forks keep it.
3. Update the team's local `.env` files with the new value.
