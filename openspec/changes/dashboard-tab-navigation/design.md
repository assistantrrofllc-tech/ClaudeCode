## Context

CrewOS is a modular field ops platform with two live modules (CrewLedger, CrewCert) served as a Flask app on a Hostinger VPS. Currently the dashboard is open — anyone with the URL can see everything. Before Kim and Doug get logins, every route needs authentication. The app already has a `user_permissions` table and `check_permission()` helper, but no login gate.

Google OAuth credentials already exist in the VPS `.env` (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`). The app is in Google's "Testing" mode — only listed test users can sign in.

The current `/` route is the CrewLedger dashboard. After this change, `/` becomes the home screen and the ledger dashboard moves.

## Goals / Non-Goals

**Goals:**
- Every dashboard route requires Google OAuth login
- Post-login home screen shows module cards with live data
- SMS webhooks, QR verification, and health check remain unprotected
- Session-based auth with 24-hour inactivity timeout
- Robert can add/remove authorized users via the DB

**Non-Goals:**
- Password-based login — Google only
- User self-registration — Robert adds users manually
- Per-module access gating — all authorized users see everything for now
- Settings page for user management — manual DB for v1
- Multi-tenant / org switching
- Changes to CrewLedger or CrewCert functionality — login wraps around them

## Decisions

### 1. OAuth library: authlib
**Choice:** `authlib` for OAuth flow.
**Why:** Clean Flask integration, actively maintained, handles the full OAuth2 code flow. Alternatives considered: `flask-oauthlib` (deprecated), `flask-dance` (heavier than needed), raw `requests` (too manual).

### 2. Session storage: Flask server-side sessions
**Choice:** Use Flask's built-in session with `SECRET_KEY` (already configured).
**Why:** Simple, no new dependencies. Session stores email, name, picture URL, and role. SQLite-backed sessions were considered but unnecessary at current user count (<10 users).
**Trade-off:** Session data is client-side (signed cookie). Fine for small payloads (email + name + role).

### 3. Auth blueprint: separate `src/api/auth.py`
**Choice:** New blueprint `auth_bp` at `/auth/*` routes, registered in `app.py`.
**Why:** Keeps auth logic isolated from dashboard routes. The `@login_required` decorator lives in a shared module (`src/services/auth.py`) importable by any blueprint.

### 4. Home screen route: `/` replaces ledger dashboard
**Choice:** `/` becomes the home screen. Ledger dashboard moves to `/ledger/dashboard` (or just keep `/` subnav pointing to the right place).
**Why:** Home screen is the natural landing after login. Existing bookmarks to `/ledger`, `/crew`, `/projects` continue to work unchanged.
**Alternative:** Keep `/` as ledger, put home at `/home`. Rejected — home screen should be the root.

### 5. Decorator approach: `@login_required` on each route
**Choice:** Explicit decorator on every protected route rather than `before_request` on the app.
**Why:** Makes protection visible per-route. Unprotected routes (webhooks, QR verify) don't need special exemption logic. The decorator checks `session.get("user")` and redirects to `/auth/login` if missing.
**Alternative:** `app.before_request` with an allowlist. More brittle — easy to forget to exempt a new webhook route.

### 6. Authorized users: DB table, not config
**Choice:** `authorized_users` SQLite table with email, name, role, is_active, last_login.
**Why:** Robert can add Kim and Doug without redeploying. Links to existing `user_permissions` by email. Seed Robert's email on schema creation.

## Risks / Trade-offs

**[Google Testing Mode]** → Only emails listed as test users in Google Cloud Console can sign in. Robert must add Kim's and Doug's emails there too, not just in the DB. Document this in deploy steps.

**[Session cookie size]** → Storing user info in signed cookie means ~200 bytes per request. Fine for current scale. → If user count grows or more data needed, migrate to server-side sessions.

**[Route move: / → home]** → Anyone bookmarking `/` will now see the home screen instead of ledger dashboard. → Low risk — only Robert currently uses it, and subnav links remain.

**[No rollback for auth]** → Once deployed, unauthenticated access is gone. → Keep a `DISABLE_AUTH` env var that skips the decorator in emergencies. Remove after stable.

**[A2P 10DLC still pending]** → SMS webhook routes must stay unprotected regardless. No impact on this change.

## Migration Plan

1. Add `authlib` to `requirements.txt`
2. Add `authorized_users` table to `schema.sql` + seed Robert's email
3. Deploy schema (CREATE IF NOT EXISTS handles it cleanly)
4. Add Robert's, Kim's, Doug's emails as test users in Google Cloud Console
5. Deploy code — all routes now require login
6. Verify: hit any route → redirected to login → sign in → home screen
7. Rollback: set `DISABLE_AUTH=1` in `.env` and restart to bypass auth

## Open Questions

- Should the `DISABLE_AUTH` escape hatch be included for emergency bypass, or is that a security risk worth accepting for now?
- Does Robert want to add Kim and Doug to Google Cloud Console test users before or after deploy?
