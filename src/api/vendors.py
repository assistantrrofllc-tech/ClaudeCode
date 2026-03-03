"""
Vendors routes — Shared CrewOS infrastructure.

Platform-level vendor management: list, detail hub, contacts, receipt matching,
cross-module wiring to CrewLedger, CrewInventory, and CrewAsset.
"""

import logging
import os
from functools import wraps

from flask import (
    Blueprint, render_template, jsonify, request, abort, session,
    send_from_directory,
)
from thefuzz import fuzz

from config.settings import VENDOR_IMAGE_STORAGE_PATH
from src.database.connection import get_db
from src.services.auth import login_required
from src.services.permissions import get_current_role

log = logging.getLogger(__name__)

vendors_bp = Blueprint("vendors", __name__)

VENDOR_TYPES = ("supplier", "rental", "subcontractor", "training", "service")


def _render_vendors(template, active_subnav="", **kwargs):
    """Render a template with Vendors module navigation context."""
    role = get_current_role()
    role_level = {"super_admin": 4, "company_admin": 3, "manager": 2, "employee": 1}.get(role, 1)
    defaults = {
        "can_edit": role_level >= 3,
        "user_role": role,
    }
    defaults.update(kwargs)
    return render_template(
        template,
        active_module="vendors",
        active_subnav=active_subnav,
        module_nav=[
            {"id": "list", "label": "All Vendors", "href": "/vendors"},
        ],
        **defaults,
    )


# ══════════════════════════════════════════════════════════════
# PAGES
# ══════════════════════════════════════════════════════════════


@vendors_bp.route("/vendors")
@login_required
def vendors_list_page():
    """Vendor list page with search, type filters, and stats."""
    return _render_vendors("vendors_list.html", active_subnav="list")


@vendors_bp.route("/vendors/<int:vendor_id>")
@login_required
def vendor_detail_page(vendor_id):
    """Vendor detail hub — tabbed page with cross-module data."""
    db = get_db()
    try:
        vendor = db.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if not vendor:
            abort(404)
        return _render_vendors(
            "vendor_detail.html",
            active_subnav="list",
            vendor=dict(vendor),
        )
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Vendor CRUD
# ══════════════════════════════════════════════════════════════


@vendors_bp.route("/api/vendors", methods=["GET"])
@login_required
def api_vendors_list():
    """List vendors with optional search and type filter."""
    db = get_db()
    try:
        search = request.args.get("search", "").strip()
        vendor_type = request.args.get("type", "").strip()
        status = request.args.get("status", "active").strip()

        query = """
            SELECT v.*,
                   (SELECT COUNT(*) FROM stock_items si WHERE si.vendor_id = v.id) AS item_count,
                   (SELECT COALESCE(SUM(r.total), 0) FROM receipts r WHERE r.vendor_id = v.id) AS total_spend,
                   (SELECT MAX(r.purchase_date) FROM receipts r WHERE r.vendor_id = v.id) AS last_receipt_date,
                   (SELECT vc.name FROM vendor_contacts vc WHERE vc.vendor_id = v.id AND vc.is_primary = 1 LIMIT 1) AS primary_contact_name,
                   (SELECT vc.email FROM vendor_contacts vc WHERE vc.vendor_id = v.id AND vc.is_primary = 1 LIMIT 1) AS primary_contact_email
            FROM vendors v
            WHERE 1=1
        """
        params = []

        if status and status != "all":
            query += " AND v.status = ?"
            params.append(status)

        if vendor_type and vendor_type != "all":
            query += " AND v.vendor_type = ?"
            params.append(vendor_type)

        if search:
            query += " AND (v.name LIKE ? OR v.contact_name LIKE ? OR v.contact_email LIKE ? OR v.account_number LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like, like, like])

        query += " ORDER BY v.name"
        rows = db.execute(query, params).fetchall()
        return jsonify({"vendors": [dict(r) for r in rows]})
    except Exception as e:
        log.exception("Error listing vendors")
        return jsonify({"vendors": [], "error": str(e)})
    finally:
        db.close()


@vendors_bp.route("/api/vendors", methods=["POST"])
@login_required
def api_vendors_create():
    """Create a new vendor."""
    db = get_db()
    try:
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Vendor name is required"}), 400

        vendor_type = data.get("vendor_type", "supplier")
        if vendor_type not in VENDOR_TYPES:
            vendor_type = "supplier"

        cursor = db.execute("""
            INSERT INTO vendors (name, vendor_type, address, city, state, zip, phone,
                                 website, account_number, payment_terms, contact_name,
                                 contact_email, contact_phone, notes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            vendor_type,
            (data.get("address") or "").strip(),
            (data.get("city") or "").strip(),
            (data.get("state") or "").strip(),
            (data.get("zip") or "").strip(),
            (data.get("phone") or "").strip(),
            (data.get("website") or "").strip(),
            (data.get("account_number") or "").strip(),
            (data.get("payment_terms") or "").strip(),
            (data.get("contact_name") or "").strip(),
            (data.get("contact_email") or "").strip(),
            (data.get("contact_phone") or "").strip(),
            (data.get("notes") or "").strip(),
            "active",
        ))
        db.commit()

        # If contact_name provided, also create a vendor_contact
        contact_name = (data.get("contact_name") or "").strip()
        if contact_name:
            db.execute("""
                INSERT INTO vendor_contacts (vendor_id, name, email, phone, is_primary)
                VALUES (?, ?, ?, ?, 1)
            """, (
                cursor.lastrowid,
                contact_name,
                (data.get("contact_email") or "").strip(),
                (data.get("contact_phone") or "").strip(),
            ))
            db.commit()

        return jsonify({"id": cursor.lastrowid, "message": "Vendor created"}), 201
    finally:
        db.close()


@vendors_bp.route("/api/vendors/<int:vendor_id>", methods=["GET"])
@login_required
def api_vendor_detail(vendor_id):
    """Full vendor detail JSON — stats from all modules."""
    db = get_db()
    try:
        vendor = db.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if not vendor:
            abort(404)

        vendor_dict = dict(vendor)

        # Contacts
        contacts = [dict(r) for r in db.execute(
            "SELECT * FROM vendor_contacts WHERE vendor_id = ? ORDER BY is_primary DESC, name",
            (vendor_id,),
        ).fetchall()]

        # Stats: total spend from receipts
        spend_row = db.execute(
            "SELECT COALESCE(SUM(total), 0) AS total_spend, COUNT(*) AS receipt_count FROM receipts WHERE vendor_id = ?",
            (vendor_id,),
        ).fetchone()

        # Stats: spend this month
        month_spend = db.execute(
            """SELECT COALESCE(SUM(total), 0) AS spend
               FROM receipts WHERE vendor_id = ? AND purchase_date >= date('now', 'start of month')""",
            (vendor_id,),
        ).fetchone()["spend"]

        # Items supplied
        item_count = db.execute(
            "SELECT COUNT(*) AS c FROM stock_items WHERE vendor_id = ?", (vendor_id,)
        ).fetchone()["c"]

        # Reorder count
        reorder_count = 0
        try:
            reorder_count = db.execute(
                "SELECT COUNT(*) AS c FROM reorder_requests WHERE vendor_id = ?", (vendor_id,)
            ).fetchone()["c"]
        except Exception:
            pass

        # Aliases
        aliases = [dict(r) for r in db.execute(
            "SELECT * FROM vendor_aliases WHERE vendor_id = ? ORDER BY alias", (vendor_id,)
        ).fetchall()]

        return jsonify({
            "vendor": vendor_dict,
            "contacts": contacts,
            "aliases": aliases,
            "stats": {
                "total_spend": round(spend_row["total_spend"], 2),
                "receipt_count": spend_row["receipt_count"],
                "month_spend": round(month_spend, 2),
                "item_count": item_count,
                "reorder_count": reorder_count,
            },
        })
    finally:
        db.close()


@vendors_bp.route("/api/vendors/<int:vendor_id>", methods=["PUT"])
@login_required
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
        for col in ("name", "vendor_type", "address", "city", "state", "zip",
                     "phone", "website", "account_number", "payment_terms",
                     "contact_name", "contact_email", "contact_phone", "notes",
                     "image_path", "status"):
            if col in data:
                fields.append(f"{col} = ?")
                val = data[col]
                if isinstance(val, str):
                    val = val.strip()
                values.append(val)

        if not fields:
            return jsonify({"error": "No fields to update"}), 400

        fields.append("updated_at = datetime('now')")
        values.append(vendor_id)
        db.execute(f"UPDATE vendors SET {', '.join(fields)} WHERE id = ?", values)
        db.commit()

        return jsonify({"message": "Vendor updated"})
    finally:
        db.close()


@vendors_bp.route("/api/vendors/<int:vendor_id>", methods=["DELETE"])
@login_required
def api_vendors_delete(vendor_id):
    """Soft-delete (archive) a vendor."""
    db = get_db()
    try:
        vendor = db.execute("SELECT id FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if not vendor:
            abort(404)
        db.execute("UPDATE vendors SET status = 'archived', updated_at = datetime('now') WHERE id = ?", (vendor_id,))
        db.commit()
        return jsonify({"message": "Vendor archived"})
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Vendor Contacts
# ══════════════════════════════════════════════════════════════


@vendors_bp.route("/api/vendors/<int:vendor_id>/contacts", methods=["GET"])
@login_required
def api_vendor_contacts_list(vendor_id):
    """List contacts for a vendor."""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT * FROM vendor_contacts WHERE vendor_id = ? ORDER BY is_primary DESC, name",
            (vendor_id,),
        ).fetchall()
        return jsonify({"contacts": [dict(r) for r in rows]})
    finally:
        db.close()


@vendors_bp.route("/api/vendors/<int:vendor_id>/contacts", methods=["POST"])
@login_required
def api_vendor_contacts_create(vendor_id):
    """Add a contact to a vendor."""
    db = get_db()
    try:
        vendor = db.execute("SELECT id FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if not vendor:
            abort(404)

        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Contact name is required"}), 400

        is_primary = 1 if data.get("is_primary") else 0
        # If setting as primary, clear other primaries
        if is_primary:
            db.execute("UPDATE vendor_contacts SET is_primary = 0 WHERE vendor_id = ?", (vendor_id,))

        cursor = db.execute("""
            INSERT INTO vendor_contacts (vendor_id, name, role, email, phone, is_primary, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            vendor_id, name,
            (data.get("role") or "").strip(),
            (data.get("email") or "").strip(),
            (data.get("phone") or "").strip(),
            is_primary,
            (data.get("notes") or "").strip(),
        ))
        db.commit()
        return jsonify({"id": cursor.lastrowid, "message": "Contact added"}), 201
    finally:
        db.close()


@vendors_bp.route("/api/vendors/<int:vendor_id>/contacts/<int:contact_id>", methods=["PUT"])
@login_required
def api_vendor_contacts_update(vendor_id, contact_id):
    """Update a vendor contact."""
    db = get_db()
    try:
        contact = db.execute(
            "SELECT id FROM vendor_contacts WHERE id = ? AND vendor_id = ?",
            (contact_id, vendor_id),
        ).fetchone()
        if not contact:
            abort(404)

        data = request.get_json(silent=True) or {}
        fields = []
        values = []
        for col in ("name", "role", "email", "phone", "notes"):
            if col in data:
                fields.append(f"{col} = ?")
                values.append((data[col] or "").strip())

        if "is_primary" in data:
            is_primary = 1 if data["is_primary"] else 0
            if is_primary:
                db.execute("UPDATE vendor_contacts SET is_primary = 0 WHERE vendor_id = ?", (vendor_id,))
            fields.append("is_primary = ?")
            values.append(is_primary)

        if not fields:
            return jsonify({"error": "No fields to update"}), 400

        values.append(contact_id)
        db.execute(f"UPDATE vendor_contacts SET {', '.join(fields)} WHERE id = ?", values)
        db.commit()
        return jsonify({"message": "Contact updated"})
    finally:
        db.close()


@vendors_bp.route("/api/vendors/<int:vendor_id>/contacts/<int:contact_id>", methods=["DELETE"])
@login_required
def api_vendor_contacts_delete(vendor_id, contact_id):
    """Delete a vendor contact."""
    db = get_db()
    try:
        contact = db.execute(
            "SELECT id FROM vendor_contacts WHERE id = ? AND vendor_id = ?",
            (contact_id, vendor_id),
        ).fetchone()
        if not contact:
            abort(404)
        db.execute("DELETE FROM vendor_contacts WHERE id = ?", (contact_id,))
        db.commit()
        return jsonify({"message": "Contact deleted"})
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Cross-Module: Receipts
# ══════════════════════════════════════════════════════════════


@vendors_bp.route("/api/vendors/<int:vendor_id>/receipts", methods=["GET"])
@login_required
def api_vendor_receipts(vendor_id):
    """Receipts matched to this vendor."""
    db = get_db()
    try:
        rows = db.execute("""
            SELECT r.id, r.purchase_date, r.total, r.vendor_name, r.status,
                   r.payment_method, r.image_path,
                   e.name AS employee_name,
                   p.name AS project_name
            FROM receipts r
            LEFT JOIN employees e ON e.id = r.employee_id
            LEFT JOIN projects p ON p.id = r.project_id
            WHERE r.vendor_id = ?
            ORDER BY r.purchase_date DESC
        """, (vendor_id,)).fetchall()

        total_spend = sum(r["total"] or 0 for r in rows)

        return jsonify({
            "receipts": [dict(r) for r in rows],
            "total_spend": round(total_spend, 2),
        })
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Cross-Module: Inventory Items
# ══════════════════════════════════════════════════════════════


@vendors_bp.route("/api/vendors/<int:vendor_id>/items", methods=["GET"])
@login_required
def api_vendor_items(vendor_id):
    """Inventory items from this vendor."""
    db = get_db()
    try:
        rows = db.execute("""
            SELECT si.id, si.name, si.category, si.unit, si.reorder_point, si.image_path,
                   COALESCE(SUM(inv.quantity), 0) AS total_qty
            FROM stock_items si
            LEFT JOIN shop_inventory inv ON inv.item_id = si.id
            WHERE si.vendor_id = ?
            GROUP BY si.id
            ORDER BY si.name
        """, (vendor_id,)).fetchall()
        return jsonify({"items": [dict(r) for r in rows]})
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Cross-Module: Reorders
# ══════════════════════════════════════════════════════════════


@vendors_bp.route("/api/vendors/<int:vendor_id>/reorders", methods=["GET"])
@login_required
def api_vendor_reorders(vendor_id):
    """Reorder history for this vendor."""
    db = get_db()
    try:
        rows = db.execute("""
            SELECT * FROM reorder_requests
            WHERE vendor_id = ?
            ORDER BY created_at DESC
        """, (vendor_id,)).fetchall()
        return jsonify({"reorders": [dict(r) for r in rows]})
    except Exception:
        return jsonify({"reorders": []})
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Vendor Matching (Receipt → Vendor)
# ══════════════════════════════════════════════════════════════


@vendors_bp.route("/api/vendors/match", methods=["POST"])
@login_required
def api_vendor_match():
    """Manually match a receipt's vendor_name to a vendor record.

    Creates an alias so future matches are automatic.
    """
    db = get_db()
    try:
        data = request.get_json(silent=True) or {}
        receipt_id = data.get("receipt_id")
        vendor_id = data.get("vendor_id")

        if not receipt_id or not vendor_id:
            return jsonify({"error": "receipt_id and vendor_id are required"}), 400

        receipt = db.execute("SELECT id, vendor_name FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
        if not receipt:
            return jsonify({"error": "Receipt not found"}), 404

        vendor = db.execute("SELECT id FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if not vendor:
            return jsonify({"error": "Vendor not found"}), 404

        # Link receipt to vendor
        db.execute("UPDATE receipts SET vendor_id = ? WHERE id = ?", (vendor_id, receipt_id))

        # Save alias for auto-matching
        alias_text = (receipt["vendor_name"] or "").strip()
        if alias_text:
            try:
                db.execute(
                    "INSERT OR IGNORE INTO vendor_aliases (vendor_id, alias) VALUES (?, ?)",
                    (vendor_id, alias_text),
                )
            except Exception:
                pass

        db.commit()
        return jsonify({"message": "Receipt matched to vendor", "alias_saved": bool(alias_text)})
    finally:
        db.close()


@vendors_bp.route("/api/vendors/auto-match", methods=["POST"])
@login_required
def api_vendor_auto_match():
    """Run auto-matching on all unmatched receipts.

    1. Check vendor_aliases for exact match
    2. Fuzzy match against vendor names (>80% threshold)
    """
    db = get_db()
    try:
        unmatched = db.execute(
            "SELECT id, vendor_name FROM receipts WHERE vendor_id IS NULL AND vendor_name IS NOT NULL AND vendor_name != ''"
        ).fetchall()

        if not unmatched:
            return jsonify({"matched": 0, "total_unmatched": 0})

        # Load all aliases
        aliases = db.execute("SELECT vendor_id, alias FROM vendor_aliases").fetchall()
        alias_map = {a["alias"].lower().strip(): a["vendor_id"] for a in aliases}

        # Load all vendors
        vendors = db.execute("SELECT id, name FROM vendors WHERE status = 'active'").fetchall()

        matched = 0
        for receipt in unmatched:
            vendor_name = (receipt["vendor_name"] or "").strip()
            if not vendor_name:
                continue

            vendor_name_lower = vendor_name.lower()

            # 1. Exact alias match
            if vendor_name_lower in alias_map:
                db.execute("UPDATE receipts SET vendor_id = ? WHERE id = ?",
                           (alias_map[vendor_name_lower], receipt["id"]))
                matched += 1
                continue

            # 2. Fuzzy match against vendor names
            best_score = 0
            best_vendor_id = None
            for v in vendors:
                score = fuzz.ratio(vendor_name_lower, v["name"].lower())
                if score > best_score:
                    best_score = score
                    best_vendor_id = v["id"]

            if best_score >= 80 and best_vendor_id:
                db.execute("UPDATE receipts SET vendor_id = ? WHERE id = ?",
                           (best_vendor_id, receipt["id"]))
                # Save alias for next time
                try:
                    db.execute(
                        "INSERT OR IGNORE INTO vendor_aliases (vendor_id, alias) VALUES (?, ?)",
                        (best_vendor_id, vendor_name),
                    )
                except Exception:
                    pass
                matched += 1

        db.commit()
        return jsonify({
            "matched": matched,
            "total_unmatched": len(unmatched),
            "remaining": len(unmatched) - matched,
        })
    finally:
        db.close()


@vendors_bp.route("/api/vendors/unmatched", methods=["GET"])
@login_required
def api_vendors_unmatched():
    """List receipts with no vendor_id match."""
    db = get_db()
    try:
        rows = db.execute("""
            SELECT r.id, r.vendor_name, r.purchase_date, r.total, r.status,
                   e.name AS employee_name, p.name AS project_name
            FROM receipts r
            LEFT JOIN employees e ON e.id = r.employee_id
            LEFT JOIN projects p ON p.id = r.project_id
            WHERE r.vendor_id IS NULL AND r.vendor_name IS NOT NULL AND r.vendor_name != ''
            ORDER BY r.purchase_date DESC
        """).fetchall()
        return jsonify({"receipts": [dict(r) for r in rows]})
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
# API — Vendor Image
# ══════════════════════════════════════════════════════════════


@vendors_bp.route("/api/vendors/<int:vendor_id>/image", methods=["POST"])
@login_required
def api_vendor_image_upload(vendor_id):
    """Upload a vendor logo/image."""
    db = get_db()
    try:
        vendor = db.execute("SELECT id FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if not vendor:
            abort(404)

        if "image" not in request.files:
            return jsonify({"error": "No image file"}), 400

        file = request.files["image"]
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in ("jpg", "jpeg", "png", "webp"):
            return jsonify({"error": "Invalid image type"}), 400

        os.makedirs(VENDOR_IMAGE_STORAGE_PATH, exist_ok=True)
        filename = f"vendor_{vendor_id}.{ext}"
        filepath = os.path.join(VENDOR_IMAGE_STORAGE_PATH, filename)
        file.save(filepath)

        db.execute("UPDATE vendors SET image_path = ?, updated_at = datetime('now') WHERE id = ?",
                    (filename, vendor_id))
        db.commit()

        return jsonify({"message": "Image uploaded", "image_path": filename})
    finally:
        db.close()


@vendors_bp.route("/vendors/images/<path:filename>")
@login_required
def serve_vendor_image(filename):
    """Serve vendor images."""
    return send_from_directory(VENDOR_IMAGE_STORAGE_PATH, filename)
