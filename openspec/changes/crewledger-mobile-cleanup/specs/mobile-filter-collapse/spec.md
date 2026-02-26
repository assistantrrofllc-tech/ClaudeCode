## ADDED Requirements

### Requirement: Collapsible filter panel on mobile
The system SHALL collapse the sort/filter dropdowns behind a toggle button on screens ≤768px wide.

#### Scenario: Initial state on mobile
- **WHEN** the ledger page loads on a screen ≤768px
- **THEN** time pills are visible, sort/filter dropdowns are hidden, and a "Filters" button is shown

#### Scenario: Expand filters
- **WHEN** user taps the "Filters" button
- **THEN** the sort/filter dropdowns become visible below the time pills

#### Scenario: Collapse filters
- **WHEN** user taps the "Filters" button while filters are expanded
- **THEN** the sort/filter dropdowns are hidden

#### Scenario: Summary line always visible
- **WHEN** the ledger page is displayed on mobile
- **THEN** the totals bar showing transaction count and total amount remains visible regardless of filter panel state

#### Scenario: Desktop unchanged
- **WHEN** the screen width is >768px
- **THEN** all filters and sort dropdowns display normally without a toggle button
