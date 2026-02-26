"""
Fleet routes — CrewAsset Vehicles module.

Vehicle fleet management: overview, detail, and maintenance CRUD.
"""

import logging
from datetime import datetime

from flask import (
    Blueprint, render_template, jsonify, request, abort,
)

from src.database.connection import get_db
from src.services.auth import login_required
from src.services.permissions import (
    check_permission, require_role, require_permission, get_current_role,
    get_current_employee_id, is_own_data_only, has_minimum_role,
)

log = logging.getLogger(__name__)

fleet_bp = Blueprint("fleet", __name__)

# Per-module sub-navigation for CrewAsset
MODULE_NAVS = {
    "crewasset": [
        {"id": "vehicles", "label": "Vehicles", "href": "/fleet/"},
        {"id": "inventory", "label": "Inventory", "href": "#", "disabled": True},
        {"id": "equipment", "label": "Equipment", "href": "#", "disabled": True},
    ],
}


def _render_module(template, active_subnav="", **kwargs):
    """Render a template with CrewAsset module navigation context."""
    role = get_current_role()
    role_level = {"super_admin": 4, "company_admin": 3, "manager": 2, "employee": 1}.get(role, 1)
    nav_items = MODULE_NAVS.get("crewasset", [])
    defaults = {
        "can_edit": role_level >= 3,
        "can_export": role_level >= 3,
        "user_role": role,
    }
    defaults.update(kwargs)
    return render_template(
        template,
        active_module="crewasset",
        active_subnav=active_subnav,
        module_nav=nav_items,
        **defaults,
    )


# ── Fleet Overview ────────────────────────────────────────────


@fleet_bp.route("/fleet/")
@login_required
def fleet_overview():
    """Fleet overview — all vehicles with aggregated maintenance stats.

    If the request accepts JSON, return data as JSON.
    Otherwise, render the fleet.html template.
    """
    db = get_db()
    try:
        rows = db.execute("""
            SELECT
                v.id, v.year, v.make, v.model, v.nickname,
                v.plate_number, v.vin, v.color, v.tire_size,
                v.assigned_to, v.status,
                MAX(m.service_date) AS last_service_date,
                COALESCE(SUM(m.cost), 0) AS total_spend,
                COUNT(m.id) AS maintenance_count
            FROM vehicles v
            LEFT JOIN vehicle_maintenance m ON m.vehicle_id = v.id
            GROUP BY v.id
            ORDER BY v.nickname
        """).fetchall()

        vehicles = []
        for r in rows:
            # Get latest mileage from most recent service_date
            latest_mileage = None
            if r["last_service_date"]:
                ml = db.execute("""
                    SELECT mileage FROM vehicle_maintenance
                    WHERE vehicle_id = ? AND service_date = ?
                    ORDER BY id DESC LIMIT 1
                """, (r["id"], r["last_service_date"])).fetchone()
                if ml:
                    latest_mileage = ml["mileage"]

            vehicles.append({
                "id": r["id"],
                "year": r["year"],
                "make": r["make"],
                "model": r["model"],
                "nickname": r["nickname"] or "",
                "plate_number": r["plate_number"] or "",
                "vin": r["vin"] or "",
                "color": r["color"] or "",
                "tire_size": r["tire_size"] or "",
                "assigned_to": r["assigned_to"] or "",
                "status": r["status"],
                "last_service_date": r["last_service_date"],
                "total_spend": round(r["total_spend"], 2),
                "maintenance_count": r["maintenance_count"],
                "latest_mileage": latest_mileage,
            })

        total_vehicles = len(vehicles)
        total_spend = round(sum(v["total_spend"] for v in vehicles), 2)

        # Vehicles needing service: no maintenance in last 90 days
        needing_service = 0
        for v in vehicles:
            if v["status"] != "active":
                continue
            if not v["last_service_date"]:
                needing_service += 1
            else:
                try:
                    last_dt = datetime.strptime(v["last_service_date"], "%Y-%m-%d")
                    if (datetime.now() - last_dt).days > 90:
                        needing_service += 1
                except ValueError:
                    needing_service += 1

        avg_cost = round(total_spend / total_vehicles, 2) if total_vehicles > 0 else 0

        summary = {
            "total_vehicles": total_vehicles,
            "total_spend": total_spend,
            "vehicles_needing_service": needing_service,
            "avg_cost_per_vehicle": avg_cost,
        }

        if request.accept_mimetypes.best_match(["application/json", "text/html"]) == "application/json":
            return jsonify({"vehicles": vehicles, "summary": summary})

        return _render_module(
            "fleet.html",
            active_subnav="vehicles",
            vehicles=vehicles,
            summary=summary,
        )
    finally:
        db.close()


# ── Vehicle Detail ────────────────────────────────────────────


@fleet_bp.route("/fleet/<int:vehicle_id>")
@login_required
def vehicle_detail(vehicle_id):
    """Vehicle detail page — vehicle info + maintenance history."""
    db = get_db()
    try:
        vehicle = db.execute(
            "SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)
        ).fetchone()
        if not vehicle:
            abort(404)

        maintenance = db.execute("""
            SELECT * FROM vehicle_maintenance
            WHERE vehicle_id = ?
            ORDER BY service_date DESC
        """, (vehicle_id,)).fetchall()

        # Vendor summary: name, visit count, total spend
        vendor_summary = db.execute("""
            SELECT vendor, COUNT(*) AS visit_count, COALESCE(SUM(cost), 0) AS total_spend
            FROM vehicle_maintenance
            WHERE vehicle_id = ? AND vendor IS NOT NULL AND vendor != ''
            GROUP BY vendor
            ORDER BY total_spend DESC
        """, (vehicle_id,)).fetchall()

        # Total spend and latest mileage
        stats_row = db.execute("""
            SELECT COALESCE(SUM(cost), 0) AS total_spend, COUNT(*) AS record_count
            FROM vehicle_maintenance WHERE vehicle_id = ?
        """, (vehicle_id,)).fetchone()

        latest_mileage_row = db.execute("""
            SELECT mileage FROM vehicle_maintenance
            WHERE vehicle_id = ? AND mileage IS NOT NULL
            ORDER BY service_date DESC, id DESC LIMIT 1
        """, (vehicle_id,)).fetchone()

        return _render_module(
            "fleet_detail.html",
            active_subnav="vehicles",
            vehicle=dict(vehicle),
            maintenance=[dict(m) for m in maintenance],
            vendor_summary=[dict(vs) for vs in vendor_summary],
            total_spend=round(stats_row["total_spend"], 2),
            record_count=stats_row["record_count"],
            latest_mileage=latest_mileage_row["mileage"] if latest_mileage_row else None,
        )
    finally:
        db.close()


# ── Maintenance JSON Endpoint ─────────────────────────────────


@fleet_bp.route("/fleet/<int:vehicle_id>/maintenance")
@login_required
def vehicle_maintenance_list(vehicle_id):
    """Return maintenance records for a vehicle as JSON."""
    db = get_db()
    try:
        vehicle = db.execute(
            "SELECT id FROM vehicles WHERE id = ?", (vehicle_id,)
        ).fetchone()
        if not vehicle:
            abort(404)

        records = db.execute("""
            SELECT * FROM vehicle_maintenance
            WHERE vehicle_id = ?
            ORDER BY service_date DESC
        """, (vehicle_id,)).fetchall()

        return jsonify({"maintenance": [dict(r) for r in records]})
    finally:
        db.close()


# ── Add Maintenance Record ────────────────────────────────────


@fleet_bp.route("/fleet/<int:vehicle_id>/maintenance", methods=["POST"])
@login_required
@require_permission("crewasset", "edit")
def add_maintenance(vehicle_id):
    """Add a maintenance record to a vehicle.

    Requires edit permission on crewasset (manager+).
    """
    db = get_db()
    try:
        vehicle = db.execute(
            "SELECT id FROM vehicles WHERE id = ?", (vehicle_id,)
        ).fetchone()
        if not vehicle:
            abort(404)

        data = request.get_json(silent=True) or {}
        service_date = data.get("service_date")
        description = data.get("description")
        cost = data.get("cost")
        mileage = data.get("mileage")
        vendor = data.get("vendor")

        if not description:
            return jsonify({"error": "description is required"}), 400

        cursor = db.execute("""
            INSERT INTO vehicle_maintenance (vehicle_id, service_date, description, cost, mileage, vendor)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (vehicle_id, service_date, description, cost, mileage, vendor))
        db.commit()

        return jsonify({"id": cursor.lastrowid, "message": "Maintenance record added"}), 201
    finally:
        db.close()


# ── Edit Maintenance Record ───────────────────────────────────


@fleet_bp.route("/fleet/maintenance/<int:record_id>", methods=["PUT"])
@login_required
@require_permission("crewasset", "edit")
def edit_maintenance(record_id):
    """Edit a maintenance record.

    Requires edit permission on crewasset (company_admin+).
    """
    db = get_db()
    try:
        record = db.execute(
            "SELECT * FROM vehicle_maintenance WHERE id = ?", (record_id,)
        ).fetchone()
        if not record:
            abort(404)

        data = request.get_json(silent=True) or {}

        fields = []
        values = []
        for col in ("service_date", "description", "cost", "mileage", "vendor"):
            if col in data:
                fields.append(f"{col} = ?")
                values.append(data[col])

        if not fields:
            return jsonify({"error": "No fields to update"}), 400

        values.append(record_id)
        db.execute(
            f"UPDATE vehicle_maintenance SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        db.commit()

        return jsonify({"message": "Maintenance record updated"})
    finally:
        db.close()


# ── Delete Maintenance Record ─────────────────────────────────


@fleet_bp.route("/fleet/maintenance/<int:record_id>", methods=["DELETE"])
@login_required
@require_role("super_admin", "company_admin")
def delete_maintenance(record_id):
    """Delete a maintenance record.

    Restricted to super_admin and company_admin.
    """
    db = get_db()
    try:
        record = db.execute(
            "SELECT id FROM vehicle_maintenance WHERE id = ?", (record_id,)
        ).fetchone()
        if not record:
            abort(404)

        db.execute("DELETE FROM vehicle_maintenance WHERE id = ?", (record_id,))
        db.commit()

        return jsonify({"message": "Maintenance record deleted"})
    finally:
        db.close()
