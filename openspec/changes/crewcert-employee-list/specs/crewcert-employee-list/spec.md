## ADDED Requirements

### Requirement: Employee list displays on Crew tab
The Crew tab at `/crew` SHALL display a roster of all employees with columns: name, phone, email, crew/role, status (Active/Inactive), and a certification badge row.

#### Scenario: Employee list renders
- **WHEN** user navigates to `/crew`
- **THEN** all employees SHALL be listed with their basic info and cert badge summary

#### Scenario: Empty state
- **WHEN** no employees exist in the system
- **THEN** the page SHALL display a message indicating no employees and an "Add Employee" button

### Requirement: Certification badge row per employee
Each employee row SHALL display one small badge icon per certification type, color-coded by status: green (valid, >90 days remaining), yellow (expiring, <90 days remaining), red (expired), gray (not held / not on file).

#### Scenario: Employee with valid cert
- **WHEN** an employee has a certification expiring more than 90 days from now
- **THEN** that cert's badge SHALL display in green

#### Scenario: Employee with expiring cert
- **WHEN** an employee has a certification expiring within 90 days
- **THEN** that cert's badge SHALL display in yellow

#### Scenario: Employee with expired cert
- **WHEN** an employee has a certification with expires_at in the past
- **THEN** that cert's badge SHALL display in red

#### Scenario: Employee without a cert type
- **WHEN** an employee has no record for a certification type
- **THEN** that cert type's badge SHALL display in gray

### Requirement: Search and filter bar
The Crew tab SHALL have a search bar that filters the employee list by name, crew, or cert status. Filtering SHALL happen client-side without page reload.

#### Scenario: Filter by name
- **WHEN** user types "Mario" in the search bar
- **THEN** only employees whose name contains "Mario" SHALL be visible

#### Scenario: Filter by cert status
- **WHEN** user selects a filter for "expired" certs
- **THEN** only employees who have at least one expired cert SHALL be visible

### Requirement: Add Employee button
The Crew tab SHALL have an "Add Employee" button that opens an inline form or modal to create a new employee with fields: first name, last name/full name, phone, email, crew, role.

#### Scenario: Add employee successfully
- **WHEN** user fills in required fields (first name, phone) and submits
- **THEN** the employee SHALL be created and appear in the list

### Requirement: Employee row is clickable
Clicking an employee row SHALL navigate to the employee detail page at `/crew/<employee_id>`.

#### Scenario: Navigate to detail
- **WHEN** user clicks an employee row
- **THEN** the browser SHALL navigate to `/crew/<employee_id>`

### Requirement: Mobile-first layout
The employee list SHALL be readable on a phone screen (375px width). Badge icons SHALL be small enough to fit in a single row. Phone numbers SHALL be click-to-call links.

#### Scenario: Mobile viewport
- **WHEN** viewing on a 375px wide screen
- **THEN** the employee list SHALL be scrollable and readable without horizontal overflow
