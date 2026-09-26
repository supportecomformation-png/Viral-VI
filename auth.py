import re

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g

from db import query_one, execute
from auth_utils import hash_password, verify_password

bp = Blueprint("auth", __name__, url_prefix="/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _safe_next():
    """URL de retour après connexion : uniquement un chemin relatif interne."""
    target = request.args.get("next", "")
    if target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return None


@bp.route("/signup", methods=("GET", "POST"))
def signup():
    if g.get("user"):
        return redirect(_safe_next() or url_for("sim.traders"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        display_name = request.form.get("display_name", "").strip() or email.split("@")[0]

        error = None
        if not email or not EMAIL_RE.match(email):
            error = "Adresse email invalide."
        elif len(password) < 8:
            error = "Le mot de passe doit contenir au moins 8 caractères."
        elif query_one("SELECT id FROM users WHERE email = ?", (email,)):
            error = "Un compte existe déjà avec cet email."

        if error is None:
            user_id = execute(
                "INSERT INTO users (email, password_hash, display_name) VALUES (?, ?, ?)",
                (email, hash_password(password), display_name[:60]),
            )
            session.clear()
            session["user_id"] = user_id
            session.permanent = True
            flash("Compte créé ! Colle l'adresse d'un wallet pour lancer ta première simulation.", "success")
            return redirect(_safe_next() or url_for("sim.traders"))

        flash(error, "error")

    return render_template("auth/signup.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.get("user"):
        return redirect(_safe_next() or url_for("sim.traders"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = query_one("SELECT * FROM users WHERE email = ?", (email,))
        error = None
        if user is None or not verify_password(user["password_hash"], password):
            error = "Email ou mot de passe incorrect."

        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            session.permanent = True
            return redirect(_safe_next() or url_for("sim.traders"))

        flash(error, "error")

    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))
