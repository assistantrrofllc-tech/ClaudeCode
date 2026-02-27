"""
Tests for document classifier service.

Covers:
- Mock OpenAI responses for each document type
- Handles API failure gracefully (falls back to receipt)
- Missing API key handling
- Invalid JSON handling
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["DATABASE_PATH"] = "/tmp/test_crewledger_docclass.db"
os.environ["TWILIO_AUTH_TOKEN"] = ""
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["RECEIPT_STORAGE_PATH"] = "/tmp/test_receipt_images"

import config.settings as _settings
_settings.OPENAI_API_KEY = "test-key"

from src.services.doc_classifier import classify_document

# Create a test image file
TEST_IMAGE = "/tmp/test_classify_image.jpg"


def setup_function():
    Path(TEST_IMAGE).write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)


def teardown_function():
    if Path(TEST_IMAGE).exists():
        Path(TEST_IMAGE).unlink()


def _mock_openai_response(content_text):
    """Create a mock OpenAI response object."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content_text
    return mock_response


# ── Classification Tests ─────────────────────────────

@patch("src.services.doc_classifier.OPENAI_API_KEY", "test-key")
@patch("src.services.doc_classifier.OpenAI")
def test_classify_receipt(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        '{"doc_type": "receipt", "confidence": 0.95}'
    )
    result = classify_document(TEST_IMAGE)
    assert result["doc_type"] == "receipt"
    assert result["confidence"] == 0.95


@patch("src.services.doc_classifier.OPENAI_API_KEY", "test-key")
@patch("src.services.doc_classifier.OpenAI")
def test_classify_invoice(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        '{"doc_type": "invoice", "confidence": 0.92}'
    )
    result = classify_document(TEST_IMAGE)
    assert result["doc_type"] == "invoice"
    assert result["confidence"] == 0.92


@patch("src.services.doc_classifier.OPENAI_API_KEY", "test-key")
@patch("src.services.doc_classifier.OpenAI")
def test_classify_packing_slip(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        '{"doc_type": "packing_slip", "confidence": 0.88}'
    )
    result = classify_document(TEST_IMAGE)
    assert result["doc_type"] == "packing_slip"


@patch("src.services.doc_classifier.OPENAI_API_KEY", "test-key")
@patch("src.services.doc_classifier.OpenAI")
def test_classify_purchase_order(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        '{"doc_type": "purchase_order", "confidence": 0.90}'
    )
    result = classify_document(TEST_IMAGE)
    assert result["doc_type"] == "purchase_order"


@patch("src.services.doc_classifier.OPENAI_API_KEY", "test-key")
@patch("src.services.doc_classifier.OpenAI")
def test_classify_unknown(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        '{"doc_type": "unknown", "confidence": 0.3}'
    )
    result = classify_document(TEST_IMAGE)
    assert result["doc_type"] == "unknown"


# ── Error Handling ───────────────────────────────────

@patch("src.services.doc_classifier.OPENAI_API_KEY", "test-key")
@patch("src.services.doc_classifier.OpenAI")
def test_api_failure_falls_back_to_receipt(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("API error")
    result = classify_document(TEST_IMAGE)
    assert result["doc_type"] == "receipt"
    assert result["confidence"] == 0.0


@patch("src.services.doc_classifier.OPENAI_API_KEY", "test-key")
@patch("src.services.doc_classifier.OpenAI")
def test_invalid_json_falls_back_to_receipt(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        "This is not valid JSON"
    )
    result = classify_document(TEST_IMAGE)
    assert result["doc_type"] == "receipt"
    assert result["confidence"] == 0.0


def test_missing_image_falls_back_to_receipt():
    result = classify_document("/tmp/nonexistent_image.jpg")
    assert result["doc_type"] == "receipt"
    assert result["confidence"] == 0.0


def test_no_api_key_falls_back_to_receipt():
    original = _settings.OPENAI_API_KEY
    _settings.OPENAI_API_KEY = ""
    try:
        # Need to reimport to pick up the empty key
        import importlib
        import src.services.doc_classifier as dc
        importlib.reload(dc)
        result = dc.classify_document(TEST_IMAGE)
        assert result["doc_type"] == "receipt"
    finally:
        _settings.OPENAI_API_KEY = original


@patch("src.services.doc_classifier.OPENAI_API_KEY", "test-key")
@patch("src.services.doc_classifier.OpenAI")
def test_markdown_wrapped_json(mock_openai_cls):
    """Model sometimes wraps JSON in markdown code blocks."""
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        '```json\n{"doc_type": "invoice", "confidence": 0.91}\n```'
    )
    result = classify_document(TEST_IMAGE)
    assert result["doc_type"] == "invoice"


@patch("src.services.doc_classifier.OPENAI_API_KEY", "test-key")
@patch("src.services.doc_classifier.OpenAI")
def test_invalid_doc_type_defaults_to_receipt(mock_openai_cls):
    """If the model returns an unrecognized doc_type, default to receipt."""
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        '{"doc_type": "memo", "confidence": 0.8}'
    )
    result = classify_document(TEST_IMAGE)
    assert result["doc_type"] == "receipt"


@patch("src.services.doc_classifier.OPENAI_API_KEY", "test-key")
@patch("src.services.doc_classifier.OpenAI")
def test_uses_low_detail_for_cost_efficiency(mock_openai_cls):
    """Classification should use detail: 'low' to save API costs."""
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        '{"doc_type": "receipt", "confidence": 0.95}'
    )
    classify_document(TEST_IMAGE)

    call_args = mock_client.chat.completions.create.call_args
    messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else [])
    content = messages[0]["content"]
    image_part = [c for c in content if isinstance(c, dict) and c.get("type") == "image_url"][0]
    assert image_part["image_url"]["detail"] == "low"
