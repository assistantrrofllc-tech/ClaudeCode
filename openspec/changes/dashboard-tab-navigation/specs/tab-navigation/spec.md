## ADDED Requirements

### Requirement: Module bar includes home button
The module bar SHALL display a home icon/button on the far left (before "CrewLedger" tab) that navigates to `/`. The home button SHALL be visually distinct from module tabs.

#### Scenario: User clicks home button
- **WHEN** user clicks the home button in the module bar
- **THEN** the system SHALL navigate to `/`

#### Scenario: Home button visible on all pages
- **WHEN** any authenticated dashboard page renders
- **THEN** the module bar SHALL display the home button on the far left

### Requirement: Header displays user avatar and logout
The module bar header area SHALL display the authenticated user's Google profile picture (or initials fallback) and a logout action. Clicking logout SHALL navigate to `/auth/logout`.

#### Scenario: User avatar displayed
- **WHEN** an authenticated user views any dashboard page
- **THEN** the module bar SHALL show the user's profile picture on the far right

#### Scenario: User without profile picture
- **WHEN** the user has no Google profile picture
- **THEN** the module bar SHALL display the user's first initial as a fallback avatar

#### Scenario: Logout from module bar
- **WHEN** user clicks the logout action in the module bar
- **THEN** the system SHALL navigate to `/auth/logout`
