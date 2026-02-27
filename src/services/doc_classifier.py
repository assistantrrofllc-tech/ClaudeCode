"""
Document classifier using GPT-4o-mini Vision.

Classifies an uploaded image as one of:
  - receipt
  - invoice
  - packing_slip
  - purchase_order
  - unknown

Uses detail: "low" for cost efficiency — classification doesn't
need high-res pixel analysis, just document layout recognition.
Falls back to "receipt" on any failure (backward compatible).
"""

import base64
import json
import logging
from pathlib import Path

from openai import OpenAI

from config.settings import OPENAI_API_KEY

log = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """Look at this document image and classify it as one of these types:
- receipt: A retail receipt or register tape showing items purchased
- invoice: A business invoice requesting payment, typically with invoice number, terms, bill-to address
- packing_slip: A shipping/packing slip listing items shipped, typically with PO number, ship-to address
- purchase_order: A purchase order from a buyer to a vendor
- unknown: Cannot determine the type

Return ONLY valid JSON with this structure (no markdown, no explanation):
{"doc_type": "receipt", "confidence": 0.95}"""


def classify_document(image_path: str) -> dict:
    """Classify a document image by type.

    Args:
        image_path: Absolute path to the document image file.

    Returns:
        Dict with 'doc_type' and 'confidence' keys.
        Falls back to {"doc_type": "receipt", "confidence": 0.0} on failure.
    """
    fallback = {"doc_type": "receipt", "confidence": 0.0}

    if not OPENAI_API_KEY:
        log.warning("OPENAI_API_KEY not set — defaulting to receipt")
        return fallback

    path = Path(image_path)
    if not path.exists():
        log.error("Image not found for classification: %s", image_path)
        return fallback

    # Read and base64-encode the image
    image_bytes = path.read_bytes()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

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
                        {"type": "text", "text": CLASSIFICATION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}",
                                "detail": "low",
                            },
                        },
                    ],
                }
            ],
            max_tokens=100,
            temperature=0,
        )

        raw_text = response.choices[0].message.content.strip()

        # Strip markdown code blocks if present
        text = raw_text
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        data = json.loads(text)
        doc_type = data.get("doc_type", "receipt")
        confidence = float(data.get("confidence", 0))

        # Validate doc_type
        valid_types = {"receipt", "invoice", "packing_slip", "purchase_order", "unknown"}
        if doc_type not in valid_types:
            doc_type = "receipt"

        log.info("Document classified: %s (%.0f%% confidence)", doc_type, confidence * 100)
        return {"doc_type": doc_type, "confidence": confidence}

    except json.JSONDecodeError as e:
        log.warning("Failed to parse classification JSON: %s", e)
        return fallback
    except Exception as e:
        log.error("Document classification API call failed: %s", e)
        return fallback
