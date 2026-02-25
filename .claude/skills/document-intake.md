---
name: document-intake
description: "Trigger when working on the SMS document pipeline, OCR processing, or document classification. Use when handling receipts, packing slips, invoices, or purchase orders."
---

# Document Intake System

## One Number, Smart Routing
All documents come through the same Twilio number.
System classifies FIRST, then processes.

## Classification (before any extraction)
GPT Vision identifies document type:
- Receipt → CrewLedger (extract vendor, items, prices, total)
- Packing slip → CrewInventory (extract vendor, items, quantities, PO#)
- Invoice → CrewLedger + link to matching packing slip
- Purchase order → CrewInventory
- Unknown → flag for manual review, save image, don't guess

## File Storage Structure
Every photo saved, organized by type and project:
/opt/crewledger/storage/receipts/{project}/
/opt/crewledger/storage/receipts/unassigned/
/opt/crewledger/storage/packing-slips/{project}/
/opt/crewledger/storage/packing-slips/unassigned/
/opt/crewledger/storage/invoices/{project}/
/opt/crewledger/storage/invoices/unassigned/

## Item Learning System
- OCR pulls line items from receipts
- Keys on VENDOR + ITEM STRING (not just item string)
- Same SKU at different stores = separate entries
- First time unknown item appears → flag for user identification
- User identifies once → system remembers forever
- Cross-vendor matching: suggest, never auto-merge
- Manual override always wins

## OCR Confidence
- High confidence → process normally
- Low confidence → flag for review, don't guess
- Blurry image → reply "couldn't read clearly, can you retake?"

## Language
- Employee language preference stored on record
- First interaction asks: English or Español
- All future communications in preferred language
