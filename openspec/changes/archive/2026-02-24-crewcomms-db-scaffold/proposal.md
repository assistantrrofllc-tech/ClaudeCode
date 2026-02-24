## Why

CrewComms is the next module after CrewCert. The database table needs to exist before any UI or import work. This is invisible infrastructure — no UI, no nav links, no routes. Just the table and an SMS backup import script.

## What Changes

- New `communications` table for tracking SMS, email, and call records
- Import script `scripts/import_sms_backup.py` for SMS Backup & Restore XML files
- No UI elements, no new routes, no nav changes

## Capabilities

### New Capabilities
- `crewcomms-data-model`: Communications table for cross-channel message history

### Modified Capabilities

## Impact

- **Database:** New `communications` table added to schema.sql
- **Scripts:** New `scripts/import_sms_backup.py`
- **Zero UI change** — nothing visible in the dashboard
