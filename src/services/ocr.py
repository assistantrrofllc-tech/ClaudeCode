"""
Receipt OCR via OpenAI GPT-4o-mini Vision.

Sends a receipt image to the Vision API and gets back structured JSON
with vendor, date, items, totals, and payment method.

One API call per receipt — the only thing in CrewLedger that needs
cloud intelligence.
"""

import base64
import json
import logging
from pathlib import Path

from openai import OpenAI

from config.settings import OPENAI_API_KEY

log = logging.getLogger(__name__)

# Structured prompt that tells GPT-4o-mini exactly what to extract
RECEIPT_EXTRACTION_PROMPT = """You are a receipt reading assistant. Extract ALL information from this receipt image and return it as valid JSON.

Return ONLY a JSON object with this exact structure (no markdown, no explanation):

{
  "vendor_name": "Store name exactly as printed",
  "vendor_city": "City if visible, null otherwise",
  "vendor_state": "Two-letter state code if visible, null otherwise",
  "purchase_date": "YYYY-MM-DD format",
  "subtotal": 0.00,
  "tax": 0.00,
  "total": 0.00,
  "payment_method": "CASH or last 4 digits of card (e.g. VISA 1234)",
  "line_items": [
    {
      "item_name": "Item description as printed",
      "quantity": 1,
      "unit_price": 0.00,
      "extended_price": 0.00
    }
  ]
}

Rules:
- All dollar amounts as numbers (no $ sign)
- If a value is not visible or unreadable, use null
- For returns/refunds, use negative amounts
- If quantity is not explicitly shown, default to 1
- extended_price = quantity × unit_price
- If only a total price is shown for an item (no unit price), set both unit_price and extended_price to that amount
- Parse the date as YYYY-MM-DD regardless of how it appears on the receipt
- For payment method, look for CASH, CREDIT, DEBIT, VISA, MC, AMEX, or card last 4 digits
- Return ONLY valid JSON, no other text"""


def extract_receipt_data(image_path: str) -> dict | None:
    """Send a receipt image to GPT-4o-mini Vision and parse the response.

    Args:
        image_path: Absolute path to the receipt image file.

    Returns:
        Parsed receipt dict on success, None on failure.
        The dict matches the JSON structure in the prompt above.
    """
    if not OPENAI_API_KEY:
        log.error("OPENAI_API_KEY not set — cannot process receipt")
        return None

    path = Path(image_path)
    if not path.exists():
        log.error("Image not found: %s", image_path)
        return None

    # Read and base64-encode the image
    image_bytes = path.read_bytes()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    # Detect MIME type from extension
    suffix = path.suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    mime_type = mime_types.get(suffix, "image/jpeg")

    client = OpenAI(api_key=OPENAI_API_KEY)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": RECEIPT_EXTRACTION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            max_tokens=1500,
            temperature=0,
        )

        raw_text = response.choices[0].message.content.strip()
        log.info("OCR raw response length: %d chars", len(raw_text))

        # Parse the JSON response
        receipt_data = _parse_ocr_response(raw_text)

        if receipt_data:
            log.info(
                "OCR success: %s — $%.2f — %d items",
                receipt_data.get("vendor_name", "unknown"),
                receipt_data.get("total") or 0,
                len(receipt_data.get("line_items") or []),
            )

        return receipt_data

    except Exception as e:
        log.error("OpenAI Vision API call failed: %s", e)
        return None


def _parse_ocr_response(raw_text: str) -> dict | None:
    """Parse the GPT response text into a dict.

    Handles cases where the model wraps JSON in markdown code blocks.
    """
    text = raw_text.strip()

    # Strip markdown code block if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        log.error("Failed to parse OCR JSON: %s\nRaw: %s", e, text[:500])
        return None

    # Validate required fields exist
    if not isinstance(data, dict):
        log.error("OCR response is not a dict: %s", type(data))
        return None

    # Ensure line_items is a list
    if "line_items" not in data or not isinstance(data["line_items"], list):
        data["line_items"] = []

    # Coerce numeric fields
    for field in ("subtotal", "tax", "total"):
        val = data.get(field)
        if val is not None:
            try:
                data[field] = round(float(val), 2)
            except (ValueError, TypeError):
                data[field] = None

    # Coerce line item numeric fields
    for item in data["line_items"]:
        for field in ("quantity", "unit_price", "extended_price"):
            val = item.get(field)
            if val is not None:
                try:
                    item[field] = round(float(val), 2)
                except (ValueError, TypeError):
                    item[field] = None
        # Default quantity to 1 if missing
        if item.get("quantity") is None:
            item["quantity"] = 1

    return data


def format_confirmation_message(receipt_data: dict, first_name: str, project_name: str | None) -> str:
    """Format the OCR results into a human-readable SMS confirmation.

    This is the message the employee sees and replies YES/NO to.
    Matches the spec format:
        "Ace Home & Supply, Kissimmee FL — 02/18/26 — $100.64
         3 items: Utility Lighter ($7.59), Propane Exchange ($27.99), ...
         Project: Sparrow
         Is that correct, Omar? Reply YES to save or NO to flag."
    """
    vendor = receipt_data.get("vendor_name") or "Unknown vendor"
    city = receipt_data.get("vendor_city") or ""
    state = receipt_data.get("vendor_state") or ""
    location_parts = " ".join(filter(None, [city, state]))
    location = f", {location_parts}" if location_parts else ""

    date_str = receipt_data.get("purchase_date") or "unknown date"
    # Convert YYYY-MM-DD to MM/DD/YY for readability
    if len(date_str) == 10 and date_str[4] == "-":
        try:
            parts = date_str.split("-")
            date_str = f"{parts[1]}/{parts[2]}/{parts[0][2:]}"
        except (IndexError, ValueError):
            pass

    total = receipt_data.get("total")
    total_str = f"${total:.2f}" if total is not None else "unknown amount"

    # Format line items summary
    items = receipt_data.get("line_items") or []
    if items:
        count = len(items)
        item_parts = []
        for item in items[:5]:  # Cap at 5 to keep SMS short
            name = item.get("item_name", "?")
            price = item.get("extended_price") or item.get("unit_price")
            if price is not None:
                item_parts.append(f"{name} (${price:.2f})")
            else:
                item_parts.append(name)
        items_line = f"{count} item{'s' if count != 1 else ''}: {', '.join(item_parts)}"
        if count > 5:
            items_line += f" +{count - 5} more"
    else:
        items_line = "No line items detected"

    # Build the message
    lines = [
        f"{vendor}{location} — {date_str} — {total_str}",
        items_line,
    ]

    if project_name:
        lines.append(f"Project: {project_name}")

    lines.append(f"\nIs that correct, {first_name}? Reply YES to save or NO to flag.")

    return "\n".join(lines)
