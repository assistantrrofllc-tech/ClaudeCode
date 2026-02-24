"""
Tests for cert status calculation — single source of truth.

Covers:
- Expired certs (past expiry date)
- Expiring certs (within 90 days)
- Valid certs (more than 90 days out)
- No expiry date
- Edge cases (today, boundary dates, bad formats)
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.cert_status import calculate_cert_status, days_until_expiry


# ── Expired ──

def test_expired_cert():
    """Cert with past expiry date → expired."""
    assert calculate_cert_status("2025-02-23") == "expired"


def test_expired_yesterday():
    """Cert that expired yesterday → expired."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    assert calculate_cert_status(yesterday) == "expired"


def test_expired_long_ago():
    """Cert that expired over a year ago → expired."""
    assert calculate_cert_status("2020-01-01") == "expired"


# ── Expiring Soon ──

def test_expiring_in_45_days():
    """Cert expiring in 45 days → expiring."""
    d = (date.today() + timedelta(days=45)).isoformat()
    assert calculate_cert_status(d) == "expiring"


def test_expiring_in_90_days():
    """Cert expiring in exactly 90 days → expiring."""
    d = (date.today() + timedelta(days=90)).isoformat()
    assert calculate_cert_status(d) == "expiring"


def test_expiring_in_1_day():
    """Cert expiring tomorrow → expiring."""
    d = (date.today() + timedelta(days=1)).isoformat()
    assert calculate_cert_status(d) == "expiring"


# ── Valid ──

def test_valid_cert():
    """Cert expiring in 200 days → valid."""
    d = (date.today() + timedelta(days=200)).isoformat()
    assert calculate_cert_status(d) == "valid"


def test_valid_in_91_days():
    """Cert expiring in 91 days → valid (just outside window)."""
    d = (date.today() + timedelta(days=91)).isoformat()
    assert calculate_cert_status(d) == "valid"


# ── No Expiry ──

def test_no_expiry_none():
    """Cert with None expiry → no_expiry."""
    assert calculate_cert_status(None) == "no_expiry"


def test_no_expiry_empty():
    """Cert with empty string expiry → no_expiry."""
    assert calculate_cert_status("") == "no_expiry"


def test_no_expiry_bad_format():
    """Cert with garbage date → no_expiry."""
    assert calculate_cert_status("not-a-date") == "no_expiry"


# ── Edge Cases ──

def test_expires_today():
    """Cert expiring today → expiring (not expired until tomorrow)."""
    d = date.today().isoformat()
    assert calculate_cert_status(d) == "expiring"


def test_datetime_format():
    """Cert with datetime format (YYYY-MM-DD HH:MM:SS) works."""
    assert calculate_cert_status("2020-01-01 12:00:00") == "expired"


# ── Days Until Expiry ──

def test_days_until_expiry_past():
    """Past expiry date → negative days."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    assert days_until_expiry(yesterday) == -1


def test_days_until_expiry_future():
    """Future expiry date → positive days."""
    d = (date.today() + timedelta(days=30)).isoformat()
    assert days_until_expiry(d) == 30


def test_days_until_expiry_none():
    """No expiry date → None."""
    assert days_until_expiry(None) is None


def test_days_until_expiry_today():
    """Expiring today → 0 days."""
    assert days_until_expiry(date.today().isoformat()) == 0
