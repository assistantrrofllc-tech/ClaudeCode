---
name: startup-routine
description: "Trigger at session start. Reads desktop summary journal, updates Plash HTML tracker, runs preflight checks. Use when starting a new session or when Rob says 'start up' or 'good morning' or 'let's go'."
---

# Startup Routine

Run this at the beginning of every session, before any build work.

## Step 1: Read Yesterday's Summary
- Read ~/Desktop/crewos-summary.md
- Understand what was done last session
- Note any open items or blockers

## Step 2: Update Desktop Tracker
- Read ~/Desktop/crewos-tracker.html
- Add any new items from the summary that aren't already tracked
- Add any new bugs, features, or tasks that came in overnight
- Update status of completed items
- Save the file — Plash auto-refreshes on the desktop

## Step 3: Preflight Self-Check
- Verify Python venv: source /opt/crewledger/.venv/bin/activate
- Verify database accessible: sqlite3 /opt/crewledger/crewledger.db ".tables"
- Verify deploy script exists: ls /opt/crewledger/deploy/update.sh
- Verify git status clean: git status
- Check disk usage: df -h /opt/crewledger
- If disk > 70% — warn immediately
- If disk > 85% — alert Rob before doing anything else
- If any check fails — fix it before proceeding

## Step 4: Report
Print a brief summary:
- What was done last session
- What's queued for today
- Any issues found in preflight
- Disk usage percentage

Then wait for instructions.
