from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user, login_required


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                flash("Você não tem permissão para acessar esta área.", "error")
                return redirect(url_for("dashboard.index"))
            return view(*args, **kwargs)
        return wrapped
    return decorator
