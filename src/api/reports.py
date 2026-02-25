"""
Report API endpoints.

Provides endpoints to trigger and preview weekly reports.
The /reports/weekly/send endpoint can be hit by a cron job
every Monday morning to deliver the report automatically.
"""

import logging

from flask import Blueprint, request, jsonify

from src.database.connection import get_db
from src.services.auth import login_required
from src.services.report_generator import get_weekly_report_data
from src.services.email_sender import send_weekly_report, render_report_html, render_report_plaintext

log = logging.getLogger(__name__)

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/reports/weekly/preview", methods=["GET"])
@login_required
def preview_weekly_report():
    """Render the weekly report as HTML in the browser for review.

    Query params:
        week_start: YYYY-MM-DD (optional, defaults to last week)
        week_end:   YYYY-MM-DD (optional, defaults to last week)
    """
    week_start = request.args.get("week_start")
    week_end = request.args.get("week_end")

    db = get_db()
    try:
        report = get_weekly_report_data(db, week_start, week_end)
        html = render_report_html(report)
        return html, 200, {"Content-Type": "text/html"}
    finally:
        db.close()


@reports_bp.route("/reports/weekly/send", methods=["POST"])
@login_required
def send_weekly_report_endpoint():
    """Send the weekly report email.

    Intended to be called by a cron job or manually from the dashboard.

    JSON body (all optional):
        recipient:  Override email address
        week_start: YYYY-MM-DD
        week_end:   YYYY-MM-DD
    """
    data = request.get_json(silent=True) or {}
    recipient = data.get("recipient")
    week_start = data.get("week_start")
    week_end = data.get("week_end")

    db = get_db()
    try:
        success = send_weekly_report(
            recipient=recipient,
            week_start=week_start,
            week_end=week_end,
            db=db,
        )
        if success:
            return jsonify({"status": "sent", "recipient": recipient or "default"}), 200
        return jsonify({"status": "failed", "error": "Check server logs for details"}), 500
    finally:
        db.close()


@reports_bp.route("/reports/weekly/data", methods=["GET"])
@login_required
def weekly_report_data():
    """Return the raw weekly report data as JSON (for dashboard consumption).

    Query params:
        week_start: YYYY-MM-DD (optional)
        week_end:   YYYY-MM-DD (optional)
    """
    week_start = request.args.get("week_start")
    week_end = request.args.get("week_end")

    db = get_db()
    try:
        report = get_weekly_report_data(db, week_start, week_end)
        return jsonify(report), 200
    finally:
        db.close()
