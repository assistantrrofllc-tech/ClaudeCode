# CrewOS — Agent Rules

## Context Management Rules
- Before any structural change (navigation, database schema, new module,
  major refactor) — run /compact first
- Never compact mid-change — finish current change, merge to main, deploy,
  verify live, THEN compact
- If auto-compact triggers mid-change — finish current task from memory,
  do not start anything new until next session starts clean
- After every merge to main — compact before starting next change
