## ADDED Requirements

### Requirement: Authorized users table stores allowed emails
The system SHALL maintain an `authorized_users` table with columns: id, email (unique, not null), name, role (default 'viewer'), is_active (default 1), created_at, last_login. The system SHALL seed Robert's email (`official.techquest.ai@gmail.com`) with role `admin` on schema creation.

#### Scenario: Table exists after schema init
- **WHEN** the database schema is initialized
- **THEN** the `authorized_users` table SHALL exist with Robert's email seeded as admin

#### Scenario: Duplicate email rejected
- **WHEN** an attempt is made to insert a duplicate email
- **THEN** the system SHALL reject the insert with a unique constraint violation

### Requirement: Login page displays Google sign-in
The system SHALL serve a login page at `GET /auth/login` with a "Sign in with Google" button. The page SHALL use the dark theme matching the existing dashboard aesthetic, display the CrewOS brand, and be mobile responsive.

#### Scenario: Unauthenticated user visits login page
- **WHEN** a user navigates to `/auth/login`
- **THEN** the system SHALL display the login page with the Google sign-in button

#### Scenario: Already authenticated user visits login page
- **WHEN** an authenticated user navigates to `/auth/login`
- **THEN** the system SHALL redirect to `/`

### Requirement: Google OAuth redirect initiates authorization
The system SHALL redirect the user to Google's OAuth consent screen at `GET /auth/google`. The redirect SHALL request the `openid`, `email`, and `profile` scopes.

#### Scenario: User clicks sign-in button
- **WHEN** user clicks "Sign in with Google"
- **THEN** the system SHALL redirect to Google's OAuth authorization endpoint with the correct client ID, redirect URI, and scopes

### Requirement: OAuth callback authenticates authorized users
The system SHALL handle Google's OAuth callback at `GET /auth/callback`. The system SHALL exchange the authorization code for user info (email, name, picture). If the email exists in `authorized_users` with `is_active = 1`, the system SHALL create a session and redirect to `/`. If the email is not authorized, the system SHALL display an access denied page.

#### Scenario: Authorized user completes OAuth flow
- **WHEN** Google redirects to `/auth/callback` with a valid code for an authorized email
- **THEN** the system SHALL create a session with email, name, picture, and role, update `last_login`, and redirect to `/`

#### Scenario: Unauthorized user completes OAuth flow
- **WHEN** Google redirects to `/auth/callback` with a valid code for an email NOT in `authorized_users`
- **THEN** the system SHALL display the access denied page with Robert's contact info

#### Scenario: Deactivated user attempts login
- **WHEN** Google redirects to `/auth/callback` for an email with `is_active = 0`
- **THEN** the system SHALL display the access denied page

### Requirement: Access denied page shows contact info
The system SHALL display an access denied page for unauthorized emails showing: "You don't have access to CrewOS", Robert's contact email, and a "Try a different account" link back to `/auth/login`.

#### Scenario: Unauthorized user sees access denied
- **WHEN** an unauthorized user is shown the access denied page
- **THEN** the page SHALL display a message, Robert's contact info, and a link to try a different account

### Requirement: Logout clears session
The system SHALL clear the user's session at `GET /auth/logout` and redirect to `/auth/login`.

#### Scenario: User logs out
- **WHEN** an authenticated user navigates to `/auth/logout`
- **THEN** the session SHALL be cleared and the user SHALL be redirected to `/auth/login`

### Requirement: Protected routes require authentication
The system SHALL enforce authentication on all dashboard routes via a `@login_required` decorator. Unauthenticated requests SHALL be redirected to `/auth/login` with the original URL preserved for post-login redirect.

#### Scenario: Unauthenticated user hits protected route
- **WHEN** an unauthenticated user navigates to `/ledger`
- **THEN** the system SHALL redirect to `/auth/login?next=/ledger`

#### Scenario: Post-login redirect to original URL
- **WHEN** a user completes login with `?next=/projects/5` in the flow
- **THEN** the system SHALL redirect to `/projects/5` instead of `/`

### Requirement: Specific routes remain unprotected
The following routes SHALL NOT require authentication: `/auth/*`, `/webhook/sms`, `/sms/status`, `/crew/verify/<token>`, `/health`.

#### Scenario: Twilio webhook works without login
- **WHEN** Twilio sends a POST to `/webhook/sms`
- **THEN** the system SHALL process the request without requiring authentication

#### Scenario: QR verification works without login
- **WHEN** a visitor navigates to `/crew/verify/<token>`
- **THEN** the system SHALL display the verification page without requiring authentication

### Requirement: Sessions expire after inactivity
User sessions SHALL expire after 24 hours of inactivity. Expired sessions SHALL redirect to `/auth/login`.

#### Scenario: Session expires
- **WHEN** a user's last activity was more than 24 hours ago
- **THEN** the next request SHALL redirect to `/auth/login`
