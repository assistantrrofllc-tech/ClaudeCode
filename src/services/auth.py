"""
Authentication helpers for CrewOS.

Provides the @login_required decorator used by all protected routes.
"""

from functools import wraps

from flask import redirect, request, session, url_for


def login_required(f):
    """Decorator that redirects unauthenticated users to the login page.

    Preserves the original URL so the user lands there after login.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            next_url = request.url
            return redirect(url_for("auth.login", next=next_url))
        return f(*args, **kwargs)
    return decorated
