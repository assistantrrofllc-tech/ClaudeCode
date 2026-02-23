"""
Tests for the OCR service — JSON parsing, field coercion,
and confirmation message formatting.

These tests do NOT call the OpenAI API. They test the parsing
and formatting logic that sits around the API call.
"""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.ocr import _parse_ocr_response, format_confirmation_message


# ── _parse_ocr_response tests ───────────────────────────────


def test_parse_clean_json():
    """Standard clean JSON from the model."""
    raw = json.dumps({
        "vendor_name": "Ace Home & Supply",
        "vendor_city": "Kissimmee",
        "vendor_state": "FL",
        "purchase_date": "2026-02-18",
        "subtotal": 94.57,
        "tax": 6.07,
        "total": 100.64,
        "payment_method": "VISA 1234",
        "line_items": [
            {"item_name": "Utility Lighter", "quantity": 1, "unit_price": 7.59, "extended_price": 7.59},
            {"item_name": "Propane Exchange", "quantity": 1, "unit_price": 27.99, "extended_price": 27.99},
            {"item_name": "20lb Propane Cylinder", "quantity": 1, "unit_price": 59.99, "extended_price": 59.99},
        ],
    })
    result = _parse_ocr_response(raw)
    assert result is not None
    assert result["vendor_name"] == "Ace Home & Supply"
    assert result["total"] == 100.64
    assert len(result["line_items"]) == 3
    assert result["line_items"][0]["item_name"] == "Utility Lighter"
    print("  PASS: clean JSON parsed correctly")


def test_parse_markdown_wrapped():
    """Model wraps JSON in ```json code block."""
    inner = json.dumps({
        "vendor_name": "Home Depot",
        "vendor_city": "Orlando",
        "vendor_state": "FL",
        "purchase_date": "2026-02-15",
        "subtotal": 42.50,
        "tax": 2.87,
        "total": 45.37,
        "payment_method": "CASH",
        "line_items": [
            {"item_name": "Roofing Nails 1lb", "quantity": 2, "unit_price": 8.99, "extended_price": 17.98},
        ],
    })
    raw = f"```json\n{inner}\n```"
    result = _parse_ocr_response(raw)
    assert result is not None
    assert result["vendor_name"] == "Home Depot"
    assert result["total"] == 45.37
    print("  PASS: markdown-wrapped JSON parsed correctly")


def test_parse_string_numbers():
    """Model returns numbers as strings — should be coerced to float."""
    raw = json.dumps({
        "vendor_name": "Lowe's",
        "total": "89.99",
        "subtotal": "84.15",
        "tax": "5.84",
        "line_items": [
            {"item_name": "Caulk Gun", "quantity": "1", "unit_price": "12.49", "extended_price": "12.49"},
        ],
    })
    result = _parse_ocr_response(raw)
    assert result["total"] == 89.99
    assert result["subtotal"] == 84.15
    assert result["line_items"][0]["unit_price"] == 12.49
    assert result["line_items"][0]["quantity"] == 1.0
    print("  PASS: string numbers coerced to floats")


def test_parse_null_fields():
    """Model returns nulls for unreadable fields."""
    raw = json.dumps({
        "vendor_name": "Some Store",
        "vendor_city": None,
        "vendor_state": None,
        "purchase_date": None,
        "subtotal": None,
        "tax": None,
        "total": 25.00,
        "payment_method": None,
        "line_items": [],
    })
    result = _parse_ocr_response(raw)
    assert result is not None
    assert result["vendor_city"] is None
    assert result["purchase_date"] is None
    assert result["total"] == 25.00
    assert result["line_items"] == []
    print("  PASS: null fields handled correctly")


def test_parse_missing_line_items():
    """Model omits line_items entirely."""
    raw = json.dumps({
        "vendor_name": "Gas Station",
        "total": 40.00,
    })
    result = _parse_ocr_response(raw)
    assert result is not None
    assert result["line_items"] == []
    print("  PASS: missing line_items defaults to empty list")


def test_parse_missing_quantity():
    """Line items without quantity default to 1."""
    raw = json.dumps({
        "vendor_name": "Store",
        "total": 10.00,
        "line_items": [
            {"item_name": "Widget", "unit_price": 10.00, "extended_price": 10.00},
        ],
    })
    result = _parse_ocr_response(raw)
    assert result["line_items"][0]["quantity"] == 1
    print("  PASS: missing quantity defaults to 1")


def test_parse_invalid_json():
    """Model returns garbage — should return None."""
    result = _parse_ocr_response("I can't read this receipt, sorry!")
    assert result is None
    print("  PASS: invalid JSON returns None")


def test_parse_return_receipt():
    """Negative amounts for returns/refunds."""
    raw = json.dumps({
        "vendor_name": "Home Depot",
        "total": -23.47,
        "subtotal": -21.95,
        "tax": -1.52,
        "line_items": [
            {"item_name": "Returned Drill Bit Set", "quantity": 1, "unit_price": -21.95, "extended_price": -21.95},
        ],
    })
    result = _parse_ocr_response(raw)
    assert result["total"] == -23.47
    assert result["line_items"][0]["unit_price"] == -21.95
    print("  PASS: negative amounts for returns")


def test_parse_preserves_category():
    """OCR response with category field is preserved through parsing."""
    raw = json.dumps({
        "vendor_name": "Shell Gas Station",
        "total": 45.00,
        "category": "Fuel",
        "line_items": [
            {"item_name": "Regular Unleaded", "quantity": 1, "unit_price": 45.00, "extended_price": 45.00},
        ],
    })
    result = _parse_ocr_response(raw)
    assert result is not None
    assert result["category"] == "Fuel"
    print("  PASS: category field preserved from OCR")


def test_parse_category_common_vendors():
    """OCR category suggestion maps correctly for common vendor types."""
    test_cases = [
        ("Shell", "Fuel"),
        ("Home Depot", "Materials"),
        ("McDonald's", "Food & Drinks"),
        ("Hilton Hotel", "Lodging"),
        ("Safety Supply Co", "Safety Gear"),
    ]
    for vendor, expected_cat in test_cases:
        raw = json.dumps({
            "vendor_name": vendor,
            "total": 50.00,
            "category": expected_cat,
            "line_items": [],
        })
        result = _parse_ocr_response(raw)
        assert result is not None
        assert result["category"] == expected_cat
    print("  PASS: category preserved for common vendor types")


# ── format_confirmation_message tests ────────────────────────


def test_format_full_receipt():
    """Full receipt with all fields → properly formatted confirmation."""
    data = {
        "vendor_name": "Ace Home & Supply",
        "vendor_city": "Kissimmee",
        "vendor_state": "FL",
        "purchase_date": "2026-02-18",
        "subtotal": 94.57,
        "tax": 6.07,
        "total": 100.64,
        "payment_method": "VISA 1234",
        "line_items": [
            {"item_name": "Utility Lighter", "quantity": 1, "unit_price": 7.59, "extended_price": 7.59},
            {"item_name": "Propane Exchange", "quantity": 1, "unit_price": 27.99, "extended_price": 27.99},
            {"item_name": "20lb Propane Cylinder", "quantity": 1, "unit_price": 59.99, "extended_price": 59.99},
        ],
    }
    msg = format_confirmation_message(data, "Omar", "Project Sparrow")
    assert "Ace Home & Supply" in msg
    assert "Kissimmee FL" in msg
    assert "02/18/26" in msg
    assert "$100.64" in msg
    assert "3 items" in msg
    assert "Utility Lighter ($7.59)" in msg
    assert "Project: Project Sparrow" in msg
    assert "Omar" in msg
    assert "YES" in msg
    assert "NO" in msg
    print("  PASS: full receipt formatted correctly")


def test_format_no_project():
    """Receipt without project name — no Project line."""
    data = {
        "vendor_name": "QuikTrip",
        "vendor_city": None,
        "vendor_state": None,
        "purchase_date": "2026-02-10",
        "total": 35.00,
        "line_items": [
            {"item_name": "Fuel", "extended_price": 35.00},
        ],
    }
    msg = format_confirmation_message(data, "Mario", None)
    assert "Project:" not in msg
    assert "QuikTrip" in msg
    assert "Mario" in msg
    print("  PASS: no project name → no Project line")


def test_format_no_items():
    """Receipt with no line items detected."""
    data = {
        "vendor_name": "Corner Store",
        "total": 12.50,
        "line_items": [],
    }
    msg = format_confirmation_message(data, "Luis", "Hawk")
    assert "No line items detected" in msg
    assert "$12.50" in msg
    print("  PASS: no items → 'No line items detected'")


def test_format_many_items_truncated():
    """More than 5 items → truncated with '+N more'."""
    items = [
        {"item_name": f"Item {i}", "unit_price": 1.00, "extended_price": 1.00}
        for i in range(8)
    ]
    data = {
        "vendor_name": "Big Store",
        "total": 8.00,
        "line_items": items,
    }
    msg = format_confirmation_message(data, "Omar", None)
    assert "8 items" in msg
    assert "+3 more" in msg
    print("  PASS: 8 items → shows 5 + '+3 more'")


def test_format_null_total():
    """Total is None → 'unknown amount'."""
    data = {
        "vendor_name": "Mystery Store",
        "total": None,
        "line_items": [],
    }
    msg = format_confirmation_message(data, "Omar", None)
    assert "unknown amount" in msg
    print("  PASS: null total → 'unknown amount'")


if __name__ == "__main__":
    print("Testing OCR service (parsing + formatting)...\n")

    # Parsing tests
    test_parse_clean_json()
    test_parse_markdown_wrapped()
    test_parse_string_numbers()
    test_parse_null_fields()
    test_parse_missing_line_items()
    test_parse_missing_quantity()
    test_parse_invalid_json()
    test_parse_return_receipt()

    # Formatting tests
    test_format_full_receipt()
    test_format_no_project()
    test_format_no_items()
    test_format_many_items_truncated()
    test_format_null_total()

    print("\nAll OCR tests passed!")
