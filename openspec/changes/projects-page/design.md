## Context

Projects are managed inside Settings as a table with add/remove. The Employees page is the model for standalone management pages — it has add form, search, table, and per-row actions. The projects page follows the same pattern but adds inline editing.

## Goals / Non-Goals

**Goals:**
- Dedicated `/projects` page following the employees page pattern
- All existing project fields exposed (including end_date, notes for future CrewGroup use)
- Inline edit without page reload
- Status management (active/on_hold/completed) instead of hard delete
- Settings page cleaned up to just link to `/projects`

**Non-Goals:**
- Project detail drill-down page (future feature)
- Receipts-per-project view from this page
- New API endpoints (reusing existing CRUD)

## Decisions

### 1. Follow employees.html pattern exactly
**Why:** Consistent UI. Same page-header + add form + search + table + per-row actions structure. Users already know how it works.

### 2. Inline edit via row expansion
**Why:** Click "Edit" shows a form row below the project row with pre-filled fields. Save/Cancel. Avoids modal complexity. Same approach can be added to employees later.

### 3. Status toggle instead of delete
**Why:** Deactivate (→ completed) is safer than delete. Keep the Remove button but add "Set Completed" / "Reactivate" as primary actions. Remove requires confirmation.

### 4. Keep Remove as secondary action
**Why:** Some sample/test projects need to be deleted entirely. Remove stays but is styled as danger with confirmation.
