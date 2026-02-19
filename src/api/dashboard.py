"""
Dashboard API endpoints.

Powers the mobile-first web dashboard with JSON data for:
- Home screen (summary stats, spend breakdown, recent activity)
- Flagged receipt review queue
- Search & filter with export integration
- Drill-down: employee receipts, receipt detail with image

Management only — no employee-facing views.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, request, jsonify, render_template, send_from_directory, abort

from src.database.connection import get_db

log = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__)


# ── Page routes ────────────────────────────────────────────────


@dashboard_bp.route("/")
@dashboard_bp.route("/dashboard")
def dashboard_home():
    """Serve the single-page dashboard HTML."""
    return render_template("dashboard.html")


# ── API: Home screen data ─────────────────────────────────────


@dashboard_bp.route("/api/dashboard/summary", methods=["GET"])
def dashboard_summary():
    """Home screen data: week total, quick stats, flagged count, recent activity.

    Query params:
        week_start — YYYY-MM-DD (default: last Monday)
        week_end   — YYYY-MM-DD (default: last Sunday)
    """
    week_start = request.args.get("week_start")
    week_end = request.args.get("week_end")

    if not week_start or not week_end:
        week_start, week_end = _default_week_range()

    # Also compute the previous week for comparison
    ws = datetime.strptime(week_start, "%Y-%m-%d").date()
    we = datetime.strptime(week_end, "%Y-%m-%d").date()
    prev_start = (ws - timedelta(days=7)).isoformat()
    prev_end = (we - timedelta(days=7)).isoformat()

    db = get_db()
    try:
        # Current week totals
        current = db.execute(
            """SELECT
                   COALESCE(SUM(total), 0) AS total_spend,
                   COUNT(*) AS receipt_count
               FROM receipts
               WHERE purchase_date >= ? AND purchase_date <= ?
                 AND status IN ('confirmed', 'pending')""",
            (week_start, week_end),
        ).fetchone()

        # Previous week totals (for comparison)
        previous = db.execute(
            """SELECT
                   COALESCE(SUM(total), 0) AS total_spend,
                   COUNT(*) AS receipt_count
               FROM receipts
               WHERE purchase_date >= ? AND purchase_date <= ?
                 AND status IN ('confirmed', 'pending')""",
            (prev_start, prev_end),
        ).fetchone()

        # Flagged count (all time, unresolved)
        flagged = db.execute(
            "SELECT COUNT(*) AS cnt FROM receipts WHERE status = 'flagged'"
        ).fetchone()

        # Spend breakdown by crew (employee)
        by_crew = db.execute(
            """SELECT e.id AS employee_id, e.first_name, e.full_name, e.crew,
                      COALESCE(SUM(r.total), 0) AS spend,
                      COUNT(r.id) AS receipt_count
               FROM receipts r
               JOIN employees e ON r.employee_id = e.id
               WHERE r.purchase_date >= ? AND r.purchase_date <= ?
                 AND r.status IN ('confirmed', 'pending')
               GROUP BY e.id
               ORDER BY spend DESC""",
            (week_start, week_end),
        ).fetchall()

        # Spend breakdown by project
        by_project = db.execute(
            """SELECT COALESCE(p.name, r.matched_project_name, 'Unassigned') AS project_name,
                      COALESCE(SUM(r.total), 0) AS spend,
                      COUNT(r.id) AS receipt_count
               FROM receipts r
               LEFT JOIN projects p ON r.project_id = p.id
               WHERE r.purchase_date >= ? AND r.purchase_date <= ?
                 AND r.status IN ('confirmed', 'pending')
               GROUP BY project_name
               ORDER BY spend DESC""",
            (week_start, week_end),
        ).fetchall()

        # Spend breakdown by cardholder (payment method)
        by_cardholder = db.execute(
            """SELECT COALESCE(r.payment_method, 'Unknown') AS payment_method,
                      COALESCE(SUM(r.total), 0) AS spend,
                      COUNT(r.id) AS receipt_count
               FROM receipts r
               WHERE r.purchase_date >= ? AND r.purchase_date <= ?
                 AND r.status IN ('confirmed', 'pending')
               GROUP BY payment_method
               ORDER BY spend DESC""",
            (week_start, week_end),
        ).fetchall()

        # Recent activity — last 10 receipts
        recent = db.execute(
            """SELECT r.id, r.vendor_name, r.total, r.purchase_date, r.status,
                      r.matched_project_name, r.created_at, r.image_path,
                      e.id AS employee_id, e.first_name, e.full_name,
                      p.name AS project_name
               FROM receipts r
               JOIN employees e ON r.employee_id = e.id
               LEFT JOIN projects p ON r.project_id = p.id
               ORDER BY r.created_at DESC
               LIMIT 10""",
        ).fetchall()

        return jsonify({
            "week_start": week_start,
            "week_end": week_end,
            "current_week": {
                "total_spend": round(current["total_spend"], 2),
                "receipt_count": current["receipt_count"],
            },
            "previous_week": {
                "total_spend": round(previous["total_spend"], 2),
                "receipt_count": previous["receipt_count"],
            },
            "flagged_count": flagged["cnt"],
            "by_crew": [
                {
                    "id": r["employee_id"],
                    "name": r["full_name"] or r["first_name"],
                    "crew": r["crew"] or "",
                    "spend": round(r["spend"], 2),
                    "receipt_count": r["receipt_count"],
                }
                for r in by_crew
            ],
            "by_project": [
                {
                    "name": r["project_name"],
                    "spend": round(r["spend"], 2),
                    "receipt_count": r["receipt_count"],
                }
                for r in by_project
            ],
            "by_cardholder": [
                {
                    "name": r["payment_method"],
                    "spend": round(r["spend"], 2),
                    "receipt_count": r["receipt_count"],
                }
                for r in by_cardholder
            ],
            "recent_activity": [
                {
                    "id": r["id"],
                    "vendor": r["vendor_name"] or "Unknown",
                    "total": r["total"],
                    "date": r["purchase_date"],
                    "status": r["status"],
                    "project": r["project_name"] or r["matched_project_name"] or "",
                    "employee": r["full_name"] or r["first_name"],
                    "employee_id": r["employee_id"],
                    "has_image": bool(r["image_path"]),
                    "created_at": r["created_at"],
                }
                for r in recent
            ],
        })
    finally:
        db.close()


# ── API: Flagged receipts queue ────────────────────────────────


@dashboard_bp.route("/api/dashboard/flagged", methods=["GET"])
def flagged_receipts():
    """Return all flagged receipts for the review queue."""
    db = get_db()
    try:
        rows = db.execute(
            """SELECT r.id, r.vendor_name, r.total, r.purchase_date, r.status,
                      r.flag_reason, r.image_path, r.is_missed_receipt, r.is_return,
                      r.matched_project_name, r.created_at, r.subtotal, r.tax,
                      r.payment_method,
                      e.first_name, e.full_name,
                      p.name AS project_name
               FROM receipts r
               JOIN employees e ON r.employee_id = e.id
               LEFT JOIN projects p ON r.project_id = p.id
               WHERE r.status = 'flagged'
               ORDER BY r.created_at DESC""",
        ).fetchall()

        results = []
        for r in rows:
            # Get line items
            items = db.execute(
                """SELECT item_name, quantity, unit_price, extended_price
                   FROM line_items WHERE receipt_id = ? ORDER BY id""",
                (r["id"],),
            ).fetchall()

            results.append({
                "id": r["id"],
                "vendor": r["vendor_name"] or "Unknown",
                "total": r["total"],
                "subtotal": r["subtotal"],
                "tax": r["tax"],
                "date": r["purchase_date"],
                "flag_reason": r["flag_reason"] or "No reason specified",
                "image_path": r["image_path"],
                "is_missed": bool(r["is_missed_receipt"]),
                "is_return": bool(r["is_return"]),
                "payment_method": r["payment_method"] or "",
                "project": r["project_name"] or r["matched_project_name"] or "",
                "employee": r["full_name"] or r["first_name"],
                "created_at": r["created_at"],
                "line_items": [
                    {
                        "name": i["item_name"],
                        "qty": i["quantity"],
                        "price": i["extended_price"],
                    }
                    for i in items
                ],
            })

        return jsonify({"flagged": results, "count": len(results)})
    finally:
        db.close()


@dashboard_bp.route("/api/dashboard/flagged/<int:receipt_id>/approve", methods=["POST"])
def approve_receipt(receipt_id):
    """Approve a flagged receipt — sets status to confirmed."""
    db = get_db()
    try:
        receipt = db.execute("SELECT id, status FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
        if not receipt:
            return jsonify({"error": "Receipt not found"}), 404
        if receipt["status"] != "flagged":
            return jsonify({"error": "Receipt is not flagged"}), 400

        db.execute(
            "UPDATE receipts SET status = 'confirmed', confirmed_at = datetime('now') WHERE id = ?",
            (receipt_id,),
        )
        db.commit()
        log.info("Receipt #%d approved via dashboard", receipt_id)
        return jsonify({"status": "approved", "id": receipt_id})
    finally:
        db.close()


@dashboard_bp.route("/api/dashboard/flagged/<int:receipt_id>/dismiss", methods=["POST"])
def dismiss_receipt(receipt_id):
    """Dismiss a flagged receipt — sets status to rejected."""
    db = get_db()
    try:
        receipt = db.execute("SELECT id, status FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
        if not receipt:
            return jsonify({"error": "Receipt not found"}), 404
        if receipt["status"] != "flagged":
            return jsonify({"error": "Receipt is not flagged"}), 400

        db.execute(
            "UPDATE receipts SET status = 'rejected' WHERE id = ?",
            (receipt_id,),
        )
        db.commit()
        log.info("Receipt #%d dismissed via dashboard", receipt_id)
        return jsonify({"status": "dismissed", "id": receipt_id})
    finally:
        db.close()


@dashboard_bp.route("/api/dashboard/flagged/<int:receipt_id>/edit", methods=["POST"])
def edit_receipt(receipt_id):
    """Edit a flagged receipt's fields, then approve it."""
    data = request.get_json(silent=True) or {}
    db = get_db()
    try:
        receipt = db.execute("SELECT id, status FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
        if not receipt:
            return jsonify({"error": "Receipt not found"}), 404

        # Build update dynamically from provided fields
        updatable = {
            "vendor_name": data.get("vendor"),
            "total": data.get("total"),
            "subtotal": data.get("subtotal"),
            "tax": data.get("tax"),
            "purchase_date": data.get("date"),
            "payment_method": data.get("payment_method"),
            "matched_project_name": data.get("project"),
        }
        # Filter out None values
        updates = {k: v for k, v in updatable.items() if v is not None}

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values())
            values.append(receipt_id)
            db.execute(
                f"UPDATE receipts SET {set_clause}, status = 'confirmed', confirmed_at = datetime('now') WHERE id = ?",
                values,
            )
        else:
            db.execute(
                "UPDATE receipts SET status = 'confirmed', confirmed_at = datetime('now') WHERE id = ?",
                (receipt_id,),
            )

        db.commit()
        log.info("Receipt #%d edited and approved via dashboard", receipt_id)
        return jsonify({"status": "updated", "id": receipt_id})
    finally:
        db.close()


# ── API: Search & filter ──────────────────────────────────────


@dashboard_bp.route("/api/dashboard/search", methods=["GET"])
def search_receipts():
    """Search receipts with filters.

    Query params:
        date_start   — YYYY-MM-DD
        date_end     — YYYY-MM-DD
        employee     — employee name (partial match)
        employee_id  — employee ID (exact)
        project      — project name (partial match)
        vendor       — vendor name (partial match)
        category     — category name
        amount_min   — minimum total
        amount_max   — maximum total
        status       — confirmed, pending, flagged, rejected
        sort         — date, amount, employee, vendor, project (default: date)
        order        — asc, desc (default: desc)
        page         — page number (default: 1)
        per_page     — results per page (default: 25)
    """
    date_start = request.args.get("date_start")
    date_end = request.args.get("date_end")
    employee = request.args.get("employee")
    employee_id = request.args.get("employee_id", type=int)
    project = request.args.get("project")
    vendor = request.args.get("vendor")
    category = request.args.get("category")
    amount_min = request.args.get("amount_min", type=float)
    amount_max = request.args.get("amount_max", type=float)
    status = request.args.get("status")
    sort_by = request.args.get("sort", "date")
    order = request.args.get("order", "desc")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)

    db = get_db()
    try:
        sql = """
            SELECT r.id, r.vendor_name, r.vendor_city, r.vendor_state,
                   r.total, r.subtotal, r.tax, r.purchase_date, r.status,
                   r.payment_method, r.image_path, r.flag_reason,
                   r.is_missed_receipt, r.is_return,
                   r.matched_project_name, r.created_at,
                   e.first_name, e.full_name, e.id AS employee_id,
                   p.name AS project_name
            FROM receipts r
            JOIN employees e ON r.employee_id = e.id
            LEFT JOIN projects p ON r.project_id = p.id
            WHERE 1=1
        """
        params: list = []

        if date_start:
            sql += " AND r.purchase_date >= ?"
            params.append(date_start)
        if date_end:
            sql += " AND r.purchase_date <= ?"
            params.append(date_end)
        if employee:
            sql += " AND (e.first_name LIKE ? OR e.full_name LIKE ?)"
            params.extend([f"%{employee}%", f"%{employee}%"])
        if employee_id is not None:
            sql += " AND e.id = ?"
            params.append(employee_id)
        if project:
            sql += " AND (p.name LIKE ? OR r.matched_project_name LIKE ?)"
            params.extend([f"%{project}%", f"%{project}%"])
        if vendor:
            sql += " AND r.vendor_name LIKE ?"
            params.append(f"%{vendor}%")
        if amount_min is not None:
            sql += " AND r.total >= ?"
            params.append(amount_min)
        if amount_max is not None:
            sql += " AND r.total <= ?"
            params.append(amount_max)
        if status:
            sql += " AND r.status = ?"
            params.append(status)

        # Category filter requires a subquery on line_items
        if category:
            sql += """ AND r.id IN (
                SELECT li.receipt_id FROM line_items li
                JOIN categories c ON li.category_id = c.id
                WHERE c.name LIKE ?
            )"""
            params.append(f"%{category}%")

        # Sorting
        sort_map = {
            "date": "r.purchase_date",
            "amount": "r.total",
            "employee": "e.first_name",
            "vendor": "r.vendor_name",
            "project": "COALESCE(p.name, r.matched_project_name)",
        }
        sort_col = sort_map.get(sort_by, "r.purchase_date")
        sort_dir = "ASC" if order == "asc" else "DESC"
        sql += f" ORDER BY {sort_col} {sort_dir}"

        # Count total results before pagination
        count_sql = f"SELECT COUNT(*) AS cnt FROM ({sql})"
        total_count = db.execute(count_sql, params).fetchone()["cnt"]

        # Pagination
        offset = (page - 1) * per_page
        sql += " LIMIT ? OFFSET ?"
        params.extend([per_page, offset])

        rows = db.execute(sql, params).fetchall()

        results = []
        for r in rows:
            items = db.execute(
                """SELECT li.item_name, li.quantity, li.extended_price,
                          c.name AS category_name
                   FROM line_items li
                   LEFT JOIN categories c ON li.category_id = c.id
                   WHERE li.receipt_id = ? ORDER BY li.id""",
                (r["id"],),
            ).fetchall()

            results.append({
                "id": r["id"],
                "vendor": r["vendor_name"] or "Unknown",
                "vendor_city": r["vendor_city"] or "",
                "vendor_state": r["vendor_state"] or "",
                "total": r["total"],
                "subtotal": r["subtotal"],
                "tax": r["tax"],
                "date": r["purchase_date"],
                "status": r["status"],
                "payment_method": r["payment_method"] or "",
                "image_path": r["image_path"],
                "flag_reason": r["flag_reason"],
                "is_missed": bool(r["is_missed_receipt"]),
                "is_return": bool(r["is_return"]),
                "project": r["project_name"] or r["matched_project_name"] or "",
                "employee": r["full_name"] or r["first_name"],
                "employee_id": r["employee_id"],
                "created_at": r["created_at"],
                "line_items": [
                    {
                        "name": i["item_name"],
                        "qty": i["quantity"],
                        "price": i["extended_price"],
                        "category": i["category_name"],
                    }
                    for i in items
                ],
            })

        # Get filter options for the UI
        employees_list = db.execute(
            "SELECT id, first_name, full_name FROM employees WHERE is_active = 1 ORDER BY first_name"
        ).fetchall()
        projects_list = db.execute(
            "SELECT id, name FROM projects WHERE status = 'active' ORDER BY name"
        ).fetchall()
        categories_list = db.execute(
            "SELECT id, name FROM categories ORDER BY name"
        ).fetchall()

        return jsonify({
            "results": results,
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, -(-total_count // per_page)),  # ceil division
            "filters": {
                "employees": [{"id": e["id"], "name": e["full_name"] or e["first_name"]} for e in employees_list],
                "projects": [{"id": p["id"], "name": p["name"]} for p in projects_list],
                "categories": [{"id": c["id"], "name": c["name"]} for c in categories_list],
            },
        })
    finally:
        db.close()


# ── API: Employee receipts drill-down ─────────────────────────


@dashboard_bp.route("/api/dashboard/employee/<int:employee_id>/receipts", methods=["GET"])
def employee_receipts(employee_id):
    """Return all receipts for a given employee, newest first.

    Query params:
        status — optional filter (confirmed, pending, flagged, rejected)
        limit  — max rows (default: 50)
    """
    status_filter = request.args.get("status")
    limit = request.args.get("limit", 50, type=int)

    db = get_db()
    try:
        # Get employee info
        emp = db.execute(
            "SELECT id, first_name, full_name, phone_number, crew FROM employees WHERE id = ?",
            (employee_id,),
        ).fetchone()
        if not emp:
            return jsonify({"error": "Employee not found"}), 404

        sql = """
            SELECT r.id, r.vendor_name, r.total, r.subtotal, r.tax,
                   r.purchase_date, r.status, r.payment_method,
                   r.image_path, r.flag_reason, r.is_missed_receipt,
                   r.is_return, r.matched_project_name, r.created_at,
                   p.name AS project_name
            FROM receipts r
            LEFT JOIN projects p ON r.project_id = p.id
            WHERE r.employee_id = ?
        """
        params: list = [employee_id]

        if status_filter:
            sql += " AND r.status = ?"
            params.append(status_filter)

        sql += " ORDER BY r.created_at DESC LIMIT ?"
        params.append(limit)

        rows = db.execute(sql, params).fetchall()

        results = []
        for r in rows:
            items = db.execute(
                """SELECT item_name, quantity, unit_price, extended_price
                   FROM line_items WHERE receipt_id = ? ORDER BY id""",
                (r["id"],),
            ).fetchall()

            results.append({
                "id": r["id"],
                "vendor": r["vendor_name"] or "Unknown",
                "total": r["total"],
                "subtotal": r["subtotal"],
                "tax": r["tax"],
                "date": r["purchase_date"],
                "status": r["status"],
                "payment_method": r["payment_method"] or "",
                "image_path": r["image_path"],
                "flag_reason": r["flag_reason"],
                "is_missed": bool(r["is_missed_receipt"]),
                "is_return": bool(r["is_return"]),
                "project": r["project_name"] or r["matched_project_name"] or "",
                "created_at": r["created_at"],
                "line_items": [
                    {
                        "name": i["item_name"],
                        "qty": i["quantity"],
                        "price": i["extended_price"],
                    }
                    for i in items
                ],
            })

        return jsonify({
            "employee": {
                "id": emp["id"],
                "name": emp["full_name"] or emp["first_name"],
                "phone": emp["phone_number"],
                "crew": emp["crew"] or "",
            },
            "receipts": results,
            "count": len(results),
        })
    finally:
        db.close()


# ── API: Receipt detail ──────────────────────────────────────


@dashboard_bp.route("/api/dashboard/receipt/<int:receipt_id>", methods=["GET"])
def receipt_detail(receipt_id):
    """Return full detail for a single receipt including line items and image path."""
    db = get_db()
    try:
        r = db.execute(
            """SELECT r.id, r.vendor_name, r.vendor_city, r.vendor_state,
                      r.total, r.subtotal, r.tax, r.purchase_date, r.status,
                      r.payment_method, r.image_path, r.flag_reason,
                      r.is_missed_receipt, r.is_return,
                      r.matched_project_name, r.created_at, r.confirmed_at,
                      r.raw_ocr_json,
                      e.first_name, e.full_name, e.phone_number, e.id AS employee_id,
                      p.name AS project_name
               FROM receipts r
               JOIN employees e ON r.employee_id = e.id
               LEFT JOIN projects p ON r.project_id = p.id
               WHERE r.id = ?""",
            (receipt_id,),
        ).fetchone()

        if not r:
            return jsonify({"error": "Receipt not found"}), 404

        items = db.execute(
            """SELECT li.item_name, li.quantity, li.unit_price, li.extended_price,
                      c.name AS category_name
               FROM line_items li
               LEFT JOIN categories c ON li.category_id = c.id
               WHERE li.receipt_id = ? ORDER BY li.id""",
            (receipt_id,),
        ).fetchall()

        # Check if image file actually exists
        has_image = False
        if r["image_path"]:
            img_full = Path(r["image_path"])
            if not img_full.is_absolute():
                img_full = Path(__file__).resolve().parent.parent.parent / r["image_path"]
            has_image = img_full.exists()

        return jsonify({
            "id": r["id"],
            "vendor": r["vendor_name"] or "Unknown",
            "vendor_city": r["vendor_city"] or "",
            "vendor_state": r["vendor_state"] or "",
            "total": r["total"],
            "subtotal": r["subtotal"],
            "tax": r["tax"],
            "date": r["purchase_date"],
            "status": r["status"],
            "payment_method": r["payment_method"] or "",
            "image_path": r["image_path"],
            "has_image": has_image,
            "flag_reason": r["flag_reason"],
            "is_missed": bool(r["is_missed_receipt"]),
            "is_return": bool(r["is_return"]),
            "project": r["project_name"] or r["matched_project_name"] or "",
            "employee": r["full_name"] or r["first_name"],
            "employee_id": r["employee_id"],
            "phone": r["phone_number"],
            "created_at": r["created_at"],
            "confirmed_at": r["confirmed_at"],
            "line_items": [
                {
                    "name": i["item_name"],
                    "qty": i["quantity"],
                    "unit_price": i["unit_price"],
                    "price": i["extended_price"],
                    "category": i["category_name"],
                }
                for i in items
            ],
        })
    finally:
        db.close()


# ── Receipt image serving ─────────────────────────────────────


@dashboard_bp.route("/receipt-image/<int:receipt_id>")
def serve_receipt_image(receipt_id):
    """Serve the receipt image file for a given receipt."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT image_path FROM receipts WHERE id = ?", (receipt_id,)
        ).fetchone()
    finally:
        db.close()

    if not row or not row["image_path"]:
        abort(404)

    image_path = Path(row["image_path"])
    if not image_path.is_absolute():
        image_path = Path(__file__).resolve().parent.parent.parent / row["image_path"]

    if not image_path.exists():
        abort(404)

    return send_from_directory(
        str(image_path.parent), image_path.name,
    )


# ── Helpers ────────────────────────────────────────────────────


def _default_week_range() -> tuple[str, str]:
    """Return (last Monday, last Sunday) as YYYY-MM-DD strings."""
    today = datetime.now().date()
    days_since_monday = today.weekday()
    if days_since_monday == 0:
        last_monday = today - timedelta(days=7)
    else:
        last_monday = today - timedelta(days=days_since_monday + 7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday.isoformat(), last_sunday.isoformat()
