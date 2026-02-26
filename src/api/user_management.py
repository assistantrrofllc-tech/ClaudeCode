"""
User management — super_admin only.

CRUD for authorized_users table: add/remove users, change roles,
link employee records.
"""

import logging

from flask import Blueprint, jsonify, render_template, request

from src.database.connection import get_db
from src.services.auth import login_required
from src.services.permissions import require_role

log = logging.getLogger(__name__)

user_mgmt_bp = Blueprint("user_mgmt", __name__)

VALID_SYSTEM_ROLES = ("super_admin", "company_admin", "manager", "employee")


@user_mgmt_bp.route("/admin/users")
@login_required
@require_role("super_admin")
def users_page():
    """User management page — list all authorized users."""
    db = get_db()
    try:
        users = db.execute("""
            SELECT au.*, e.first_name as emp_first_name, e.full_name as emp_full_name
            FROM authorized_users au
            LEFT JOIN employees e ON au.employee_id = e.id
            ORDER BY au.email
        """).fetchall()
        employees = db.execute(
            "SELECT id, first_name, full_name FROM employees WHERE is_active = 1 ORDER BY first_name"
        ).fetchall()
        return render_template(
            "user_management.html",
            users=[dict(u) for u in users],
            employees=[dict(e) for e in employees],
            valid_roles=VALID_SYSTEM_ROLES,
        )
    finally:
        db.close()


@user_mgmt_bp.route("/api/admin/users", methods=["GET"])
@login_required
@require_role("super_admin")
def api_list_users():
    """List all authorized users as JSON."""
    db = get_db()
    try:
        users = db.execute("""
            SELECT au.*, e.first_name as emp_first_name, e.full_name as emp_full_name
            FROM authorized_users au
            LEFT JOIN employees e ON au.employee_id = e.id
            ORDER BY au.email
        """).fetchall()
        return jsonify([dict(u) for u in users])
    finally:
        db.close()


@user_mgmt_bp.route("/api/admin/users", methods=["POST"])
@login_required
@require_role("super_admin")
def api_add_user():
    """Add a new authorized user."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Valid email is required"}), 400

    system_role = data.get("system_role", "employee")
    if system_role not in VALID_SYSTEM_ROLES:
        return jsonify({"error": f"Invalid role: {system_role}"}), 400

    employee_id = data.get("employee_id") or None
    name = (data.get("name") or "").strip()

    # Map system_role to legacy role for backward compatibility
    legacy_map = {"super_admin": "admin", "company_admin": "admin", "manager": "manager", "employee": "viewer"}
    legacy_role = legacy_map.get(system_role, "viewer")

    db = get_db()
    try:
        existing = db.execute("SELECT id FROM authorized_users WHERE email = ?", (email,)).fetchone()
        if existing:
            return jsonify({"error": "Email already exists"}), 409

        db.execute(
            """INSERT INTO authorized_users (email, name, role, system_role, employee_id)
               VALUES (?, ?, ?, ?, ?)""",
            (email, name, legacy_role, system_role, employee_id),
        )
        db.commit()
        log.info("Authorized user added: %s (system_role=%s)", email, system_role)
        return jsonify({"status": "created", "email": email}), 201
    finally:
        db.close()


@user_mgmt_bp.route("/api/admin/users/<int:user_id>", methods=["PUT"])
@login_required
@require_role("super_admin")
def api_update_user(user_id):
    """Update an authorized user's role or employee link."""
    data = request.get_json(silent=True) or {}
    db = get_db()
    try:
        user = db.execute("SELECT * FROM authorized_users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404

        updates = []
        params = []

        if "system_role" in data:
            if data["system_role"] not in VALID_SYSTEM_ROLES:
                return jsonify({"error": f"Invalid role: {data['system_role']}"}), 400
            updates.append("system_role = ?")
            params.append(data["system_role"])
            # Sync legacy role
            legacy_map = {"super_admin": "admin", "company_admin": "admin", "manager": "manager", "employee": "viewer"}
            updates.append("role = ?")
            params.append(legacy_map.get(data["system_role"], "viewer"))

        if "employee_id" in data:
            updates.append("employee_id = ?")
            params.append(data["employee_id"] or None)

        if "is_active" in data:
            updates.append("is_active = ?")
            params.append(1 if data["is_active"] else 0)

        if "name" in data:
            updates.append("name = ?")
            params.append(data["name"])

        if not updates:
            return jsonify({"error": "No valid fields to update"}), 400

        params.append(user_id)
        db.execute(f"UPDATE authorized_users SET {', '.join(updates)} WHERE id = ?", params)
        db.commit()

        log.info("Authorized user #%d updated: %s", user_id, ", ".join(k for k in data if k in ("system_role", "employee_id", "is_active")))
        return jsonify({"status": "updated"})
    finally:
        db.close()


@user_mgmt_bp.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@login_required
@require_role("super_admin")
def api_delete_user(user_id):
    """Remove an authorized user (permanently)."""
    db = get_db()
    try:
        user = db.execute("SELECT * FROM authorized_users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404

        db.execute("DELETE FROM authorized_users WHERE id = ?", (user_id,))
        db.commit()
        log.info("Authorized user removed: %s", user["email"])
        return jsonify({"status": "deleted"})
    finally:
        db.close()
