"""
Weekly report data aggregation.

Queries the database for a date range and organizes receipts
per-employee for Kim's weekly email report.

Spec: "Framed as 'Here is Omar's week' — not one giant data dump.
Each section: daily spend summary at top, full transaction breakdown below.
Flagged receipts clearly marked."
"""

import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


def get_weekly_report_data(db, week_start: str = None, week_end: str = None) -> dict:
    """Build the full weekly report data structure.

    Args:
        db: SQLite connection.
        week_start: YYYY-MM-DD start date (defaults to last Monday).
        week_end: YYYY-MM-DD end date (defaults to last Sunday).

    Returns:
        {
            "week_start": "2026-02-09",
            "week_end": "2026-02-15",
            "total_spend": 1234.56,
            "total_receipts": 42,
            "flagged_count": 3,
            "employees": [
                {
                    "name": "Omar",
                    "total_spend": 456.78,
                    "receipt_count": 12,
                    "daily_summary": {
                        "2026-02-09": {"spend": 100.00, "count": 3},
                        ...
                    },
                    "receipts": [ ... ],
                    "flagged_receipts": [ ... ],
                }
            ]
        }
    """
    if not week_start or not week_end:
        week_start, week_end = _default_week_range()

    report = {
        "week_start": week_start,
        "week_end": week_end,
        "total_spend": 0.0,
        "total_receipts": 0,
        "flagged_count": 0,
        "employees": [],
    }

    # Get all active employees who submitted receipts this week
    employees = db.execute(
        """SELECT DISTINCT e.id, e.first_name, e.full_name
           FROM employees e
           JOIN receipts r ON r.employee_id = e.id
           WHERE r.created_at >= ? AND r.created_at < date(?, '+1 day')
           ORDER BY e.first_name""",
        (week_start, week_end),
    ).fetchall()

    for emp in employees:
        emp_data = _build_employee_section(db, emp, week_start, week_end)
        report["employees"].append(emp_data)
        report["total_spend"] += emp_data["total_spend"]
        report["total_receipts"] += emp_data["receipt_count"]
        report["flagged_count"] += len(emp_data["flagged_receipts"])

    report["total_spend"] = round(report["total_spend"], 2)
    return report


def _default_week_range() -> tuple[str, str]:
    """Return (last Monday, last Sunday) as YYYY-MM-DD strings."""
    today = datetime.now().date()
    # Last Monday = most recent Monday before today
    days_since_monday = today.weekday()  # Mon=0, Sun=6
    if days_since_monday == 0:
        # Today is Monday — report covers the previous week
        last_monday = today - timedelta(days=7)
    else:
        last_monday = today - timedelta(days=days_since_monday)
        # If today is mid-week, cover the previous full week
        last_monday = last_monday - timedelta(days=7)

    last_sunday = last_monday + timedelta(days=6)
    return last_monday.isoformat(), last_sunday.isoformat()


def _build_employee_section(db, employee, week_start: str, week_end: str) -> dict:
    """Build one employee's section of the weekly report."""
    emp_id = employee["id"]
    name = employee["full_name"] or employee["first_name"]

    # Get all receipts for this employee in the date range
    receipts = db.execute(
        """SELECT r.*, p.name as project_name
           FROM receipts r
           LEFT JOIN projects p ON r.project_id = p.id
           WHERE r.employee_id = ?
             AND r.created_at >= ?
             AND r.created_at < date(?, '+1 day')
           ORDER BY r.created_at""",
        (emp_id, week_start, week_end),
    ).fetchall()

    total_spend = 0.0
    daily_summary = {}
    receipt_list = []
    flagged_list = []

    for r in receipts:
        receipt_dict = _receipt_to_dict(db, r)
        amount = r["total"] or 0.0
        total_spend += amount

        # Daily summary
        day = (r["purchase_date"] or r["created_at"] or "unknown")[:10]
        if day not in daily_summary:
            daily_summary[day] = {"spend": 0.0, "count": 0}
        daily_summary[day]["spend"] = round(daily_summary[day]["spend"] + amount, 2)
        daily_summary[day]["count"] += 1

        receipt_list.append(receipt_dict)
        if r["status"] == "flagged":
            flagged_list.append(receipt_dict)

    return {
        "id": emp_id,
        "name": name,
        "total_spend": round(total_spend, 2),
        "receipt_count": len(receipts),
        "daily_summary": dict(sorted(daily_summary.items())),
        "receipts": receipt_list,
        "flagged_receipts": flagged_list,
    }


def _receipt_to_dict(db, receipt) -> dict:
    """Convert a receipt row + its line items to a plain dict."""
    # Fetch line items
    items = db.execute(
        """SELECT li.item_name, li.quantity, li.unit_price, li.extended_price,
                  c.name as category_name
           FROM line_items li
           LEFT JOIN categories c ON li.category_id = c.id
           WHERE li.receipt_id = ?
           ORDER BY li.id""",
        (receipt["id"],),
    ).fetchall()

    return {
        "id": receipt["id"],
        "vendor_name": receipt["vendor_name"] or "Unknown",
        "vendor_city": receipt["vendor_city"],
        "vendor_state": receipt["vendor_state"],
        "purchase_date": receipt["purchase_date"],
        "subtotal": receipt["subtotal"],
        "tax": receipt["tax"],
        "total": receipt["total"],
        "payment_method": receipt["payment_method"],
        "status": receipt["status"],
        "flag_reason": receipt["flag_reason"],
        "is_return": bool(receipt["is_return"]),
        "is_missed_receipt": bool(receipt["is_missed_receipt"]),
        "project_name": receipt["project_name"] or receipt["matched_project_name"],
        "created_at": receipt["created_at"],
        "line_items": [
            {
                "item_name": i["item_name"],
                "quantity": i["quantity"],
                "unit_price": i["unit_price"],
                "extended_price": i["extended_price"],
                "category": i["category_name"],
            }
            for i in items
        ],
    }
