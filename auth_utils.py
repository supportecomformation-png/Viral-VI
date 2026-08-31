from functools import wraps

from flask import session, redirect, url_for, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

from db import query_one


def hash_password(raw_password):
    return generate_password_hash(raw_password)


def verify_password(password_hash, raw_password):
    return check_password_hash(password_hash, raw_password)


def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        g.user = query_one("SELECT * FROM users WHERE id = ?", (user_id,))


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.get("user") is None:
            flash("Connecte-toi pour accéder à cette page.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped_view
