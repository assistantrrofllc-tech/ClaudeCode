"""
QuickBooks CSV export endpoint.

Exports receipt data as a QuickBooks-ready CSV file.
The accountant can use this immediately — no dashboard required.

GET /export/quickbooks
    Optional query params:
        week_start  — ISO date (default: last Monday)
        week_end    — ISO date (default: last Sunday)
        employee_id — filter by specific employee
        project     — filter by project name
        category    — filter by category
"""

import csv
import io
import logging
from datetime import datetime, timedelta

from flask import Blueprint, request, Response

from src.database.connection import get_db
from src.services.auth import login_required

log = logging.getLogger(__name__)

export_bp = Blueprint("export", __name__)


def _default_week_range() -> tuple[str, str]:
    """Return (last Monday, last Sunday) as YYYY-MM-DD strings."""
    today = datetime.now().date()
    days_since_monday = today.weekday()  # Mon=0, Sun=6
    if days_since_monday == 0:
        last_monday = today - timedelta(days=7)
    else:
        last_monday = today - timedelta(days=days_since_monday + 7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday.isoformat(), last_sunday.isoformat()


@export_bp.route("/export/quickbooks", methods=["GET"])
@login_required
def quickbooks_export():
    """Export receipts as a QuickBooks-ready CSV download.

    Filters:
        week_start  — YYYY-MM-DD (default: last Monday)
        week_end    — YYYY-MM-DD (default: last Sunday)
        employee_id — integer employee ID
        project     — project name (exact match)
        category    — category name (matches any line item category)
    """
    week_start = request.args.get("week_start")
    week_end = request.args.get("week_end")
    employee_id = request.args.get("employee_id", type=int)
    project = request.args.get("project")
    category = request.args.get("category")

    if not week_start or not week_end:
        week_start, week_end = _default_week_range()

    db = get_db()
    try:
        rows = _query_receipts(db, week_start, week_end, employee_id, project, category)
        csv_content = _build_csv(rows)

        # Build filename with date range
        filename = f"crewledger_export_{week_start}_to_{week_end}.csv"

        return Response(
            csv_content,
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
            },
        )
    finally:
        db.close()


def _query_receipts(
    db,
    week_start: str,
    week_end: str,
    employee_id: int = None,
    project: str = None,
    category: str = None,
) -> list[dict]:
    """Query receipts with optional filters and join employee + line item data."""

    # Base query — join receipts with employees and projects
    sql = """
        SELECT
            r.id AS receipt_id,
            r.purchase_date,
            r.vendor_name,
            r.subtotal,
            r.tax AS tax_amount,
            r.total AS total_amount,
            r.payment_method,
            r.matched_project_name,
            e.first_name,
            e.full_name,
            p.name AS project_name
        FROM receipts r
        JOIN employees e ON r.employee_id = e.id
        LEFT JOIN projects p ON r.project_id = p.id
        WHERE r.purchase_date >= ?
          AND r.purchase_date <= ?
          AND r.status IN ('confirmed', 'pending')
    """
    params: list = [week_start, week_end]

    if employee_id is not None:
        sql += " AND r.employee_id = ?"
        params.append(employee_id)

    if project:
        sql += " AND (p.name = ? OR r.matched_project_name = ?)"
        params.append(project)
        params.append(project)

    sql += " ORDER BY r.purchase_date, r.id"

    receipts = db.execute(sql, params).fetchall()

    results = []
    for r in receipts:
        # Get line items for this receipt
        items = db.execute(
            """SELECT li.item_name, li.quantity, li.unit_price, li.extended_price,
                      c.name AS category_name
               FROM line_items li
               LEFT JOIN categories c ON li.category_id = c.id
               WHERE li.receipt_id = ?
               ORDER BY li.id""",
            (r["receipt_id"],),
        ).fetchall()

        # If category filter is set, check if any line item matches
        if category:
            has_matching_category = any(
                i["category_name"] and i["category_name"].lower() == category.lower()
                for i in items
            )
            if not has_matching_category:
                continue

        # Determine the category to use (most common among line items, or first)
        item_categories = [i["category_name"] for i in items if i["category_name"]]
        primary_category = item_categories[0] if item_categories else ""

        # Build pipe-separated line items summary
        item_summaries = []
        for item in items:
            qty = f" x{item['quantity']:.0f}" if item["quantity"] and item["quantity"] != 1 else ""
            price = f"${item['extended_price']:,.2f}" if item["extended_price"] is not None else ""
            item_summaries.append(f"{item['item_name']}{qty} ({price})")
        line_items_str = " | ".join(item_summaries)

        # Employee display name
        emp_name = r["full_name"] or r["first_name"]

        # Project name — prefer the projects table, fall back to matched_project_name
        proj = r["project_name"] or r["matched_project_name"] or ""

        # Memo: "Project Sparrow — Omar"
        memo_parts = []
        if proj:
            memo_parts.append(proj)
        memo_parts.append(emp_name)
        memo = " — ".join(memo_parts)

        results.append({
            "Date": _format_date_mm_dd_yyyy(r["purchase_date"]),
            "Vendor": r["vendor_name"] or "",
            "Account": primary_category,
            "Amount": r["subtotal"] if r["subtotal"] is not None else "",
            "Tax": r["tax_amount"] if r["tax_amount"] is not None else "",
            "Total": r["total_amount"] if r["total_amount"] is not None else "",
            "Payment Method": r["payment_method"] or "",
            "Memo": memo,
            "Line Items": line_items_str,
        })

    return results


def _build_csv(rows: list[dict]) -> str:
    """Build a CSV string from the receipt data rows."""
    output = io.StringIO()
    fieldnames = [
        "Date",
        "Vendor",
        "Account",
        "Amount",
        "Tax",
        "Total",
        "Payment Method",
        "Memo",
        "Line Items",
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

    return output.getvalue()


def _format_date_mm_dd_yyyy(date_str: str) -> str:
    """Convert YYYY-MM-DD to MM/DD/YYYY for QuickBooks."""
    if not date_str:
        return ""
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return d.strftime("%m/%d/%Y")
    except (ValueError, TypeError):
        return date_str
