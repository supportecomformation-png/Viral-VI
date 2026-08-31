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
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.get("user") is None:
            flash("Connecte-toi pour accéder à cette page.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped_view


def is_subscribed(user):
    return bool(user) and user["plan"] == "pro"


def subscription_required(view):
    """Réserve la vue aux comptes avec un abonnement actif (`plan == 'pro'`)."""
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user = g.get("user")
        if user is None:
            if request.is_json:
                return jsonify({"error": "auth_required",
                                "message": "Connecte-toi pour continuer."}), 401
            flash("Connecte-toi pour accéder à cette page.", "error")
            return redirect(url_for("auth.login"))
        if not is_subscribed(user):
            if request.is_json:
                return jsonify({"error": "subscription_required",
                                "message": "Un abonnement actif est nécessaire pour générer des scripts."}), 402
            flash("Un abonnement actif est nécessaire pour accéder au générateur.", "error")
            return redirect(url_for("billing.pricing"))
        return view(*args, **kwargs)
    return wrapped_view
