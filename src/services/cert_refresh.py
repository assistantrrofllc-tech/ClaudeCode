"""
Automated cert status refresh job.

Scans all certifications, calculates current status, and creates
cert_alerts when status changes (expired, expiring, renewed).

Runs:
  - Daily at 6am via APScheduler
  - On app startup
  - On manual trigger via admin button
"""

import logging
from datetime import datetime

from src.database.connection import get_db
from src.services.cert_status import calculate_cert_status, days_until_expiry

log = logging.getLogger(__name__)


def run_cert_status_refresh(db_path: str | None = None):
    """Scan all certs and create alerts for status changes.

    Args:
        db_path: Optional database path (for testing). Uses default if None.
    """
    db = get_db(db_path) if db_path else get_db()
    try:
        # Ensure cert_alerts table exists
        db.execute("""
            CREATE TABLE IF NOT EXISTS cert_alerts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id     INTEGER NOT NULL,
                cert_id         INTEGER NOT NULL,
                alert_type      TEXT    NOT NULL,
                previous_status TEXT,
                new_status      TEXT,
                days_until_expiry INTEGER,
                acknowledged    INTEGER DEFAULT 0,
                acknowledged_by TEXT,
                acknowledged_at TEXT,
                created_at      TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (employee_id) REFERENCES employees(id),
                FOREIGN KEY (cert_id)     REFERENCES certifications(id)
            )
        """)

        certs = db.execute("""
            SELECT c.id, c.employee_id, c.expires_at, c.cert_type_id,
                   ct.name as cert_type_name,
                   e.first_name, e.full_name
            FROM certifications c
            JOIN certification_types ct ON c.cert_type_id = ct.id
            JOIN employees e ON c.employee_id = e.id
            WHERE c.is_active = 1
        """).fetchall()

        checked = 0
        alerts_created = 0

        for cert in certs:
            checked += 1
            new_status = calculate_cert_status(cert["expires_at"])
            days = days_until_expiry(cert["expires_at"])

            # Check if we already have an unacknowledged alert for this cert
            # with the same status (avoid duplicate alerts)
            existing = db.execute("""
                SELECT id, new_status FROM cert_alerts
                WHERE cert_id = ? AND acknowledged = 0
                ORDER BY created_at DESC LIMIT 1
            """, (cert["id"],)).fetchone()

            if existing and existing["new_status"] == new_status:
                continue  # Same status, no new alert needed

            # Create alert for actionable status changes
            alert_type = None
            if new_status == "expired":
                alert_type = "expired"
            elif new_status == "expiring":
                alert_type = "expiring"

            if alert_type:
                prev_status = existing["new_status"] if existing else None
                db.execute("""
                    INSERT INTO cert_alerts
                    (employee_id, cert_id, alert_type, previous_status, new_status, days_until_expiry)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (cert["employee_id"], cert["id"], alert_type, prev_status, new_status, days))
                alerts_created += 1

                name = cert["full_name"] or cert["first_name"]
                _log_notification(name, cert["cert_type_name"], alert_type, days)

        db.commit()
        log.info(
            "Cert status refresh complete: %d checked, %d alerts created",
            checked, alerts_created,
        )
        return {"checked": checked, "alerts_created": alerts_created}
    except Exception:
        log.exception("Cert status refresh failed")
        raise
    finally:
        db.close()


def _log_notification(employee_name, cert_name, alert_type, days):
    """Log notification (scaffold for future email/SMS)."""
    if alert_type == "expired":
        log.warning(
            "CERT ALERT: %s — %s — EXPIRED (%d days ago)",
            employee_name, cert_name, abs(days) if days else 0,
        )
    elif alert_type == "expiring":
        log.warning(
            "CERT ALERT: %s — %s — expiring in %d days",
            employee_name, cert_name, days or 0,
        )
    # TODO: email_admin(alert) when email configured
    # TODO: sms_employee(alert) when A2P approved
