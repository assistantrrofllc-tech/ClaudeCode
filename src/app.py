"""
CrewLedger — Flask application entry point.

Run with:
    python src/app.py
"""

import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from flask import Flask

from config.settings import APP_HOST, APP_PORT, APP_DEBUG, SECRET_KEY
from src.api.twilio_webhook import twilio_bp
from src.api.reports import reports_bp
from src.api.dashboard import dashboard_bp


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parent.parent / "dashboard" / "templates"),
        static_folder=str(Path(__file__).resolve().parent.parent / "dashboard" / "static"),
    )
    app.secret_key = SECRET_KEY

    # Register blueprints
    app.register_blueprint(twilio_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(dashboard_bp)

    @app.route("/health")
    def health():
        return {"status": "ok", "service": "crewledger"}

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host=APP_HOST, port=APP_PORT, debug=APP_DEBUG)
