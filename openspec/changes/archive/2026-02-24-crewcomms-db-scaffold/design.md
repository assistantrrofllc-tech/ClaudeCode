## Context

CrewComms will eventually be a full communications module. This change only lays the database foundation and provides a CLI import tool for historical SMS data from Android SMS Backup & Restore XML format.

## Goals / Non-Goals

**Goals:**
- Communications table with all columns per spec
- CLI import script that parses SMS Backup & Restore XML

**Non-Goals:**
- Any UI elements
- Any routes or API endpoints
- Real-time message processing

## Decisions

### 1. XML parsing with stdlib ElementTree
SMS Backup & Restore uses simple XML. No need for lxml — stdlib xml.etree.ElementTree handles it.

### 2. Duplicate detection by external_id
Each SMS has a unique identifier from the backup. Store as external_id to skip duplicates on re-import.

## Risks / Trade-offs
- None — this is pure invisible infrastructure with zero user-facing changes.
