---
name: white-label-strip
description: "Trigger during end-of-shift when stripping RROF-specific data for the clean template repo. Use when Rob says 'strip it' or during shutdown routine."
---

# White Label Strip Process

## What Gets Stripped
- Company name: "Roofing & Renovations of Florida" → "Your Company Name"
- Employee names → generic (Employee A, Employee B)
- Project names: "Sparrow", "Disney" → "Project Alpha", "Project Beta"
- Phone numbers → placeholder format
- Email addresses → placeholder@example.com
- API keys → REPLACE_WITH_YOUR_KEY
- Twilio credentials → placeholders
- OpenAI credentials → placeholders
- Any address or location data → generic
- Customer numbers → placeholder

## What Stays
- All code logic
- Database schema
- UI templates (with placeholder data)
- Configuration structure
- Documentation
- Test framework (with generic test data)

## Process
1. Checkout clean branch: git checkout -b clean-template
2. Run strip script (or manually replace)
3. Verify no RROF data remains: grep -r "RROF\|Roofing.*Renovation\|Sparrow\|Disney\|Mario\|Justino" .
4. Push to clean template repo
5. Switch back to main
