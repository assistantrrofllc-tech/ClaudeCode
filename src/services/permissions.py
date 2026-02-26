"""
Role-based permission system for CrewOS.

Roles (highest to lowest):
    super_admin  (4) — Full platform control, user management
    company_admin (3) — Full data access, no settings/user management
    manager      (2) — View all data, no edit/export
    employee     (1) — View own data only, masked contacts

Access levels per module: none < view < edit < admin

The require_role() and require_permission() decorators protect routes.
"""

from functools import wraps

from flask import abort, redirect, session, url_for

from src.database.connection import get_db

# ── Role hierarchy ────────────────────────────────────────

ROLE_HIERARCHY = {
    "super_admin": 4,
    "company_admin": 3,
    "manager": 2,
    "employee": 1,
}

# Access level ordering — higher index = more access
ACCESS_LEVELS = ["none", "view", "edit", "admin"]

# Default access by role → module → access level
DEFAULT_ACCESS = {
    "super_admin": {
        "crewledger": "admin",
        "crewcert": "admin",
        "crewschedule": "admin",
        "crewasset": "admin",
        "crewinventory": "admin",
        "crewcomms": "admin",
        "settings": "admin",
        "user_management": "admin",
    },
    "company_admin": {
        "crewledger": "edit",
        "crewcert": "edit",
        "crewschedule": "edit",
        "crewasset": "edit",
        "crewinventory": "edit",
        "crewcomms": "edit",
        "settings": "none",
        "user_management": "none",
    },
    "manager": {
        "crewledger": "view",
        "crewcert": "view",
        "crewschedule": "view",
        "crewasset": "view",
        "crewinventory": "view",
        "crewcomms": "view",
        "settings": "none",
        "user_management": "none",
    },
    "employee": {
        "crewledger": "view",
        "crewcert": "view",
        "crewschedule": "none",
        "crewasset": "none",
        "crewinventory": "none",
        "crewcomms": "none",
        "settings": "none",
        "user_management": "none",
    },
}


# ── Session helpers ───────────────────────────────────────

def get_current_role() -> str:
    """Get the current user's system_role from the session."""
    user = session.get("user")
    if not user:
        return "employee"
    return user.get("system_role", "employee")


def get_current_employee_id() -> int | None:
    """Get the current user's employee_id from the session."""
    return session.get("employee_id")


def get_role_level(role: str) -> int:
    """Get the numeric level for a role string."""
    return ROLE_HIERARCHY.get(role, 0)


def has_role(*roles: str) -> bool:
    """Check if the current user has one of the specified roles."""
    current = get_current_role()
    return current in roles


def has_minimum_role(min_role: str) -> bool:
    """Check if the current user's role level >= the minimum role level."""
    return get_role_level(get_current_role()) >= get_role_level(min_role)


def is_own_data_only() -> bool:
    """True if the user should only see their own data (employee role).

    Returns False for any non-employee role, and also False if the session
    is missing system_role (stale session from before permissions migration).
    """
    user = session.get("user")
    if not user:
        return False
    # Only restrict to own data when explicitly set to employee role
    return user.get("system_role") == "employee"


# ── Permission checking ──────────────────────────────────

def check_permission(user_id: int | None, module: str, required_level: str) -> bool:
    """Check if a user has the required access level for a module.

    Uses DEFAULT_ACCESS based on role. Falls back to user_permissions table
    for per-module overrides (future use).

    Args:
        user_id: Ignored (kept for backward compatibility). Uses session.
        module: Module name (e.g., 'crewledger', 'crewcert').
        required_level: Minimum access level needed ('view', 'edit', 'admin').

    Returns:
        True if user has sufficient access, False otherwise.
    """
    try:
        role = get_current_role()
    except RuntimeError:
        return True  # Outside request context = allow

    if not session.get("user"):
        return True  # No auth session (shouldn't happen with @login_required)

    # Get default access for the role
    role_defaults = DEFAULT_ACCESS.get(role, {})
    user_level = role_defaults.get(module, "none")

    required_idx = ACCESS_LEVELS.index(required_level) if required_level in ACCESS_LEVELS else 0
    user_idx = ACCESS_LEVELS.index(user_level) if user_level in ACCESS_LEVELS else 0

    if user_idx >= required_idx:
        return True

    # Check per-module override in user_permissions table
    employee_id = get_current_employee_id()
    if employee_id:
        db = get_db()
        try:
            perm = db.execute(
                "SELECT access_level FROM user_permissions WHERE user_id = ? AND module = ?",
                (employee_id, module),
            ).fetchone()
            if perm:
                override_idx = ACCESS_LEVELS.index(perm["access_level"]) if perm["access_level"] in ACCESS_LEVELS else 0
                return override_idx >= required_idx
        finally:
            db.close()

    return False


def get_user_permissions(user_id: int) -> dict:
    """Get all module permissions for a user.

    Returns: {"crewledger": "edit", "crewcert": "view", ...}
    """
    db = get_db()
    try:
        rows = db.execute(
            "SELECT module, access_level FROM user_permissions WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        return {r["module"]: r["access_level"] for r in rows}
    finally:
        db.close()


# ── Route protection decorators ───────────────────────────

def require_role(*allowed_roles):
    """Decorator that restricts a route to specific roles.

    Usage:
        @require_role("super_admin", "company_admin")
        def admin_route():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            role = get_current_role()
            if role not in allowed_roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def require_permission(module: str, level: str):
    """Decorator that checks module-level permission.

    Usage:
        @require_permission("crewledger", "edit")
        def edit_receipt():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not check_permission(None, module, level):
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def require_module_access(module: str):
    """Decorator that redirects to home if the user lacks view access to a module.

    super_admin always passes. Other roles are checked against DEFAULT_ACCESS
    and per-user overrides via check_permission().

    Usage:
        @require_module_access("crewledger")
        def ledger_page():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            role = get_current_role()
            if role == "super_admin":
                return f(*args, **kwargs)
            if not check_permission(None, module, "view"):
                return redirect("/")
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Data masking helpers ──────────────────────────────────

def mask_phone(phone: str) -> str:
    """Mask a phone number for restricted users. Shows last 4 digits."""
    if not phone or len(phone) < 4:
        return phone or ""
    return "***-***-" + phone[-4:]


def mask_email(email: str) -> str:
    """Mask an email for restricted users. Shows first char + domain."""
    if not email or "@" not in email:
        return email or ""
    local, domain = email.split("@", 1)
    return local[0] + "***@" + domain
