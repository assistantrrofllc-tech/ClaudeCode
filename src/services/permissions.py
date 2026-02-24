"""
Permission checking for CrewOS modules.

Access levels (ordered): none < view < edit < admin
System roles: super_admin, company_admin, manager, employee

Until auth is implemented, check_permission() returns True by default
(no user session = admin access). When auth is added, it will read
the user_id from the Flask session.
"""

from flask import session

from src.database.connection import get_db

# Access level ordering — higher index = more access
ACCESS_LEVELS = ["none", "view", "edit", "admin"]


def check_permission(user_id: int | None, module: str, required_level: str) -> bool:
    """Check if a user has the required access level for a module.

    Args:
        user_id: Employee ID. If None, checks session. If no session, returns True.
        module: Module name (e.g., 'crewcert', 'crewledger').
        required_level: Minimum access level needed ('view', 'edit', 'admin').

    Returns:
        True if user has sufficient access, False otherwise.
    """
    # No auth yet — default to allow
    if user_id is None:
        try:
            user_id = session.get("user_id")
        except RuntimeError:
            return True  # Outside request context = allow
    if user_id is None:
        return True  # No auth session = admin access (permissive default)

    required_idx = ACCESS_LEVELS.index(required_level) if required_level in ACCESS_LEVELS else 0

    db = get_db()
    try:
        # Check system role first — super_admin and company_admin bypass module permissions
        emp = db.execute(
            "SELECT system_role FROM employees WHERE id = ?", (user_id,)
        ).fetchone()
        if emp and emp["system_role"] in ("super_admin", "company_admin"):
            return True

        # Check module-specific permission
        perm = db.execute(
            "SELECT access_level FROM user_permissions WHERE user_id = ? AND module = ?",
            (user_id, module),
        ).fetchone()

        if not perm:
            return False  # No permission record = no access

        user_idx = ACCESS_LEVELS.index(perm["access_level"]) if perm["access_level"] in ACCESS_LEVELS else 0
        return user_idx >= required_idx
    finally:
        db.close()


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
