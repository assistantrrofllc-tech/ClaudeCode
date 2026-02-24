## Why

CrewOS is expanding beyond CrewLedger into multiple modules (CrewCert, CrewComms, etc.). The current nav bar has flat page links (Dashboard, Ledger, Employees, Projects, Settings) that don't scale to a multi-module platform. We need a top-level tab navigation system that lets users switch between module home screens, with each module owning its own content area. This is the structural prerequisite for every module that follows.

## What Changes

- Add a horizontal tab bar below the main header nav, showing module tabs (Ledger, Crew)
- Active tab is visually distinct using the existing navy color scheme via CSS variables
- Tab switching uses URL query parameter (`?tab=crew`) for shareable links — no full page reload required
- Current ledger content wrapped in a "Ledger" tab panel with zero functional changes
- New "Crew" tab panel added as empty placeholder (populated by Change 2)
- Tab bar is mobile-first — large tappable targets for field use
- Tab structure is extensible — adding future modules means adding a tab entry and a content panel

## Capabilities

### New Capabilities
- `tab-navigation`: Top-level module tab bar with URL-aware tab switching, mobile-first layout, and extensible structure for future modules

### Modified Capabilities

## Impact

- **Templates:** `base.html` gets the tab bar markup; `ledger.html` content wrapped in tab panel
- **Routes:** Dashboard route updated to read `?tab=` parameter and pass active tab to template
- **CSS:** New tab bar styles using CSS custom properties (no hardcoded colors)
- **JS:** Tab switching logic (show/hide panels, update URL, sync active state)
- **No database changes, no new dependencies, no API changes**
