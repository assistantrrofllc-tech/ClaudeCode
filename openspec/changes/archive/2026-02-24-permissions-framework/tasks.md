## 1. Database

- [ ] 1.1 Add `user_permissions` table to schema.sql
- [ ] 1.2 Add `system_role` column to employees table

## 2. Helper Function

- [ ] 2.1 Create `src/services/permissions.py` with `check_permission(user_id, module, required_level)`
- [ ] 2.2 Implement access level ordering (none < view < edit < admin)
- [ ] 2.3 Default to True when no auth session

## 3. Integration

- [ ] 3.1 Apply permission check to CrewCert employee list route as proof of concept

## 4. Testing

- [ ] 4.1 Test check_permission with various access levels
- [ ] 4.2 Test default allows when no session
- [ ] 4.3 Run full test suite
