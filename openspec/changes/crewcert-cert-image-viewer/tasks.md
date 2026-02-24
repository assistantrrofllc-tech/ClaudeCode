## 1. Document Serving

- [ ] 1.1 Add cert document serving route `/certifications/document/<employee_uuid>/<filename>` with path traversal protection
- [ ] 1.2 Create cert storage base directory structure (`storage/certifications/`)

## 2. Modal UI

- [ ] 2.1 Add cert document modal to `crew_detail.html` (reuse modal CSS pattern)
- [ ] 2.2 Add open/close/download JS functions
- [ ] 2.3 Wire document icon in cert table to open modal
- [ ] 2.4 Pinch-to-zoom via `touch-action: pinch-zoom` on cert image

## 3. Testing

- [ ] 3.1 Test doc serving route blocks path traversal
- [ ] 3.2 Test doc serving returns file for valid path
- [ ] 3.3 Run full test suite
