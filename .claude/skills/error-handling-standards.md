---
name: error-handling-standards
description: "Trigger when fixing bugs, handling errors, or building error notification systems. Use when working on pipeline reliability, silent failures, or admin alerts."
---

# Error Handling Standards

## Core Principle
No silent failures. Ever. If something breaks, someone knows about it.

## Who Gets Notified
System administrator only. Not employees, not office managers.
Currently: Rob is system admin for all clients.
Notification goes to admin role, not hardcoded contact info.

## Admin Hierarchy
- Level 1: Client internal admin — user access, settings, day-to-day
- Level 2: Tech Quest (Rob) — pipeline issues, bugs, outages
- Level 3: Platform self-healing — auto-fix where possible

## Error States to Handle
- API credits exhausted → alert admin, queue incoming, don't lose data
- OpenAI endpoint down → alert admin, queue for retry
- Twilio webhook fails → log attempt, alert admin
- Image too blurry → flag for review, don't guess
- Document isn't a receipt → classify and route correctly
- Employee not recognized → log the attempt, alert admin
- Database write fails → alert admin immediately, preserve raw data
- VPS disk full → stop accepting images, alert admin urgently
- Twilio balance low → alert at $10, urgent at $5

## Prevention Rule
Every error you fix, add a prevention step so it never recurs.
Document what went wrong and what guard was added.
Add to CLAUDE.md or relevant skill if it's a recurring pattern.

## Receipt Pipeline Specific
- One pending confirmation NEVER blocks the queue
- Each receipt is its own async job
- Failed OCR = flag for manual review, don't discard
- Unknown document type = "Looks like a packing slip, not a receipt. Want me to save it for inventory?"
