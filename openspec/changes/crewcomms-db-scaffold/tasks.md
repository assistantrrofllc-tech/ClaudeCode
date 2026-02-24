## 1. Database

- [ ] 1.1 Add `communications` table to schema.sql with all specified columns and indexes

## 2. Import Script

- [ ] 2.1 Create `scripts/import_sms_backup.py` that parses SMS Backup & Restore XML
- [ ] 2.2 Handle duplicate detection by external_id
- [ ] 2.3 Print import summary (count, skipped, date range)

## 3. Verification

- [ ] 3.1 Table exists and has correct schema
- [ ] 3.2 Script accepts a test XML snippet without crashing
- [ ] 3.3 No new UI elements visible in dashboard
- [ ] 3.4 Run full test suite
