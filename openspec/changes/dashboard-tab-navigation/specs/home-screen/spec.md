## ADDED Requirements

### Requirement: Home screen displays module cards after login
The system SHALL serve a home screen at `GET /` showing module cards for each CrewOS module. The home screen SHALL require authentication.

#### Scenario: Authenticated user visits home
- **WHEN** an authenticated user navigates to `/`
- **THEN** the system SHALL display the home screen with module cards

### Requirement: CrewLedger card shows live summary data
The CrewLedger module card SHALL display: the module name, a receipt/dollar icon, the number of receipts this week, the total spend this month, and a "Live" status badge. Clicking the card SHALL navigate to `/ledger`.

#### Scenario: CrewLedger card with data
- **WHEN** the home screen renders and there are 12 receipts this week totaling $3,450
- **THEN** the CrewLedger card SHALL display "12 receipts this week" and "$3,450.00 this month"

#### Scenario: CrewLedger card click
- **WHEN** user clicks the CrewLedger card
- **THEN** the system SHALL navigate to `/ledger`

### Requirement: CrewCert card shows live summary data
The CrewCert module card SHALL display: the module name, a shield/certificate icon, the number of active employees, the number of certs expiring soon (within 30 days), and a "Live" status badge. Clicking the card SHALL navigate to `/crew`.

#### Scenario: CrewCert card with data
- **WHEN** the home screen renders and there are 38 employees and 5 certs expiring soon
- **THEN** the CrewCert card SHALL display "38 employees" and "5 certs expiring soon"

#### Scenario: CrewCert card click
- **WHEN** user clicks the CrewCert card
- **THEN** the system SHALL navigate to `/crew`

### Requirement: Future module cards are displayed but disabled
Module cards for CrewSchedule, CrewSafe, and CrewAsset SHALL be displayed in a dimmed/disabled state with a "Coming Soon" badge. They SHALL NOT be clickable.

#### Scenario: Future module card display
- **WHEN** the home screen renders
- **THEN** CrewSchedule, CrewSafe, and CrewAsset cards SHALL appear dimmed with "Coming Soon" text

### Requirement: Home screen card layout is responsive
Module cards SHALL display in a 2-column grid on desktop and a single column on mobile (below 600px).

#### Scenario: Desktop layout
- **WHEN** the viewport is wider than 600px
- **THEN** module cards SHALL display in a 2-column grid

#### Scenario: Mobile layout
- **WHEN** the viewport is 375px wide
- **THEN** module cards SHALL stack in a single column

### Requirement: Home screen shows user identity
The home screen header SHALL display the authenticated user's name and Google profile picture, plus a logout link.

#### Scenario: User info displayed
- **WHEN** an authenticated user views the home screen
- **THEN** the header SHALL show the user's name, profile picture, and a logout link to `/auth/logout`
