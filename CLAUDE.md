# CrewOS Build Instructions

## OpenSpec Workflow — No code without an approved spec
openspec new change <n> → /opsx:ff → wait for Robert's approval → build → test → deploy → archive

## Context Management
- Before structural change → /compact first
- Never compact mid-change
- After merge to main → compact before next change
- Save progress to memory before context window refreshes
- Don't stop tasks early — save state and continue

## Lane Discipline
- Backend agent: Python/Flask/DB only — never templates or CSS
- Frontend agent: Templates/CSS/JS only — never Python or DB
- QA agent: Test files and docs only — never application code

## CSS Rule
No hardcoded colors. All colors via :root CSS custom properties.

## BUILD TRACKER — MANDATORY
Two tracker files live on this Mac's Desktop:
- ~/crewos-build-tracker/crewos-build-tracker.html (visual dashboard)
- ~/BUILD_TRACKER.md (summary)

Update BOTH after every major task completion (new feature, module milestone, data import).

When Robert says "update everything" — this is end-of-shift:
1. Update both tracker files with everything completed this session
2. git add, commit, push all pending work
3. Deploy: bash /opt/crewledger/deploy/update.sh
4. Verify live
5. Report what was committed and what changed on the tracker

The tracker files are LOCAL ONLY — never committed, never on VPS.

## Data Connections (required on every feature)
Document: reads_from, writes_to, exposes, depends_on
Never duplicate shared table data into module-private tables.
Modules communicate via hooks, never direct calls.

## Shared Tables (never recreate)
employees, crews, sites, projects, schedule, documents, communications, user_permissions, cert_alerts, scope_items

## Deploy
- VPS: srv1306217.hstgr.cloud
- Deploy: bash /opt/crewledger/deploy/update.sh
- Live: https://srv1306217.hstgr.cloud
- GitHub: merge to main after every completed change
