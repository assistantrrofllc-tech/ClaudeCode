---
name: openspec-workflow
description: "Trigger when creating, reviewing, or archiving OpenSpec documents. Use when Rob says 'new spec', 'write a spec', 'openspec', or when starting a new feature build."
---

# OpenSpec Workflow

## Creating a New Spec
1. openspec new change <number>
2. Write spec in /opt/crewledger/openspec/specs/
3. Include: what, why, how, data connections (reads_from, writes_to, exposes, depends_on)
4. Wait for Rob's approval before building
5. Never code without an approved spec

## Building from Spec
1. Read the approved spec completely
2. Backend agent handles Python/Flask/DB
3. Frontend agent handles Jinja2/CSS/JS
4. QA agent runs tests and updates docs
5. Follow lane discipline — never cross boundaries

## Archiving
1. After feature is deployed and verified
2. Move spec to /opt/crewledger/openspec/archive/
3. Update CHANGELOG.md
