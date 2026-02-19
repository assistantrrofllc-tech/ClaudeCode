"""
Weekly email report — rendering and sending.

Builds an HTML email from the report data and sends it via SMTP.
Kim opens her email Monday morning — everything is already organized.
"""

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config.settings import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    ACCOUNTANT_EMAIL,
)
from src.database.connection import get_db
from src.services.report_generator import get_weekly_report_data

log = logging.getLogger(__name__)


def send_weekly_report(
    recipient: str = None,
    week_start: str = None,
    week_end: str = None,
    db=None,
) -> bool:
    """Generate and send the weekly email report.

    Args:
        recipient: Override email address (defaults to ACCOUNTANT_EMAIL).
        week_start: YYYY-MM-DD (defaults to last Monday).
        week_end: YYYY-MM-DD (defaults to last Sunday).
        db: Optional DB connection (opens one if not provided).

    Returns:
        True on success, False on failure.
    """
    to_email = recipient or ACCOUNTANT_EMAIL
    if not to_email:
        log.error("No recipient email configured — set ACCOUNTANT_EMAIL")
        return False

    close_db = False
    if db is None:
        db = get_db()
        close_db = True

    try:
        report = get_weekly_report_data(db, week_start, week_end)

        if not report["employees"]:
            log.info("No receipts for week %s to %s — skipping email", report["week_start"], report["week_end"])
            return True

        subject = f"CrewLedger Weekly Report — {_format_date_range(report['week_start'], report['week_end'])}"
        html_body = render_report_html(report)
        plain_body = render_report_plaintext(report)

        return _send_email(to_email, subject, html_body, plain_body)
    finally:
        if close_db:
            db.close()


def render_report_html(report: dict) -> str:
    """Render the weekly report as an HTML email body."""
    week_range = _format_date_range(report["week_start"], report["week_end"])

    sections = []
    for emp in report["employees"]:
        sections.append(_render_employee_html(emp))

    flagged_note = ""
    if report["flagged_count"] > 0:
        flagged_note = f"""
        <div style="background:#FEE2E2;border-left:4px solid #DC2626;padding:12px 16px;margin-bottom:24px;border-radius:4px;">
            <strong style="color:#DC2626;">&#9888; {report['flagged_count']} flagged receipt{'s' if report['flagged_count'] != 1 else ''}</strong>
            — marked below for your attention
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#F3F4F6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:640px;margin:0 auto;padding:24px;">

    <!-- Header -->
    <div style="background:#1E3A5F;color:white;padding:24px;border-radius:8px 8px 0 0;">
        <h1 style="margin:0;font-size:22px;">CrewLedger Weekly Report</h1>
        <p style="margin:8px 0 0;opacity:0.85;font-size:14px;">{week_range}</p>
    </div>

    <!-- Summary Bar -->
    <div style="background:white;padding:20px 24px;border-bottom:1px solid #E5E7EB;">
        <table width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;">
        <tr>
            <td style="text-align:center;padding:0 8px;">
                <div style="font-size:28px;font-weight:bold;color:#1E3A5F;">${report['total_spend']:,.2f}</div>
                <div style="color:#6B7280;font-size:12px;">Total Spend</div>
            </td>
            <td style="text-align:center;padding:0 8px;">
                <div style="font-size:28px;font-weight:bold;color:#1E3A5F;">{report['total_receipts']}</div>
                <div style="color:#6B7280;font-size:12px;">Receipts</div>
            </td>
            <td style="text-align:center;padding:0 8px;">
                <div style="font-size:28px;font-weight:bold;color:#1E3A5F;">{len(report['employees'])}</div>
                <div style="color:#6B7280;font-size:12px;">Employees</div>
            </td>
        </tr>
        </table>
    </div>

    <!-- Content -->
    <div style="background:white;padding:24px;border-radius:0 0 8px 8px;">
        {flagged_note}
        {''.join(sections)}
    </div>

    <!-- Footer -->
    <div style="text-align:center;padding:16px;color:#9CA3AF;font-size:12px;">
        CrewLedger — Roofing &amp; Renovations of Florida LLC<br>
        Generated {datetime.now().strftime('%m/%d/%Y at %I:%M %p')}
    </div>

</div>
</body>
</html>"""


def _render_employee_html(emp: dict) -> str:
    """Render one employee's section."""
    # Daily summary rows
    daily_rows = ""
    for day, summary in emp["daily_summary"].items():
        day_display = _format_date_short(day)
        daily_rows += f"""
            <tr>
                <td style="padding:4px 8px;font-size:13px;">{day_display}</td>
                <td style="padding:4px 8px;font-size:13px;text-align:right;">{summary['count']} receipt{'s' if summary['count'] != 1 else ''}</td>
                <td style="padding:4px 8px;font-size:13px;text-align:right;font-weight:bold;">${summary['spend']:,.2f}</td>
            </tr>"""

    # Transaction rows
    tx_rows = ""
    for r in emp["receipts"]:
        badges = []
        if r["is_missed_receipt"]:
            badges.append('<span style="background:#FEF3C7;color:#D97706;padding:2px 6px;border-radius:3px;font-size:11px;">MISSED</span>')
        if r["is_return"]:
            badges.append('<span style="background:#DBEAFE;color:#2563EB;padding:2px 6px;border-radius:3px;font-size:11px;">RETURN</span>')
        if r["status"] == "flagged":
            reason = f" — {r['flag_reason']}" if r["flag_reason"] else ""
            badges.append(f'<span style="background:#FEE2E2;color:#DC2626;padding:2px 6px;border-radius:3px;font-size:11px;">FLAGGED{reason}</span>')
        status_badge = " ".join(badges)

        project = f"<br><span style='color:#6B7280;font-size:12px;'>Project: {r['project_name']}</span>" if r.get("project_name") else ""
        total_str = f"${r['total']:,.2f}" if r["total"] is not None else "—"
        date_str = _format_date_short(r["purchase_date"]) if r["purchase_date"] else "—"

        # Line items detail
        items_html = ""
        if r["line_items"]:
            item_lines = []
            for item in r["line_items"]:
                price = f"${item['extended_price']:,.2f}" if item["extended_price"] is not None else "—"
                qty = f" x{item['quantity']:.0f}" if item["quantity"] and item["quantity"] != 1 else ""
                item_lines.append(f"<span style='color:#6B7280;font-size:12px;'>{item['item_name']}{qty} — {price}</span>")
            items_html = "<br>" + "<br>".join(item_lines)

        tx_rows += f"""
            <tr style="border-bottom:1px solid #F3F4F6;">
                <td style="padding:8px;font-size:13px;vertical-align:top;">
                    <strong>{r['vendor_name']}</strong>{project}{items_html}
                </td>
                <td style="padding:8px;font-size:13px;text-align:center;vertical-align:top;">{date_str}</td>
                <td style="padding:8px;font-size:13px;text-align:right;vertical-align:top;">
                    {total_str}<br>{status_badge}
                </td>
            </tr>"""

    return f"""
    <!-- Employee: {emp['name']} -->
    <div style="margin-bottom:32px;">
        <div style="background:#F0F7FF;padding:12px 16px;border-radius:6px;margin-bottom:12px;">
            <h2 style="margin:0;font-size:16px;color:#1E3A5F;">
                {emp['name']}'s Week
                <span style="float:right;font-size:18px;">${emp['total_spend']:,.2f}</span>
            </h2>
            <span style="font-size:13px;color:#6B7280;">{emp['receipt_count']} receipt{'s' if emp['receipt_count'] != 1 else ''}</span>
        </div>

        <!-- Daily Summary -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:12px;">
            <tr style="border-bottom:1px solid #E5E7EB;">
                <th style="padding:4px 8px;font-size:12px;color:#6B7280;text-align:left;">Day</th>
                <th style="padding:4px 8px;font-size:12px;color:#6B7280;text-align:right;">Receipts</th>
                <th style="padding:4px 8px;font-size:12px;color:#6B7280;text-align:right;">Spend</th>
            </tr>
            {daily_rows}
        </table>

        <!-- Full Transaction Breakdown -->
        <table width="100%" cellpadding="0" cellspacing="0">
            <tr style="border-bottom:2px solid #E5E7EB;">
                <th style="padding:6px 8px;font-size:12px;color:#6B7280;text-align:left;">Vendor</th>
                <th style="padding:6px 8px;font-size:12px;color:#6B7280;text-align:center;">Date</th>
                <th style="padding:6px 8px;font-size:12px;color:#6B7280;text-align:right;">Amount</th>
            </tr>
            {tx_rows}
        </table>
    </div>"""


def render_report_plaintext(report: dict) -> str:
    """Render a plain-text fallback version of the report."""
    week_range = _format_date_range(report["week_start"], report["week_end"])
    lines = [
        f"CREWLEDGER WEEKLY REPORT — {week_range}",
        f"Total Spend: ${report['total_spend']:,.2f} | "
        f"Receipts: {report['total_receipts']} | "
        f"Employees: {len(report['employees'])}",
        "",
    ]

    if report["flagged_count"]:
        lines.append(f"*** {report['flagged_count']} FLAGGED RECEIPT(S) — SEE BELOW ***")
        lines.append("")

    for emp in report["employees"]:
        lines.append("=" * 50)
        lines.append(f"{emp['name']}'s Week — ${emp['total_spend']:,.2f} ({emp['receipt_count']} receipts)")
        lines.append("-" * 50)

        # Daily summary
        for day, s in emp["daily_summary"].items():
            lines.append(f"  {_format_date_short(day)}: {s['count']} receipt(s) — ${s['spend']:,.2f}")
        lines.append("")

        # Transaction detail
        for r in emp["receipts"]:
            date_str = _format_date_short(r["purchase_date"]) if r["purchase_date"] else "N/A"
            total_str = f"${r['total']:,.2f}" if r["total"] is not None else "N/A"
            flag = " [FLAGGED]" if r["status"] == "flagged" else ""
            missed = " [MISSED]" if r["is_missed_receipt"] else ""
            project = f" | Project: {r['project_name']}" if r.get("project_name") else ""
            lines.append(f"  {r['vendor_name']} — {date_str} — {total_str}{flag}{missed}{project}")
            for item in r["line_items"]:
                price = f"${item['extended_price']:,.2f}" if item["extended_price"] is not None else "N/A"
                lines.append(f"    - {item['item_name']} — {price}")
        lines.append("")

    lines.append(f"Generated {datetime.now().strftime('%m/%d/%Y at %I:%M %p')}")
    return "\n".join(lines)


def _send_email(to_email: str, subject: str, html_body: str, plain_body: str) -> bool:
    """Send an email via SMTP."""
    if not SMTP_USER or not SMTP_PASSWORD:
        log.error("SMTP credentials not configured — cannot send email")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to_email

    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())

        log.info("Weekly report sent to %s", to_email)
        return True
    except Exception as e:
        log.error("Failed to send email to %s: %s", to_email, e)
        return False


# ── Date formatting helpers ──────────────────────────────────


def _format_date_range(start: str, end: str) -> str:
    """'2026-02-09' + '2026-02-15' → 'Feb 9 – 15, 2026'."""
    try:
        s = datetime.strptime(start, "%Y-%m-%d")
        e = datetime.strptime(end, "%Y-%m-%d")
        if s.month == e.month and s.year == e.year:
            return f"{s.strftime('%b')} {s.day} – {e.day}, {s.year}"
        elif s.year == e.year:
            return f"{s.strftime('%b')} {s.day} – {e.strftime('%b')} {e.day}, {s.year}"
        return f"{s.strftime('%b %d, %Y')} – {e.strftime('%b %d, %Y')}"
    except (ValueError, TypeError):
        return f"{start} – {end}"


def _format_date_short(date_str: str) -> str:
    """'2026-02-09' → 'Mon 2/9'."""
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return f"{d.strftime('%a')} {d.month}/{d.day}"
    except (ValueError, TypeError):
        return date_str or "—"
