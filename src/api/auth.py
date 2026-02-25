"""
Google OAuth authentication routes.

Routes:
    GET  /auth/login     — login page with Google button
    GET  /auth/google    — redirect to Google OAuth
    GET  /auth/callback  — handle Google's response
    GET  /auth/logout    — clear session, redirect to login
"""

import logging

from authlib.integrations.flask_client import OAuth
from flask import Blueprint, redirect, render_template, request, session, url_for

from src.database.connection import get_db

log = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)

# OAuth client — initialized by init_oauth() called from app.py
oauth = OAuth()


def init_oauth(app):
    """Register the Google OAuth provider with the Flask app."""
    oauth.init_app(app)
    oauth.register(
        name="google",
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


@auth_bp.route("/auth/login")
def login():
    """Show the login page, or redirect home if already authenticated."""
    if session.get("user"):
        return redirect("/")
    return render_template("login.html")


@auth_bp.route("/auth/google")
def google_login():
    """Redirect user to Google's OAuth consent screen."""
    # Preserve the ?next= param through the OAuth flow
    next_url = request.args.get("next", "/")
    session["_auth_next"] = next_url
    redirect_uri = url_for("auth.callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/auth/callback")
def callback():
    """Handle Google's OAuth callback."""
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get("userinfo")
        if not user_info:
            user_info = oauth.google.userinfo()
    except Exception:
        log.exception("OAuth callback failed")
        return redirect(url_for("auth.login"))

    email = user_info.get("email", "").lower()
    name = user_info.get("name", "")
    picture = user_info.get("picture", "")

    # Check authorized_users table
    db = get_db()
    try:
        user = db.execute(
            "SELECT * FROM authorized_users WHERE email = ? AND is_active = 1",
            (email,),
        ).fetchone()

        if not user:
            log.warning("Unauthorized login attempt: %s", email)
            return render_template("access_denied.html", email=email)

        # Update last_login
        db.execute(
            "UPDATE authorized_users SET last_login = datetime('now'), name = ? WHERE id = ?",
            (name, user["id"]),
        )
        db.commit()

        # Create session
        session["user"] = {
            "email": email,
            "name": name,
            "picture": picture,
            "role": user["role"],
        }
        session.permanent = True

        log.info("User logged in: %s (%s)", email, user["role"])
    finally:
        db.close()

    next_url = session.pop("_auth_next", "/")
    return redirect(next_url)


@auth_bp.route("/auth/logout")
def logout():
    """Clear session and redirect to login."""
    user = session.get("user", {})
    session.clear()
    log.info("User logged out: %s", user.get("email", "unknown"))
    return redirect(url_for("auth.login"))
