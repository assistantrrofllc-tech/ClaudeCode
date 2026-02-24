## Context

The current dashboard uses a flat nav bar (`base.html`) with links to Dashboard, Ledger, Employees, Projects, and Settings. Each is a separate Flask route rendering a full page. CrewOS is expanding to multiple modules — the first new module (CrewCert) needs a "Crew" tab alongside the existing "Ledger" tab. The tab bar sits below the main nav and acts as the primary module switcher.

The existing nav bar remains for cross-module pages (Settings, future global views). The tab bar is module-level navigation within the dashboard workspace.

## Goals / Non-Goals

**Goals:**
- Add a tab bar below the main nav with Ledger (default) and Crew tabs
- URL reflects active tab via `?tab=` query parameter for shareable links
- Mobile-first — tappable tab targets on phone screens
- All colors via CSS custom properties (no hardcoded hex values)
- Extensible — adding a new module tab requires minimal code changes
- Zero disruption to existing ledger functionality

**Non-Goals:**
- Per-module theming or color differentiation (future)
- Role-based tab visibility (handled by Change 8 — permissions framework)
- Module home screen widgets or dashboards (each module builds its own)
- SPA-style client-side routing — Flask routes are the source of truth

## Decisions

### 1. Flask route with query parameter (not client-side show/hide)

Each tab corresponds to a Flask route parameter. The dashboard route reads `?tab=crew` and renders the appropriate template content. This keeps the server as the source of truth and makes tab state shareable via URL.

**Alternative considered:** Pure JS show/hide with `history.pushState`. Rejected because it would require loading all module content upfront (wasteful) and complicates Flask template rendering for module-specific data.

### 2. Tab bar in base.html, tab content in child templates

The tab bar markup lives in `base.html` so it appears on all dashboard pages. Each module provides its own content via Jinja2 blocks. The `active_tab` variable (set by the route) controls which tab is highlighted and which content panel renders.

**Alternative considered:** Separate template per module with its own tab bar. Rejected — duplicates markup and makes tab bar changes require multi-file edits.

### 3. Tab bar below main nav, not replacing it

The main nav (CrewLedger brand, Settings gear) stays. The tab bar is a second row specifically for module switching. This separates global navigation from module navigation cleanly.

### 4. Tab data defined in a simple list

Tabs are defined as a Python list of dicts (`[{"id": "ledger", "label": "Ledger", "icon": None}, ...]`) passed to the template. Adding a new module = appending to this list.

## Risks / Trade-offs

- **Two rows of navigation on mobile** — The nav + tab bar takes vertical space. Mitigation: keep tab bar compact (single row, no padding bloat). The nav bar is minimal already.
- **Query parameter approach means page reload on tab switch** — Acceptable tradeoff for simplicity. Content is server-rendered anyway. Can add client-side caching later if needed.
- **Tab bar in base.html shows on all pages** — Need to conditionally render it only on dashboard-type pages (not Settings, not login). Use a `show_tabs` template variable.
