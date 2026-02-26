"""
Receipt image download and storage.

Downloads MMS images from Twilio's media URLs and saves them
to local storage with systematic naming:
    {firstName}_{YYYYMMDD}_{HHMMSS}.jpg

Twilio media URLs require Basic Auth with your Account SID and Auth Token.
"""

import logging
from datetime import datetime
from pathlib import Path

import requests

from config.settings import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, RECEIPT_STORAGE_PATH

log = logging.getLogger(__name__)


def download_and_save_image(media_url: str, employee_id: int, db) -> str | None:
    """Download an image from Twilio and save it locally.

    Returns the relative file path on success, None on failure.
    """
    # Look up employee name for the filename
    employee = db.execute(
        "SELECT first_name FROM employees WHERE id = ?", (employee_id,)
    ).fetchone()
    name = employee["first_name"] if employee else "unknown"

    # Build systematic filename: omar_20260218_143052.jpg
    now = datetime.now()
    filename = f"{name.lower()}_{now.strftime('%Y%m%d_%H%M%S')}.jpg"

    # Ensure storage directory exists
    storage_dir = Path(RECEIPT_STORAGE_PATH)
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = storage_dir / filename

    try:
        # Twilio media URLs require authentication
        auth = None
        if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
            auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        # Retry up to 3 times on transient failures (401/5xx)
        last_error = None
        for attempt in range(3):
            try:
                response = requests.get(media_url, auth=auth, timeout=30)
                response.raise_for_status()
                break
            except requests.RequestException as e:
                last_error = e
                if attempt < 2:
                    import time
                    time.sleep(1 * (attempt + 1))
                    log.warning("Image download attempt %d failed, retrying: %s", attempt + 1, e)
                else:
                    raise

        file_path.write_bytes(response.content)
        log.info("Image saved: %s (%d bytes)", file_path, len(response.content))

        # Return path relative to project root for DB storage
        return str(file_path)

    except requests.RequestException as e:
        log.error("Failed to download image from %s: %s", media_url, e)
        return None
