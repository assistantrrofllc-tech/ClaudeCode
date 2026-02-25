## 1. Database + Dependencies

- [ ] 1.1 Add `authlib` to `requirements.txt`
- [ ] 1.2 Add `authorized_users` table to `src/database/schema.sql` with seed data (Robert's email as admin)
- [ ] 1.3 Run schema on local DB to verify table creation

## 2. Auth Module

- [ ] 2.1 Create `src/services/auth.py` — `login_required` decorator (checks `session["user"]`, redirects to `/auth/login?next=<original_url>`)
- [ ] 2.2 Create `src/api/auth.py` — `auth_bp` blueprint with routes: `/auth/login`, `/auth/google`, `/auth/callback`, `/auth/logout`
- [ ] 2.3 Register `auth_bp` in `src/app.py`, configure authlib OAuth client with Google provider
- [ ] 2.4 Set `PERMANENT_SESSION_LIFETIME` to 24 hours in app config

## 3. Auth Templates

- [ ] 3.1 Create `dashboard/templates/login.html` — dark theme, CrewOS brand, "Sign in with Google" button, mobile responsive
- [ ] 3.2 Create `dashboard/templates/access_denied.html` — message, Robert's contact email, "Try a different account" link

## 4. Home Screen

- [ ] 4.1 Create `dashboard/templates/home.html` — module cards grid (2-col desktop, 1-col mobile), user name + avatar + logout in header
- [ ] 4.2 Add home screen route `GET /` in `dashboard.py` — queries live data (receipts this week, spend this month, employee count, expiring certs count)
- [ ] 4.3 Move existing ledger dashboard from `/` to new subnav-accessible route (update `MODULE_NAVS` crewledger dashboard href)

## 5. Protect Routes

- [ ] 5.1 Apply `@login_required` to all routes in `src/api/dashboard.py`
- [ ] 5.2 Apply `@login_required` to all routes in `src/api/reports.py`
- [ ] 5.3 Apply `@login_required` to all routes in `src/api/export.py`
- [ ] 5.4 Apply `@login_required` to all routes in `src/api/admin_tools.py`
- [ ] 5.5 Verify unprotected routes remain open: `/webhook/sms`, `/sms/status`, `/crew/verify/<token>`, `/health`

## 6. Navigation Updates

- [ ] 6.1 Add home icon/button to module bar in `base.html` (far left, before module tabs)
- [ ] 6.2 Add user avatar + logout to module bar header area in `base.html` (far right)
- [ ] 6.3 Pass `session["user"]` data to templates via context processor in `app.py`
- [ ] 6.4 Add CSS for home button, user avatar, and avatar initials fallback in `style.css`

## 7. Testing

- [ ] 7.1 Write tests for auth flow: login redirect, callback with authorized/unauthorized email, logout, session expiry
- [ ] 7.2 Write tests for home screen: authenticated access shows cards, unauthenticated redirects to login
- [ ] 7.3 Write tests for protected routes: verify redirect behavior, verify unprotected routes still work
- [ ] 7.4 Run full test suite — all existing tests must pass (set `TESTING=1` to skip scheduler + auth)

## 8. Deploy + Verify

- [ ] 8.1 Ensure Robert has added Kim's and Doug's emails as test users in Google Cloud Console
- [ ] 8.2 Deploy to VPS: `bash /opt/crewledger/deploy/update.sh`
- [ ] 8.3 Verify login flow end-to-end on live site
- [ ] 8.4 Verify SMS webhook still works (Twilio test)
- [ ] 8.5 Verify QR cert verification still works without login
- [ ] 8.6 Bump cache version
