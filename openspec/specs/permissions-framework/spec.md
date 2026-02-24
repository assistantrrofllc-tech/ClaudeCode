# permissions-framework Specification

## Purpose
TBD - created by archiving change permissions-framework. Update Purpose after archive.
## Requirements
### Requirement: User permissions table
The system SHALL have a `user_permissions` table with columns: id, user_id (FK employees), module, access_level (none/view/edit/admin), granted_by, created_at, updated_at.

#### Scenario: Table exists
- **WHEN** the database schema is applied
- **THEN** the user_permissions table SHALL exist with correct columns

### Requirement: System role on employees
The employees table SHALL have a `system_role` column with values: super_admin, company_admin, manager, employee (default: employee).

#### Scenario: Default role
- **WHEN** a new employee is created without specifying system_role
- **THEN** system_role SHALL default to 'employee'

### Requirement: check_permission helper function
The system SHALL provide a `check_permission(user_id, module, required_level)` function that returns True if the user has the required access level or higher for the given module.

#### Scenario: Admin has access
- **WHEN** check_permission is called for a user with 'admin' access on 'crewcert'
- **THEN** it SHALL return True for any required_level

#### Scenario: No auth session defaults to allow
- **WHEN** check_permission is called with no active user session
- **THEN** it SHALL return True (permissive default until auth is added)

#### Scenario: Insufficient access
- **WHEN** a user has 'view' access and 'edit' is required
- **THEN** check_permission SHALL return False

### Requirement: Permission check on one route
At least one route (CrewCert employee list) SHALL use check_permission as proof of concept.

#### Scenario: Route with permission check
- **WHEN** a user with sufficient access visits the protected route
- **THEN** the page SHALL render normally

