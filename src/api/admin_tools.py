"""
Admin tools — cert PDF splitter, CSV import, and other admin-only utilities.
"""

import csv
import io
import json
import logging
import shutil
import tempfile
import uuid
from pathlib import Path

from flask import Blueprint, render_template, request, jsonify, abort
from thefuzz import fuzz

from config.settings import CERT_STORAGE_PATH
from src.database.connection import get_db

log = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__)

# Temp storage for upload sessions (in-memory tracking, files on disk)
_upload_sessions = {}


@admin_bp.route("/admin/cert-splitter")
def cert_splitter_page():
    """Admin tool — PDF splitter for multi-page cert documents."""
    db = get_db()
    try:
        employees = db.execute(
            "SELECT id, first_name, full_name, employee_uuid FROM employees WHERE is_active = 1 ORDER BY first_name"
        ).fetchall()
        cert_types = db.execute(
            "SELECT id, name, slug FROM certification_types WHERE is_active = 1 ORDER BY sort_order"
        ).fetchall()
        return render_template(
            "cert_splitter.html",
            employees=[dict(e) for e in employees],
            cert_types=[dict(ct) for ct in cert_types],
        )
    finally:
        db.close()


@admin_bp.route("/admin/cert-splitter/upload", methods=["POST"])
def cert_splitter_upload():
    """Upload a multi-page PDF, split into pages, extract text from each."""
    import pdfplumber
    from pypdf import PdfReader, PdfWriter

    if "pdf" not in request.files:
        return jsonify({"error": "No PDF file uploaded"}), 400

    pdf_file = request.files["pdf"]
    if not pdf_file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "File must be a PDF"}), 400

    # Save upload to temp dir
    session_id = str(uuid.uuid4())
    tmp_dir = Path(tempfile.mkdtemp(prefix="certsplit_"))
    upload_path = tmp_dir / "upload.pdf"
    pdf_file.save(str(upload_path))

    try:
        # Extract text per page with pdfplumber
        page_data = []
        with pdfplumber.open(str(upload_path)) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                page_data.append({
                    "page_num": i + 1,
                    "extracted_text": text[:500],  # Limit text preview
                    "suggested_name": _extract_name_from_text(text),
                })

        # Split into individual page PDFs with pypdf
        reader = PdfReader(str(upload_path))
        for i in range(len(reader.pages)):
            writer = PdfWriter()
            writer.add_page(reader.pages[i])
            page_path = tmp_dir / f"page_{i + 1}.pdf"
            with open(str(page_path), "wb") as f:
                writer.write(f)

        # Store session info
        _upload_sessions[session_id] = {
            "tmp_dir": str(tmp_dir),
            "page_count": len(page_data),
            "original_filename": pdf_file.filename,
        }

        return jsonify({
            "session_id": session_id,
            "page_count": len(page_data),
            "pages": page_data,
        })

    except Exception as e:
        shutil.rmtree(str(tmp_dir), ignore_errors=True)
        log.error("PDF split failed: %s", e)
        return jsonify({"error": f"Failed to process PDF: {str(e)}"}), 500


@admin_bp.route("/admin/cert-splitter/save", methods=["POST"])
def cert_splitter_save():
    """Save assigned pages to employee cert storage directories.

    Expects JSON: {
        "session_id": "...",
        "cert_type_id": 4,
        "issued_at": "2024-11-02",
        "expires_at": "2027-11-02",
        "assignments": [
            {"page_num": 1, "employee_id": 5},
            {"page_num": 2, "employee_id": 8},
            ...
        ]
    }
    """
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    assignments = data.get("assignments", [])
    cert_type_id = data.get("cert_type_id")
    issued_at = data.get("issued_at")
    expires_at = data.get("expires_at")
    issuing_org = data.get("issuing_org", "")

    if not session_id or session_id not in _upload_sessions:
        return jsonify({"error": "Invalid or expired session"}), 400
    if not assignments:
        return jsonify({"error": "No assignments provided"}), 400

    session = _upload_sessions[session_id]
    tmp_dir = Path(session["tmp_dir"])

    db = get_db()
    try:
        # Get cert type slug for filename
        ct = db.execute("SELECT slug FROM certification_types WHERE id = ?", (cert_type_id,)).fetchone()
        cert_slug = ct["slug"] if ct else "cert"

        saved = []
        skipped = []

        for assignment in assignments:
            page_num = assignment.get("page_num")
            employee_id = assignment.get("employee_id")

            if not page_num or not employee_id:
                skipped.append({"page_num": page_num, "reason": "Missing page or employee"})
                continue

            # Get employee UUID for storage path
            emp = db.execute(
                "SELECT id, employee_uuid, first_name, full_name FROM employees WHERE id = ?",
                (employee_id,),
            ).fetchone()
            if not emp:
                skipped.append({"page_num": page_num, "reason": "Employee not found"})
                continue

            # Source page file
            page_path = tmp_dir / f"page_{page_num}.pdf"
            if not page_path.exists():
                skipped.append({"page_num": page_num, "reason": "Page file not found"})
                continue

            # Destination
            emp_dir = Path(CERT_STORAGE_PATH) / emp["employee_uuid"]
            emp_dir.mkdir(parents=True, exist_ok=True)

            date_str = issued_at or "undated"
            dest_filename = f"{cert_slug}_{date_str}.pdf"
            dest_path = emp_dir / dest_filename

            # Don't overwrite existing files
            if dest_path.exists():
                counter = 1
                while dest_path.exists():
                    dest_filename = f"{cert_slug}_{date_str}_{counter}.pdf"
                    dest_path = emp_dir / dest_filename
                    counter += 1

            shutil.copy2(str(page_path), str(dest_path))

            # Build document_path relative for DB storage
            doc_path = f"/certifications/document/{emp['employee_uuid']}/{dest_filename}"

            # Link to cert record if one exists, or create one
            existing = db.execute(
                """SELECT id FROM certifications
                   WHERE employee_id = ? AND cert_type_id = ? AND is_active = 1
                   ORDER BY issued_at DESC LIMIT 1""",
                (employee_id, cert_type_id),
            ).fetchone()

            if existing:
                db.execute(
                    "UPDATE certifications SET document_path = ?, updated_at = datetime('now') WHERE id = ?",
                    (doc_path, existing["id"]),
                )
            else:
                db.execute(
                    """INSERT INTO certifications
                       (employee_id, cert_type_id, issued_at, expires_at, document_path, issuing_org)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (employee_id, cert_type_id, issued_at, expires_at, doc_path, issuing_org),
                )

            saved.append({
                "page_num": page_num,
                "employee": emp["full_name"] or emp["first_name"],
                "file": dest_filename,
            })

        db.commit()

        # Cleanup temp files
        shutil.rmtree(str(tmp_dir), ignore_errors=True)
        del _upload_sessions[session_id]

        return jsonify({
            "status": "complete",
            "saved": len(saved),
            "skipped": len(skipped),
            "details": saved,
            "skipped_details": skipped,
        })

    except Exception as e:
        log.error("Cert splitter save failed: %s", e)
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


def _extract_name_from_text(text: str) -> str:
    """Try to extract a person's name from cert page text.

    Simple heuristic: look for lines that look like names
    (2-3 capitalized words, no numbers).
    """
    if not text:
        return ""

    lines = text.strip().split("\n")
    for line in lines:
        line = line.strip()
        # Skip empty lines and very short/long lines
        if not line or len(line) < 5 or len(line) > 50:
            continue
        # Skip lines with numbers (likely dates, cert numbers)
        if any(c.isdigit() for c in line):
            continue
        # Check if it looks like a name (2-4 words, mostly alpha)
        words = line.split()
        if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
            alpha_ratio = sum(c.isalpha() or c.isspace() for c in line) / len(line)
            if alpha_ratio > 0.9:
                return line

    return ""


# ── Bulk CSV Import ──────────────────────────────────────────


@admin_bp.route("/admin/cert-import")
def cert_import_page():
    """Admin tool — bulk CSV import for certifications."""
    db = get_db()
    try:
        employees = db.execute(
            "SELECT id, first_name, full_name FROM employees WHERE is_active = 1 ORDER BY first_name"
        ).fetchall()
        cert_types = db.execute(
            "SELECT id, name, slug FROM certification_types WHERE is_active = 1 ORDER BY sort_order"
        ).fetchall()
        return render_template(
            "cert_import.html",
            employees=[dict(e) for e in employees],
            cert_types=[dict(ct) for ct in cert_types],
        )
    finally:
        db.close()


@admin_bp.route("/admin/cert-import/upload", methods=["POST"])
def cert_import_upload():
    """Parse CSV and fuzzy-match employee names, return preview data."""
    if "csv" not in request.files:
        return jsonify({"error": "No CSV file uploaded"}), 400

    csv_file = request.files["csv"]
    content = csv_file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))

    db = get_db()
    try:
        employees = db.execute(
            "SELECT id, first_name, full_name FROM employees WHERE is_active = 1"
        ).fetchall()
        emp_list = [{"id": e["id"], "name": e["full_name"] or e["first_name"]} for e in employees]

        cert_types = db.execute(
            "SELECT id, name FROM certification_types WHERE is_active = 1"
        ).fetchall()
        ct_list = [{"id": ct["id"], "name": ct["name"]} for ct in cert_types]

        rows = []
        for i, row in enumerate(reader):
            emp_name = (row.get("Employee Name") or row.get("employee_name") or "").strip()
            cert_name = (row.get("Certification Type") or row.get("cert_type") or "").strip()
            issued = (row.get("Issue Date") or row.get("issued_at") or "").strip()
            expires = (row.get("Expiry Date") or row.get("expires_at") or "").strip()
            issuing_org = (row.get("Issuing Org") or row.get("issuing_org") or "").strip()
            notes = (row.get("Notes") or row.get("notes") or "").strip()

            # Fuzzy match employee
            emp_match = _fuzzy_match(emp_name, emp_list)

            # Fuzzy match cert type
            ct_match = _fuzzy_match(cert_name, ct_list)

            # Check for duplicate
            is_duplicate = False
            if emp_match["id"] and ct_match["id"] and issued:
                dup = db.execute(
                    """SELECT id FROM certifications
                       WHERE employee_id = ? AND cert_type_id = ? AND issued_at = ? AND is_active = 1""",
                    (emp_match["id"], ct_match["id"], issued),
                ).fetchone()
                is_duplicate = bool(dup)

            rows.append({
                "row_num": i + 1,
                "employee_name": emp_name,
                "employee_match": emp_match,
                "cert_type_name": cert_name,
                "cert_type_match": ct_match,
                "issued_at": issued,
                "expires_at": expires,
                "issuing_org": issuing_org,
                "notes": notes,
                "is_duplicate": is_duplicate,
            })

        return jsonify({"rows": rows, "count": len(rows)})
    finally:
        db.close()


@admin_bp.route("/admin/cert-import/save", methods=["POST"])
def cert_import_save():
    """Import selected certification rows.

    Expects JSON: {
        "rows": [
            {"employee_id": 5, "cert_type_id": 4, "issued_at": "...", "expires_at": "...", "issuing_org": "...", "notes": "..."},
            ...
        ]
    }
    """
    data = request.get_json(silent=True) or {}
    rows = data.get("rows", [])
    if not rows:
        return jsonify({"error": "No rows to import"}), 400

    db = get_db()
    try:
        imported = 0
        skipped = 0
        errors = []

        for row in rows:
            emp_id = row.get("employee_id")
            ct_id = row.get("cert_type_id")
            issued = row.get("issued_at")
            expires = row.get("expires_at")

            if not emp_id or not ct_id:
                errors.append({"row": row, "reason": "Missing employee or cert type"})
                continue

            # Skip duplicates
            if issued:
                dup = db.execute(
                    """SELECT id FROM certifications
                       WHERE employee_id = ? AND cert_type_id = ? AND issued_at = ? AND is_active = 1""",
                    (emp_id, ct_id, issued),
                ).fetchone()
                if dup:
                    skipped += 1
                    continue

            db.execute(
                """INSERT INTO certifications
                   (employee_id, cert_type_id, issued_at, expires_at, issuing_org, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (emp_id, ct_id, issued or None, expires or None,
                 row.get("issuing_org") or None, row.get("notes") or None),
            )
            imported += 1

        db.commit()

        return jsonify({
            "status": "complete",
            "imported": imported,
            "skipped": skipped,
            "errors": len(errors),
            "error_details": errors[:10],
        })
    finally:
        db.close()


def _fuzzy_match(name: str, candidates: list) -> dict:
    """Fuzzy match a name against a list of {id, name} dicts.

    Returns: {"id": int|None, "name": str, "score": int, "confidence": str}
    """
    if not name or not candidates:
        return {"id": None, "name": "", "score": 0, "confidence": "none"}

    best_id = None
    best_name = ""
    best_score = 0

    for c in candidates:
        score = fuzz.token_sort_ratio(name.lower(), c["name"].lower())
        if score > best_score:
            best_score = score
            best_id = c["id"]
            best_name = c["name"]

    if best_score >= 80:
        confidence = "high"
    elif best_score >= 60:
        confidence = "medium"
    else:
        confidence = "low"

    return {"id": best_id, "name": best_name, "score": best_score, "confidence": confidence}
