## Why

CrewOS is multi-module. Different users need different access levels per module. Kim edits CrewLedger, crew members view only, Robert has admin on everything. This change lays the permission database and helper function — no settings UI yet.

## What Changes

- New `user_permissions` table (user_id, module, access_level, granted_by)
- New `system_role` column on employees table (super_admin, company_admin, manager, employee)
- Helper function `check_permission(user_id, module, required_level)` returns True/False
- CrewCert employee list route gets a permission check as proof of concept
- Default permissions: new employees get `none` on all modules
- No visible UI change for current admin user

## Capabilities

### New Capabilities
- `permissions-framework`: Module-level permission system with access levels and helper function

### Modified Capabilities

## Impact

- **Database:** New `user_permissions` table, `system_role` column on employees
- **Code:** New `src/services/permissions.py` with `check_permission()`
- **Routes:** One route gets permission check applied (CrewCert list)
- **No visible UI change** for admin users
