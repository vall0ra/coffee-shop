from functools import wraps

from flask import abort
from flask_login import current_user

from app.models import User


def role_required(*roles):
    """Restrict a route to logged-in Users (not Members) with one of the given roles.
    Enforced server-side — never rely on the frontend to hide manager-only pages.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or not isinstance(current_user, User):
                abort(403)
            if current_user.role not in roles:
                abort(403)
            if not current_user.active:
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def next_order_number():
    """Generate the next sequential order number, e.g. #10007."""
    from app import db
    from app.models import Order
    count = db.session.query(Order).count()
    return f"#{10001 + count}"
