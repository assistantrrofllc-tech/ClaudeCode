## ADDED Requirements

### Requirement: Dedicated projects page at /projects
The system SHALL serve a dedicated projects management page at `/projects` with full CRUD.

#### Scenario: Page loads with project data
- **WHEN** user navigates to `/projects`
- **THEN** page displays a table of all projects
- **AND** columns show: Name, Code, Location (city, state), Status, Start Date, Receipts, Spend, Actions

#### Scenario: Add a new project
- **WHEN** user clicks "+ Add Project"
- **THEN** a form appears with fields: name (required), code, address, city, state, start date, end date, notes
- **AND** submitting calls `POST /api/projects`
- **AND** the new project appears in the table without page reload

#### Scenario: Edit an existing project
- **WHEN** user clicks "Edit" on a project row
- **THEN** an edit form appears below the row with pre-filled values
- **AND** user can modify any field and save via `PUT /api/projects/<id>`
- **AND** the row updates without page reload

#### Scenario: Change project status
- **WHEN** user clicks status action on a project
- **THEN** active projects can be set to completed or on_hold
- **AND** completed/on_hold projects can be reactivated to active

#### Scenario: Remove a project
- **WHEN** user clicks "Remove" on a project
- **THEN** a confirmation dialog appears
- **AND** confirming calls `DELETE /api/projects/<id>`
- **AND** the row is removed from the table

### Requirement: Projects link in main navigation
The navigation bar SHALL include a "Projects" link between "Employees" and the Settings gear icon.

#### Scenario: Nav highlights active page
- **WHEN** user is on `/projects`
- **THEN** the "Projects" nav link has the active class

### Requirement: Settings page links to projects
The Settings page SHALL replace the inline projects section with a link card to `/projects`.

#### Scenario: Settings shows project link
- **WHEN** user navigates to `/settings`
- **THEN** a "Project Management" link card is shown (similar to Employee Management card)
- **AND** the full projects table and add form are NOT on this page
