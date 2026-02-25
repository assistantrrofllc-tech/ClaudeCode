---
name: shutdown-routine
description: "Trigger at end of session. Pushes code, deploys, updates journal and tracker, strips white label. Use when Rob says 'update everything', 'end of shift', 'wrap it up', 'shut it down', or 'that's it for today'."
---

# End of Shift Routine

Run this when Rob says "update everything" or signals end of session.

## Step 1: Tests
- Run full test suite: python -m pytest
- All tests must pass before proceeding
- If tests fail, fix them first

## Step 2: Git
- git add all changed files
- git commit with descriptive message
- git push to main

## Step 3: Deploy
- bash /opt/crewledger/deploy/update.sh
- Verify live at https://srv1306217.hstgr.cloud

## Step 4: Update Desktop Summary Journal
- Open ~/Desktop/crewos-summary.md
- APPEND a new dated section — NEVER overwrite previous entries
- Format:
  ## 2026-MM-DD
  - Bullet point of each thing completed
  - Bugs fixed
  - Features added
  - Data imported
  - Any blockers or open items for next session

## Step 5: Update Desktop HTML Tracker
- Open ~/Desktop/crewos-tracker.html
- Check off completed items
- Add any new items discovered during the session
- Update dates on completed items
- Save — Plash auto-refreshes

## Step 6: White Label Strip
- Create/update clean branch: git checkout -b clean-template
- Strip all RROF-specific data: company names, employee names, project names, API keys, phone numbers, email addresses
- Replace with generic placeholders
- Push to clean template repo
- Switch back to main: git checkout main

## Step 7: Local Backup
- Verify local git clone on Mac is current

## Step 8: Report
Print summary of everything done:
- Commits pushed (with hashes)
- Deploy status
- Journal entry added
- Tracker items updated
- White label status
