# tab-navigation Specification

## Purpose
TBD - created by archiving change dashboard-tab-navigation. Update Purpose after archive.
## Requirements
### Requirement: Tab bar displays available modules
The system SHALL render a horizontal tab bar below the main navigation header on all dashboard pages. The tab bar SHALL display one tab per enabled module. Initial tabs: **Ledger** (default) and **Crew**.

#### Scenario: User visits dashboard with no tab parameter
- **WHEN** user navigates to `/dashboard` or `/ledger` with no `?tab=` parameter
- **THEN** the Ledger tab SHALL be active and ledger content SHALL render

#### Scenario: User visits dashboard with tab=crew
- **WHEN** user navigates to `/dashboard?tab=crew`
- **THEN** the Crew tab SHALL be active and crew content SHALL render

#### Scenario: User visits with invalid tab parameter
- **WHEN** user navigates to `/dashboard?tab=nonexistent`
- **THEN** the system SHALL fall back to the Ledger tab as default

### Requirement: Active tab is visually distinct
The active tab SHALL be visually distinguished from inactive tabs using the primary color scheme. All tab colors SHALL use CSS custom properties — no hardcoded color values.

#### Scenario: Active tab styling
- **WHEN** a tab is active
- **THEN** it SHALL have a bottom border or background using `var(--primary)` and text in the active color

#### Scenario: Inactive tab styling
- **WHEN** a tab is not active
- **THEN** it SHALL appear in a muted/secondary color and respond to hover with a subtle highlight

### Requirement: Tab bar is mobile-first
The tab bar SHALL be tappable on mobile devices. Each tab target area SHALL be at least 44px tall for touch accessibility.

#### Scenario: Mobile viewport
- **WHEN** the viewport is 375px wide (typical phone)
- **THEN** all tabs SHALL be visible without horizontal scrolling and each tab SHALL have a minimum tap target of 44px height

### Requirement: URL reflects active tab
The active tab state SHALL be encoded in the URL query parameter `?tab=<tab_id>` so that links are shareable and bookmarkable.

#### Scenario: Tab switch updates URL
- **WHEN** user clicks a tab
- **THEN** the URL SHALL update to include `?tab=<tab_id>` and the page SHALL render the selected tab's content

### Requirement: Tab structure is extensible
Adding a new module tab SHALL require only adding an entry to the tab configuration list and providing a content template block. No changes to tab bar rendering logic SHALL be needed.

#### Scenario: Adding a future module tab
- **WHEN** a developer adds a new tab entry `{"id": "schedule", "label": "Schedule"}` to the tab config
- **THEN** the tab bar SHALL render the new tab without any changes to tab bar markup or CSS

### Requirement: Existing ledger functionality is preserved
Wrapping ledger content in a tab panel SHALL NOT change any existing ledger behavior, styling, or functionality.

#### Scenario: Ledger tab contains all existing content
- **WHEN** the Ledger tab is active
- **THEN** all existing ledger features (filters, sorting, export, receipt modal, add receipt) SHALL function identically to before

