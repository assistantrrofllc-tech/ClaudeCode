"""
Cert status calculation — single source of truth.

Every status determination in the app goes through calculate_cert_status().
No other code should independently compute whether a cert is valid/expiring/expired.
"""

from datetime import date, datetime


def calculate_cert_status(expires_at: str | None) -> str:
    """Calculate cert status from expiry date string.

    Args:
        expires_at: Expiry date as 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS', or None.

    Returns:
        'valid'     — more than 90 days until expiry
        'expiring'  — 90 days or fewer until expiry
        'expired'   — past expiry date
        'no_expiry' — no expiry date on file
    """
    if not expires_at:
        return "no_expiry"

    try:
        exp = datetime.strptime(expires_at, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        try:
            exp = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S").date()
        except (ValueError, TypeError):
            return "no_expiry"

    today = date.today()
    if exp < today:
        return "expired"
    days_remaining = (exp - today).days
    if days_remaining <= 90:
        return "expiring"
    return "valid"


def days_until_expiry(expires_at: str | None) -> int | None:
    """Calculate days until expiry. Negative = days past expiry."""
    if not expires_at:
        return None
    try:
        exp = datetime.strptime(expires_at, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        try:
            exp = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S").date()
        except (ValueError, TypeError):
            return None
    return (exp - date.today()).days
