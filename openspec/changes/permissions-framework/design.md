## Context

No auth system exists yet — the app is open. This change adds the permission data model and helper function so it's ready when auth is added. For now, all routes pass (no user session = admin access by default).

## Goals / Non-Goals

**Goals:**
- Permission table and helper function
- System roles on employees
- One route with permission check as proof of concept

**Non-Goals:**
- Auth/login system
- Settings UI for managing permissions
- Multi-tenant gating

## Decisions

### 1. Permission check returns True when no auth session exists
Since there's no login yet, `check_permission()` returns True by default. When auth is added, it will read from the session.

### 2. Access levels are ordered: none < view < edit < admin
The helper checks if the user's level is >= the required level.

### 3. system_role on employees, not a separate users table
Employees ARE users. The system_role column gives them a platform-wide role. Module permissions are per-module overrides.

## Risks / Trade-offs
- **No enforcement yet** — The helper exists but isn't wired to most routes. This is intentional — enforcement comes when auth is added.
