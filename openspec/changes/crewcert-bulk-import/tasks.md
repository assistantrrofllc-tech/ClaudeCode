## 1. Backend

- [ ] 1.1 Add `/admin/cert-import` GET route
- [ ] 1.2 Add `/admin/cert-import/upload` POST route (parse CSV, fuzzy match, return preview JSON)
- [ ] 1.3 Add `/admin/cert-import/save` POST route (import selected rows, skip duplicates, return summary)

## 2. Frontend

- [ ] 2.1 Create `cert_import.html` with upload form
- [ ] 2.2 Preview table with match confidence indicators and employee dropdown override
- [ ] 2.3 Import button and results summary

## 3. Testing

- [ ] 3.1 Test CSV parsing and fuzzy matching
- [ ] 3.2 Test duplicate detection
- [ ] 3.3 Run full test suite
