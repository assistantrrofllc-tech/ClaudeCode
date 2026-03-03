"""
CrewStock routes — CrewInventory module.

QR-code-driven inventory management: shop inventory dashboard, item CRUD,
QR label generation, mobile scanner, cart/checkout, project inventory lifecycle.

Phase 2: vendor management, item images, project inventory docs,
item detail, quick reorder, CrewAsset cross-wire.
"""

import io
import json
import logging
import os
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Blueprint, render_template, jsonify, request, abort, session, Response,
    send_file, send_from_directory,
)

from config.settings import STOCK_IMAGE_STORAGE_PATH, INVENTORY_DOC_STORAGE_PATH
from src.database.connection import get_db
from src.services.auth import login_required
from src.services.permissions import (
    get_current_role, require_module_access,
)

log = logging.getLogger(__name__)

stock_bp = Blueprint("stock", __name__)

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

# ── Phase 1 access lock ──────────────────────────────────────

STOCK_ALLOWED_EMAILS = {"rob.rrofllc@gmail.com"}


def require_stock_access(f):
    """Phase-1 decorator: restrict CrewStock to allow-listed emails."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = session.get("user")
        if not user:
            abort(403)
        email = (user.get("email") or "").lower().strip()
        if email not in STOCK_ALLOWED_EMAILS:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── Module navigation ─────────────────────────────────────────

MODULE_NAVS = {
    "crewinventory": [
        {"id": "dashboard", "label": "Dashboard", "href": "/stock/"},
        {"id": "items", "label": "Items", "href": "/stock/items"},
        {"id": "vendors", "label": "Vendors", "href": "/stock/vendors"},
        {"id": "scanner", "label": "Scanner", "href": "/stock/scan"},
        {"id": "labels", "label": "Labels", "href": "/stock/labels"},
        {"id": "reorder", "label": "Reorder", "href": "/stock/reorder"},
    ],
}


def _render_stock(template, active_subnav="", **kwargs):
    """Render a template with CrewInventory module navigation context."""
    role = get_current_role()
    role_level = {"super_admin": 4, "company_admin": 3, "manager": 2, "employee": 1}.get(role, 1)
    nav_items = MODULE_NAVS.get("crewinventory", [])
    defaults = {
        "can_edit": role_level >= 3,
        "can_export": role_level >= 3,
        "user_role": role,
    }
    defaults.update(kwargs)
    return render_template(
        template,
        active_module="crewinventory",
        active_subnav=active_subnav,
        module_nav=nav_items,
        **defaults,
    )


# ── CrewAsset cross-wire helper ───────────────────────────────


def _sync_tool_to_asset(db, item_id):
    """On item create/update where category='tool', create/update assets row."""
    try:
        item = db.execute(
            "SELECT id, name, vendor_id, category FROM stock_items WHERE id = ?",
            (item_id,),
        ).fetchone()
        if not item or (item["category"] or "").lower() != "tool":
            return

        existing = db.execute(
            "SELECT id FROM assets WHERE stock_item_id = ?", (item_id,)
        ).fetchone()

        if existing:
            db.execute(
                """UPDATE assets SET name = ?, vendor_id = ?, updated_at = datetime('now')
                   WHERE stock_item_id = ?""",
                (item["name"], item["vendor_id"], item_id),
            )
        else:
            db.execute(
                """INSERT INTO assets (name, category, stock_item_id, vendor_id)
                   VALUES (?, 'tool', ?, ?)""",
                (item["name"], item_id, item["vendor_id"]),
            )
    except Exception:
        # Gracefully skip if assets table doesn't exist yet
        pass


# ══════════════════════════════════════════════════════════════
# PAGES
# ══════════════════════════════════════════════════════════════


@stock_bp.route("/stock/")
@login_required
@require_stock_access
def stock_dashboard():
    """Shop inventory dashboard — landing page."""
    return _render_stock("stock_dashboard.html", active_subnav="dashboard")


@stock_bp.route("/stock/items")
@login_required
@require_stock_access
def stock_items_page():
    """Item management CRUD page."""
    return _render_stock("stock_items.html", active_subnav="items")


@stock_bp.route("/stock/vendors")
@login_required
@require_stock_access
def stock_vendors_page():
    """Vendor management page."""
    return _render_stock("stock_vendors.html", active_subnav="vendors")


@stock_bp.route("/stock/scan")
@login_required
@require_stock_access
def stock_scanner_page():
    """QR scanner + cart page (mobile-first)."""
    return _render_stock("stock_scanner.html", active_subnav="scanner")


@stock_bp.route("/stock/labels")
@login_required
@require_stock_access
def stock_labels_page():
    """QR label generator page."""
    return _render_stock("stock_labels.html", active_subnav="labels")


@stock_bp.route("/stock/reorder")
@login_required
@require_stock_access
def stock_reorder_page():
    """Reorder review/history page."""
    return _render_stock("stock_reorder.html", active_subnav="reorder")


@stock_bp.route("/stock/project/<int:project_id>")
@login_required
@require_stock_access
def stock_project_page(project_id):
    """Project inventory view."""
    db = get_db()
    try:
        project = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not project:
            abort(404)
        return _render_stock(
            "stock_project.html",
            active_subnav="dashboard",
            project=dict(project),
        )
    finally:
        db.close()


@stock_bp.route("/stock/project/<int:project_id>/upload")
@login_required
@require_stock_access
def stock_project_upload_page(project_id):
    """Project document upload page (PO/invoice)."""
    db = get_db()
    try:
        project = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not project:
            abort(404)
        return _render_stock(
            "stock_project_upload.html",
            active_subnav="dashboard",
            project=dict(project),
        )
    finally:
        db.close()


@stock_bp.route("/stock/items/<int:item_id>")
@login_required
@require_stock_access
def stock_item_detail_page(item_id):
    """Item detail page."""
    db = get_db()
    try:
        item = db.execute("SELECT * FROM stock_items WHERE id = ?", (item_id,)).fetchone()
        if not item:
            abort(404)
        return _render_stock(
            "stock_item_detail.html",
            active_subnav="items",
            item=dict(item),
        )
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Dashboard
# ══════════════════════════════════════════════════════════════


@stock_bp.route("/stock/api/dashboard")
@login_required
@require_stock_access
def api_dashboard():
    """Dashboard summary stats."""
    db = get_db()
    try:
        total_items = db.execute("SELECT COUNT(*) AS c FROM stock_items").fetchone()["c"]
        total_qty = db.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS c FROM shop_inventory"
        ).fetchone()["c"]

        # Low stock: items where total shop qty <= reorder_point
        low_stock = db.execute("""
            SELECT COUNT(*) AS c FROM stock_items si
            WHERE si.reorder_point > 0
              AND (SELECT COALESCE(SUM(inv.quantity), 0) FROM shop_inventory inv
                   WHERE inv.item_id = si.id) <= si.reorder_point
        """).fetchone()["c"]

        checked_out = db.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS c FROM project_inventory WHERE quantity > 0"
        ).fetchone()["c"]

        shops = [dict(r) for r in db.execute("SELECT * FROM stock_shops ORDER BY name").fetchall()]

        # Projects with inventory for dashboard tabs
        projects_with_inv = db.execute("""
            SELECT p.id, p.name,
                   COALESCE(SUM(pi.quantity), 0) AS total_qty
            FROM projects p
            JOIN project_inventory pi ON pi.project_id = p.id
            WHERE pi.quantity > 0
            GROUP BY p.id
            ORDER BY p.name
        """).fetchall()

        return jsonify({
            "total_items": total_items,
            "total_qty": int(total_qty),
            "low_stock": low_stock,
            "checked_out": int(checked_out),
            "shops": shops,
            "projects_with_inventory": [dict(r) for r in projects_with_inv],
        })
    finally:
        db.close()


@stock_bp.route("/stock/api/inventory")
@login_required
@require_stock_access
def api_inventory():
    """Per-shop inventory listing with search, now with vendor info."""
    db = get_db()
    try:
        shop_id = request.args.get("shop_id", type=int)
        search = request.args.get("search", "").strip()

        query = """
            SELECT si.id, si.name, si.sku, si.manufacturer, si.category, si.unit,
                   si.reorder_point, si.qr_code_id, si.image_path, si.vendor_id,
                   inv.quantity, inv.section, inv.shop_id,
                   sh.name AS shop_name,
                   v.name AS vendor_name
            FROM stock_items si
            LEFT JOIN shop_inventory inv ON inv.item_id = si.id
            LEFT JOIN stock_shops sh ON sh.id = inv.shop_id
            LEFT JOIN vendors v ON v.id = si.vendor_id
            WHERE 1=1
        """
        params = []

        if shop_id:
            query += " AND inv.shop_id = ?"
            params.append(shop_id)

        if search:
            query += " AND (si.name LIKE ? OR si.sku LIKE ? OR si.manufacturer LIKE ? OR v.name LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like, like, like])

        query += " ORDER BY si.name"

        rows = db.execute(query, params).fetchall()
        items = []
        for r in rows:
            item = dict(r)
            item["low_stock"] = (
                item["reorder_point"] > 0
                and (item["quantity"] or 0) <= item["reorder_point"]
            )
            items.append(item)

        return jsonify({"items": items})
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Items CRUD
# ══════════════════════════════════════════════════════════════


@stock_bp.route("/stock/api/items", methods=["GET"])
@login_required
@require_stock_access
def api_items_list():
    """List all items in the catalog with vendor info."""
    db = get_db()
    try:
        search = request.args.get("search", "").strip()
        query = """
            SELECT si.*, v.name AS vendor_name
            FROM stock_items si
            LEFT JOIN vendors v ON v.id = si.vendor_id
            WHERE 1=1
        """
        params = []
        if search:
            query += " AND (si.name LIKE ? OR si.sku LIKE ? OR si.manufacturer LIKE ? OR v.name LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like, like, like])
        query += " ORDER BY si.name"
        rows = db.execute(query, params).fetchall()
        return jsonify({"items": [dict(r) for r in rows]})
    finally:
        db.close()


@stock_bp.route("/stock/api/items", methods=["POST"])
@login_required
@require_stock_access
def api_items_create():
    """Create a new item."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Item name is required"}), 400

    db = get_db()
    try:
        qr_code_id = uuid.uuid4().hex[:16]
        vendor_id = data.get("vendor_id")
        if vendor_id is not None:
            vendor_id = int(vendor_id) if vendor_id else None

        cursor = db.execute(
            """INSERT INTO stock_items (name, sku, manufacturer, category, unit,
                                        pieces_per_unit, reorder_point, qr_code_id, vendor_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                (data.get("sku") or "").strip(),
                (data.get("manufacturer") or "").strip(),
                (data.get("category") or "General").strip(),
                (data.get("unit") or "EACH").strip().upper(),
                data.get("pieces_per_unit", 1),
                data.get("reorder_point", 0),
                qr_code_id,
                vendor_id,
            ),
        )
        db.commit()
        item_id = cursor.lastrowid

        # Cross-wire to assets if category is 'tool'
        _sync_tool_to_asset(db, item_id)
        db.commit()

        return jsonify({"id": item_id, "qr_code_id": qr_code_id}), 201
    finally:
        db.close()


@stock_bp.route("/stock/api/items/<int:item_id>", methods=["PUT"])
@login_required
@require_stock_access
def api_items_update(item_id):
    """Update an existing item."""
    db = get_db()
    try:
        item = db.execute("SELECT id FROM stock_items WHERE id = ?", (item_id,)).fetchone()
        if not item:
            abort(404)

        data = request.get_json(silent=True) or {}
        fields = []
        values = []
        for col in ("name", "sku", "manufacturer", "category", "unit",
                     "pieces_per_unit", "reorder_point", "vendor_id"):
            if col in data:
                fields.append(f"{col} = ?")
                val = data[col]
                if col == "vendor_id" and val is not None:
                    val = int(val) if val else None
                values.append(val)

        if not fields:
            return jsonify({"error": "No fields to update"}), 400

        fields.append("updated_at = datetime('now')")
        values.append(item_id)
        db.execute(
            f"UPDATE stock_items SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        db.commit()

        # Cross-wire to assets if category is 'tool'
        _sync_tool_to_asset(db, item_id)
        db.commit()

        return jsonify({"message": "Item updated"})
    finally:
        db.close()


@stock_bp.route("/stock/api/items/<int:item_id>", methods=["DELETE"])
@login_required
@require_stock_access
def api_items_delete(item_id):
    """Delete an item and its inventory records."""
    db = get_db()
    try:
        item = db.execute("SELECT id FROM stock_items WHERE id = ?", (item_id,)).fetchone()
        if not item:
            abort(404)

        db.execute("DELETE FROM shop_inventory WHERE item_id = ?", (item_id,))
        db.execute("DELETE FROM project_inventory WHERE item_id = ?", (item_id,))
        db.execute("DELETE FROM stock_items WHERE id = ?", (item_id,))
        db.commit()
        return jsonify({"message": "Item deleted"})
    finally:
        db.close()


# ── Shop inventory quantity management ────────────────────────


@stock_bp.route("/stock/api/inventory", methods=["POST"])
@login_required
@require_stock_access
def api_inventory_set():
    """Set or update shop inventory for an item."""
    data = request.get_json(silent=True) or {}
    item_id = data.get("item_id")
    shop_id = data.get("shop_id")
    quantity = data.get("quantity")
    section = data.get("section", "")

    if not item_id or not shop_id or quantity is None:
        return jsonify({"error": "item_id, shop_id, and quantity are required"}), 400

    db = get_db()
    try:
        db.execute(
            """INSERT INTO shop_inventory (item_id, shop_id, quantity, section)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(item_id, shop_id)
               DO UPDATE SET quantity = excluded.quantity,
                             section = COALESCE(NULLIF(excluded.section, ''), section),
                             updated_at = datetime('now')""",
            (item_id, shop_id, quantity, section),
        )
        db.commit()
        return jsonify({"message": "Inventory updated"})
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Shops
# ══════════════════════════════════════════════════════════════


@stock_bp.route("/stock/api/shops")
@login_required
@require_stock_access
def api_shops_list():
    """List all shops."""
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM stock_shops ORDER BY name").fetchall()
        return jsonify({"shops": [dict(r) for r in rows]})
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Vendors CRUD
# ══════════════════════════════════════════════════════════════


@stock_bp.route("/stock/api/vendors", methods=["GET"])
@login_required
@require_stock_access
def api_vendors_list():
    """List all vendors."""
    db = get_db()
    try:
        search = request.args.get("search", "").strip()
        query = "SELECT * FROM vendors WHERE 1=1"
        params = []
        if search:
            query += " AND (name LIKE ? OR contact_name LIKE ? OR contact_email LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like, like])
        query += " ORDER BY name"
        rows = db.execute(query, params).fetchall()
        return jsonify({"vendors": [dict(r) for r in rows]})
    finally:
        db.close()


@stock_bp.route("/stock/api/vendors", methods=["POST"])
@login_required
@require_stock_access
def api_vendors_create():
    """Create a new vendor."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Vendor name is required"}), 400

    db = get_db()
    try:
        cursor = db.execute(
            """INSERT INTO vendors (name, address, phone, contact_name, contact_email, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                name,
                (data.get("address") or "").strip(),
                (data.get("phone") or "").strip(),
                (data.get("contact_name") or "").strip(),
                (data.get("contact_email") or "").strip(),
                (data.get("notes") or "").strip(),
            ),
        )
        db.commit()
        return jsonify({"id": cursor.lastrowid}), 201
    finally:
        db.close()


@stock_bp.route("/stock/api/vendors/<int:vendor_id>", methods=["PUT"])
@login_required
@require_stock_access
def api_vendors_update(vendor_id):
    """Update a vendor."""
    db = get_db()
    try:
        vendor = db.execute("SELECT id FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if not vendor:
            abort(404)

        data = request.get_json(silent=True) or {}
        fields = []
        values = []
        for col in ("name", "address", "phone", "contact_name", "contact_email", "notes"):
            if col in data:
                fields.append(f"{col} = ?")
                values.append((data[col] or "").strip())

        if not fields:
            return jsonify({"error": "No fields to update"}), 400

        fields.append("updated_at = datetime('now')")
        values.append(vendor_id)
        db.execute(
            f"UPDATE vendors SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        db.commit()
        return jsonify({"message": "Vendor updated"})
    finally:
        db.close()


@stock_bp.route("/stock/api/vendors/<int:vendor_id>", methods=["DELETE"])
@login_required
@require_stock_access
def api_vendors_delete(vendor_id):
    """Delete a vendor (only if no items reference it)."""
    db = get_db()
    try:
        vendor = db.execute("SELECT id FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if not vendor:
            abort(404)

        item_count = db.execute(
            "SELECT COUNT(*) AS c FROM stock_items WHERE vendor_id = ?", (vendor_id,)
        ).fetchone()["c"]
        if item_count > 0:
            return jsonify({"error": f"Cannot delete vendor — {item_count} items reference it"}), 409

        db.execute("DELETE FROM vendors WHERE id = ?", (vendor_id,))
        db.commit()
        return jsonify({"message": "Vendor deleted"})
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Item Images
# ══════════════════════════════════════════════════════════════


@stock_bp.route("/stock/api/items/<int:item_id>/image", methods=["POST"])
@login_required
@require_stock_access
def api_item_image_upload(item_id):
    """Upload an image for an item."""
    db = get_db()
    try:
        item = db.execute("SELECT id FROM stock_items WHERE id = ?", (item_id,)).fetchone()
        if not item:
            abort(404)

        if "image" not in request.files:
            return jsonify({"error": "No image file provided"}), 400

        file = request.files["image"]
        if not file.filename:
            return jsonify({"error": "No file selected"}), 400

        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            return jsonify({"error": f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"}), 400

        filename = f"item_{item_id}.{ext}"
        storage_path = Path(STOCK_IMAGE_STORAGE_PATH)
        storage_path.mkdir(parents=True, exist_ok=True)

        # Remove old image if exists
        old_path = db.execute(
            "SELECT image_path FROM stock_items WHERE id = ?", (item_id,)
        ).fetchone()
        if old_path and old_path["image_path"]:
            old_file = storage_path / old_path["image_path"]
            if old_file.exists():
                old_file.unlink()

        file.save(str(storage_path / filename))
        db.execute(
            "UPDATE stock_items SET image_path = ?, updated_at = datetime('now') WHERE id = ?",
            (filename, item_id),
        )
        db.commit()
        return jsonify({"message": "Image uploaded", "image_path": filename})
    finally:
        db.close()


@stock_bp.route("/stock/api/items/<int:item_id>/image", methods=["DELETE"])
@login_required
@require_stock_access
def api_item_image_delete(item_id):
    """Delete an item's image."""
    db = get_db()
    try:
        item = db.execute("SELECT image_path FROM stock_items WHERE id = ?", (item_id,)).fetchone()
        if not item:
            abort(404)

        if item["image_path"]:
            file_path = Path(STOCK_IMAGE_STORAGE_PATH) / item["image_path"]
            if file_path.exists():
                file_path.unlink()

        db.execute(
            "UPDATE stock_items SET image_path = NULL, updated_at = datetime('now') WHERE id = ?",
            (item_id,),
        )
        db.commit()
        return jsonify({"message": "Image deleted"})
    finally:
        db.close()


@stock_bp.route("/stock/images/<path:filename>")
@login_required
@require_stock_access
def serve_stock_image(filename):
    """Serve a stock item image."""
    return send_from_directory(STOCK_IMAGE_STORAGE_PATH, filename)


# ══════════════════════════════════════════════════════════════
# API — Item Detail
# ══════════════════════════════════════════════════════════════


@stock_bp.route("/stock/api/items/<int:item_id>/detail")
@login_required
@require_stock_access
def api_item_detail(item_id):
    """Full item detail: info, shop/project quantities, transaction history."""
    db = get_db()
    try:
        item = db.execute("""
            SELECT si.*, v.name AS vendor_name, v.phone AS vendor_phone,
                   v.contact_email AS vendor_email
            FROM stock_items si
            LEFT JOIN vendors v ON v.id = si.vendor_id
            WHERE si.id = ?
        """, (item_id,)).fetchone()
        if not item:
            abort(404)

        # Shop quantities
        shop_inventory = db.execute("""
            SELECT inv.quantity, inv.section, sh.id AS shop_id, sh.name AS shop_name
            FROM shop_inventory inv
            JOIN stock_shops sh ON sh.id = inv.shop_id
            WHERE inv.item_id = ?
            ORDER BY sh.name
        """, (item_id,)).fetchall()

        # Project quantities
        project_inventory = db.execute("""
            SELECT pi.quantity, pi.quantity_ordered, p.id AS project_id, p.name AS project_name
            FROM project_inventory pi
            JOIN projects p ON p.id = pi.project_id
            WHERE pi.item_id = ? AND pi.quantity > 0
            ORDER BY p.name
        """, (item_id,)).fetchall()

        # Transaction history
        transactions = db.execute("""
            SELECT st.*, sh.name AS shop_name, p.name AS project_name,
                   e.full_name AS employee_name
            FROM stock_transactions st
            LEFT JOIN stock_shops sh ON sh.id = st.shop_id
            LEFT JOIN projects p ON p.id = st.project_id
            LEFT JOIN employees e ON e.id = st.employee_id
            WHERE st.item_id = ?
            ORDER BY st.created_at DESC
            LIMIT 100
        """, (item_id,)).fetchall()

        total_shop_qty = sum(r["quantity"] or 0 for r in shop_inventory)
        total_project_qty = sum(r["quantity"] or 0 for r in project_inventory)

        return jsonify({
            "item": dict(item),
            "shop_inventory": [dict(r) for r in shop_inventory],
            "project_inventory": [dict(r) for r in project_inventory],
            "transactions": [dict(r) for r in transactions],
            "total_shop_qty": int(total_shop_qty),
            "total_project_qty": int(total_project_qty),
        })
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — QR Generation + Labels PDF
# ══════════════════════════════════════════════════════════════


@stock_bp.route("/stock/api/items/<int:item_id>/qr")
@login_required
@require_stock_access
def api_item_qr(item_id):
    """Generate QR code PNG for an item."""
    import qrcode

    db = get_db()
    try:
        item = db.execute(
            "SELECT qr_code_id, name FROM stock_items WHERE id = ?", (item_id,)
        ).fetchone()
        if not item:
            abort(404)

        qr_data = f"crewstock:item:{item['qr_code_id']}"
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png", download_name=f"qr_{item['qr_code_id']}.png")
    finally:
        db.close()


@stock_bp.route("/stock/api/labels/pdf", methods=["POST"])
@login_required
@require_stock_access
def api_labels_pdf():
    """Generate a PDF with 2x1 inch QR labels for selected items."""
    import qrcode
    from fpdf import FPDF

    data = request.get_json(silent=True) or {}
    item_ids = data.get("item_ids", [])
    if not item_ids:
        return jsonify({"error": "No items selected"}), 400

    db = get_db()
    try:
        placeholders = ",".join("?" for _ in item_ids)
        items = db.execute(
            f"SELECT id, name, sku, qr_code_id FROM stock_items WHERE id IN ({placeholders})",
            item_ids,
        ).fetchall()

        if not items:
            return jsonify({"error": "No items found"}), 404

        # Build PDF — 2" x 1" labels, 4 columns x 10 rows on letter paper
        pdf = FPDF(orientation="P", unit="in", format="Letter")
        pdf.set_auto_page_break(auto=False)

        label_w = 2.0
        label_h = 1.0
        margin_x = 0.25
        margin_y = 0.5
        cols = 4
        rows_per_page = 10

        pdf.add_page()
        idx = 0

        import tempfile

        for item in items:
            if idx > 0 and idx % (cols * rows_per_page) == 0:
                pdf.add_page()

            pos_on_page = idx % (cols * rows_per_page)
            col = pos_on_page % cols
            row = pos_on_page // cols

            x = margin_x + col * label_w
            y = margin_y + row * label_h

            qr_data = f"crewstock:item:{item['qr_code_id']}"
            qr = qrcode.QRCode(version=1, box_size=6, border=1)
            qr.add_data(qr_data)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")

            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            qr_img.save(tmp, format="PNG")
            tmp.close()

            try:
                pdf.image(tmp.name, x=x + 0.05, y=y + 0.05, w=0.9, h=0.9)
            finally:
                os.unlink(tmp.name)

            pdf.set_font("Helvetica", size=7)
            text_x = x + 1.0
            text_y = y + 0.15
            name = item["name"]
            if len(name) > 22:
                name = name[:20] + ".."
            pdf.set_xy(text_x, text_y)
            pdf.cell(0.9, 0.2, name, ln=True)

            if item["sku"]:
                pdf.set_xy(text_x, text_y + 0.22)
                pdf.set_font("Helvetica", size=6)
                pdf.cell(0.9, 0.15, f"SKU: {item['sku']}")

            pdf.set_xy(text_x, text_y + 0.5)
            pdf.set_font("Helvetica", size=5)
            pdf.cell(0.9, 0.15, item["qr_code_id"])

            idx += 1

        buf = io.BytesIO()
        pdf.output(buf)
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/pdf",
            download_name="crewstock_labels.pdf",
            as_attachment=True,
        )
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — QR Lookup (for scanner)
# ══════════════════════════════════════════════════════════════


@stock_bp.route("/stock/api/lookup")
@login_required
@require_stock_access
def api_qr_lookup():
    """Look up item by QR code ID."""
    qr_code_id = request.args.get("qr", "").strip()
    if not qr_code_id:
        return jsonify({"error": "qr parameter required"}), 400

    db = get_db()
    try:
        item = db.execute(
            "SELECT * FROM stock_items WHERE qr_code_id = ?", (qr_code_id,)
        ).fetchone()
        if not item:
            return jsonify({"error": "Item not found"}), 404

        inventory = db.execute(
            """SELECT inv.*, sh.name AS shop_name
               FROM shop_inventory inv
               JOIN stock_shops sh ON sh.id = inv.shop_id
               WHERE inv.item_id = ?""",
            (item["id"],),
        ).fetchall()

        return jsonify({
            "item": dict(item),
            "inventory": [dict(r) for r in inventory],
        })
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Employees + Projects (for scanner pickers)
# ══════════════════════════════════════════════════════════════


@stock_bp.route("/stock/api/employees")
@login_required
@require_stock_access
def api_employees():
    """List employees for the picker."""
    db = get_db()
    try:
        search = request.args.get("search", "").strip()
        query = "SELECT id, first_name, full_name, role, crew FROM employees WHERE 1=1"
        params = []
        if search:
            query += " AND (first_name LIKE ? OR full_name LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like])
        query += " ORDER BY full_name"
        rows = db.execute(query, params).fetchall()
        return jsonify({"employees": [dict(r) for r in rows]})
    finally:
        db.close()


@stock_bp.route("/stock/api/projects")
@login_required
@require_stock_access
def api_projects():
    """List active projects for the picker."""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, name, status FROM projects WHERE status = 'active' ORDER BY name"
        ).fetchall()
        return jsonify({"projects": [dict(r) for r in rows]})
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Checkout
# ══════════════════════════════════════════════════════════════


@stock_bp.route("/stock/api/checkout", methods=["POST"])
@login_required
@require_stock_access
def api_checkout():
    """Process cart checkout — move items from shop to project."""
    data = request.get_json(silent=True) or {}
    shop_id = data.get("shop_id")
    employee_id = data.get("employee_id")
    project_id = data.get("project_id")
    items = data.get("items", [])

    if not shop_id or not employee_id or not project_id or not items:
        return jsonify({"error": "shop_id, employee_id, project_id, and items are required"}), 400

    user = session.get("user", {})
    created_by = user.get("email", "")

    db = get_db()
    try:
        shop = db.execute("SELECT id FROM stock_shops WHERE id = ?", (shop_id,)).fetchone()
        if not shop:
            return jsonify({"error": "Shop not found"}), 404

        project = db.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not project:
            return jsonify({"error": "Project not found"}), 404

        for cart_item in items:
            item_id = cart_item.get("item_id")
            qty = cart_item.get("quantity", 0)
            if not item_id or qty <= 0:
                continue

            inv = db.execute(
                "SELECT quantity FROM shop_inventory WHERE item_id = ? AND shop_id = ?",
                (item_id, shop_id),
            ).fetchone()

            current_qty = inv["quantity"] if inv else 0
            if current_qty < qty:
                item_name = db.execute(
                    "SELECT name FROM stock_items WHERE id = ?", (item_id,)
                ).fetchone()
                name = item_name["name"] if item_name else f"Item #{item_id}"
                db.rollback()
                return jsonify({
                    "error": f"Insufficient stock for {name}: have {int(current_qty)}, need {int(qty)}"
                }), 409

            db.execute(
                "UPDATE shop_inventory SET quantity = quantity - ?, updated_at = datetime('now') WHERE item_id = ? AND shop_id = ?",
                (qty, item_id, shop_id),
            )

            db.execute(
                """INSERT INTO project_inventory (item_id, project_id, quantity)
                   VALUES (?, ?, ?)
                   ON CONFLICT(item_id, project_id)
                   DO UPDATE SET quantity = quantity + excluded.quantity,
                                 updated_at = datetime('now')""",
                (item_id, project_id, qty),
            )

            db.execute(
                """INSERT INTO stock_transactions
                   (type, item_id, shop_id, project_id, employee_id, quantity, created_by)
                   VALUES ('checkout', ?, ?, ?, ?, ?, ?)""",
                (item_id, shop_id, project_id, employee_id, qty, created_by),
            )

        db.commit()
        return jsonify({"message": "Checkout complete", "item_count": len(items)})
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Return to Shop
# ══════════════════════════════════════════════════════════════


@stock_bp.route("/stock/api/return", methods=["POST"])
@login_required
@require_stock_access
def api_return():
    """Return items from project back to shop."""
    data = request.get_json(silent=True) or {}
    shop_id = data.get("shop_id")
    project_id = data.get("project_id")
    employee_id = data.get("employee_id")
    items = data.get("items", [])

    if not shop_id or not project_id or not items:
        return jsonify({"error": "shop_id, project_id, and items are required"}), 400

    user = session.get("user", {})
    created_by = user.get("email", "")

    db = get_db()
    try:
        for cart_item in items:
            item_id = cart_item.get("item_id")
            qty = cart_item.get("quantity", 0)
            if not item_id or qty <= 0:
                continue

            proj_inv = db.execute(
                "SELECT quantity FROM project_inventory WHERE item_id = ? AND project_id = ?",
                (item_id, project_id),
            ).fetchone()

            current_qty = proj_inv["quantity"] if proj_inv else 0
            if current_qty < qty:
                db.rollback()
                return jsonify({"error": f"Cannot return more than checked out for item {item_id}"}), 409

            db.execute(
                "UPDATE project_inventory SET quantity = quantity - ?, updated_at = datetime('now') WHERE item_id = ? AND project_id = ?",
                (qty, item_id, project_id),
            )

            db.execute(
                """INSERT INTO shop_inventory (item_id, shop_id, quantity)
                   VALUES (?, ?, ?)
                   ON CONFLICT(item_id, shop_id)
                   DO UPDATE SET quantity = quantity + excluded.quantity,
                                 updated_at = datetime('now')""",
                (item_id, shop_id, qty),
            )

            db.execute(
                """INSERT INTO stock_transactions
                   (type, item_id, shop_id, project_id, employee_id, quantity, created_by)
                   VALUES ('return', ?, ?, ?, ?, ?, ?)""",
                (item_id, shop_id, project_id, employee_id, qty, created_by),
            )

        db.commit()
        return jsonify({"message": "Return complete", "item_count": len(items)})
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Restock (delivery received)
# ══════════════════════════════════════════════════════════════


@stock_bp.route("/stock/api/restock", methods=["POST"])
@login_required
@require_stock_access
def api_restock():
    """Add new stock to shop (delivery received)."""
    data = request.get_json(silent=True) or {}
    shop_id = data.get("shop_id")
    items = data.get("items", [])
    notes = data.get("notes", "")

    if not shop_id or not items:
        return jsonify({"error": "shop_id and items are required"}), 400

    user = session.get("user", {})
    created_by = user.get("email", "")

    db = get_db()
    try:
        for cart_item in items:
            item_id = cart_item.get("item_id")
            qty = cart_item.get("quantity", 0)
            if not item_id or qty <= 0:
                continue

            db.execute(
                """INSERT INTO shop_inventory (item_id, shop_id, quantity)
                   VALUES (?, ?, ?)
                   ON CONFLICT(item_id, shop_id)
                   DO UPDATE SET quantity = quantity + excluded.quantity,
                                 updated_at = datetime('now')""",
                (item_id, shop_id, qty),
            )

            db.execute(
                """INSERT INTO stock_transactions
                   (type, item_id, shop_id, quantity, notes, created_by)
                   VALUES ('restock', ?, ?, ?, ?, ?)""",
                (item_id, shop_id, qty, notes, created_by),
            )

        db.commit()
        return jsonify({"message": "Restock complete", "item_count": len(items)})
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Project Inventory
# ══════════════════════════════════════════════════════════════


@stock_bp.route("/stock/api/project/<int:project_id>/inventory")
@login_required
@require_stock_access
def api_project_inventory(project_id):
    """Items checked out to a project with ordered vs on-site tracking."""
    db = get_db()
    try:
        items = db.execute(
            """SELECT pi.item_id, pi.quantity, pi.quantity_ordered, pi.updated_at,
                      si.name, si.sku, si.unit, si.qr_code_id, si.vendor_id,
                      v.name AS vendor_name
               FROM project_inventory pi
               JOIN stock_items si ON si.id = pi.item_id
               LEFT JOIN vendors v ON v.id = si.vendor_id
               WHERE pi.project_id = ? AND (pi.quantity > 0 OR pi.quantity_ordered > 0)
               ORDER BY si.name""",
            (project_id,),
        ).fetchall()

        transactions = db.execute(
            """SELECT st.*, si.name AS item_name, sh.name AS shop_name,
                      e.full_name AS employee_name
               FROM stock_transactions st
               JOIN stock_items si ON si.id = st.item_id
               LEFT JOIN stock_shops sh ON sh.id = st.shop_id
               LEFT JOIN employees e ON e.id = st.employee_id
               WHERE st.project_id = ?
               ORDER BY st.created_at DESC
               LIMIT 100""",
            (project_id,),
        ).fetchall()

        return jsonify({
            "items": [dict(r) for r in items],
            "transactions": [dict(r) for r in transactions],
        })
    finally:
        db.close()


@stock_bp.route("/stock/api/projects/with-inventory")
@login_required
@require_stock_access
def api_projects_with_inventory():
    """List projects that have checked-out inventory."""
    db = get_db()
    try:
        rows = db.execute(
            """SELECT p.id, p.name, p.status,
                      COALESCE(SUM(pi.quantity), 0) AS total_items
               FROM projects p
               JOIN project_inventory pi ON pi.project_id = p.id
               WHERE pi.quantity > 0
               GROUP BY p.id
               ORDER BY p.name"""
        ).fetchall()
        return jsonify({"projects": [dict(r) for r in rows]})
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Project Documents (PO/Invoice upload)
# ══════════════════════════════════════════════════════════════


@stock_bp.route("/stock/api/project/<int:project_id>/documents", methods=["POST"])
@login_required
@require_stock_access
def api_project_doc_upload(project_id):
    """Upload a PO/invoice document for a project."""
    db = get_db()
    try:
        project = db.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not project:
            abort(404)

        if "document" not in request.files:
            return jsonify({"error": "No document file provided"}), 400

        file = request.files["document"]
        if not file.filename:
            return jsonify({"error": "No file selected"}), 400

        doc_type = request.form.get("doc_type", "unknown")
        vendor_id = request.form.get("vendor_id")
        vendor_id = int(vendor_id) if vendor_id else None

        # Save file
        storage_path = Path(INVENTORY_DOC_STORAGE_PATH)
        storage_path.mkdir(parents=True, exist_ok=True)
        safe_name = f"proj{project_id}_{uuid.uuid4().hex[:8]}_{file.filename}"
        file.save(str(storage_path / safe_name))

        user = session.get("user", {})
        cursor = db.execute(
            """INSERT INTO inventory_documents
               (project_id, vendor_id, doc_type, filename, file_path, uploaded_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (project_id, vendor_id, doc_type, file.filename, safe_name, user.get("email", "")),
        )
        db.commit()

        return jsonify({"id": cursor.lastrowid, "filename": file.filename}), 201
    finally:
        db.close()


@stock_bp.route("/stock/api/project/<int:project_id>/documents", methods=["GET"])
@login_required
@require_stock_access
def api_project_docs_list(project_id):
    """List uploaded documents for a project."""
    db = get_db()
    try:
        rows = db.execute(
            """SELECT d.*, v.name AS vendor_name
               FROM inventory_documents d
               LEFT JOIN vendors v ON v.id = d.vendor_id
               WHERE d.project_id = ?
               ORDER BY d.created_at DESC""",
            (project_id,),
        ).fetchall()
        return jsonify({"documents": [dict(r) for r in rows]})
    finally:
        db.close()


@stock_bp.route("/stock/api/project/<int:project_id>/documents/<int:doc_id>/items")
@login_required
@require_stock_access
def api_project_doc_items(project_id, doc_id):
    """Get parsed line items from a document."""
    db = get_db()
    try:
        doc = db.execute(
            "SELECT id FROM inventory_documents WHERE id = ? AND project_id = ?",
            (doc_id, project_id),
        ).fetchone()
        if not doc:
            abort(404)

        rows = db.execute(
            """SELECT di.*, si.name AS matched_item_name
               FROM inventory_document_items di
               LEFT JOIN stock_items si ON si.id = di.stock_item_id
               WHERE di.document_id = ?
               ORDER BY di.line_number""",
            (doc_id,),
        ).fetchall()
        return jsonify({"items": [dict(r) for r in rows]})
    finally:
        db.close()


@stock_bp.route("/stock/api/project/<int:project_id>/documents/<int:doc_id>/match", methods=["POST"])
@login_required
@require_stock_access
def api_project_doc_match(project_id, doc_id):
    """Match a document line item to a stock item."""
    db = get_db()
    try:
        data = request.get_json(silent=True) or {}
        line_item_id = data.get("line_item_id")
        stock_item_id = data.get("stock_item_id")

        if not line_item_id:
            return jsonify({"error": "line_item_id is required"}), 400

        line_item = db.execute(
            "SELECT id FROM inventory_document_items WHERE id = ? AND document_id = ?",
            (line_item_id, doc_id),
        ).fetchone()
        if not line_item:
            abort(404)

        if stock_item_id:
            db.execute(
                "UPDATE inventory_document_items SET stock_item_id = ?, match_status = 'matched' WHERE id = ?",
                (stock_item_id, line_item_id),
            )
        else:
            db.execute(
                "UPDATE inventory_document_items SET stock_item_id = NULL, match_status = 'skipped' WHERE id = ?",
                (line_item_id,),
            )
        db.commit()
        return jsonify({"message": "Match updated"})
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Quick Reorder via Email
# ══════════════════════════════════════════════════════════════


@stock_bp.route("/stock/api/reorder/generate", methods=["POST"])
@login_required
@require_stock_access
def api_reorder_generate():
    """Generate reorder drafts grouped by vendor for selected items."""
    data = request.get_json(silent=True) or {}
    items_to_reorder = data.get("items", [])
    # items_to_reorder: [{item_id, quantity, notes}, ...]

    if not items_to_reorder:
        return jsonify({"error": "No items selected for reorder"}), 400

    user = session.get("user", {})
    created_by = user.get("email", "")

    db = get_db()
    try:
        # Group items by vendor
        vendor_groups = {}
        for entry in items_to_reorder:
            item_id = entry.get("item_id")
            qty = entry.get("quantity", 0)
            notes = entry.get("notes", "")

            item = db.execute(
                """SELECT si.id, si.name, si.unit, si.vendor_id,
                          v.name AS vendor_name, v.contact_email
                   FROM stock_items si
                   LEFT JOIN vendors v ON v.id = si.vendor_id
                   WHERE si.id = ?""",
                (item_id,),
            ).fetchone()
            if not item:
                continue

            vendor_id = item["vendor_id"] or 0  # 0 = no vendor
            if vendor_id not in vendor_groups:
                vendor_groups[vendor_id] = {
                    "vendor_id": item["vendor_id"],
                    "vendor_name": item["vendor_name"] or "No Vendor",
                    "contact_email": item["contact_email"] or "",
                    "items": [],
                }
            vendor_groups[vendor_id]["items"].append({
                "item_id": item["id"],
                "name": item["name"],
                "quantity": qty,
                "unit": item["unit"],
                "notes": notes,
            })

        # Create reorder_requests
        created_ids = []
        for vg in vendor_groups.values():
            items_json = json.dumps(vg["items"])
            email_to = vg["contact_email"]
            email_subject = f"CrewOS Reorder — {vg['vendor_name']}"
            lines = [f"Please supply the following items:\n"]
            for it in vg["items"]:
                lines.append(f"- {it['name']}: {it['quantity']} {it['unit']}")
                if it.get("notes"):
                    lines.append(f"  Note: {it['notes']}")
            lines.append(f"\nThank you,\n{created_by}")
            email_body = "\n".join(lines)

            cursor = db.execute(
                """INSERT INTO reorder_requests
                   (vendor_id, items_json, email_to, email_subject, email_body, created_by)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (vg["vendor_id"], items_json, email_to, email_subject, email_body, created_by),
            )
            created_ids.append(cursor.lastrowid)

        db.commit()
        return jsonify({"message": f"Created {len(created_ids)} reorder draft(s)", "ids": created_ids}), 201
    finally:
        db.close()


@stock_bp.route("/stock/api/reorder/<int:reorder_id>", methods=["GET"])
@login_required
@require_stock_access
def api_reorder_detail(reorder_id):
    """Get reorder draft detail."""
    db = get_db()
    try:
        row = db.execute(
            """SELECT r.*, v.name AS vendor_name
               FROM reorder_requests r
               LEFT JOIN vendors v ON v.id = r.vendor_id
               WHERE r.id = ?""",
            (reorder_id,),
        ).fetchone()
        if not row:
            abort(404)

        result = dict(row)
        result["items"] = json.loads(result["items_json"]) if result["items_json"] else []
        return jsonify({"reorder": result})
    finally:
        db.close()


@stock_bp.route("/stock/api/reorder/<int:reorder_id>", methods=["PUT"])
@login_required
@require_stock_access
def api_reorder_update(reorder_id):
    """Edit a reorder draft (quantities, notes, email body)."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT id, status FROM reorder_requests WHERE id = ?", (reorder_id,)
        ).fetchone()
        if not row:
            abort(404)
        if row["status"] != "draft":
            return jsonify({"error": "Can only edit draft orders"}), 400

        data = request.get_json(silent=True) or {}
        fields = []
        values = []
        for col in ("items_json", "notes", "email_to", "email_subject", "email_body"):
            if col in data:
                fields.append(f"{col} = ?")
                values.append(data[col])

        if not fields:
            return jsonify({"error": "No fields to update"}), 400

        fields.append("updated_at = datetime('now')")
        values.append(reorder_id)
        db.execute(
            f"UPDATE reorder_requests SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        db.commit()
        return jsonify({"message": "Reorder updated"})
    finally:
        db.close()


@stock_bp.route("/stock/api/reorder/<int:reorder_id>/send", methods=["POST"])
@login_required
@require_stock_access
def api_reorder_send(reorder_id):
    """Send reorder email to vendor."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT * FROM reorder_requests WHERE id = ?", (reorder_id,)
        ).fetchone()
        if not row:
            abort(404)
        if row["status"] != "draft":
            return jsonify({"error": "Order already sent or cancelled"}), 400

        email_to = row["email_to"]
        if not email_to:
            return jsonify({"error": "No vendor email address configured"}), 400

        from src.services.email_sender import send_custom_email

        html_body = f"<pre>{row['email_body']}</pre>"
        success = send_custom_email(
            to_email=email_to,
            subject=row["email_subject"],
            html_body=html_body,
            plain_body=row["email_body"],
        )

        if success:
            db.execute(
                "UPDATE reorder_requests SET status = 'sent', sent_at = datetime('now') WHERE id = ?",
                (reorder_id,),
            )
            db.commit()
            return jsonify({"message": "Reorder email sent"})
        else:
            return jsonify({"error": "Failed to send email — check SMTP settings"}), 500
    finally:
        db.close()


@stock_bp.route("/stock/api/reorder/history")
@login_required
@require_stock_access
def api_reorder_history():
    """List all reorder requests."""
    db = get_db()
    try:
        rows = db.execute(
            """SELECT r.*, v.name AS vendor_name
               FROM reorder_requests r
               LEFT JOIN vendors v ON v.id = r.vendor_id
               ORDER BY r.created_at DESC
               LIMIT 200"""
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["items"] = json.loads(d["items_json"]) if d["items_json"] else []
            results.append(d)
        return jsonify({"orders": results})
    finally:
        db.close()
