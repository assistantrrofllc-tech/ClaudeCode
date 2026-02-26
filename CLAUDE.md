# CrewOS Build Instructions

## Lane Discipline
- Backend agent: Python/Flask/DB only — never templates or CSS
- Frontend agent: Templates/CSS/JS only — never Python or DB
- QA agent: Test files and docs only — never application code

## CSS Rule
No hardcoded colors. All colors via :root CSS custom properties.

## Commit Rules
- All tests pass before every commit
- Update CHANGELOG.md with what changed
- Update README.md if scope changed
- Merge to main → deploy → verify live

## Scribe Agent — MANDATORY
After EVERY commit, spawn the scribe agent (`.claude/agents/scribe.md`) in background.
Before EVERY context compact, spawn the scribe agent.
At end of EVERY session (shutdown), spawn the scribe agent.
The scribe updates these files — no exceptions:
1. Build journal: `/Users/kaiclawd/Desktop/crewos-build-journal.md`
2. HTML tracker: `/Users/kaiclawd/Desktop/CLAUDE/PROJECTS/crewos-tracker/index.html`
3. CHANGELOG.md in repo
If you skip the scribe, changes get lost. This is top priority.

## Shared Tables (never recreate)
employees, crews, sites, projects, schedule, documents, communications, user_permissions, cert_alerts, scope_items, authorized_users

## Data Connections (required on every feature)
Document: reads_from, writes_to, exposes, depends_on
Never duplicate shared table data into module-private tables.
Modules communicate via hooks, never direct calls.

## Deploy
- VPS: srv1306217.hstgr.cloud
- Deploy: bash /opt/crewledger/deploy/update.sh
- Live: https://srv1306217.hstgr.cloud
- GitHub: merge to main after every completed change

## Error Handling
- See skills/error-handling-standards.md for full rules
- Core rule: no silent failures. Every error notifies the system admin.
- Never hit the same error twice. Every fix includes prevention.

## Skills (load on demand)
startup-routine, shutdown-routine, openspec-workflow, error-handling-standards, document-intake, white-label-strip

## .gitignore Additions
sheets/
BUILD_TRACKER.md
