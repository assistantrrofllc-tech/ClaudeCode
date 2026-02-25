## Why

The dashboard is currently open to anyone with the URL. Before giving access to Kim, Doug, or anyone outside Robert, every route needs authentication. Google OAuth means no passwords to manage — everyone signs in with their existing Google account. Once login works, the home screen becomes a module launcher instead of jumping straight into CrewLedger.

## What Changes

- **Google OAuth login flow** — `/auth/login`, `/auth/google`, `/auth/callback`, `/auth/logout` routes using authlib
- **`authorized_users` table** — email whitelist with role (admin/manager/viewer), seeded with Robert's email
- **`@login_required` decorator** — applied to all dashboard routes; SMS webhooks, QR verify, and health check remain unprotected
- **Post-login home screen at `/`** — module cards with live summary data (receipt count, cert count, expiring certs)
- **Ledger dashboard moves from `/` to `/ledger/dashboard`** — existing `/ledger` route stays as-is
- **Navigation update** — home icon added to module bar, user avatar + logout in header
- **Login page** — dark theme, "Sign in with Google" button, CrewOS branding
- **Access denied page** — for unauthorized emails, shows Robert's contact info
- **Session management** — 24-hour inactivity timeout, stores email/name/picture/role

## Capabilities

### New Capabilities
- `google-oauth`: Google OAuth login flow — routes, session management, login_required decorator, authorized_users table
- `home-screen`: Post-login home screen with module cards showing live summary data

### Modified Capabilities
- `tab-navigation`: Home icon added to module bar, user avatar + logout in header area

## Impact

- **New dependency:** `authlib` (pip install)
- **New routes:** `/auth/login`, `/auth/google`, `/auth/callback`, `/auth/logout`, `/` (home screen)
- **Route change:** `/` moves from CrewLedger dashboard to home screen; ledger dashboard moves to a sub-route
- **New templates:** `login.html`, `access_denied.html`, `home.html`
- **New table:** `authorized_users`
- **Modified files:** `base.html` (header area), `dashboard.py` (home route, decorator), `app.py` (auth blueprint), `requirements.txt`
- **Environment:** `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` already in VPS `.env`
- **Unprotected routes:** `/webhook/sms`, `/sms/status`, `/crew/verify/<token>`, `/health`, `/auth/*`
