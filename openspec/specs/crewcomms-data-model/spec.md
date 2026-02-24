# crewcomms-data-model Specification

## Purpose
TBD - created by archiving change crewcomms-db-scaffold. Update Purpose after archive.
## Requirements
### Requirement: Communications table
The system SHALL have a `communications` table with columns: id (UUID), direction, channel, from_number, to_number, body, duration_seconds, recording_url, transcript, project_id, contact_id, employee_id, external_id, imported_at, created_at.

#### Scenario: Table exists after migration
- **WHEN** the database schema is applied
- **THEN** the communications table SHALL exist with all specified columns

### Requirement: SMS backup import script
The system SHALL provide a CLI script at `scripts/import_sms_backup.py` that accepts an SMS Backup & Restore XML file and imports messages into the communications table.

#### Scenario: Import SMS backup
- **WHEN** running `python scripts/import_sms_backup.py backup.xml`
- **THEN** messages SHALL be imported and a summary printed (X imported, X skipped, date range)

#### Scenario: Skip duplicates
- **WHEN** the same XML file is imported twice
- **THEN** the second import SHALL skip all duplicate messages (matched by external_id)

