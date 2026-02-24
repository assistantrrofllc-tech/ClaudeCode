## ADDED Requirements

### Requirement: Certification types lookup table
The system SHALL maintain a `certification_types` table with columns: id, name, slug, sort_order, is_active. The table SHALL be seeded with 9 types: OSHA 10, OSHA 30, First Aid / CPR, Fall Protection, Extended Reach Forklift, Driver, Bilingual, Crew Lead, Card Holder.

#### Scenario: Default cert types exist after migration
- **WHEN** the database migration runs
- **THEN** all 9 certification types SHALL exist in the `certification_types` table with unique slugs and sequential sort_order

### Requirement: Certifications table
The system SHALL maintain a `certifications` table linking employees to certification types with columns: id, employee_id (FK), cert_type_id (FK), issued_at, expires_at, document_path, issuing_org, notes, is_active, created_at, updated_at. Composite unique constraint on (employee_id, cert_type_id, issued_at) SHALL prevent duplicate entries.

#### Scenario: Store a certification record
- **WHEN** a certification is created with employee_id, cert_type_id, issued_at, and expires_at
- **THEN** the record SHALL be stored and retrievable with all fields

#### Scenario: Prevent duplicate certification
- **WHEN** a certification with the same employee_id, cert_type_id, and issued_at already exists
- **THEN** the insert SHALL fail with a unique constraint violation

### Requirement: Employee email column
The employees table SHALL have an `email` column (TEXT, nullable) for contact information.

#### Scenario: Email column exists
- **WHEN** querying the employees table
- **THEN** the `email` column SHALL be available and nullable
