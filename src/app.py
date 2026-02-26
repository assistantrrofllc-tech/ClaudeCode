"""
CrewLedger — Flask application entry point.

Run with:
    python src/app.py
"""

import atexit
import logging
import os
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from datetime import timedelta

from flask import Flask, send_from_directory, session

from config.settings import APP_HOST, APP_PORT, APP_DEBUG, SECRET_KEY
from src.api.twilio_webhook import twilio_bp
from src.api.reports import reports_bp
from src.api.export import export_bp
from src.api.dashboard import dashboard_bp
from src.api.admin_tools import admin_bp
from src.api.auth import auth_bp, init_oauth
from src.api.user_management import user_mgmt_bp
from src.api.fleet import fleet_bp

log = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parent.parent / "dashboard" / "templates"),
        static_folder=str(Path(__file__).resolve().parent.parent / "dashboard" / "static"),
    )
    app.secret_key = SECRET_KEY
    app.permanent_session_lifetime = timedelta(hours=24)

    # Google OAuth config
    app.config["GOOGLE_CLIENT_ID"] = os.environ.get("GOOGLE_CLIENT_ID", "")
    app.config["GOOGLE_CLIENT_SECRET"] = os.environ.get("GOOGLE_CLIENT_SECRET", "")

    # Initialize OAuth
    init_oauth(app)

    # Cache-busting version for static files (changes on each deploy)
    app.config["CACHE_VERSION"] = os.environ.get("CACHE_VERSION", "20")

    # CrewOS module definitions — available to all templates
    CREWOS_MODULES = [
        {"id": "crewledger", "label": "CrewLedger", "href": "/ledger", "enabled": True},
        {"id": "crewcert", "label": "CrewCert", "href": "/crewcert", "enabled": True},
        {"id": "crewschedule", "label": "CrewSchedule", "href": "#", "enabled": False},
        {"id": "crewasset", "label": "CrewAsset", "href": "/fleet/", "enabled": True},
        {"id": "crewinventory", "label": "CrewInventory", "href": "#", "enabled": False},
    ]

    @app.context_processor
    def inject_globals():
        user = session.get("user")
        user_role = user.get("system_role", "employee") if user else "employee"
        role_level = {"super_admin": 4, "company_admin": 3, "manager": 2, "employee": 1}.get(user_role, 1)

        # Filter modules — employee only sees enabled modules with view access
        visible_modules = CREWOS_MODULES
        if user and user_role == "employee":
            from src.services.permissions import DEFAULT_ACCESS
            emp_access = DEFAULT_ACCESS.get("employee", {})
            visible_modules = [
                m for m in CREWOS_MODULES
                if emp_access.get(m["id"], "none") != "none" or not m["enabled"]
            ]

        return {
            "cache_version": app.config["CACHE_VERSION"],
            "crewos_modules": visible_modules,
            "current_user": user,
            "user_role": user_role,
            "can_edit": role_level >= 3,  # company_admin+
            "can_export": role_level >= 3,  # company_admin+
            "can_manage_employees": role_level >= 3,  # company_admin+
            "can_manage_settings": role_level >= 4,  # super_admin only
        }

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(twilio_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(user_mgmt_bp)
    app.register_blueprint(fleet_bp)

    @app.route("/health")
    def health():
        return {"status": "ok", "service": "crewledger"}

    # Legal pages (public, no auth required)
    legal_dir = str(Path(__file__).resolve().parent.parent / "legal")

    @app.route("/legal/privacy-policy")
    def legal_privacy():
        return send_from_directory(legal_dir, "privacy-policy.html")

    @app.route("/legal/terms-and-conditions")
    def legal_terms():
        return send_from_directory(legal_dir, "terms.html")

    @app.route("/legal")
    def legal_index():
        return send_from_directory(legal_dir, "index.html")

    # Start cert status refresh scheduler (daily at 6am + on startup)
    # Skip during testing to avoid spawning threads per test
    if os.environ.get("TESTING") != "1":
        _start_cert_scheduler(app)

    return app


def _start_cert_scheduler(app):
    """Start the daily cert status refresh job using APScheduler."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from src.services.cert_refresh import run_cert_status_refresh

        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(
            func=run_cert_status_refresh,
            trigger="cron",
            hour=6,
            minute=0,
            id="daily_cert_refresh",
            replace_existing=True,
        )
        scheduler.start()
        atexit.register(scheduler.shutdown)
        app.config["CERT_SCHEDULER"] = scheduler

        # Run on startup (in background thread to not block app startup)
        import threading
        threading.Thread(target=run_cert_status_refresh, daemon=True).start()

        log.info("Cert status scheduler started (daily at 6:00am)")
    except ImportError:
        log.warning("APScheduler not installed — cert refresh job disabled")
    except Exception:
        log.exception("Failed to start cert scheduler")


if __name__ == "__main__":
    app = create_app()
    app.run(host=APP_HOST, port=APP_PORT, debug=APP_DEBUG)
