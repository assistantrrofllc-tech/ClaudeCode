"""
Twilio webhook endpoint.

Twilio POSTs here for every incoming SMS/MMS. This module:
1. Validates the request is actually from Twilio
2. Parses the incoming message (text body, media URLs, sender)
3. Hands off to the SMS handler for routing
4. Returns a TwiML response
"""

import logging

from flask import Blueprint, request
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from config.settings import TWILIO_AUTH_TOKEN
from src.messaging.sms_handler import handle_incoming_message

log = logging.getLogger(__name__)

twilio_bp = Blueprint("twilio", __name__)


def _validate_twilio_request() -> bool:
    """Verify the request signature is from Twilio."""
    if not TWILIO_AUTH_TOKEN:
        log.warning("TWILIO_AUTH_TOKEN not set — skipping signature validation (dev mode)")
        return True

    validator = RequestValidator(TWILIO_AUTH_TOKEN)
    url = request.url
    params = request.form.to_dict()
    signature = request.headers.get("X-Twilio-Signature", "")
    return validator.validate(url, params, signature)


def _parse_incoming_message(form: dict) -> dict:
    """Extract the fields we care about from a Twilio webhook POST.

    Twilio sends these key fields:
        From          — sender phone number (e.g. +14075551234)
        Body          — text content of the message
        NumMedia      — number of media attachments (0 for plain SMS)
        MediaUrl0..N  — URL for each attached image
        MediaContentType0..N — MIME type of each attachment
    """
    num_media = int(form.get("NumMedia", 0))
    media_items = []
    for i in range(num_media):
        url = form.get(f"MediaUrl{i}")
        content_type = form.get(f"MediaContentType{i}", "")
        if url:
            media_items.append({"url": url, "content_type": content_type})

    return {
        "from_number": form.get("From", ""),
        "body": (form.get("Body") or "").strip(),
        "num_media": num_media,
        "media": media_items,
        "message_sid": form.get("MessageSid", ""),
        "to_number": form.get("To", ""),
    }


@twilio_bp.route("/webhook/sms", methods=["POST"])
def sms_webhook():
    """Main entry point for all incoming SMS/MMS messages."""
    # Validate request origin
    if not _validate_twilio_request():
        log.warning("Invalid Twilio signature — rejecting request")
        return "Forbidden", 403

    # Parse the incoming message
    parsed = _parse_incoming_message(request.form.to_dict())
    log.info(
        "SMS from %s | body=%r | media=%d",
        parsed["from_number"],
        parsed["body"][:80],
        parsed["num_media"],
    )

    # Route to the SMS handler — returns the reply text
    reply_text = handle_incoming_message(parsed)

    # Build TwiML response
    resp = MessagingResponse()
    if reply_text:
        resp.message(reply_text)

    return str(resp), 200, {"Content-Type": "text/xml"}
