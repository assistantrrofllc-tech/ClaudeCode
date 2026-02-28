"""CrewCert training scheduling and intake routes."""

from __future__ import annotations

import json
from datetime import datetime

from flask import Blueprint, abort, jsonify, render_template, request

from src.database.connection import get_db
from src.services.auth import login_required
from src.services.permissions import check_permission, require_module_access
from src.services.email_sender import send_custom_email
from src.api.dashboard import MODULE_NAVS

training_bp = Blueprint("training", __name__)


CERT_DURATION_YEARS = {
    "OSHA 10": 5,
    "OSHA 30": 5,
    "Fall Protection Competent Person": 2,
    "Fall Protection": 2,
    "CPR / First Aid / AED": 2,
    "CPR/First Aid/AED": 2,
    "Aerial Work Platform": 3,
    "Extended Reach Forklift": 3,
    "Forklift / Extended Reach": 3,
}


def _render_training(template: str, active_subnav: str, **kwargs):
    role_can_edit = check_permission(None, "crewcert", "edit")
    nav_items = MODULE_NAVS.get("crewcert", [])
    return render_template(
        template,
        active_module="crewcert",
        active_subnav=active_subnav,
        module_nav=nav_items,
        can_manage_training=role_can_edit,
        **kwargs,
    )


def _json_load(raw: str | None):
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


def _serialize_provider(row):
    out = dict(row)
    out["certs_offered"] = _json_load(out.get("certs_offered"))
    return out


def _format_timeframe(value: str | None) -> str:
    labels = {
        "asap": "ASAP",
        "2_weeks": "Within 2 weeks",
        "30_days": "Within 30 days",
        "60_days": "Within 60 days",
        "flexible": "Flexible",
    }
    return labels.get(value or "", value or "")


def _format_location(value: str | None) -> str:
    labels = {
        "onsite": "On-site",
        "provider": "Provider facility",
        "either": "Either",
    }
    return labels.get(value or "", value or "")


def _provider_email_bodies(provider: dict, payload: dict):
    cert_lines = "\n".join(f"- {c}" for c in payload["certs_requested"])
    subject = f"CrewOS Training Request — {payload.get('company_name') or 'Client'}"

    plain = f"""Hi {provider.get('contact_name') or 'Trainer'},

We'd like to schedule certification training for our crew.
Here are the details:

Certifications Needed:
{cert_lines}

Number of Attendees: {payload.get('num_employees') or ''}
Preferred Timeframe: {_format_timeframe(payload.get('timeframe'))}
Preferred Location: {_format_location(payload.get('location_pref'))}

Contact Information:
- Name: {payload.get('contact_name')}
- Email: {payload.get('contact_email')}
- Phone: {payload.get('contact_phone') or ''}
- Company: {payload.get('company_name') or ''}

Additional Notes:
{payload.get('notes') or ''}

Please reply to this email with available dates and pricing.

---
Sent via CrewOS — CrewCert Module
"""

    html_cert_lines = "".join(f"<li>{c}</li>" for c in payload["certs_requested"])
    html = f"""<p>Hi {provider.get('contact_name') or 'Trainer'},</p>
<p>We'd like to schedule certification training for our crew. Here are the details:</p>
<p><strong>Certifications Needed:</strong></p>
<ul>{html_cert_lines}</ul>
<p><strong>Number of Attendees:</strong> {payload.get('num_employees') or ''}<br>
<strong>Preferred Timeframe:</strong> {_format_timeframe(payload.get('timeframe'))}<br>
<strong>Preferred Location:</strong> {_format_location(payload.get('location_pref'))}</p>
<p><strong>Contact Information:</strong><br>
Name: {payload.get('contact_name')}<br>
Email: {payload.get('contact_email')}<br>
Phone: {payload.get('contact_phone') or ''}<br>
Company: {payload.get('company_name') or ''}</p>
<p><strong>Additional Notes:</strong><br>{payload.get('notes') or ''}</p>
<p>Please reply to this email with available dates and pricing.</p>
<hr>
<p>Sent via CrewOS — CrewCert Module</p>
"""

    return subject, plain, html


def _resolve_cert_type_id(db, cert_name: str):
    normalized = cert_name.strip().lower()
    row = db.execute(
        "SELECT id FROM certification_types WHERE lower(name) = lower(?) AND is_active = 1",
        (cert_name,),
    ).fetchone()
    if row:
        return row["id"]

    if "forklift" in normalized:
        alt = "Extended Reach Forklift"
    elif "cpr" in normalized or "first aid" in normalized:
        alt = "First Aid / CPR"
    elif "fall" in normalized:
        alt = "Fall Protection"
    else:
        alt = cert_name

    row = db.execute(
        "SELECT id FROM certification_types WHERE lower(name) = lower(?) AND is_active = 1",
        (alt,),
    ).fetchone()
    return row["id"] if row else None


def _next_expiry_for(cert_name: str, issued_date: str):
    dt = datetime.strptime(issued_date, "%Y-%m-%d")
    years = CERT_DURATION_YEARS.get(cert_name, 1)
    try:
        return dt.replace(year=dt.year + years).strftime("%Y-%m-%d")
    except ValueError:
        # leap-day safe fallback
        return dt.replace(month=2, day=28, year=dt.year + years).strftime("%Y-%m-%d")


# ---------------- Pages ----------------


@training_bp.route("/crewcert/training")
@login_required
@require_module_access("crewcert")
def training_hub_page():
    return _render_training("training_hub.html", "training")


@training_bp.route("/crewcert/training/providers")
@login_required
@require_module_access("crewcert")
def training_providers_page():
    return _render_training("training_providers.html", "training")


@training_bp.route("/crewcert/training/sessions/<int:session_id>")
@login_required
@require_module_access("crewcert")
def training_session_detail_page(session_id: int):
    db = get_db()
    try:
        session = db.execute(
            """
            SELECT ts.*, tp.company_name AS trainer_name, p.name AS project_name
            FROM training_sessions ts
            LEFT JOIN training_providers tp ON tp.id = ts.trainer_id
            LEFT JOIN projects p ON p.id = ts.project_id
            WHERE ts.id = ?
            """,
            (session_id,),
        ).fetchone()
        if not session:
            abort(404)

        certs = db.execute(
            "SELECT cert_type FROM training_session_certs WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        attendees = db.execute(
            """
            SELECT tsa.*, e.first_name, e.full_name, e.crew
            FROM training_session_attendees tsa
            JOIN employees e ON e.id = tsa.employee_id
            WHERE tsa.session_id = ?
            ORDER BY e.crew, e.first_name
            """,
            (session_id,),
        ).fetchall()

        return _render_training(
            "training_session_detail.html",
            "training",
            session=dict(session),
            certs=[c["cert_type"] for c in certs],
            attendees=[dict(a) for a in attendees],
        )
    finally:
        db.close()


# ---------------- Providers API ----------------


@training_bp.get("/api/training-providers")
@login_required
@require_module_access("crewcert")
def api_training_providers():
    include_inactive = request.args.get("include_inactive") == "1"
    db = get_db()
    try:
        if include_inactive and check_permission(None, "crewcert", "edit"):
            rows = db.execute("SELECT * FROM training_providers ORDER BY company_name").fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM training_providers WHERE status = 'active' ORDER BY company_name"
            ).fetchall()
        return jsonify([_serialize_provider(r) for r in rows])
    finally:
        db.close()


@training_bp.post("/api/training-providers")
@login_required
@require_module_access("crewcert")
def api_training_providers_create():
    if not check_permission(None, "crewcert", "edit"):
        return jsonify({"error": "forbidden"}), 403

    body = request.get_json(force=True)
    required = ["company_name", "contact_email"]
    missing = [k for k in required if not (body.get(k) or "").strip()]
    if missing:
        return jsonify({"error": "missing_fields", "fields": missing}), 400

    certs_offered = body.get("certs_offered") or []
    if not isinstance(certs_offered, list):
        return jsonify({"error": "invalid_certs_offered"}), 400

    db = get_db()
    try:
        cur = db.execute(
            """
            INSERT INTO training_providers (
                company_name, contact_name, contact_email, contact_phone,
                website, certs_offered, logo_path, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.get("company_name"),
                body.get("contact_name"),
                body.get("contact_email"),
                body.get("contact_phone"),
                body.get("website"),
                json.dumps(certs_offered),
                body.get("logo_path"),
                body.get("status", "active"),
                body.get("notes"),
            ),
        )
        db.commit()
        row = db.execute("SELECT * FROM training_providers WHERE id = ?", (cur.lastrowid,)).fetchone()
        return jsonify(_serialize_provider(row)), 201
    finally:
        db.close()


@training_bp.put("/api/training-providers/<int:provider_id>")
@login_required
@require_module_access("crewcert")
def api_training_providers_update(provider_id: int):
    if not check_permission(None, "crewcert", "edit"):
        return jsonify({"error": "forbidden"}), 403

    body = request.get_json(force=True)
    fields = [
        "company_name", "contact_name", "contact_email", "contact_phone",
        "website", "certs_offered", "logo_path", "status", "notes",
    ]

    sets = []
    values = []
    for f in fields:
        if f in body:
            sets.append(f"{f} = ?")
            v = body[f]
            if f == "certs_offered":
                if not isinstance(v, list):
                    return jsonify({"error": "invalid_certs_offered"}), 400
                v = json.dumps(v)
            values.append(v)

    if not sets:
        return jsonify({"error": "no_changes"}), 400

    db = get_db()
    try:
        exists = db.execute("SELECT id FROM training_providers WHERE id = ?", (provider_id,)).fetchone()
        if not exists:
            return jsonify({"error": "not_found"}), 404

        values.append(provider_id)
        db.execute(f"UPDATE training_providers SET {', '.join(sets)} WHERE id = ?", values)
        db.commit()
        row = db.execute("SELECT * FROM training_providers WHERE id = ?", (provider_id,)).fetchone()
        return jsonify(_serialize_provider(row))
    finally:
        db.close()


@training_bp.delete("/api/training-providers/<int:provider_id>")
@login_required
@require_module_access("crewcert")
def api_training_providers_delete(provider_id: int):
    if not check_permission(None, "crewcert", "edit"):
        return jsonify({"error": "forbidden"}), 403

    db = get_db()
    try:
        cur = db.execute(
            "UPDATE training_providers SET status = 'inactive' WHERE id = ?",
            (provider_id,),
        )
        db.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "not_found"}), 404
        return jsonify({"success": True})
    finally:
        db.close()


# ---------------- Requests API ----------------


@training_bp.post("/api/training-requests")
@login_required
@require_module_access("crewcert")
def api_training_requests_create():
    body = request.get_json(force=True)

    required = ["provider_id", "contact_name", "contact_email", "certs_requested"]
    missing = [k for k in required if not body.get(k)]
    if missing:
        return jsonify({"error": "missing_fields", "fields": missing}), 400

    certs_requested = body.get("certs_requested")
    if not isinstance(certs_requested, list) or len(certs_requested) == 0:
        return jsonify({"error": "invalid_certs_requested"}), 400

    db = get_db()
    try:
        provider = db.execute(
            "SELECT * FROM training_providers WHERE id = ? AND status = 'active'",
            (body["provider_id"],),
        ).fetchone()
        if not provider:
            return jsonify({"error": "provider_not_found"}), 404

        provider_dict = _serialize_provider(provider)

        subject, plain_body, html_body = _provider_email_bodies(provider_dict, body)
        sent = send_custom_email(
            to_email=provider["contact_email"],
            subject=subject,
            html_body=html_body,
            plain_body=plain_body,
            reply_to=body.get("contact_email"),
            cc_email=body.get("contact_email"),
        )

        status = "submitted" if sent else "draft"
        email_sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if sent else None

        cur = db.execute(
            """
            INSERT INTO training_requests (
                provider_id, company_name, contact_name, contact_email, contact_phone,
                certs_requested, num_employees, timeframe, location_pref, notes,
                status, email_sent_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body["provider_id"],
                body.get("company_name"),
                body["contact_name"],
                body["contact_email"],
                body.get("contact_phone"),
                json.dumps(certs_requested),
                body.get("num_employees"),
                body.get("timeframe"),
                body.get("location_pref"),
                body.get("notes"),
                status,
                email_sent_at,
            ),
        )
        db.commit()

        row = db.execute(
            """
            SELECT tr.*, tp.company_name as provider_company, tp.contact_name as provider_contact
            FROM training_requests tr
            JOIN training_providers tp ON tp.id = tr.provider_id
            WHERE tr.id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()

        out = dict(row)
        out["certs_requested"] = _json_load(out.get("certs_requested"))
        out["email_send_success"] = sent

        if not sent:
            return jsonify({"error": "email_failed", "request": out}), 502
        return jsonify(out), 201
    finally:
        db.close()


@training_bp.get("/api/training-requests")
@login_required
@require_module_access("crewcert")
def api_training_requests_list():
    limit = request.args.get("limit", type=int)
    db = get_db()
    try:
        query = """
            SELECT tr.*, tp.company_name AS provider_company, tp.contact_name AS provider_contact
            FROM training_requests tr
            JOIN training_providers tp ON tp.id = tr.provider_id
            ORDER BY tr.created_at DESC
        """
        params = []
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        rows = db.execute(query, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["certs_requested"] = _json_load(d.get("certs_requested"))
            out.append(d)
        return jsonify(out)
    finally:
        db.close()


@training_bp.put("/api/training-requests/<int:request_id>")
@login_required
@require_module_access("crewcert")
def api_training_requests_update(request_id: int):
    if not check_permission(None, "crewcert", "edit"):
        return jsonify({"error": "forbidden"}), 403

    body = request.get_json(force=True)
    allowed = {"status", "notes", "timeframe", "location_pref", "num_employees"}
    update_fields = [k for k in body.keys() if k in allowed]
    if not update_fields:
        return jsonify({"error": "no_changes"}), 400

    sets = []
    values = []
    for f in update_fields:
        sets.append(f"{f} = ?")
        values.append(body[f])

    db = get_db()
    try:
        values.append(request_id)
        cur = db.execute(
            f"UPDATE training_requests SET {', '.join(sets)} WHERE id = ?",
            values,
        )
        db.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "not_found"}), 404
        row = db.execute("SELECT * FROM training_requests WHERE id = ?", (request_id,)).fetchone()
        d = dict(row)
        d["certs_requested"] = _json_load(d.get("certs_requested"))
        return jsonify(d)
    finally:
        db.close()


# ---------------- Sessions API ----------------


@training_bp.get("/api/training-sessions")
@login_required
@require_module_access("crewcert")
def api_training_sessions_list():
    limit = request.args.get("limit", type=int)
    db = get_db()
    try:
        query = """
            SELECT ts.*, tp.company_name AS trainer_name, p.name AS project_name
            FROM training_sessions ts
            LEFT JOIN training_providers tp ON tp.id = ts.trainer_id
            LEFT JOIN projects p ON p.id = ts.project_id
            ORDER BY COALESCE(ts.session_date, ts.preferred_date_start) ASC, ts.created_at DESC
        """
        params = []
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        rows = db.execute(query, params).fetchall()

        out = []
        for r in rows:
            d = dict(r)
            certs = db.execute(
                "SELECT cert_type FROM training_session_certs WHERE session_id = ? ORDER BY id",
                (d["id"],),
            ).fetchall()
            d["certs"] = [c["cert_type"] for c in certs]
            out.append(d)
        return jsonify(out)
    finally:
        db.close()


@training_bp.post("/api/training-sessions")
@login_required
@require_module_access("crewcert")
def api_training_sessions_create():
    if not check_permission(None, "crewcert", "edit"):
        return jsonify({"error": "forbidden"}), 403

    body = request.get_json(force=True)
    certs = body.get("certs") or []
    if not isinstance(certs, list) or not certs:
        return jsonify({"error": "missing_certs"}), 400

    db = get_db()
    try:
        cur = db.execute(
            """
            INSERT INTO training_sessions (
                title, trainer_id, session_date, session_time,
                preferred_date_start, preferred_date_end, location, project_id,
                request_id, num_attendees, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.get("title"),
                body.get("trainer_id"),
                body.get("session_date"),
                body.get("session_time"),
                body.get("preferred_date_start"),
                body.get("preferred_date_end"),
                body.get("location"),
                body.get("project_id"),
                body.get("request_id"),
                body.get("num_attendees"),
                body.get("status", "requested"),
                body.get("notes"),
            ),
        )
        session_id = cur.lastrowid

        for cert in certs:
            db.execute(
                "INSERT INTO training_session_certs (session_id, cert_type) VALUES (?, ?)",
                (session_id, cert),
            )

        db.commit()
        row = db.execute("SELECT * FROM training_sessions WHERE id = ?", (session_id,)).fetchone()
        out = dict(row)
        out["certs"] = certs
        return jsonify(out), 201
    finally:
        db.close()


@training_bp.put("/api/training-sessions/<int:session_id>")
@login_required
@require_module_access("crewcert")
def api_training_sessions_update(session_id: int):
    if not check_permission(None, "crewcert", "edit"):
        return jsonify({"error": "forbidden"}), 403

    body = request.get_json(force=True)
    allowed = {
        "title", "trainer_id", "session_date", "session_time", "preferred_date_start",
        "preferred_date_end", "location", "project_id", "request_id", "num_attendees",
        "status", "notes",
    }
    fields = [k for k in body.keys() if k in allowed]
    if not fields and "certs" not in body:
        return jsonify({"error": "no_changes"}), 400

    db = get_db()
    try:
        exists = db.execute("SELECT id FROM training_sessions WHERE id = ?", (session_id,)).fetchone()
        if not exists:
            return jsonify({"error": "not_found"}), 404

        if fields:
            sets = [f"{f} = ?" for f in fields]
            values = [body[f] for f in fields]
            values.append(session_id)
            db.execute(f"UPDATE training_sessions SET {', '.join(sets)} WHERE id = ?", values)

        if "certs" in body:
            certs = body.get("certs") or []
            if not isinstance(certs, list):
                return jsonify({"error": "invalid_certs"}), 400
            db.execute("DELETE FROM training_session_certs WHERE session_id = ?", (session_id,))
            for cert in certs:
                db.execute(
                    "INSERT INTO training_session_certs (session_id, cert_type) VALUES (?, ?)",
                    (session_id, cert),
                )

        db.commit()
        row = db.execute("SELECT * FROM training_sessions WHERE id = ?", (session_id,)).fetchone()
        out = dict(row)
        certs = db.execute(
            "SELECT cert_type FROM training_session_certs WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        out["certs"] = [c["cert_type"] for c in certs]
        return jsonify(out)
    finally:
        db.close()


@training_bp.get("/api/training-sessions/<int:session_id>/attendees")
@login_required
@require_module_access("crewcert")
def api_training_session_attendees_list(session_id: int):
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT tsa.*, e.first_name, e.full_name, e.crew
            FROM training_session_attendees tsa
            JOIN employees e ON e.id = tsa.employee_id
            WHERE tsa.session_id = ?
            ORDER BY e.crew, e.first_name
            """,
            (session_id,),
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        db.close()


@training_bp.post("/api/training-sessions/<int:session_id>/attendees")
@login_required
@require_module_access("crewcert")
def api_training_session_attendees_assign(session_id: int):
    if not check_permission(None, "crewcert", "edit"):
        return jsonify({"error": "forbidden"}), 403

    body = request.get_json(force=True)
    employee_ids = body.get("employee_ids") or []
    if not isinstance(employee_ids, list) or len(employee_ids) == 0:
        return jsonify({"error": "missing_employee_ids"}), 400

    db = get_db()
    try:
        for emp_id in employee_ids:
            db.execute(
                """
                INSERT INTO training_session_attendees (session_id, employee_id, attended, cert_updated)
                VALUES (?, ?, 0, 0)
                ON CONFLICT(session_id, employee_id) DO NOTHING
                """,
                (session_id, emp_id),
            )

        db.execute(
            "UPDATE training_sessions SET num_attendees = (SELECT COUNT(*) FROM training_session_attendees WHERE session_id = ?) WHERE id = ?",
            (session_id, session_id),
        )
        db.commit()
        return jsonify({"success": True})
    finally:
        db.close()


@training_bp.put("/api/training-sessions/<int:session_id>/attendees/<int:emp_id>")
@login_required
@require_module_access("crewcert")
def api_training_session_attendee_mark(session_id: int, emp_id: int):
    if not check_permission(None, "crewcert", "edit"):
        return jsonify({"error": "forbidden"}), 403

    body = request.get_json(force=True)
    attended = 1 if body.get("attended") else 0
    notes = body.get("notes")

    db = get_db()
    try:
        cur = db.execute(
            """
            UPDATE training_session_attendees
            SET attended = ?, notes = ?
            WHERE session_id = ? AND employee_id = ?
            """,
            (attended, notes, session_id, emp_id),
        )
        db.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "not_found"}), 404
        return jsonify({"success": True})
    finally:
        db.close()


@training_bp.post("/api/training-sessions/<int:session_id>/complete")
@login_required
@require_module_access("crewcert")
def api_training_session_complete(session_id: int):
    if not check_permission(None, "crewcert", "edit"):
        return jsonify({"error": "forbidden"}), 403

    body = request.get_json(force=True)
    session_date = body.get("session_date")
    if not session_date:
        return jsonify({"error": "missing_session_date"}), 400

    db = get_db()
    try:
        session = db.execute("SELECT * FROM training_sessions WHERE id = ?", (session_id,)).fetchone()
        if not session:
            return jsonify({"error": "not_found"}), 404

        cert_rows = db.execute(
            "SELECT cert_type FROM training_session_certs WHERE session_id = ?",
            (session_id,),
        ).fetchall()
        cert_types = [r["cert_type"] for r in cert_rows]

        attendees = db.execute(
            "SELECT employee_id, attended FROM training_session_attendees WHERE session_id = ?",
            (session_id,),
        ).fetchall()

        updated_count = 0
        created_count = 0
        for a in attendees:
            if not a["attended"]:
                continue
            for cert_name in cert_types:
                cert_type_id = _resolve_cert_type_id(db, cert_name)
                if not cert_type_id:
                    continue

                expires_at = _next_expiry_for(cert_name, session_date)
                current = db.execute(
                    """
                    SELECT id FROM certifications
                    WHERE employee_id = ? AND cert_type_id = ? AND is_active = 1
                    ORDER BY updated_at DESC, id DESC LIMIT 1
                    """,
                    (a["employee_id"], cert_type_id),
                ).fetchone()

                if current:
                    db.execute(
                        """
                        UPDATE certifications
                        SET issued_at = ?, expires_at = ?, updated_at = datetime('now')
                        WHERE id = ?
                        """,
                        (session_date, expires_at, current["id"]),
                    )
                    updated_count += 1
                else:
                    db.execute(
                        """
                        INSERT INTO certifications (
                            employee_id, cert_type_id, issued_at, expires_at, notes, is_active
                        ) VALUES (?, ?, ?, ?, ?, 1)
                        """,
                        (
                            a["employee_id"],
                            cert_type_id,
                            session_date,
                            expires_at,
                            f"Auto-created from training session #{session_id}",
                        ),
                    )
                    created_count += 1

                db.execute(
                    """
                    UPDATE training_session_attendees
                    SET cert_updated = 1
                    WHERE session_id = ? AND employee_id = ?
                    """,
                    (session_id, a["employee_id"]),
                )

        db.execute(
            """
            UPDATE training_sessions
            SET status = 'completed', session_date = ?
            WHERE id = ?
            """,
            (session_date, session_id),
        )
        db.commit()

        return jsonify(
            {
                "success": True,
                "updated_certifications": updated_count,
                "created_certifications": created_count,
            }
        )
    finally:
        db.close()


# -------- dashboard helper APIs --------


@training_bp.get("/api/crew/employees/<int:employee_id>/upcoming-training")
@login_required
@require_module_access("crewcert")
def api_employee_upcoming_training(employee_id: int):
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT ts.id, ts.title, ts.session_date, ts.session_time, ts.location, ts.status,
                   tp.company_name AS trainer_name
            FROM training_session_attendees tsa
            JOIN training_sessions ts ON ts.id = tsa.session_id
            LEFT JOIN training_providers tp ON tp.id = ts.trainer_id
            WHERE tsa.employee_id = ?
              AND (ts.session_date IS NULL OR date(ts.session_date) >= date('now'))
              AND ts.status IN ('requested', 'confirmed', 'scheduled')
            ORDER BY COALESCE(ts.session_date, ts.preferred_date_start)
            """,
            (employee_id,),
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        db.close()



# ---------------- Simple Training Request Email ----------------


@training_bp.post("/api/training/send-request")
@login_required
@require_module_access("crewcert")
def api_send_training_request():
    """Send a training request email to a provider."""
    body = request.get_json(force=True)

    provider_id = body.get("provider_id")
    certs = body.get("certs") or []
    employee_names = body.get("employee_names") or []
    preferred_date = body.get("preferred_date") or ""
    location = body.get("location") or ""
    notes = body.get("notes") or ""

    if not provider_id:
        return jsonify({"error": "Select a training provider."}), 400
    if not certs:
        return jsonify({"error": "Select at least one certification."}), 400

    db = get_db()
    try:
        provider = db.execute(
            "SELECT * FROM training_providers WHERE id = ?", (provider_id,)
        ).fetchone()
        if not provider:
            return jsonify({"error": "Provider not found."}), 404

        provider_name = provider["company_name"]
        contact_name = provider["contact_name"] or "Training Coordinator"
        contact_email = provider["contact_email"]

        if not contact_email:
            return jsonify({"error": "Provider has no email address configured."}), 400

        # Build email
        cert_list = "\n".join(f"  - {c}" for c in certs)
        emp_list = "\n".join(f"  - {n}" for n in employee_names) if employee_names else "  (To be confirmed)"
        date_line = f"Preferred Date: {preferred_date}" if preferred_date else "Preferred Date: Flexible"
        location_line = f"Location: {location}" if location else "Location: To be discussed"
        notes_line = f"\nAdditional Notes:\n{notes}" if notes else ""

        subject = f"Training Request — {', '.join(certs[:3])}"
        if len(certs) > 3:
            subject += f" + {len(certs) - 3} more"

        plain_body = f"""Hi {contact_name},

We would like to schedule certification training for our crew. Below are the details:

Certifications Needed:
{cert_list}

Employees to Train ({len(employee_names)}):
{emp_list}

{date_line}
{location_line}
{notes_line}

Please reply with available dates and pricing. We look forward to hearing from you.

Best regards,
Roofing & Renovations of Florida LLC
---
Sent via CrewOS"""

        html_body = f"""<p>Hi {contact_name},</p>
<p>We would like to schedule certification training for our crew. Below are the details:</p>
<p><strong>Certifications Needed:</strong></p>
<ul>{"".join(f"<li>{c}</li>" for c in certs)}</ul>
<p><strong>Employees to Train ({len(employee_names)}):</strong></p>
<ul>{"".join(f"<li>{n}</li>" for n in employee_names) if employee_names else "<li><em>To be confirmed</em></li>"}</ul>
<p><strong>{date_line}</strong><br>
<strong>{location_line}</strong></p>
{"<p><strong>Additional Notes:</strong><br>" + notes + "</p>" if notes else ""}
<p>Please reply with available dates and pricing. We look forward to hearing from you.</p>
<p>Best regards,<br>Roofing &amp; Renovations of Florida LLC</p>
<hr><p style="font-size:12px; color:#999;">Sent via CrewOS</p>"""

        sent = send_custom_email(
            to_email=contact_email,
            subject=subject,
            html_body=html_body,
            plain_body=plain_body,
        )

        if not sent:
            return jsonify({"error": "Failed to send email. Check SMTP configuration."}), 502

        return jsonify({"success": True, "provider_name": provider_name})
    finally:
        db.close()
