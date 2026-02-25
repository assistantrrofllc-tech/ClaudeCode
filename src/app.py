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

from flask import Flask, session

from config.settings import APP_HOST, APP_PORT, APP_DEBUG, SECRET_KEY
from src.api.twilio_webhook import twilio_bp
from src.api.reports import reports_bp
from src.api.export import export_bp
from src.api.dashboard import dashboard_bp
from src.api.admin_tools import admin_bp
from src.api.auth import auth_bp, init_oauth

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
    app.config["CACHE_VERSION"] = os.environ.get("CACHE_VERSION", "18")

    # CrewOS module definitions — available to all templates
    CREWOS_MODULES = [
        {"id": "crewledger", "label": "CrewLedger", "href": "/ledger", "enabled": True},
        {"id": "crewcert", "label": "CrewCert", "href": "/crewcert", "enabled": True},
        {"id": "crewschedule", "label": "CrewSchedule", "href": "#", "enabled": False},
        {"id": "crewasset", "label": "CrewAsset", "href": "#", "enabled": False},
        {"id": "crewinventory", "label": "CrewInventory", "href": "#", "enabled": False},
    ]

    @app.context_processor
    def inject_globals():
        return {
            "cache_version": app.config["CACHE_VERSION"],
            "crewos_modules": CREWOS_MODULES,
            "current_user": session.get("user"),
        }

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(twilio_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)

    @app.route("/health")
    def health():
        return {"status": "ok", "service": "crewledger"}

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
