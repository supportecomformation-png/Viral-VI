from functools import wraps

from flask import session, redirect, url_for, flash, g, request, jsonify
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
    """Réserve la vue aux utilisateurs connectés.

    Les routes /api/* reçoivent un 401 JSON ; les pages sont redirigées vers
    la connexion, avec `next` pour revenir sur la page demandée ensuite.
    """
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.get("user") is None:
            if request.path.startswith("/api/"):
                return jsonify({"error": "auth_required",
                                "message": "Connecte-toi pour continuer."}), 401
            flash("Connecte-toi pour accéder à cette page.", "error")
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return wrapped_view
