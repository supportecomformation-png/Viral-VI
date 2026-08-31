from flask import Blueprint, render_template, redirect, url_for, flash, g, current_app, request, jsonify

from auth_utils import login_required
from db import execute
from engine.stripe_client import is_configured, create_checkout_session, verify_and_parse_webhook

bp = Blueprint("billing", __name__, url_prefix="/billing")


@bp.route("/pricing")
def pricing():
    return render_template(
        "billing/pricing.html",
        stripe_configured=is_configured(current_app.config),
        price=current_app.config["PRO_PLAN_PRICE_EUR"],
    )


@bp.route("/upgrade", methods=["POST"])
@login_required
def upgrade():
    if not is_configured(current_app.config):
        # Mode démo : pas de vraie facturation configurée -> on active Pro
        # directement pour permettre de tester tout le parcours produit.
        execute("UPDATE users SET plan = 'pro' WHERE id = ?", (g.user["id"],))
        flash("Mode démo : compte passé en Pro (aucun paiement réel, configure Stripe pour la prod).", "success")
        return redirect(url_for("dashboard.home"))

    success_url = url_for("billing.success", _external=True)
    cancel_url = url_for("billing.pricing", _external=True)
    checkout_url, error = create_checkout_session(
        current_app.config, g.user["email"], success_url, cancel_url, g.user["id"]
    )
    if error:
        flash(f"Erreur Stripe : {error}", "error")
        return redirect(url_for("billing.pricing"))

    return redirect(checkout_url)


@bp.route("/success")
@login_required
def success():
    flash("Paiement confirmé (ou en cours de confirmation par le webhook). Bienvenue dans ViralVI Pro !", "success")
    return redirect(url_for("dashboard.home"))


@bp.route("/webhook", methods=["POST"])
def webhook():
    payload_body = request.get_data()
    signature = request.headers.get("Stripe-Signature", "")
    webhook_secret = current_app.config["STRIPE_WEBHOOK_SECRET"]

    if not webhook_secret:
        return jsonify({"error": "webhook_not_configured"}), 400

    event, error = verify_and_parse_webhook(payload_body, signature, webhook_secret)
    if error:
        return jsonify({"error": error}), 400

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        user_id = data_object.get("client_reference_id")
        customer_id = data_object.get("customer")
        subscription_id = data_object.get("subscription")
        try:
            user_id = int(user_id) if user_id is not None else None
        except (TypeError, ValueError):
            user_id = None
        if user_id:
            execute(
                """UPDATE users
                   SET plan = 'pro', stripe_customer_id = ?, stripe_subscription_id = ?
                   WHERE id = ?""",
                (customer_id, subscription_id, user_id),
            )

    elif event_type in ("customer.subscription.deleted", "customer.subscription.canceled"):
        customer_id = data_object.get("customer")
        if customer_id:
            execute(
                "UPDATE users SET plan = 'free' WHERE stripe_customer_id = ?",
                (customer_id,),
            )

    return jsonify({"ok": True})
